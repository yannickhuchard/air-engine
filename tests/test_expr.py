from copy import deepcopy
import json
import pytest
from air.expr import Budget, evaluate


def lit(t, v):
    return {"literal": {"type": t, "value": v}}


def expression(ast, result_type="Boolean", **inputs):
    return {"language": "AIR-Expr", "language_version": "0.1", "result_type": result_type,
            "required_inputs": [{"name": k, "type": v} for k, v in inputs.items()], "ast": ast}


def call(op, *args):
    return {"op": op, "args": list(args)}


def ev(ast, t="Boolean", inputs=None, declarations=None, budget=None):
    return evaluate({"expression": expression(ast, t, **(declarations or {})), "inputs": inputs or {}}, budget)


@pytest.mark.parametrize("op,known,expected", [("and", False, "VIOLATED"), ("and", True, "UNKNOWN"),
                                              ("or", True, "SATISFIED"), ("or", False, "UNKNOWN")])
def test_unknown_truth_table_both_orders(op, known, expected):
    for args in ([lit("Boolean", known), {"ref": "missing"}], [{"ref": "missing"}, lit("Boolean", known)]):
        result = ev(call(op, *args), declarations={"missing": "Boolean"})
        assert result["execution"] == "EXECUTED" and result["result"] == expected
        assert result["diagnostics"] == [{"code": "AIR_EXPR_UNKNOWN", "input": "missing"}]
    assert ev(call("not", {"ref": "missing"}), declarations={"missing": "Boolean"})["result"] == "UNKNOWN"


def test_conflict_is_distinct_and_never_masked():
    result = ev(call("and", lit("Boolean", False), {"ref": "x"}),
                inputs={"x": {"type": "Boolean", "state": "CONFLICTING"}}, declarations={"x": "Boolean"})
    assert result["result"] == "CONFLICTING"
    assert result["diagnostics"][0]["code"] == "AIR_EXPR_CONFLICTING"


def test_decimal_exactness_and_units():
    assert ev(call("eq", call("add", lit("Decimal", "0.1"), lit("Decimal", "0.2")), lit("Decimal", "0.3")))[
        "result"] == "SATISFIED"
    result = ev(call("sub", lit("Quantity[FTE]", "5"), lit("Quantity[FTE]", "4")), "Quantity[FTE]")
    assert result["value"] == {"type": "Quantity[FTE]", "value": "1"}
    assert ev(call("eq", lit("Quantity[FTE]", "1"), lit("Quantity[h]", "1")))["execution"] == "ERROR"
    assert ev(call("mul", lit("Quantity[FTE]", "2"), lit("Quantity[FTE]", "2")), "Quantity[FTE]")["execution"] == "ERROR"


@pytest.mark.parametrize("ast,t", [
    (call("div", lit("Integer", 1), lit("Integer", 0)), "Decimal"),
    (call("div", lit("Decimal", "1"), lit("Decimal", "3")), "Decimal"),
    (call("add", lit("Integer", 9007199254740991), lit("Integer", 1)), "Integer"),
    (call("mul", lit("Decimal", "0.000000000000000001"), lit("Decimal", "0.1")), "Decimal"),
])
def test_arithmetic_errors_do_not_become_success(ast, t):
    report = ev(ast, t)
    assert report["execution"] == "ERROR" and report["result"] == "UNKNOWN"


def test_time_duration_reference_and_membership():
    assert ev(call("lt", lit("Instant", "2026-10-01T00:00:00Z"), lit("Instant", "2026-10-01T00:00:00.001Z")))["result"] == "SATISFIED"
    assert ev(call("add", lit("Duration", "1.5"), lit("Duration", "0.5")), "Duration")["value"]["value"] == "2"
    ref = {"id": "urn:test:one", "revision": 1}
    assert ev(call("in", lit("Reference", ref), lit("Collection[Reference]", [{"type": "Reference", "value": ref}])))["result"] == "SATISFIED"
    assert ev(lit("Instant", "2026-02-30T00:00:00Z"), "Instant")["execution"] == "ERROR"


def test_bounded_quantification_and_budget():
    collection = lit("Collection[Integer]", [{"type": "Integer", "value": i} for i in range(6)])
    ast = {"op": "every", "over": collection, "predicate": call("gte", {"ref": "$item"}, lit("Integer", 0))}
    assert ev(ast)["result"] == "SATISFIED"
    assert ev(ast, budget=Budget(5))["execution"] == "BUDGET_EXCEEDED"
    ast["op"] = "some"
    ast["over"] = lit("Collection[Integer]", [])
    assert ev(ast)["result"] == "VIOLATED"
    ast["op"] = "every"
    assert ev(ast)["result"] == "SATISFIED"
    ast["over"] = lit("Collection[Integer]", [{"type": "Integer", "state": "CONFLICTING"}])
    assert ev(ast)["result"] == "CONFLICTING"


@pytest.mark.parametrize("bad", [None, [], {}, {"op": "eval", "args": []},
    {"ref": "__class__.__subclasses__"}, {"literal": {"type": "Boolean", "value": 1}},
    {"literal": {"type": "Boolean", "state": "NOT_APPLICABLE"}},
    {"literal": {"type": "Decimal", "value": "1e1000000"}},
    {"literal": {"type": "Reference", "value": {"id": "relative", "revision": True}}},
    {"op": ["eq"], "args": []}, {"ref": []},
])
def test_invalid_ast_is_rejected_even_in_inactive_branch(bad):
    result = ev(call("or", lit("Boolean", True), bad))
    assert result["execution"] == "ERROR"


def test_declarations_context_shape_and_structural_limits():
    assert ev({"ref": "x"})["execution"] == "ERROR"
    assert ev({"ref": "x"}, inputs={"x": {"type": "Integer", "value": 1}}, declarations={"x": "Boolean"})["execution"] == "ERROR"
    assert ev(lit("Boolean", True), inputs={"extra": {"type": "Boolean", "value": True}})["execution"] == "ERROR"
    ast = lit("Boolean", True)
    for _ in range(30):
        ast = call("not", ast)
    assert ev(ast)["execution"] == "ERROR"
    values = [{"type": "Integer", "value": 1}] * 257
    assert ev(lit("Collection[Integer]", values), "Collection[Integer]")["execution"] == "ERROR"


def test_report_replay_is_stable_and_cli_exit(capsys, tmp_path):
    from air.cli import main
    request = {"expression": expression(call("lte", lit("Integer", 5), lit("Integer", 4))), "inputs": {}}
    assert evaluate(request) == evaluate(deepcopy(request))
    file = tmp_path / "expression.json"
    file.write_text(json.dumps(request), encoding="utf-8")
    assert main(["expr-evaluate", str(file)]) == 1
    assert json.loads(capsys.readouterr().out)["result"] == "VIOLATED"


def test_cli_json_is_utf8_even_with_legacy_host_encoding(tmp_path):
    import os
    import subprocess
    import sys
    request = {"expression": expression(lit("Text", "Équipe 工程"), "Text"), "inputs": {}}
    file = tmp_path / "unicode.json"
    file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "air", "expr-evaluate", str(file)],
                            capture_output=True, env={**os.environ, "PYTHONIOENCODING": "ascii"}, timeout=15)
    assert result.returncode == 0
    assert json.loads(result.stdout.decode("utf-8"))["value"]["value"] == "Équipe 工程"


def test_calculation_does_not_inherit_process_decimal_context():
    from decimal import DivisionByZero, ROUND_DOWN, localcontext
    requests = [call("div", lit("Decimal", "1"), lit("Decimal", "0")),
                call("add", lit("Decimal", "1000.125"), lit("Decimal", "0.375"))]
    expected = [ev(ast, "Decimal") for ast in requests]
    with localcontext() as context:
        context.prec = 2
        context.Emax = 2
        context.Emin = -2
        context.rounding = ROUND_DOWN
        context.traps[DivisionByZero] = False
        assert [ev(ast, "Decimal") for ast in requests] == expected
