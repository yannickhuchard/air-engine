"""Exact documentary journey coverage, not research, approval or execution."""
from air.core import digest
from air.foundation import exact
from air.expr import artifact_digest

ENGINE = 'air.journey-catalog/1'
CONTEXTS = ('DIGITAL', 'PHYSICAL', 'GEOGRAPHIC')


def project(g):
    sources = {}
    descriptors = {}
    gaps = []

    def describe(o):
        key = (o['meta']['id'], o['meta']['revision'])
        if key in descriptors: return dict(descriptors[key])
        pin = {**exact(o), 'digest': digest(o)}
        sources[(pin['id'], pin['revision'])] = pin
        descriptors[key] = {'reference': pin, 'name': o['meta']['name'], 'type': o['meta']['type']}
        return dict(descriptors[key])

    def resolve(ref, owner, selector):
        o = g.get(ref)
        if o is None:
            gaps.append({'code': 'UNRESOLVED_REFERENCE', 'source': describe(owner)['reference'],
                         'selector': selector, 'target': ref})
            return {'reference': ref, 'name': ref['id'], 'type': 'UNRESOLVED'}
        return describe(o)

    journeys = []
    for o in g.of('CustomerJourney'):
        body = o['body']; row = {**describe(o), 'persona': resolve(body['persona'], o, '/body/persona'),
            'view_state': body.get('view_state', 'UNDECLARED'), 'scenario': body.get('scenario', 'Scénario à préciser'),
            'goal': body['goal'], 'category': body.get('category', 'UNDECLARED'),
            'trigger': body.get('trigger', 'Non déclaré'), 'outcome': body.get('outcome', 'Non déclaré'), 'steps': []}
        for i, step in enumerate(body['steps']):
            pointer = '/body/steps/' + str(i)
            s = {k: step[k] for k in ('id', 'name', 'channel', 'touchpoint', 'pain_points', 'outcome',
                'phase', 'action', 'thoughts', 'opportunities', 'frontstage', 'backstage', 'support_processes', 'duration') if k in step}
            s.update(source=describe(o)['reference'], selector=pointer, participants=[], usage_points=[], architecture_links=[])
            for j, ref in enumerate(step.get('participants', [])):
                s['participants'].append(resolve(ref, o, pointer + '/participants/' + str(j)))
            if 'touchpoint_ref' in step:
                tp = g.get(step['touchpoint_ref'])
                s['touchpoint_object'] = resolve(step['touchpoint_ref'], o, pointer + '/touchpoint_ref')
                if tp and tp['meta']['type'] == 'air.Touchpoint':
                    s['touchpoint_purpose'] = tp['body']['purpose']
                    s['accessibility'] = tp['body'].get('accessibility', 'Non documentée')
                    for j, ref in enumerate(tp['body'].get('participants', [])):
                        s['participants'].append(resolve(ref, tp, '/body/participants/' + str(j)))
                    for j, ref in enumerate(tp['body']['usage_points']):
                        point = g.get(ref); d = resolve(ref, tp, '/body/usage_points/' + str(j))
                        if point and point['meta']['type'] == 'air.UsagePoint':
                            d.update({k: point['body'][k] for k in ('kind', 'purpose', 'status', 'country', 'city', 'location_description') if k in point['body']})
                            parents = []; seen = {(ref['id'], ref['revision'])}; current = point
                            while 'parent' in current['body']:
                                parent_ref = current['body']['parent']; key = (parent_ref['id'], parent_ref['revision'])
                                if key in seen:
                                    gaps.append({'code': 'USAGE_POINT_CYCLE', 'source': describe(current)['reference'], 'selector': '/body/parent'}); break
                                seen.add(key); parent = g.get(parent_ref)
                                parents.append(resolve(parent_ref, current, '/body/parent'))
                                if not parent: break
                                current = parent
                            d['parents'] = parents
                            for n, link in enumerate(point['body'].get('architecture_links', [])):
                                s['architecture_links'].append({**resolve(link, point, '/body/architecture_links/' + str(n)),
                                    'witness': describe(point)['reference'], 'selector': '/body/architecture_links/' + str(n)})
                        s['usage_points'].append(d)
                    for j, ref in enumerate(tp['body'].get('architecture_links', [])):
                        s['architecture_links'].append({**resolve(ref, tp, '/body/architecture_links/' + str(j)),
                            'witness': describe(tp)['reference'], 'selector': '/body/architecture_links/' + str(j)})
            else:
                gaps.append({'code': 'TOUCHPOINT_UNTYPED', 'source': describe(o)['reference'], 'selector': pointer})
            refs = [(ref, pointer + '/architecture_links/' + str(j)) for j, ref in enumerate(step.get('architecture_links', []))]
            if 'function' in step: refs.append((step['function'], pointer + '/function'))
            if 'operation' in step:
                refs.append((step['operation']['contract'], pointer + '/operation/contract')); s['operation_name'] = step['operation']['name']
            for ref, field in refs:
                s['architecture_links'].append({**resolve(ref, o, field), 'witness': describe(o)['reference'], 'selector': field})
            if not s['architecture_links']:
                gaps.append({'code': 'STEP_ARCHITECTURE_UNLINKED', 'source': describe(o)['reference'], 'selector': pointer})
            s['participants'] = list({(p['reference']['id'], p['reference']['revision']): p for p in s['participants']}.values())
            s['systems'] = [resolve(ref, o, pointer + '/systems/' + str(n)) for n, ref in enumerate(step.get('systems', []))]
            s['linked_systems'] = list({(p['reference']['id'], p['reference']['revision']): p for p in s['architecture_links']
                if p['type'] in ('air.RuntimeComponent', 'air.ArchitectureBlock', 'air.Device')}.values())
            s['emotion'] = {k: value for k, value in step.get('emotion', {'status': 'UNKNOWN'}).items() if k != 'evidence'}
            s['emotion']['evidence'] = [resolve(ref, o, pointer + '/emotion/evidence/' + str(n))
                for n, ref in enumerate(step.get('emotion', {}).get('evidence', []))]
            s['experience_missing'] = [field for field in ('phase', 'action', 'thoughts', 'frontstage', 'backstage', 'support_processes', 'opportunities') if not step.get(field)]
            if s['emotion']['status'] == 'UNKNOWN': s['experience_missing'].append('emotion')
            if not s['systems']: s['experience_missing'].append('systems')
            row['steps'].append(s)
        journeys.append(row)
    catalogs = []; personas = {}; listed = set(); covered = set()
    for o in g.of('JourneyCatalog'):
        b = o['body']; catalog = {**describe(o), 'purpose': b['purpose'], 'scope': resolve(b['scope'], o, '/body/scope'), 'personas': []}
        for j, ref in enumerate(b['journeys']):
            resolve(ref, o, '/body/journeys/' + str(j)); listed.add((ref['id'], ref['revision']))
        for i, entry in enumerate(b['personas']):
            d = dict(resolve(entry['persona'], o, '/body/personas/' + str(i) + '/persona')); pin = d['reference']; key = (pin['id'], pin['revision'])
            relevant = [j for j in journeys if (j['persona']['reference']['id'], j['persona']['reference']['revision']) == key
                        and (j['reference']['id'], j['reference']['revision']) in {(r['id'], r['revision']) for r in b['journeys']}]
            contexts = sorted({p['kind'] for j in relevant for s in j['steps'] for p in s['usage_points'] if p.get('kind') in CONTEXTS})
            missing = sorted(set(entry['required_contexts']) - set(contexts))
            d.update(coverage=entry['coverage'], rationale=entry['rationale'], required_contexts=entry['required_contexts'],
                     declared_contexts=contexts, missing_contexts=missing, journeys=[j['reference'] for j in relevant])
            if key in personas:
                gaps.append({'code': 'PERSONA_MULTIPLE_CATALOGS', 'source': pin, 'catalog': describe(o)['reference']})
            catalog['personas'].append(d); personas[key] = d
            if entry['coverage'] == 'REQUIRED':
                covered.add(key)
                if not relevant: gaps.append({'code': 'PERSONA_JOURNEY_MISSING', 'source': pin, 'catalog': describe(o)['reference']})
                if missing: gaps.append({'code': 'PERSONA_CONTEXT_MISSING', 'source': pin, 'catalog': describe(o)['reference'], 'contexts': missing})
        catalogs.append(catalog)
    if not catalogs: gaps.append({'code': 'CATALOG_MISSING'})
    unlisted_participants = set()
    for j in journeys:
        pin = j['reference']
        if (pin['id'], pin['revision']) not in listed: gaps.append({'code': 'JOURNEY_NOT_CATALOGUED', 'source': pin})
        if (j['persona']['reference']['id'], j['persona']['reference']['revision']) not in covered:
            gaps.append({'code': 'JOURNEY_PERSONA_NOT_REQUIRED', 'source': pin})
        for step in j['steps']:
            for participant in step['participants']:
                p = participant['reference']; key = (p['id'], p['revision'])
                if key not in personas and key not in unlisted_participants:
                    unlisted_participants.add(key)
                    gaps.append({'code': 'PARTICIPANT_NOT_CATALOGUED', 'source': p})
    # A declared roster must account for all human actors and stakeholders in
    # its exact scope. Other scopes and software/robot actors are not personas
    # by inference. They can explicitly be included or excluded in the roster.
    scopes = {c['scope']['reference']['id'] for c in catalogs}
    for o in g.of('Actor') + g.of('Stakeholder'):
        boundary = o['body'].get('boundary')
        if o['meta']['type'] == 'air.Actor' and o['body'].get('kind') != 'HUMAN': continue
        if boundary and boundary['id'] not in scopes: continue
        if (o['meta']['id'], o['meta']['revision']) not in personas:
            gaps.append({'code': 'PERSONA_NOT_CATALOGUED', 'source': describe(o)['reference']})
    rules = [
        ('CATALOG', 'Périmètre des parcours et personas déclaré', {'CATALOG_MISSING', 'PERSONA_NOT_CATALOGUED', 'PARTICIPANT_NOT_CATALOGUED', 'PERSONA_MULTIPLE_CATALOGS'}),
        ('PERSONAS', 'Chaque persona requis possède un parcours inventorié', {'PERSONA_JOURNEY_MISSING', 'JOURNEY_NOT_CATALOGUED', 'JOURNEY_PERSONA_NOT_REQUIRED'}),
        ('TOUCHPOINTS', 'Chaque étape possède un point de contact typé', {'TOUCHPOINT_UNTYPED'}),
        ('CONTEXTS', 'Usages numériques, physiques et géographiques justifiés', {'PERSONA_CONTEXT_MISSING', 'USAGE_POINT_CYCLE'}),
        ('LINKS', 'Chaque étape est reliée au dossier par références exactes', {'STEP_ARCHITECTURE_UNLINKED', 'UNRESOLVED_REFERENCE'})]
    checks = [{'code': code, 'label': label, 'status': 'MET' if catalogs and not any(gap['code'] in codes for gap in gaps) else 'MISSING',
               'gap_count': sum(gap['code'] in codes for gap in gaps)} for code, label, codes in rules]
    priority = {'NOMINAL': 0, 'SUPPORT': 1, 'EXCEPTION': 2, 'OPERATIONS': 3, 'GOVERNANCE': 4}
    journeys.sort(key=lambda j: (priority.get(j['category'], 5), j['name'], j['reference']['id']))
    result = {'engine': ENGINE, 'catalogs': catalogs, 'personas': sorted(personas.values(), key=lambda p: (p['name'], p['reference']['id'])),
              'journeys': journeys, 'touchpoint_count': len(g.of('Touchpoint')), 'usage_point_count': len(g.of('UsagePoint')),
              'checks': checks, 'gaps': gaps, 'sources': [sources[k] for k in sorted(sources)],
              'semantic_completeness_certified': False, 'research_validated': False, 'business_execution_performed': False}
    return {**result, 'projection_digest': artifact_digest(result)}
