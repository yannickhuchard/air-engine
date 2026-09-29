"""Portable interactive exports of exact, access-checked AIR contexts."""
import base64
import hashlib
from html import escape
from importlib.resources import files
import json
from air.access import ScopedStore
from air.collaboration import whoami
from air.core import record, reference_slots
from air.foundation import check_schema, exact, InvalidModel
from air.projections import SNAPSHOT, snapshot

REQUEST = record({'baseline': SNAPSHOT})
ENGINE = 'air.workbench/0.14'


def compile_workbench(store, principal, policy, settings, request):
    check_schema(request, REQUEST)
    exported = snapshot(ScopedStore(store, principal, policy), request['baseline'])
    objects = sorted(exported['objects'], key=lambda o: (o['meta']['type'], o['meta']['name'], o['meta']['id']))
    data = {'baseline': request['baseline'], 'objects': objects, 'identity': whoami(principal, settings)['identity'],
        'writable_namespaces': sorted({o['meta']['namespace'] for o in objects if policy.allows(principal, 'write', o['meta']['namespace'])}),
        'links': [{'from': exact(o), 'to': {k: ref[k] for k in ('id', 'revision')}, 'field': field}
                  for o in objects for field, ref, _ in reference_slots(o)]}
    raw = json.dumps(data, ensure_ascii=True, separators=(',', ':'))
    if len(raw.encode('utf-8')) > 1024 * 1024: raise InvalidModel('Workbench context exceeds 1 MiB')
    raw = raw.replace('<', r'\u003c').replace('>', r'\u003e').replace('&', r'\u0026')
    script = files('air').joinpath('assets/workbench.js').read_text(encoding='utf-8')
    style = files('air').joinpath('assets/workbench.css').read_text(encoding='utf-8')
    def checksum(text): return base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode('ascii')
    csp = "default-src 'none'; script-src 'sha256-" + checksum(script) + "'; style-src 'sha256-" + checksum(style) + "'; connect-src 'none'; base-uri 'none'; form-action 'none'"
    title = escape(exported['baseline']['meta']['name'])
    fallback = ''.join('<li>' + escape(o['meta']['name']) + ' — ' + escape(o['meta']['type']) + ', révision ' + str(o['meta']['revision']) + '</li>' for o in objects)
    content = f'''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}"><meta name="referrer" content="no-referrer">
<title>AIR · {title}</title><style>{style}</style></head><body>
<a class="skip" href="#object-title">Aller à l’objet sélectionné</a>
<header><p>AIR Workbench</p><h1>{title}</h1><p>Contexte exact de conception · objets DRAFT</p><p id="js-status" role="status">Consultation interactive disponible avec JavaScript</p></header>
<noscript><section><h2>Contenu du contexte</h2><p>Activez JavaScript pour filtrer les objets et préparer une contribution. Aucun accès réseau n’est nécessaire.</p><ul>{fallback}</ul></section></noscript>
<div class="shell"><nav class="navigator" aria-label="Objets de la baseline"><div class="filters"><h2>Explorer le contexte</h2>
<label for="search">Rechercher</label><input type="search" id="search" placeholder="Nom, description ou contenu" autocomplete="off">
<label for="type-filter">Type d’objet</label><select id="type-filter"><option value="">Tous les types</option></select>
<p id="result-count" role="status" aria-live="polite"></p></div><p id="empty-results" hidden>Aucun objet ne correspond. Modifiez le filtre ou la recherche.</p><ul id="object-list"></ul></nav>
<main class="detail"><p id="object-type" class="muted"></p><h2 id="object-title" tabindex="-1">Objet</h2><p id="object-description"></p>
<div class="actions"><button type="button" id="prepare-contribution" class="primary" hidden>Préparer une contribution</button></div>
<p id="readonly-note" class="muted" hidden>Consultation seule dans ce périmètre.</p>
<section id="contribution-panel" hidden aria-labelledby="contribution-heading"><h3 id="contribution-heading">Préparer une contribution</h3>
<p>Le fichier préparé sera à transmettre à votre IDE pour dépôt dans AIR. Il sera soumis aux droits et à l’identité en vigueur au moment du dépôt.</p>
<form id="contribution-form"><label for="contribution-title">Titre</label><input id="contribution-title" required maxlength="200">
<label for="contribution-kind">Nature</label><select id="contribution-kind"><option value="QUESTION">Question</option><option value="PROPOSAL">Proposition</option><option value="CRITIQUE">Contestation</option><option value="REVIEW">Commentaire de revue</option></select>
<label for="contribution-message">Message</label><textarea id="contribution-message" required maxlength="10000"></textarea>
<div class="actions"><button type="submit" class="primary">Télécharger la contribution</button><button type="button" class="secondary" id="cancel-contribution">Annuler</button></div>
<p id="contribution-status" role="status" aria-live="polite"></p></form></section>
<h3>Contenu déclaré</h3><div id="properties"></div><div class="link-grid"><section><h3>S’appuie sur</h3><div id="outgoing"></div></section><section><h3>Utilisé par</h3><div id="incoming"></div></section></div>
<details><summary>Objet et références techniques</summary><pre id="raw-object"></pre></details>
<details><summary>Baseline exacte</summary><p>{escape(request['baseline']['id'])} · révision {request['baseline']['revision']}</p><p>{escape(request['baseline']['digest'])}</p></details>
<p class="notice">Ce fichier conserve un contexte exporté. Ses données doivent rester dans leur périmètre autorisé ; les droits ne sont pas réévalués hors ligne. Une contribution préparée ne modifie pas le registre.</p>
</main></div><footer>Les liens reflètent la baseline sélectionnée. Aucune approbation, admission ou action sur un système métier n’est exécutée depuis ce fichier.</footer>
<script id="air-data" type="application/json">{raw}</script><script>{script}</script></body></html>'''
    encoded = content.encode('utf-8')
    if len(encoded) > 4 * 1024 * 1024: raise InvalidModel('Workbench output exceeds 4 MiB')
    return {'engine': ENGINE, 'baseline': request['baseline'], 'media_type': 'text/html', 'content': content,
        'content_digest': 'sha256:' + hashlib.sha256(encoded).hexdigest(), 'objects': len(objects),
        'live_connection': False, 'credentials_embedded': False, 'register_modified': False,
        'source_mapping': [{'object': exact(o), 'selector': '[data-object-id=' + json.dumps(o['meta']['id']) + ']'} for o in objects]}
