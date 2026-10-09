from copy import deepcopy
import json
from pathlib import PurePosixPath
import pytest
from air import architecture_story as story
from air.core import digest
from air.skills import bundled, archive
from test_deliverables_032 import compiled, POLICY, delivery, obj  # noqa: F401


def model_from(report):
    dossier = report['website']['dossiers'][0]
    return json.loads(next(f['content'] for f in report['files'] if f['path'] == 'livrables/site/' + dossier['story_data']))


def test_story_every_excerpt_and_pin_comes_from_exact_baseline(store, compiled):
    report, request, _ = compiled
    model = model_from(report); exported = store.export_baseline(request['baselines'][0])
    assert story.verify(model) == model
    assert model['baseline'] == request['baselines'][0]
    objects = {(o['meta']['id'], o['meta']['revision']): o for o in exported['objects']}
    for phase in model['phases']:
        for entry in phase['entries']:
            ref = entry['source']; source = objects[ref['id'], ref['revision']]
            assert ref['digest'] == digest(source)
            assert entry['description'] == source['meta']['description']
            for field in entry['fields']:
                assert field['value'] == source['body'][field['selector'].removeprefix('/body/')]
    assert not model['business_execution_performed'] and not model['simulation_performed']
    assert not model['trailer']['execution_trace']
    assert model['readiness']['result'] == report['gates'][0]['result']


def test_mutation_is_rejected_and_video_is_not_silently_current(compiled):
    model = model_from(compiled[0]); receipt = {'baseline': model['baseline'], 'story_digest': model['story_digest']}
    assert story.video_freshness(model, receipt) == 'CURRENT'
    assert story.video_freshness(model, {**receipt, 'story_digest': 'sha256:'+'0'*64}) == 'STALE'
    assert story.video_freshness(model, {**receipt, 'baseline': {**model['baseline'], 'revision': 999}}) == 'STALE'
    changed = deepcopy(model); changed['readiness']['result'] = 'READY_INVENTED'
    with pytest.raises(ValueError, match='digest mismatch'): story.verify(changed)


def test_missing_phases_and_omissions_are_visible(example):
    base = {'meta': {'id':'urn:test:b','revision':1,'name':'test','namespace':'test'}}
    out = {'baseline':base,'digest':'sha256:'+'1'*64,'objects':[]}
    model = story.project(out, {'result':'NOT_READY'})
    assert all(p['empty'] and p['total_entries'] == 0 for p in model['phases'])
    out['objects'] = [obj(example, 'Intent', 'intent-'+str(i), {'desired_change':'x', 'goals':[]}) for i in range(15)]
    model = story.project(out, {'result':'NOT_READY'})
    assert model['phases'][0]['omitted_entries'] == 3
    assert len(model['phases'][0]['entries']) == 12


def test_story_is_in_offline_site_and_skill_is_portable(compiled):
    report = compiled[0]; model = model_from(report); dossier = report['website']['dossiers'][0]
    files = {f['path']:f['content'] for f in report['files']}
    assert 'livrables/site/assets/story.js' in files
    page = files['livrables/site/' + dossier['story']]
    assert all('id="story-'+p['id']+'"' in page for p in model['phases'])
    assert 'Animation narrative' in page and 'story.json' in page
    manifest = json.loads(files['livrables/site/site-manifest.json'])
    assert dossier['story'] in [r['path'] for r in manifest['pwa']['resources']]
    skill = next(s for s in bundled() if s['name'] == 'architecture-story')
    assert archive(skill) == archive(skill)
    assert 'latent-spaces/brag' in dict(skill['files'])['SKILL.md']
