import io
import pytest
from air import cli, deliverables


def test_full_pack_wire_expansion_keeps_other_responses_bounded(monkeypatch):
    monkeypatch.setattr(cli, 'MAX_BYTES', 8)
    monkeypatch.setattr(deliverables, 'TOTAL_MAX', 16)
    payload = b'{"file":"' + b'x' * 70 + b'"}'
    assert cli.read_result(io.BytesIO(payload), 'deliverables')['file'] == 'x' * 70
    with pytest.raises(ValueError, match='budget'):
        cli.read_result(io.BytesIO(payload), 'baseline-browse')
    with pytest.raises(ValueError, match='budget'):
        cli.read_result(io.BytesIO(b' ' * 129), 'deliverables')
    with pytest.raises(ValueError, match='budget'):
        cli.read_result(io.BytesIO(payload), 'deliverables', True)


def test_pack_budget_is_explicit_bounded_and_preserves_default():
    from air.foundation import check_schema, InvalidModel
    from air.deliverables import REQUEST, TOTAL_MAX
    request = {'title':'Architecture', 'baselines':[{'id':'urn:example:baseline','revision':1,'digest':'sha256:'+'a'*64}]}
    check_schema(request, REQUEST)
    check_schema({**request,'max_total_bytes':2*TOTAL_MAX}, REQUEST)
    for invalid in (True, TOTAL_MAX-1, 67108865):
        with pytest.raises(InvalidModel):
            check_schema({**request,'max_total_bytes':invalid}, REQUEST)
