"""Validate pinned native-client evidence without certifying its authorship."""
from pathlib import Path
from air.operations_acceptance import read_report
from air.operations_reception import evidence, digest, text, sha

CLIENTS = ('chatgpt', 'claude-code', 'codex')
CASES = tuple('IDE-%02d' % n for n in range(1,11))
JOURNEYS = ('individual_identities', 'independent_review', 'network_recovery',
            'credential_expiry', 'credential_rotation', 'cross_client_resume',
            'explicit_workstation_exchange', 'cli_api_mcp_parity')
LOCAL_CLIENTS = ('chatgpt', 'codex')
DEFERRED_JOURNEYS = ('independent_review', 'explicit_workstation_exchange')
LOCAL_SCOPE = 'P07_LOCAL_CODEX_CHATGPT_2026_09_28'


def check(path):
    path = Path(path)
    dossier = read_report(path)
    if not isinstance(dossier,dict) or dossier.get('format') not in ('air.p07-reception/1', 'air.p07-reception/2'):
        raise ValueError('Unsupported client reception dossier')
    local = dossier['format'] == 'air.p07-reception/2'
    issues = []
    def require(condition, field):
        if not condition: issues.append({'field':field,'code':'MISSING_INVALID_OR_NOT_EXECUTED'})
    require(text(dossier.get('air_version')), 'air_version')
    require(sha(dossier.get('source_sha256')), 'source_sha256')
    require(dossier.get('profile') == 'LOCAL_ARCHITECT_WORKSTATION', 'profile')
    if local:
        require(dossier.get('scope_decision') == LOCAL_SCOPE, 'scope_decision')
        require(dossier.get('deferred_journeys') == list(DEFERRED_JOURNEYS), 'deferred_journeys')
    clients = dossier.get('clients')
    if not isinstance(clients,dict): clients = {}
    # Required clients cannot be silently replaced by a protocol simulator, another
    # product in the same family, or a smaller list in the submitted dossier.
    for client in (LOCAL_CLIENTS if local else CLIENTS):
        ref = clients.get(client)
        try:
            report = evidence(path.parent.resolve(), ref)
            require(isinstance(report,dict), client+'.report')
            if not isinstance(report,dict): continue
            require(report.get('format') == 'air.native-client-reception/1',client+'.format')
            require(report.get('client') == client,client+'.client')
            require(report.get('execution_kind') == 'NATIVE_CLIENT',client+'.execution_kind')
            for key in ('client_version','surface','os','transport'):
                require(text(report.get(key)),client+'.'+key)
            for key in ('air_version','source_sha256'):
                require(report.get(key) == dossier.get(key),client+'.'+key)
            cases = report.get('cases',{})
            if not isinstance(cases,dict): cases = {}
            for case in CASES:
                item = cases.get(case)
                field = client+'.'+case
                require(isinstance(item,dict),field)
                if not isinstance(item,dict): continue
                require(item.get('status') == 'PASS',field+'.status')
                proof = evidence(path.parent.resolve(),item.get('evidence'))
                require(isinstance(proof,dict),field+'.evidence')
                if not isinstance(proof,dict): continue
                require(proof.get('case') == case and proof.get('client') == client,field+'.binding')
                require(proof.get('execution_kind') == 'NATIVE_CLIENT',field+'.execution_kind')
                require(proof.get('client_version') == report.get('client_version'),field+'.version')
                require(proof.get('air_version') == dossier.get('air_version') and
                        proof.get('source_sha256') == dossier.get('source_sha256'),field+'.source')
                require(sha(proof.get('transcript_sha256')),field+'.transcript')
                observations = proof.get('observations')
                require(isinstance(observations,list) and 0 < len(observations) <= 100 and
                        all(text(v) for v in observations),field+'.observations')
                require(proof.get('expected_only') is False,field+'.executed')
        except (ValueError,OSError,TypeError,KeyError): require(False,client+'.evidence')
    journeys = dossier.get('journeys',{})
    if not isinstance(journeys,dict): journeys = {}
    for key in JOURNEYS:
        if local and key in DEFERRED_JOURNEYS:
            continue
        try:
            report = evidence(path.parent.resolve(),journeys.get(key))
            require(isinstance(report,dict), 'journeys.'+key)
            if not isinstance(report,dict): continue
            require(report.get('journey') == key and report.get('status') == 'PASS','journeys.'+key+'.status')
            require(report.get('air_version') == dossier.get('air_version') and
                    report.get('source_sha256') == dossier.get('source_sha256'),'journeys.'+key+'.source')
            require(sha(report.get('transcript_sha256')),'journeys.'+key+'.transcript')
            require(report.get('expected_only') is False,'journeys.'+key+'.executed')
            if key == 'independent_review':
                require(text(report.get('author_identity')) and text(report.get('reviewer_identity')) and
                        report.get('author_identity') != report.get('reviewer_identity') and
                        report.get('human_review_performed') is True,'journeys.'+key+'.independence')
        except (ValueError,OSError,TypeError,KeyError): require(False,'journeys.'+key+'.evidence')
    return {'format':'air.p07-reception-check/1', 'status':'INCOMPLETE' if issues else 'LOCAL_TECHNICAL_EVIDENCE_COMPLETE' if local else 'READY_FOR_INDEPENDENT_REVIEW',
            'issues':issues,'evidence_complete':not issues,'p07_received':False,'production_ready':False,
            'scope_decision': LOCAL_SCOPE if local else None,
            'required_clients': list(LOCAL_CLIENTS if local else CLIENTS),
            'deferred_journeys': list(DEFERRED_JOURNEYS) if local else [],
            'authorship_verified':False,'organizational_independence_verified':False,
            'dossier_sha256':digest(dossier)}
