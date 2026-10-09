from copy import deepcopy
import json
from pathlib import PurePosixPath
import pytest
from air import deliverables, management_summary
from air.core import digest
from air.expr import artifact_digest
from air.foundation import InvalidModel
from test_deliverables_032 import compiled, delivery, frozen, obj, POLICY  # noqa: F401


def test_summary_is_standard_before_detail_and_keeps_funding_and_gate_limits(compiled):
    report, _, _ = compiled
    files = {f['path']: f['content'] for f in report['files']}
    d = report['website']['dossiers'][0]
    v = json.loads(files['livrables/site/' + d['management_summary_data']])
    assert v['baseline'] == d['baseline']
    assert v['projection_digest'] == artifact_digest({k: x for k, x in v.items() if k != 'projection_digest'})
    assert not v['live_sync'] and not v['approval_inferred']
    assert v['gate']['total'] == 12
    assert '00-management-summary.md' in files['livrables/README.md']
    home = files['livrables/site/' + d['path']]
    assert home.index('id="management-summary"') < home.index('Les réponses dont vous avez besoin')
    root = files['livrables/site/index.html']
    assert root.index('Management Summary') < root.index('id="dossier-search"')
    assert len(report['website']['dossiers']) == 1 and d['topics'] == 37
    assert 'livrables/00-management-summary.json' in files


def test_only_summary_uses_authorized_exact_projection_without_full_site(store, compiled):
    _, request, user = compiled
    report = deliverables.compile_deliverables(store, user, POLICY, {**request, 'only': ['00-management-summary']})
    assert report['website'] is None
    assert {f['path'] for f in report['files']} == {'livrables/00-management-summary.md', 'livrables/00-management-summary.json'}


def test_assumption_under_test_remains_visible_in_management_brief(store, compiled):
    from air.core import DELIVERY_PROFILE
    from air.foundation import exact
    from air.readiness import assess_readiness
    _, request, user = compiled
    before = store.export_baseline(request['baselines'][0]); scope = next(o for o in before['objects'] if o['meta']['type'] == 'air.Scope')
    hypothesis = {'meta': {**deepcopy(scope['meta']), 'id': 'urn:summary:assumption-under-test', 'type': 'air.Assumption', 'revision': 1, 'name': 'Hypothesis under test'},
        'body': {'statement': 'Pending representative measurements', 'used_by': [exact(scope)], 'impact_if_false': 'Revisit the design',
            'validation_plan': 'Collect and review observations', 'review_due': '2027-01-01T00:00:00Z', 'state': 'UNDER_TEST'}}
    store.put_bundle([hypothesis], 'fixture')
    meta = deepcopy(before['baseline']['meta']);meta.update(id='urn:summary:baseline-under-test', revision=1)
    result = store.create_baseline({'meta': meta, 'profile': DELIVERY_PROFILE, 'members': [exact(o) for o in [*before['objects'], hypothesis]], 'parent_baselines': []}, 'fixture')
    pin = {**exact(result['baseline']), 'digest': result['digest']}
    brief = management_summary.project(store.export_baseline(pin), assess_readiness(store, user, POLICY, {'baseline': pin}))
    row = next(r for r in brief['assumptions']['items'] if r['reference']['id'] == hypothesis['meta']['id'])
    assert {'field': 'statement', 'value': 'Pending representative measurements'} in row['fields']
    assert row['reference'] == {**exact(hypothesis), 'digest': digest(hypothesis)}


def test_refresh_and_mismatched_evidence_are_explicit(store, compiled):
    report, request, _ = compiled
    e = store.export_baseline(request['baselines'][0]); gate = report['website']['dossiers'][0]['baseline']
    from air.readiness import assess_readiness
    g = assess_readiness(store, {'subject': 'local-admin', 'role': 'admin'}, POLICY, {'baseline': gate})
    before = management_summary.project(e, g)
    assert management_summary.project(e, g) == before
    wrong = deepcopy(g); wrong['baseline']['revision'] += 1
    with pytest.raises(InvalidModel, match='same exact baseline'): management_summary.project(e, wrong)
    after_e = deepcopy(e); after_e['baseline']['meta']['revision'] += 1; after_e['digest'] = 'sha256:' + 'f' * 64
    after_g = deepcopy(g); after_g['baseline'] = {**gate, 'revision': gate['revision'] + 1, 'digest': after_e['digest']}
    after = management_summary.project(after_e, after_g)
    assert after['projection_digest'] != before['projection_digest']
    assert before['baseline']['revision'] + 1 == after['baseline']['revision']


def test_display_is_escaped_and_full_focus_points_to_exact_sources(compiled):
    report, _, _ = compiled
    files = {f['path']: f['content'] for f in report['files']}
    d = report['website']['dossiers'][0]
    v = json.loads(files['livrables/site/' + d['management_summary_data']])
    v['name'] = '<img src="https://invalid" onerror="alert(1)">' + chr(0x2014) + 'test'
    html = management_summary.section(v)
    assert '<img src="https://invalid"' not in html and '&lt;img' in html
    assert chr(0x2014) not in html
    assert 'management-summary.json' in html and 'objects.html#' in html
