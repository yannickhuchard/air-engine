from copy import deepcopy
import json
import pytest
from air.core import RUNTIME_PROFILE, CONSTRUCTION_PROFILE, canonical, digest, validate
from air.foundation import exact, validate_graph, InvalidModel
from test_planning import prepare


def runtime_objects(store):
    plan = prepare(store)
    scope = store.get('urn:asteria:scope:sav', 1)['object']
    meta = deepcopy(scope['meta']);meta.update(id='urn:asteria:runtime:sav:availability', type='air.RuntimeObservation', name='ERP availability observation')
    source = plan['pools'][0]['source'];meta['provenance']['source_refs'] = [{k: source[k] for k in ('id', 'revision')}]
    observation = {'meta': meta, 'body': {'instance_or_scope': exact(scope), 'metric_or_signal': 'erp_available',
        'window': {'start': '2026-09-19T10:00:00Z', 'end': '2026-09-19T10:05:00Z'},
        'value_or_artifact': {'type': 'Boolean', 'value': False},
        'coverage': {'scope': exact(scope), 'included': [plan['demands'][0]['unit'] | {}], 'excluded': [], 'completeness': 'PARTIAL', 'limitations': ['Synthetic five-minute sample; no full runtime coverage']}}}
    observation['body']['coverage']['included'] = [{k: plan['demands'][0]['unit'][k] for k in ('id', 'revision')}]
    drift_meta = deepcopy(meta);drift_meta.update(id='urn:asteria:runtime:sav:drift', type='air.Drift', name='ERP availability deviation')
    drift = {'meta': drift_meta, 'body': {'expected': {'id': 'urn:asteria:construction:sav:requirement', 'revision': 1},
        'observed': [exact(observation)], 'comparison_method': 'Explicit Boolean availability comparison', 'impact': 'ERP confirmation may be unavailable'}}
    # Select the actual requirement identity from this frozen design.
    base = store.export_baseline(plan['demands'][0]['baseline'])
    drift['body']['expected'] = exact(next(o for o in base['objects'] if o['meta']['type'] == 'air.Requirement'))
    incident_meta = deepcopy(meta);incident_meta.update(id='urn:asteria:runtime:sav:incident', type='air.Incident', name='Declared ERP interruption')
    incident = {'meta': incident_meta, 'body': {'affected_scope': exact(scope), 'occurrence': deepcopy(observation['body']['window']),
        'description': 'Synthetic interruption sample', 'observations': [exact(observation)], 'learning': [exact(drift)]}}
    return plan, [observation, drift, incident], base['objects']


def test_runtime_profile_closed_baseline_and_legacy_profile_boundary(store):
    plan, runtime, original = runtime_objects(store)
    objects = original + runtime
    assert validate(runtime)['valid'] and validate(runtime)['profile'] == RUNTIME_PROFILE
    assert validate_graph(objects, RUNTIME_PROFILE)['valid']
    assert not validate_graph(objects, CONSTRUCTION_PROFILE)['valid']
    store.put_bundle(runtime, 'observer')
    meta = deepcopy(store.export_baseline(plan['demands'][0]['baseline'])['baseline']['meta'])
    meta.update(id='urn:asteria:runtime:baseline:sav', name='Runtime evidence snapshot')
    created = store.create_baseline({'meta': meta, 'profile': RUNTIME_PROFILE, 'members': [exact(o) for o in objects], 'parent_baselines': [{k: plan['demands'][0]['baseline'][k] for k in ('id', 'revision')}]}, 'observer')
    assert store.export_baseline(exact(created['baseline']))['digest'] == created['digest']


def test_observation_types_coverage_dates_and_unknowns_remain_explicit(store):
    _, objects, _ = runtime_objects(store);observation = objects[0]
    for field, value in [('value_or_artifact', {'type': 'Boolean', 'value': 'true'}), ('value_or_artifact', {'type': 'Reference'}),
        ('window', {'start': '2026-09-19T10:05:00Z', 'end': '2026-09-19T10:00:00Z'})]:
        bad = deepcopy(observation);bad['body'][field] = value;assert not validate(bad)['valid']
    observation['body']['value_or_artifact'] = {'type': 'Boolean', 'state': 'UNKNOWN'}
    assert validate(observation)['valid']
    assert json.loads(canonical(observation))['body']['value_or_artifact'] == {'type': 'Boolean', 'state': 'UNKNOWN'}
    observation['body']['coverage']['completeness'] = 'COMPLETE'
    assert not validate(observation)['valid']


def test_runtime_canonicalization_and_missing_source_are_safe(store):
    _, objects, _ = runtime_objects(store);observation = objects[0]
    observation['body']['value_or_artifact'] = {'type': 'Decimal', 'value': '1.000'}
    normalized = deepcopy(observation);normalized['body']['value_or_artifact']['value'] = '1'
    assert digest(observation) == digest(normalized)
    observation['meta']['provenance']['source_refs'] = []
    assert not validate(observation)['valid']
    assert not validate_graph([{'meta': {'type': {}}}])['valid']
