"""Real HTTP/CLI resource admission for three synthetic Asteria dossiers."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
from air import __version__, admission
from air.access import AccessPolicy
from air.authority import sync_policy
from air.backup import snapshot, restore
from air.cli import bootstrap
from air.config import Settings, write_private
from air.mcp import APIClient, Session, PROTOCOL
from air.storage import Store, SCHEMA_VERSION
from demo_planning import prepare
from demo_experiments import read as fixture, request_for
from install import start, stop
ROOT = Path(__file__).resolve().parents[1]


def rehearse(with_lifecycle=False):
    if os.environ.get('AIR_DATABASE_URL'): raise ValueError('Use isolated default SQLite for this demonstration')
    workspace = ROOT / 'tmp' / ('air-admission-' + uuid.uuid4().hex)
    home = workspace / 'home';bootstrap(home)
    store = Store(Settings.load(home).database_url)
    roles = {'capacity-owner': ['capacity'], 'planner': ['write'], 'reviewer': ['review'], 'admitter': ['admit'], 'activator': ['activate']}
    policy_doc = {'version': 'asteria-admission-1', 'subjects': {actor: {'read': ['*'], **{action: ['*'] for action in actions}} for actor, actions in roles.items()}}
    policy_doc['subjects']['local-admin'] = {'read': ['*'], 'write': ['*']}
    try:
        plan = prepare(store)
        source = deepcopy(store.get(plan['pools'][0]['source']['id'], 1)['object'])
        source['meta'].update(id='urn:asteria:source:capacity-current', name='Synthetic current capacity source')
        source['body'].update(kind='TELEMETRY', locator='urn:asteria:synthetic:capacity', captured_at=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'))
        stored = store.put(source, 'capacity-owner');plan['pools'][0]['source'] = {k: stored[k] for k in ('id', 'revision', 'digest')}
        experiments = [request_for(store, case) for case in fixture('manifest.json')['dossiers']]
        for actor in roles: write_private(home / (actor + '.json'), store.create_token(actor, 'editor'))
        write_private(home / 'access-policy.json', policy_doc);sync_policy(store, AccessPolicy(policy_doc))
    finally: store.engine.dispose()
    with socket.socket() as probe: probe.bind(('127.0.0.1', 0));port = probe.getsockname()[1]
    def call(endpoint, body, actor='planner', expected=(200,)):
        token = json.loads((home / (actor + '.json')).read_text(encoding='utf-8'))['access_token']
        req = Request('http://127.0.0.1:' + str(port) + endpoint, data=json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            with build_opener(ProxyHandler({})).open(req, timeout=30) as result: status, value = result.status, json.load(result)
        except HTTPError as error: status, value = error.code, json.load(error)
        assert status in expected, 'Unexpected status ' + str(status) + ' at ' + endpoint
        return value
    def reviewed(request):
        proposal = call('/v1/admission/propose', request)
        review = call('/v1/admission/review', {'idempotency_key': request['idempotency_key'], 'proposal': proposal['proposal'],
            'decision': 'ACCEPT', 'rationale': 'Resource review of synthetic Asteria dossiers; no business system acceptance.',
            'expires_at': instant(datetime.now(timezone.utc) + timedelta(days=1))}, 'reviewer')
        return proposal, {'idempotency_key': request['idempotency_key'], 'proposal': proposal['proposal'], 'approvals': [review['review']]}
    instant = lambda date: date.isoformat().replace('+00:00', 'Z')
    lifecycle = None
    start(Path(sys.executable), home, port, no_worker=True)
    try:
        window = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=90)
        plan['periods'] = [{'start': instant(window + timedelta(weeks=i)), 'end': instant(window + timedelta(weeks=i+1))} for i in range(8)]
        offer = {k: deepcopy(v) for k, v in plan['pools'][0].items() if k != 'existing_reservations'}
        offer.update(idempotency_key='offer', expected_offer=None, resource_kind='HUMAN_FTE', periods=plan['periods'],
            observed_at=instant(datetime.now(timezone.utc)), expires_at=instant(window + timedelta(weeks=9)))
        offer_result = call('/v1/capacity/offers', offer, 'capacity-owner')
        request = {k: deepcopy(v) for k, v in plan.items() if k in admission.PROPOSE['properties']}
        request.update(idempotency_key='initial', offers=[offer_result['offer']])
        initial, command = reviewed(request)
        denied = call('/v1/admission/admit', command, 'admitter')
        assert denied['status'] == 'DENIED' and initial['report']['proposed']['total_shortfall_FTE_weeks'] == '4'
        concurrent = []
        for i, demand in enumerate(request['demands']):
            individual = deepcopy(request); individual.update(idempotency_key='individual-' + str(i), demands=[demand], priority_order=[{k: demand['unit'][k] for k in ('id', 'revision')}])
            proposal, cmd = reviewed(individual)
            assert proposal['report']['result'] == 'SATISFIED';concurrent.append(cmd)
        with ThreadPoolExecutor(max_workers=3) as executor:
            decisions = list(executor.map(lambda cmd: call('/v1/admission/admit', cmd, 'admitter'), concurrent))
        assert sorted(r['status'] for r in decisions) == ['ADMITTED', 'ADMITTED', 'DENIED']
        for i, receipt in enumerate(decisions):
            if receipt['status'] == 'ADMITTED': call('/v1/admission/release', {'idempotency_key': 'release-' + str(i), 'admission': receipt['receipt'], 'rationale': 'Replace separate proposals with collective sequence'}, 'admitter')
        variant = deepcopy(request);variant.update(idempotency_key='collective', strategy='SERIAL_EARLIEST_FEASIBLE')
        collective, command = reviewed(variant)
        # The child exits after the committed response without returning it to its caller.
        command_file = workspace / 'admit.json'; command_file.write_text(json.dumps(command), encoding='utf-8')
        code = "import os,json,sys;from pathlib import Path;from air.mcp import APIClient;c=APIClient(Path(sys.argv[1]),'admitter.json',int(sys.argv[2]));r=c('air_admission_admit',json.loads(Path(sys.argv[3]).read_text()));assert r['status']=='ADMITTED';os._exit(17)"
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
        child = subprocess.run([sys.executable, '-c', code, str(home), str(port), str(command_file)], cwd=ROOT,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30, **options)
        assert child.returncode == 17
        stop(home);start(Path(sys.executable), home, port, no_worker=True)
        committed = call('/v1/admission/admit', command, 'admitter')
        assert committed['status'] == 'ADMITTED' and not committed['created']
        capacity = call('/v1/capacity/read', {'pool_id': offer['scope']['id']})
        assert capacity['existing_reservations'] == ['3'] * 4 + ['2'] * 4
        session = Session(APIClient(home, 'admitter.json', port))
        session.handle({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': PROTOCOL, 'capabilities': {}, 'clientInfo': {'name': 'admission-demo', 'version': '1'}}})
        session.handle({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
        replay = session.handle({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call', 'params': {'name': 'air_admission_read', 'arguments': {'admission': committed['receipt']}}})['result']
        assert not replay['isError'] and len(replay['structuredContent']['reservations']) == 12
        simulations = [call('/v1/experiments', body) for body in experiments]
        assert [r['result'] for r in simulations] == ['SATISFIED', 'SATISFIED', 'CONFLICTING']
        first = {'idempotency_key': 'activate-sav', 'admission': committed['receipt'], 'unit': request['demands'][0]['unit']}
        call('/v1/admission/activate', first, 'activator', (409,))
        wait = (window - datetime.now(timezone.utc)).total_seconds()
        while wait > 0:
            time.sleep(min(wait, 1));wait = (window - datetime.now(timezone.utc)).total_seconds()
        activated = call('/v1/admission/activate', first, 'activator')
        assert activated['status'] == 'AUTHORIZED' and not activated['external_action_executed']
        call('/v1/admission/release', {'idempotency_key': 'protect-active', 'admission': committed['receipt'], 'rationale': 'Attempted release of active work'}, 'admitter', (409,))
        unavailable = deepcopy(offer);unavailable.update(idempotency_key='unavailable', expected_offer=offer_result['offer'], availability='UNAVAILABLE')
        call('/v1/capacity/offers', unavailable, 'capacity-owner')
        third = {'idempotency_key': 'activate-identity', 'admission': committed['receipt'], 'unit': request['demands'][2]['unit']}
        call('/v1/admission/activate', third, 'activator', (409,))
        owner = json.loads((home / 'capacity-owner.json').read_text(encoding='utf-8'))
        store = Store(Settings.load(home).database_url)
        try: store.revoke_token(owner['token_id'])
        finally: store.engine.dispose()
        call('/v1/admission/activate', third, 'activator', (403,))
        historical = call('/v1/admission/read', {'admission': committed['receipt']})
        assert historical['reservations'] == replay['structuredContent']['reservations']
        if with_lifecycle:
            # Renew identities and authority explicitly through the operator binding.
            store = Store(Settings.load(home).database_url)
            try:
                write_private(home / 'capacity-owner-renewed.json', store.create_token('capacity-owner', 'editor'))
                (home / 'capacity-owner-renewed.json').replace(home / 'capacity-owner.json')
            finally: store.engine.dispose()
            policy_doc['version'] = 'asteria-admission-2'
            policy_file = workspace / 'new-policy.json';policy_file.write_text(json.dumps(policy_doc), encoding='utf-8')
            result = subprocess.run([sys.executable, '-m', 'air', '--home', str(home), 'policy-set', str(policy_file)], capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert result.returncode == 0
            fresh = deepcopy(offer);fresh.update(idempotency_key='fresh-authority', expected_offer=call('/v1/capacity/read', {'pool_id': offer['scope']['id']})['offer'], observed_at=instant(datetime.now(timezone.utc)))
            current_offer = call('/v1/capacity/offers', fresh, 'capacity-owner')
            draft = call('/v1/renewal/propose', {'idempotency_key': 'renew-proposal', 'admission': committed['receipt'], 'expected_authorization': None, 'offers': [current_offer['offer']]})
            review = call('/v1/admission/review', {'idempotency_key': 'renew-review', 'proposal': draft['proposal'], 'decision': 'ACCEPT',
                'rationale': 'Review renewed authority for exactly the existing commitments.', 'expires_at': instant(datetime.now(timezone.utc) + timedelta(days=1))}, 'reviewer')
            renewal = call('/v1/renewal/renew', {'idempotency_key': 'renew', 'proposal': draft['proposal'], 'approvals': [review['review']]}, 'admitter')
            assert renewal['status'] == 'REAUTHORIZED' and not renewal['reservations_created']
            renewed_state = call('/v1/admission/read', {'admission': committed['receipt']})
            assert renewed_state['reservations'] == historical['reservations']
            next_activation = call('/v1/admission/activate', {**third, 'idempotency_key': 'renewed-activation'}, 'activator')
            episodes = [activated['receipt'], next_activation['receipt']]
            store = Store(Settings.load(home).database_url)
            try:
                evidence = {'id': 'urn:asteria:evidence:d01', 'revision': 1, 'digest': store.get('urn:asteria:evidence:d01', 1)['digest']}
            finally: store.engine.dispose()
            closures = []
            for i, episode in enumerate(episodes):
                closing = call('/v1/closure/propose', {'idempotency_key': 'close-' + str(i), 'activation': episode, 'outcome': 'COMPLETED',
                    'evidence': evidence, 'rationale': 'Synthetic reported completion, without external execution claim.'}, 'activator')
                review_body = {'idempotency_key': 'close-review-' + str(i), 'proposal': closing['proposal'], 'decision': 'ACCEPT',
                    'rationale': 'Independent review of synthetic episode evidence.', 'expires_at': instant(datetime.now(timezone.utc) + timedelta(days=1))}
                call('/v1/closure/review', review_body, 'activator', (403,))
                accepted = call('/v1/closure/review', review_body, 'reviewer')
                closed = call('/v1/closure/close', {'idempotency_key': 'close-' + str(i), 'proposal': closing['proposal'], 'approvals': [accepted['review']]}, 'admitter')
                assert closed['business_verification'] == 'NOT_EXECUTED' and not closed['reservations_released'];closures.append(closed)
                if i == 0: call('/v1/admission/release', {'idempotency_key': 'still-open', 'admission': committed['receipt'], 'rationale': 'Second episode remains protected'}, 'admitter', (409,))
            released = call('/v1/admission/release', {'idempotency_key': 'release-closed', 'admission': committed['receipt'],
                'rationale': 'Close finished synthetic episodes and cancel the unstarted workshop reservation.'}, 'admitter')
            historical = call('/v1/admission/read', {'admission': committed['receipt']})
            assert len(historical['episodes']) == 2 and all(e['status'] == 'CLOSED' for e in historical['episodes'])
            assert all(r['released'] == 1 for r in historical['reservations'])
            lifecycle = {'status': 'PASS_SCOPED', 'renewal': renewal, 'reservation_vector_unchanged_on_renewal': True,
                'second_activation': next_activation, 'closures': closures, 'auto_review_refused': True, 'open_episode_release_refused': True,
                'explicit_release': released, 'unstarted_workshop': 'RESERVATION_CANCELLED_NOT_COMPLETED', 'final_state': historical}

    finally: stop(home)
    snapshot(home, workspace / 'backup'); recovery = restore(workspace / 'backup', workspace / 'restored')
    restored = Store(Settings.load(workspace / 'restored').database_url)
    try:
        recovered = admission.read(restored, {'subject': 'admitter', 'role': 'editor'}, AccessPolicy.load(workspace / 'restored'), {'admission': committed['receipt']})
        assert recovered == historical
    finally: restored.engine.dispose()
    return {'status': 'PASS_SCOPED', 'version': __version__, 'schema': SCHEMA_VERSION, 'company': 'Asteria Industrie',
        'dossiers': [case['id'] for case in fixture('manifest.json')['dossiers']], 'initial': initial, 'initial_admission': denied,
        'concurrent_decisions': decisions, 'collective': collective, 'admission': committed, 'capacity': capacity,
        'activation': activated, 'simulations': simulations, 'client_exit_after_commit': 17, 'restart_replay_identical': True,
        'too_early_refused': True, 'source_unavailable_refused': True, 'collector_revoked_refused': True,
        'active_commitments_preserved': True, 'restored_commitments_identical': True, 'recovery': recovery,
        'clock': 'REAL_SERVER_UTC', 'synthetic_window_start': instant(window), 'external_action_executed': False,
        'lifecycle': lifecycle, 'limits': ['Local resource episode only', 'Weekly disjoint human pools', 'Business VerificationCases remain NOT_EXECUTED',
                   'Collector expiry is qualified with a controlled clock in tests; this HTTP demo exercises revocation', 'No distributed authority or remote execution']}


if __name__ == '__main__':
    result = rehearse(); output = ROOT / 'tmp/demo-asteria/admission.json';output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding='utf-8')
    from air.report_views import admission_html
    output.with_suffix('.html').write_text(admission_html(result), encoding='utf-8', newline='\n')
    print(json.dumps({'status': result['status'], 'version': result['version'], 'report': str(output)}))
