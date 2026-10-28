"""One isolated design, builder handoff, versioned implementation and signed regression journey."""
import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile
from air import __version__, agent, artifacts, builder_handoff, ci_evidence, evidence_impact, external_proofs, proof_runner, readiness
from air.access import AccessPolicy, ScopedStore
from air.cli import bootstrap
from air.config import Settings, write_private
from air.core import BUILD_PROFILE, digest
from air.foundation import exact
from air.projections import snapshot
from air.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def pin(obj): return {**exact(obj), 'digest': digest(obj)}
def stamp(value): return value.isoformat().replace('+00:00', 'Z')


def suite(provider_digest, consumer_digest):
    return '''import hashlib, importlib.util, pathlib, unittest
ROOT = pathlib.Path(__file__).parent
def load(name):
 spec = importlib.util.spec_from_file_location(name, ROOT / (name + '.py'))
 module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
provider, consumer = load('provider'), load('consumer')
class QuoteAcceptance(unittest.TestCase):
 def setUp(self): provider.cache.clear()
 def test_exact_implementation(self):
  self.assertEqual(hashlib.sha256((ROOT/'provider.py').read_bytes()).hexdigest(), PROVIDER_DIGEST)
  self.assertEqual(hashlib.sha256((ROOT/'consumer.py').read_bytes()).hexdigest(), CONSUMER_DIGEST)
 def test_all_valid_quantities(self):
  for quantity in range(1,101):
   response=provider.quote(consumer.request(quantity,str(quantity)))
   self.assertEqual(response['status'],200)
   self.assertEqual(response['body']['total_minor'],quantity*125)
   self.assertTrue(consumer.interpret(response,quantity)['accepted'])
 def test_invalid_and_recovery(self):
  for quantity in (0,101,True): self.assertEqual(provider.quote(consumer.request(quantity,'bad'))['status'],422)
  self.assertEqual(provider.quote(consumer.request(2,'recovered'))['body']['total_minor'],250)
 def test_replay_and_conflict(self):
  request=consumer.request(2,'repeat'); self.assertEqual(provider.quote(request),provider.quote(request))
  self.assertEqual(provider.quote(consumer.request(3,'repeat'))['status'],409)
'''.replace('PROVIDER_DIGEST', repr(provider_digest)).replace('CONSUMER_DIGEST', repr(consumer_digest))


def rehearse(output):
    output = Path(output).resolve()
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Use an isolated SQLite environment')
    output.mkdir(parents=True, exist_ok=False)
    fixture = load('journey_teams', ROOT / 'fixtures/builder_handoff/model.py'); model = fixture.build
    repository = output / 'implementation'; repository.mkdir()
    for name in ('provider.py', 'consumer.py'):
        (repository / name).write_bytes((model.ROOT / name).read_bytes())
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    def git(*args):
        result = subprocess.run(['git', '-c', 'user.name=AIR Fictional Fixture', '-c', 'user.email=fixture@example.invalid', *args],
            cwd=repository, capture_output=True, check=True, text=True, creationflags=flags)
        return result.stdout.strip()
    git('init')
    def commit(label):
        (repository / 'acceptance_suite.py').write_text(suite(
            hashlib.sha256((repository / 'provider.py').read_bytes()).hexdigest(),
            hashlib.sha256((repository / 'consumer.py').read_bytes()).hexdigest()), encoding='utf-8')
        git('add', 'provider.py', 'consumer.py', 'acceptance_suite.py'); git('commit', '-m', label)
        return git('rev-parse', 'HEAD')
    revision = commit('Fictional quote implementation matching the declared contract')
    home = output / '.air'; bootstrap(home); settings = Settings.load(home); store = Store(settings.database_url)
    credential = json.loads((home / 'credentials.json').read_text(encoding='utf-8'))
    user = store.authenticate(credential['access_token'], True); user['authorization']['instance_id'] = settings.instance_id
    try:
        policy = AccessPolicy()
        schemas = {n: artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
            'media_type': 'application/json', 'idempotency_key': n}, (model.ROOT / (n + '.schema.json')).read_bytes())['artifact_reference']
            for n in ('request', 'response')}
        objects = fixture.with_teams(model.objects(schemas))
        source = model.obj('Source', 'implementation-source', {'kind': 'CODE', 'locator': repository.as_uri(),
            'source_revision': revision, 'captured_at': stamp(datetime.now(timezone.utc)),
            'access_policy': 'Isolated fictional fixture', 'retention_policy': 'Retain the exact rehearsal'})
        case = next(o for o in objects if o['meta']['type'] == 'air.VerificationCase')
        case['meta']['provenance']['source_refs'].append(exact(source))
        environment = model.obj('Environment', 'build-environment', {'stage': 'BUILD_TEST',
            'purpose': 'Execute the fictional quote contract', 'hosting': 'Isolated local Python child process'})
        objects += [source, environment]
        store.put_bundle(objects, user['subject'])
        def freeze(members, previous=None):
            meta = deepcopy(model.obj('Baseline', 'journey', {})['meta'])
            meta['revision'] = previous['revision'] + 1 if previous else 1
            result = store.create_baseline({'meta': meta, 'profile': BUILD_PROFILE, 'members': [exact(o) for o in members],
                'parent_baselines': [{k: previous[k] for k in ('id', 'revision')}] if previous else []}, user['subject'])
            return pin(result['baseline'])
        baseline = freeze(objects)
        grants = {'version': 'journey-1', 'subjects': {user['subject']: {'read': ['*'], 'write': ['*']},
            'urn:journey:runner': {'attest': [model.NAMESPACE]}}}
        builders = []
        for side in ('provider', 'consumer'):
            token = store.create_token('fictional-' + side, 'editor')
            actor = store.authenticate(token['access_token'], True); actor['authorization']['instance_id'] = settings.instance_id
            roles = [pin(o) for o in objects if o['meta']['type'] == 'air.Role' and o['meta']['name'].startswith(side)]
            grants['subjects'][actor['subject']] = {'read': ['*'], 'receive': [model.NAMESPACE], 'builder_roles': roles}
            builders.append((actor, roles))
        write_private(home / 'access-policy.json', grants); policy = AccessPolicy(grants)
        package = builder_handoff.create_package(store, user, policy, {'package_id': 'urn:journey:handoff', 'version': 1,
            'baseline': baseline, 'units': [pin(o) for o in objects if o['meta']['type'] == 'air.ConstructionUnit'],
            'idempotency_key': 'handoff'}, settings)['package']
        for actor, roles in builders:
            for i, role in enumerate(roles):
                builder_handoff.receive(store, actor, policy, {'package': package, 'role': role,
                    'idempotency_key': actor['subject'] + str(i), 'outcome': 'ACCEPTED', 'questions': [],
                    'rationale': 'Fictional role receipt, no human-team validation',
                    'expires_at': stamp(datetime.now(timezone.utc) + timedelta(days=1))}, settings)
        assert builder_handoff.assess(store, user, policy, {'baseline': baseline})['state'] == 'RECEIVED_FOR_BUILD_PLANNING'
        key_dir = output / 'private-runner-key'; proof_runner.keygen(key_dir)
        public = json.loads((key_dir / 'public.json').read_text())['public_key']
        def execute(label, base):
            exported = snapshot(ScopedStore(store, user, policy), base)
            select = lambda kind: next(o for o in exported['objects'] if o['meta']['type'] == kind)
            case = select('air.VerificationCase'); environment = select('air.Environment')
            source = next(o for o in exported['objects'] if o['meta']['id'].endswith('implementation-source'))
            code = io.BytesIO()
            with zipfile.ZipFile(code, 'w', zipfile.ZIP_DEFLATED) as archive:
                for name in ('acceptance_suite.py', 'consumer.py', 'provider.py'):
                    archive.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), (repository / name).read_bytes())
            build = artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE,
                'media_type': 'application/zip', 'idempotency_key': label + '-build'}, code.getvalue())
            checksum = 'sha256:' + hashlib.sha256((repository / 'acceptance_suite.py').read_bytes()).hexdigest()
            now = datetime.now(timezone.utc)
            external_proofs.register_key(store, settings, {'key_id': label, 'executor': 'urn:journey:runner', 'public_key': public,
                'namespaces': [model.NAMESPACE], 'not_before': stamp(now - timedelta(seconds=5)),
                'expires_at': stamp(now + timedelta(days=1)), 'max_age_seconds': 600,
                'suite_digests': [checksum], 'environments': [pin(environment)]})
            challenge = external_proofs.challenge(store, user, policy, settings, {'idempotency_key': label,
                'baseline': base, 'case': pin(case), 'environment': pin(environment), 'run_id': 'urn:journey:run:' + label,
                'key_id': label, 'suite_digest': checksum, 'ttl_seconds': 600})
            challenge_path = output / (label + '-challenge.json'); challenge_path.write_text(json.dumps(challenge))
            attestation_path = output / (label + '-attestation.json')
            proof_runner.run(challenge_path, repository / 'acceptance_suite.py', key_dir / 'private.json', attestation_path)
            envelope = json.loads(attestation_path.read_text())
            imported = external_proofs.import_report(store, user, policy, settings, envelope)
            run = imported['verification_run']; store.put(run, user['subject'])
            result = envelope['attestation']['result']
            ledger = {'format': 'air.ci-ledger/1', 'repository': source['body']['locator'], 'executor': result['executor'],
                'source_revision': source['body']['source_revision'], 'build_artifact': build['artifact'], 'build_digest': build['content_digest'],
                'started_at': result['started_at'], 'finished_at': result['finished_at'],
                'run_url': 'https://example.invalid/air/local-rehearsal/' + label,
                'tests': [{**t, 'status': t['status'] if t['status'] in ('PASS', 'FAIL', 'ERROR', 'SKIP') else 'FAIL'} for t in result['tests']]}
            report = artifacts.put(store, user, policy, settings, {'namespace': model.NAMESPACE, 'media_type': 'application/json',
                'idempotency_key': label + '-ledger'}, json.dumps(ledger).encode())
            ingested = ci_evidence.ingest(store, user, policy, {'baseline': base, 'source': pin(source), 'case': pin(case),
                'environment': pin(environment), 'report': report['artifact'], 'object_id': 'urn:journey:operational:' + label,
                'idempotency_key': label}, settings)
            members = [*exported['objects'], run, ingested['object']]
            return freeze(members, base), run, build
        good, good_run, good_build = execute('matching', baseline)
        assert good_run['body']['result'] == 'PASS'
        assert builder_handoff.assess(store, user, policy, {'baseline': good})['state'] != 'RECEIVED_FOR_BUILD_PLANNING'
        provider = repository / 'provider.py'; provider.write_text(provider.read_text().replace('quantity * 125', 'quantity * 126'))
        broken_revision = commit('Deliberately broken fixture for contract regression')
        changed = deepcopy(source); changed['meta']['revision'] += 1; changed['body']['source_revision'] = broken_revision
        prepared = agent.rebase_drafts(store, user, policy, settings, {'base': good, 'objects': [changed], 'include_bundle': False})['prepared_change']['id']
        agent.deposit_prepared(store, user, policy, {'prepared_change': prepared})
        broken = agent.freeze_prepared(store, user, policy, {'prepared_change': prepared})['baseline']
        impact = evidence_impact.compare(store, user, policy, {'before': good, 'after': broken})
        failed, failed_run, failed_build = execute('broken', broken)
        assert failed_run['body']['result'] == 'FAIL'
        report = {'format': 'air.architecture-journey/1', 'status': 'PASS_SCOPED', 'engine_version': __version__,
            'initial_baseline': baseline, 'matching_baseline': good, 'changed_baseline': broken, 'failed_baseline': failed,
            'implementation_revisions': [revision, broken_revision], 'build_digests': [good_build['content_digest'], failed_build['content_digest']],
            'matching_run': pin(good_run), 'failed_run': pin(failed_run), 'evidence_impact': impact,
            'matching_implementation_tests': 'PASS', 'broken_implementation_tests': 'FAIL',
            'previous_handoff_acceptance_inherited': False, 'final_readiness': readiness.assess_readiness(store, user, policy, {'baseline': failed})['result'],
            'synthetic_fixture': True, 'real_team_validation': False, 'native_client_reception': False,
            'future_business_application_executed': False, 'local_python_prototype_executed': True,
            'ci_executed': False, 'independent_review_inferred': False,
            'limitations': ['Local scripted rehearsal and fictional builder identities', 'Signed runner attestation still needs independent qualification',
                           'The example.invalid run URL labels a local rehearsal; no remote CI was run']}
        (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        return report
    finally: store.engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); result = rehearse(args.output)
    print(json.dumps({k: result[k] for k in ('status', 'matching_implementation_tests', 'broken_implementation_tests', 'final_readiness')}))
