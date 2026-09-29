"""Bounded JSON and a strict YAML editing subset, without implicit timestamps."""
import json
import math
import yaml

MAX_BYTES = 1_048_576


def pairs(items):
    result = {}
    for key, value in items:
        if not isinstance(key, str):
            raise ValueError("Mapping keys must be strings")
        if key in result:
            raise ValueError(f"Duplicate key: {key}")
        result[key] = value
    return result


class StrictLoader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ValueError("YAML aliases are not supported")
        event = self.peek_event()
        if getattr(event, "tag", None) is not None or getattr(event, "anchor", None):
            raise ValueError("YAML tags and anchors are not supported")
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        return pairs((self.construct_object(k, deep=True), self.construct_object(v, deep=True))
                     for k, v in node.value)


# BaseLoader resolves scalars as text; only JSON-compatible scalar forms are allowed.
StrictLoader.yaml_implicit_resolvers = {}
import re
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$"), list("tf"))
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:null", re.compile(r"^null$"), ["n"])
StrictLoader.add_implicit_resolver("tag:yaml.org,2002:int", re.compile(r"^-?(?:0|[1-9][0-9]*)$"), list("-0123456789"))


def check_tree(value, depth=0):
    if depth > 48:
        raise ValueError("Document nesting exceeds 48 levels")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("Mapping keys must be strings")
            key.encode("utf-8")
            check_tree(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            check_tree(item, depth + 1)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite numbers are forbidden")
        raise ValueError("Use decimal strings instead of floating point values")
    elif isinstance(value, int) and not isinstance(value, bool):
        if abs(value) > 9007199254740991:
            raise ValueError("Integer outside interoperable JCS range")
    elif isinstance(value, str):
        value.encode("utf-8")
    elif value is not None and not isinstance(value, bool):
        raise ValueError("Non-JSON value")


def parse(raw: bytes, syntax="json"):
    if len(raw) > MAX_BYTES:
        raise ValueError("Document exceeds 1 MiB")
    try:
        text = raw.decode("utf-8")
        if syntax == "yaml":
            value = yaml.load(text, Loader=StrictLoader)
        elif syntax == "json":
            value = json.loads(text, object_pairs_hook=pairs)
        else:
            raise ValueError("Unsupported syntax")
        check_tree(value)
        return value
    except (UnicodeError, RecursionError, yaml.YAMLError) as exc:
        raise ValueError("Malformed or excessively nested document") from exc
