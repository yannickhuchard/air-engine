"""Compile a declared viewpoint against one authorized exact baseline."""
import base64
import hashlib
from html import escape
import json
from air.access import ScopedStore
from air.core import canonical, digest, record
from air.foundation import InvalidModel, check_schema, exact, key
from air.projections import SNAPSHOT, STYLE, snapshot
from air.storage import Conflict

ENGINE = 'air.audience/0.19'
REQUEST = record({'baseline': SNAPSHOT, 'viewpoint': SNAPSHOT})


def compile_view(store, principal, policy, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    if len(json.dumps(exported, ensure_ascii=False).encode()) > 1024 * 1024:
        raise InvalidModel('Audience view context exceeds 1 MiB')
    by_ref = {key(exact(o)): o for o in exported['objects']}
    viewpoint = by_ref.get(key(request['viewpoint']))
    if not viewpoint or viewpoint['meta']['type'] != 'air.Viewpoint':
        raise InvalidModel('Viewpoint is not a member of the requested baseline')
    if digest(viewpoint) != request['viewpoint']['digest']:
        raise Conflict('Viewpoint digest differs from the requested revision')
    body = viewpoint['body'];selection = body['selection']
    roots = {key(r) for r in selection['objects']};types = set(selection['types'])
    selected = sorted([json.loads(canonical(o)) for k, o in by_ref.items() if k in roots or o['meta']['type'] in types], key=lambda o: key(exact(o)))
    presentation = body['presentation'];assigned = set();sections = []
    for section in presentation['sections']:
        values = [o for o in selected if o['meta']['type'] in section['types']]
        assigned.update(key(exact(o)) for o in values)
        sections.append((section['id'], section['heading'], values))
    remaining = [o for o in selected if key(exact(o)) not in assigned]
    if remaining: sections.append(('air-unassigned', 'Autres objets sélectionnés', remaining))
    def anchor(obj): return 'obj-' + hashlib.sha256((obj['meta']['id'] + '@' + str(obj['meta']['revision'])).encode()).hexdigest()[:24]
    style_hash = base64.b64encode(hashlib.sha256(STYLE.encode()).digest()).decode()
    csp = "default-src 'none'; style-src 'sha256-" + style_hash + "'; base-uri 'none'; form-action 'none'; connect-src 'none'"
    title = presentation['title']
    context_mapping = [{'object': request['viewpoint'], 'selector': '#viewpoint-header'}, {'object': request['viewpoint'], 'selector': '#viewpoint-disclosure'}]
    context_mapping.extend({'object': {**ref, 'digest': digest(by_ref[key(ref)])}, 'selector': '#viewpoint-audience'} for ref in body['audience'])
    chunks = ['<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="' + escape(csp, quote=True) + '">',
        '<title>' + escape(title) + '</title><style>' + STYLE + '</style></head><body>',
        '<header id="viewpoint-header"><p>AIR · Vue par audience</p><h1>' + escape(title) + '</h1>',
        '<p id="viewpoint-audience">' + escape(', '.join(by_ref[key(r)]['meta']['name'] for r in body['audience'])) + '</p></header><main>',
        '<p class="notice">Valeurs et statuts déclarés conservés. Les objets exclus de la sélection ne sont pas évalués par cette vue.</p>',
        '<p>' + str(len(selected)) + ' objets sélectionnés ; ' + str(len(by_ref) - len(selected)) + ' objets hors sélection.</p>',
        '<details><summary>Préoccupations et conditions de lecture</summary><h2>Préoccupations</h2><ul>']
    for ref in body['concerns']:
        target = 'concern-' + anchor(by_ref[key(ref)])
        context_mapping.append({'object': {**ref, 'digest': digest(by_ref[key(ref)])}, 'selector': '#' + target})
        chunks.append('<li id="' + target + '">' + escape(by_ref[key(ref)]['body']['question']) + '</li>')
    chunks.extend(['</ul><h2>Divulgation déclarée</h2><p id="viewpoint-disclosure">' + escape(body['disclosure_policy']) + '</p>',
        '<p class="caption">Cette politique déclarée ne modifie pas les droits d’accès et n’applique aucun masquage de champs.</p></details><nav>'])
    for identifier, heading, values in sections:
        chunks.append('<a href="#section-' + escape(identifier, quote=True) + '">' + escape(heading) + ' (' + str(len(values)) + ')</a>')
    chunks.append('</nav>');mapping = []
    for identifier, heading, values in sections:
        chunks.append('<section id="section-' + escape(identifier, quote=True) + '"><h2>' + escape(heading) + '</h2>')
        if not values: chunks.append('<p>Aucun objet sélectionné pour cette section.</p>')
        for obj in values:
            target = anchor(obj);pin = {**exact(obj), 'digest': digest(obj)}
            mapping.append({'object': pin, 'selector': '#' + target})
            chunks.extend(['<article id="' + target + '"><h3>' + escape(obj['meta']['name']) + '</h3>',
                '<p class="caption">' + escape(obj['meta']['type']) + ' · révision ' + str(obj['meta']['revision']) + ' · ' + escape(obj['meta']['lifecycle']) + '</p>',
                ])
            labels = {'outcome': 'Résultat visé', 'desired_change': 'Changement souhaité', 'question': 'Question',
                'statement': 'Énoncé', 'definition': 'Définition', 'ability': 'Capacité', 'value_proposition': 'Valeur proposée',
                'offer': 'Offre', 'description': 'Description', 'reason': 'Motif', 'rationale': 'Justification', 'condition': 'Condition'}
            for field, label in labels.items():
                value = obj['body'].get(field)
                if isinstance(value, str): chunks.append('<p><strong>' + label + ' : </strong>' + escape(value) + '</p>')
            for field in ('epistemic_status', 'state'):
                if field in obj['body']: chunks.append('<p>État déclaré : <strong>' + escape(obj['body'][field]) + '</strong></p>')
            if obj['meta']['type'] == 'air.Goal':
                chunks.append('<p>Cibles déclarées, sans nouvelle évaluation :</p><pre>' + escape(json.dumps(obj['body']['targets'], ensure_ascii=False, indent=2)) + '</pre>')
            if obj['meta']['type'] == 'air.Conflict': chunks.append('<p class="warning">Conflit déclaré ; une décision documentée ne démontre pas sa résolution.</p>')
            if obj['meta']['type'] == 'air.Inference': chunks.append('<p class="warning">Dérivation déclarée, non exécutée par cette vue.</p>')
            chunks.append('<details><summary>Objet et provenance exacts</summary><pre>' + escape(json.dumps(obj, ensure_ascii=False, indent=2)) + '</pre></details></article>')
        chunks.append('</section>')
    chunks.append('<footer><p class="digest">Baseline : ' + escape(request['baseline']['id']) + ' · ' + escape(request['baseline']['digest']) + '</p><p class="digest">Viewpoint : ' + escape(request['viewpoint']['id']) + ' · ' + escape(request['viewpoint']['digest']) + '</p><p>Générateur déterministe ' + ENGINE + '. Aucune connexion active ni donnée d’authentification embarquée.</p></footer></main></body></html>')
    content = ''.join(chunks)
    if len(content.encode()) > 4 * 1024 * 1024: raise InvalidModel('Audience view exceeds 4 MiB')
    return {'engine': ENGINE, 'baseline': request['baseline'], 'viewpoint': request['viewpoint'], 'media_type': 'text/html',
        'content': content, 'content_digest': 'sha256:' + hashlib.sha256(content.encode()).hexdigest(),
        'objects_selected': len(selected), 'objects_excluded': len(by_ref) - len(selected), 'source_mapping': mapping, 'context_mapping': context_mapping,
        'selection_semantics': 'UNION_OF_TYPES_AND_EXACT_OBJECTS', 'field_redaction': False, 'authorization_granted': False,
        'model_modified': False, 'live_connection': False, 'credentials_embedded': False, 'normative_view_persisted': False}
