import json
from copy import deepcopy
import pytest
from air.core import digest, validate
from air.parsing import parse
from conftest import ROOT


def test_examples_and_honest_coverage(example):
    for obj in (example, parse((ROOT / "examples/source.yaml").read_bytes(), "yaml")):
        report = validate(obj)
        assert report["valid"]
        assert not report["conformant_air_0_1"]
        assert len(report["coverage"]["not_executed"]) == 84


@pytest.mark.parametrize("raw,syntax", [
    (b'{"a":1,"a":2}', "json"), (b'{"a":NaN}', "json"), (b'{"a":1.2}', "json"),
    (b'{"a":9007199254740992}', "json"), (b'a: 1\na: 2', "yaml"),
    (b'a: &ref [1]\nb: *ref', "yaml"), (b'a: !!str 12', "yaml"),
    (b'1: value', "yaml"), (b'a: !!python/object/apply:os.system [echo BAD]', "yaml"),
    (b'[' * 100 + b']' * 100, "json"), (b' ' * 1048577, "json"),
], ids=["duplicate-json", "nan", "float", "large-int", "duplicate-yaml", "alias", "tag", "non-string-key", "python-tag", "depth", "size"])
def test_unsafe_or_ambiguous_documents_rejected(raw, syntax):
    with pytest.raises(ValueError):
        parse(raw, syntax)


def test_yaml_no_implicit_dates_or_booleans():
    assert parse(b'a: yes\nb: 2026-01-01\nc: false\nd: 12', "yaml") == {
        "a": "yes", "b": "2026-01-01", "c": False, "d": 12}


def test_surrogate_rejected_before_canonicalization():
    with pytest.raises(ValueError):
        parse(b'{"text":"\\ud800"}')


@pytest.mark.parametrize("field,value", [("revision", 0), ("id", "invalid uri"),
    ("recorded_at", "2026-99-99T00:00:00Z"), ("type", "air.CapacityReservation"),
    ("lifecycle", "ACCEPTED"), ("classification", {"level": "SECRET"})])
def test_invalid_envelope(example, field, value):
    example["meta"][field] = value
    assert not validate(example)["valid"]


def test_time_interval_and_unknown_fields(example):
    example["meta"]["validity"]["end"] = example["meta"]["validity"]["start"]
    assert validate(example)["diagnostics"][0]["code"] == "AIR_INTERVAL"
    example["meta"]["validity"]["end"] = None
    example["body"]["approved"] = True
    assert not validate(example)["valid"]


def test_sets_canonicalize_but_content_changes_digest(example):
    example["body"]["includes"] = [{"id": "urn:b", "revision": 1}, {"id": "urn:a", "revision": 2}]
    other = deepcopy(example)
    other["body"]["includes"].reverse()
    assert digest(example) == digest(other)
    assert example["body"]["includes"][0]["id"] == "urn:b"
    other["meta"]["description"] += " changed"
    assert digest(example) != digest(other)
    assert validate(example)["coverage"]["reference_resolution"] == "NOT_EXECUTED"
    assert len(validate(example)["unresolved_references"]) == 2


def test_scope_conflict_and_duplicate_revision(example):
    ref = {"id": "urn:target", "revision": 1}
    example["body"]["includes"] = [ref]
    example["body"]["excludes"] = [ref]
    assert not validate(example)["valid"]
    assert not validate([example, example])["valid"]


@pytest.mark.parametrize("document", [None, [], {"meta": None}, {"meta": {"type": []}}])
def test_invalid_shapes_do_not_crash(document):
    assert not validate(document)["valid"]
