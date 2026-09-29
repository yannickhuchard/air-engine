"""Pure, bounded AIR-Expr interpreter. See docs/lot-expressions-portes.md."""
from dataclasses import dataclass
from datetime import datetime
from decimal import (Context, Decimal, DecimalException, DivisionByZero, Inexact,
                     InvalidOperation, Overflow, ROUND_HALF_EVEN, localcontext)
import re
import hashlib
import rfc8785

from air.parsing import MAX_BYTES, check_tree

ENGINE = "air.expr/0.3"
LIMITS = {"nodes": 2048, "depth": 24, "steps": 10000, "collection": 256}
SCALARS = {"Boolean", "Text", "Integer", "Decimal", "Instant", "Duration", "Reference"}
NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.-]{0,127}$")
NUMBER = re.compile(r"^-?(?:0|[1-9][0-9]{0,37})(?:\.[0-9]{1,18})?$")


def artifact_digest(document):
    return "sha256:" + hashlib.sha256(rfc8785.dumps(document)).hexdigest()


class ExprError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, message, code="AIR_EXPR_INVALID"):
    if not condition:
        raise ExprError(code, message)


def bounded(document):
    try:
        check_tree(document)
        require(len(rfc8785.dumps(document)) <= MAX_BYTES, "Document exceeds 1 MiB")
    except (ValueError, RecursionError, UnicodeError) as exc:
        raise ExprError("AIR_EXPR_INPUT", str(exc)) from exc


def fields(obj, required, optional=()):
    require(isinstance(obj, dict) and set(required) <= set(obj) <= set(required) | set(optional),
            "Unexpected or missing fields")


def type_name(t):
    require(isinstance(t, str), "Type must be text")
    if t in SCALARS or re.fullmatch(r"Quantity\[[A-Za-z][A-Za-z0-9_/-]{0,31}\]", t):
        return t
    if t.startswith("Collection[") and t.endswith("]"):
        inner = t[11:-1]
        require(not inner.startswith("Collection["), "Nested collections are unsupported")
        type_name(inner)
        return t
    raise ExprError("AIR_EXPR_TYPE", "Unsupported type: " + t)


def decimal(text):
    require(isinstance(text, str) and NUMBER.fullmatch(text), "Expected bounded decimal string")
    number = Decimal(text)
    require(len(number.as_tuple().digits) <= 38, "Decimal exceeds 38 significant digits")
    return number


@dataclass(frozen=True)
class Value:
    type: str
    value: object = None
    state: str = "KNOWN"


def typed(obj):
    fields(obj, ("type",), ("value", "state"))
    t = type_name(obj["type"])
    state = obj.get("state", "KNOWN")
    require(state in ("KNOWN", "UNKNOWN", "CONFLICTING"), "Invalid input state")
    if state != "KNOWN":
        require("value" not in obj, "Uncertain inputs must not carry a chosen value")
        return Value(t, state=state)
    require("value" in obj, "Known input requires a value")
    v = obj["value"]
    if t == "Boolean":
        require(type(v) is bool, "Expected Boolean")
    elif t == "Text":
        require(isinstance(v, str) and len(v) <= 10000, "Expected bounded Text")
    elif t == "Integer":
        require(type(v) is int and abs(v) <= 9007199254740991, "Integer out of range")
    elif t in ("Decimal", "Duration") or t.startswith("Quantity["):
        v = decimal(v)
    elif t == "Instant":
        require(isinstance(v, str) and re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", v),
                "Instant must be UTC with at most microsecond precision")
        try:
            v = datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ExprError("AIR_EXPR_TYPE", "Invalid instant") from exc
    elif t == "Reference":
        from jsonschema import FormatChecker
        fields(v, ("id", "revision"))
        require(isinstance(v["id"], str) and len(v["id"]) <= 512 and
                FormatChecker().conforms(v["id"], "uri") and type(v["revision"]) is int and
                1 <= v["revision"] <= 2147483647, "Expected exact URI reference")
    else:
        require(isinstance(v, list) and len(v) <= LIMITS["collection"], "Collection exceeds limit")
        v = tuple(typed(x) for x in v)
        require(all(x.type == t[11:-1] for x in v), "Collection element type mismatch")
    return Value(t, v)


def wire(v):
    if v.state != "KNOWN":
        return {"type": v.type, "state": v.state}
    value = v.value
    if isinstance(value, Decimal):
        value = format(value, "f")
        if "." in value:
            value = value.rstrip("0").rstrip(".")
        if value == "-0":
            value = "0"
    elif isinstance(value, datetime):
        value = value.isoformat().replace("+00:00", "Z")
    elif isinstance(value, tuple):
        value = [wire(x) for x in value]
    return {"type": v.type, "value": value}


@dataclass
class Budget:
    limit: int = LIMITS["steps"]
    used: int = 0

    def spend(self):
        require(self.used < self.limit, "Evaluation budget exhausted", "AIR_EXPR_BUDGET")
        self.used += 1


def numeric(t):
    return t in ("Integer", "Decimal", "Duration") or t.startswith("Quantity[")


class Program:
    def __init__(self, expression):
        fields(expression, ("language", "language_version", "result_type", "ast"), ("required_inputs",))
        require(expression["language"] == "AIR-Expr" and expression["language_version"] == "0.1",
                "Unsupported language version")
        self.expression = expression
        self.inputs = {}
        self.types = {}
        self.nodes = 0
        specs = expression.get("required_inputs", [])
        require(isinstance(specs, list) and len(specs) <= 256, "Invalid input declarations")
        for spec in specs:
            fields(spec, ("name", "type"))
            name = spec["name"]
            require(isinstance(name, str) and NAME.fullmatch(name) and name not in self.inputs,
                    "Invalid or duplicate input name")
            self.inputs[name] = type_name(spec["type"])
        require(self.check(expression["ast"]) == type_name(expression["result_type"]),
                "Declared result type does not match AST", "AIR_EXPR_TYPE")

    def check(self, node, depth=0, item_type=None):
        self.nodes += 1
        require(self.nodes <= LIMITS["nodes"] and depth <= LIMITS["depth"], "AST exceeds structural limits")
        require(isinstance(node, dict), "AST node must be an object")
        if "literal" in node:
            fields(node, ("literal",))
            value = typed(node["literal"])
            require(value.state == "KNOWN", "Uncertainty belongs to input context, not literals")
            t = value.type
        elif "ref" in node:
            fields(node, ("ref",))
            name = node["ref"]
            require(isinstance(name, str), "Reference must be text")
            t = item_type if name == "$item" else self.inputs.get(name)
            require(t is not None, "Undeclared reference: " + name, "AIR_EXPR_TYPE")
        elif node.get("op") in ("every", "some"):
            fields(node, ("op", "over", "predicate"))
            over = self.check(node["over"], depth + 1, item_type)
            require(over.startswith("Collection["), "Quantifier needs a collection", "AIR_EXPR_TYPE")
            require(self.check(node["predicate"], depth + 1, over[11:-1]) == "Boolean",
                    "Quantifier predicate must be Boolean", "AIR_EXPR_TYPE")
            t = "Boolean"
        else:
            fields(node, ("op", "args"))
            op, args = node["op"], node["args"]
            require(isinstance(op, str) and isinstance(args, list), "Invalid operator")
            arity = {"not": 1, "length": 1, "and": 2, "or": 2, "eq": 2, "ne": 2,
                     "lt": 2, "lte": 2, "gt": 2, "gte": 2, "in": 2,
                     "add": 2, "sub": 2, "mul": 2, "div": 2}
            require(op in arity and len(args) == arity[op], "Unknown operator or incorrect arity")
            ts = [self.check(a, depth + 1, item_type) for a in args]
            if op in ("and", "or", "not"):
                require(all(x == "Boolean" for x in ts), "Expected Boolean arguments", "AIR_EXPR_TYPE")
                t = "Boolean"
            elif op == "length":
                require(ts[0].startswith("Collection["), "length requires a collection", "AIR_EXPR_TYPE")
                t = "Integer"
            elif op == "in":
                require(ts[1] == "Collection[" + ts[0] + "]", "Membership type mismatch", "AIR_EXPR_TYPE")
                t = "Boolean"
            else:
                require(ts[0] == ts[1] and not ts[0].startswith("Collection["),
                        "Incompatible types or units", "AIR_EXPR_TYPE")
                if op in ("eq", "ne"):
                    t = "Boolean"
                elif op in ("lt", "lte", "gt", "gte"):
                    require(numeric(ts[0]) or ts[0] in ("Text", "Instant"), "Type is not ordered", "AIR_EXPR_TYPE")
                    t = "Boolean"
                else:
                    require(numeric(ts[0]), "Expected numeric arguments", "AIR_EXPR_TYPE")
                    require(op in ("add", "sub") or ts[0] in ("Integer", "Decimal"),
                            "Multiplication/division of dimensional values unsupported", "AIR_EXPR_TYPE")
                    t = "Decimal" if op == "div" and ts[0] == "Integer" else ts[0]
        self.types[id(node)] = t
        return t

    def execute(self, context, budget):
        require(isinstance(context, dict) and len(context) <= 256, "Invalid input context")
        require(set(context) <= set(self.inputs), "Context contains undeclared inputs")
        values, diagnostics = {}, []
        for name, t in self.inputs.items():
            value = typed(context[name]) if name in context else Value(t, state="UNKNOWN")
            require(value.type == t, "Input type mismatch: " + name, "AIR_EXPR_TYPE")
            values[name] = value
            if value.state != "KNOWN":
                diagnostics.append({"code": "AIR_EXPR_" + value.state, "input": name})

        def uncertain(t, vals):
            for state in ("CONFLICTING", "UNKNOWN"):
                if any(v.state == state for v in vals):
                    return Value(t, state=state)
            return None

        def boolean(op, vals):
            # Contradictions remain visible even when another operand determines a Boolean.
            if any(v.state == "CONFLICTING" for v in vals):
                return Value("Boolean", state="CONFLICTING")
            decisive = op == "or"
            if any(v.state == "KNOWN" and v.value is decisive for v in vals):
                return Value("Boolean", decisive)
            return uncertain("Boolean", vals) or Value("Boolean", not decisive)

        def walk(node, item=None):
            budget.spend()
            t = self.types[id(node)]
            if "literal" in node:
                return typed(node["literal"])
            if "ref" in node:
                return item if node["ref"] == "$item" else values[node["ref"]]
            op = node["op"]
            if op in ("every", "some"):
                over = walk(node["over"], item)
                if over.state != "KNOWN":
                    return Value(t, state=over.state)
                return boolean("and" if op == "every" else "or",
                               [walk(node["predicate"], v) for v in over.value])
            vals = [walk(a, item) for a in node["args"]]
            if op in ("and", "or"):
                return boolean(op, vals)
            missing = uncertain(t, vals)
            if missing:
                return missing
            a = vals[0].value
            b = vals[1].value if len(vals) > 1 else None
            if op == "in":
                comparisons = [Value("Boolean", a == v.value) if v.state == "KNOWN" else
                               Value("Boolean", state=v.state) for v in b]
                return boolean("or", comparisons)
            if op == "not":
                result = not a
            elif op == "length":
                result = len(a)
            elif op in ("eq", "ne", "lt", "lte", "gt", "gte"):
                if op == "eq": result = a == b
                elif op == "ne": result = a != b
                elif op == "lt": result = a < b
                elif op == "lte": result = a <= b
                elif op == "gt": result = a > b
                else: result = a >= b
            else:
                with localcontext(Context(prec=38, rounding=ROUND_HALF_EVEN,
                                         Emin=-999999, Emax=999999, capitals=1, clamp=0, flags=[],
                                         traps=[Inexact, InvalidOperation, DivisionByZero, Overflow])):
                    if op == "add": result = a + b
                    elif op == "sub": result = a - b
                    elif op == "mul": result = a * b
                    else: result = Decimal(a) / Decimal(b)
                # Check bounds on computed values as well as input literals.
                return typed(wire(Value(t, result)))
            return Value(t, result)

        result = walk(self.expression["ast"])
        if result.state != "KNOWN" and not any(d["code"] == "AIR_EXPR_" + result.state for d in diagnostics):
            diagnostics.append({"code": "AIR_EXPR_" + result.state})
        return result, diagnostics


def evaluate(request, budget=None):
    budget = budget if budget is not None else Budget()
    start = budget.used
    report = {"engine": ENGINE, "execution": "ERROR", "result": "UNKNOWN", "diagnostics": []}
    try:
        bounded(request)
        fields(request, ("expression", "inputs"))
        report["request_digest"] = artifact_digest(request)
        program = Program(request["expression"])
        value, diagnostics = program.execute(request["inputs"], budget)
        result = value.state if value.state != "KNOWN" else (
            ("SATISFIED" if value.value else "VIOLATED") if value.type == "Boolean" else "KNOWN")
        report.update(execution="EXECUTED", result=result, value=wire(value), diagnostics=diagnostics)
    except ExprError as exc:
        report.update(execution="BUDGET_EXCEEDED" if exc.code == "AIR_EXPR_BUDGET" else "ERROR",
                      diagnostics=[{"code": exc.code, "message": str(exc)}])
    except (DecimalException, ArithmeticError) as exc:
        report["diagnostics"] = [{"code": "AIR_EXPR_ARITHMETIC", "message": type(exc).__name__}]
    report["cost"] = {"steps": budget.used - start, "limit": budget.limit}
    return report
