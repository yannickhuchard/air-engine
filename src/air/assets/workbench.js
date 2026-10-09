'use strict';
(() => {
  const data = JSON.parse(document.getElementById('air-data').textContent);
  const byId = new Map(data.objects.map(o => [o.meta.id, o]));
  const q = id => document.getElementById(id);
  const prose = text => String(text).replace(/\u2014/g, '-');
  const make = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = prose(text); if (cls) n.className = cls; return n; };
  const typeName = o => o.meta.type.replace('air.', '');
  const labels = {statement:'Énoncé', question:'Question', author:'Auteur déclaré', authority:'Autorité déclarée', selection:'Choix retenu', alternatives:'Alternatives', rationale:'Justification', basis:'Fondement', consequences:'Conséquences', revisit_conditions:'Conditions de réexamen', message:'Message', target:'Cibles', resolution:'Résolution déclarée', expected:'Attendu', observed:'Observations', treatment:'Traitement documenté', comparison_method:'Méthode de comparaison', impact:'Impact déclaré', description:'Description', learning:'Apprentissages', affected_scope:'Périmètre affecté', observations:'Observations', occurrence:'Période', instance_or_scope:'Périmètre observé', metric_or_signal:'Signal', window:'Fenêtre', value_or_artifact:'Valeur ou artefact', coverage:'Couverture', source:'Source', limitations:'Limites', completeness:'Complétude', boundary_description:'Frontière du périmètre', acceptance:'Critères de réception', required_outputs:'Sorties attendues', source_refs:'Sources de provenance', used_by:'Utilisations', includes:'Périmètre inclus', excludes:'Périmètre exclu', evidence:'Preuves', kind:'Nature', outcome:'Objectif mesurable', targets:'Cibles', measures:'Indicateurs', horizon:'Horizon', desired_change:'Changement recherché', scope:'Périmètre', goals:'Objectifs', definition:'Définition', unit:'Unité', aggregation:'Agrégation déclarée', population:'Population déclarée', collection_method:'Collecte', concerns:'Préoccupations', identity_or_group:'Partie prenante', participation_role:'Rôle de participation', ability:'Capacité', outcomes:'Objectifs associés', required_functions:'Fonctions requises', context:'Contexte', maturity_evidence:'Preuves de maturité', beneficiaries:'Bénéficiaires', value_proposition:'Valeur proposée', capabilities:'Capacités', service_commitments:'Contrats de service', offer:'Offre', market_scope:'Périmètre de l’offre', services:'Services', lifecycle_owner:'Responsable du cycle de vie', operator:'Comparaison', id:'Identifiant', value:'Valeur', sponsor:'Sponsor', premises:'Prémisses', conclusion:'Conclusion déclarée', derivation:'Dérivation déclarée', statements:'Assertions en conflit', overlap_scope:'Périmètre commun', reason:'Motif déclaré', epistemic_status:'État de connaissance déclaré', review_due:'Échéance de revue'};
  let selected = null, prepared = null;
  function refButton(ref) {
    const obj = byId.get(ref.id), button = make('button', obj ? obj.meta.name : ref.id, 'reference');
    button.type = 'button';button.disabled = !obj || obj.meta.revision !== ref.revision;
    button.addEventListener('click', () => select(ref.id, true)); return button;
  }
  function valueNode(value) {
    if (value === null) return make('span', 'Non renseigné', 'muted');
    if (typeof value !== 'object') return make('span', typeof value === 'boolean' ? (value ? 'Oui' : 'Non') : String(value));
    if (!Array.isArray(value) && typeof value.id === 'string' && Number.isInteger(value.revision)) return refButton(value);
    if (Array.isArray(value)) {
      if (!value.length) return make('span', 'Aucun élément déclaré', 'muted');
      const ul = make('ul'); for (const item of value) { const li = make('li');li.append(valueNode(item));ul.append(li); } return ul;
    }
    const dl = make('dl'); for (const [key, item] of Object.entries(value)) { dl.append(make('dt', labels[key] || key));const dd = make('dd');dd.append(valueNode(item));dl.append(dd); } return dl;
  }
  function list() {
    const term = q('search').value.trim().toLocaleLowerCase('fr'), kind = q('type-filter').value;
    const found = data.objects.filter(o => (!kind || o.meta.type === kind) && (!term || (o.meta.name + ' ' + o.meta.description + ' ' + JSON.stringify(o.body)).toLocaleLowerCase('fr').includes(term)));
    q('object-list').replaceChildren();
    for (const o of found) {
      const li = make('li'), b = make('button', undefined, 'object-choice');b.type = 'button';b.dataset.objectId = o.meta.id;
      b.setAttribute('aria-current', String(selected === o.meta.id));b.append(make('span', o.meta.name), make('small', typeName(o) + ' · révision ' + o.meta.revision));
      b.addEventListener('click', () => select(o.meta.id, true));li.append(b);q('object-list').append(li);
    }
    q('result-count').textContent = found.length + ' objet' + (found.length === 1 ? '' : 's') + ' affiché' + (found.length === 1 ? '' : 's');
    q('empty-results').hidden = found.length !== 0;
  }
  function linksFor(id, incoming) {
    const ul = make('ul', undefined, 'link-list');
    const links = data.links.filter(l => incoming ? l.to.id === id : l.from.id === id);
    for (const l of links) { const li = make('li');li.append(refButton(incoming ? l.from : l.to), make('small', labels[l.field.split('/').pop()] || l.field.split('/').pop().replaceAll('_', ' ')));ul.append(li); }
    return links.length ? ul : make('p', 'Aucun lien déclaré dans cette baseline.', 'muted');
  }
  function select(id, focus) {
    const o = byId.get(id);if (!o) return;
    selected = id;prepared = null;q('contribution-form').reset();q('contribution-status').textContent = '';q('contribution-panel').hidden = true;
    q('object-title').textContent = prose(o.meta.name);q('object-description').textContent = prose(o.meta.description);
    q('object-type').textContent = typeName(o) + ' · révision ' + o.meta.revision + ' · DRAFT';
    const priorities = {'air.Decision':['question','selection','rationale','alternatives','basis','consequences','revisit_conditions','authority'], 'air.Conflict':['reason','statements','overlap_scope','resolution'], 'air.Inference':['conclusion','premises','derivation','limitations']};
    const priority = priorities[o.meta.type] || Object.keys(o.body);
    const body = Object.fromEntries([...new Set([...priority,...Object.keys(o.body)])].filter(k => k in o.body).map(k => [k,o.body[k]]));
    q('properties').replaceChildren(valueNode(body));
    const note = {'air.Conflict':'Conflit déclaré. Une décision documentée ne prouve pas sa résolution.', 'air.Inference':'Prémisses et conclusion déclarées ; cette vue n’exécute pas la dérivation.'}[o.meta.type];
    if (note) q('properties').prepend(make('p',note,'muted'));
    q('outgoing').replaceChildren(linksFor(id, false));q('incoming').replaceChildren(linksFor(id, true));
    q('raw-object').textContent = JSON.stringify(o, null, 2);q('prepare-contribution').hidden = !data.writable_namespaces.includes(o.meta.namespace);
    q('readonly-note').hidden = data.writable_namespaces.includes(o.meta.namespace);list();
    if (focus) q('object-title').focus();
  }
  for (const type of [...new Set(data.objects.map(o => o.meta.type))].sort()) { const option = make('option', type.replace('air.', ''));option.value = type;q('type-filter').append(option); }
  q('search').addEventListener('input', list);q('type-filter').addEventListener('change', list);
  q('prepare-contribution').addEventListener('click', () => { q('contribution-panel').hidden = false;q('contribution-title').focus(); });
  q('cancel-contribution').addEventListener('click', () => { q('contribution-panel').hidden = true;q('prepare-contribution').focus(); });
  q('contribution-form').addEventListener('input', () => { prepared = null;q('contribution-status').textContent = ''; });
  q('contribution-form').addEventListener('submit', event => {
    event.preventDefault();const o = byId.get(selected), title = q('contribution-title').value.trim(), message = q('contribution-message').value.trim();
    if (!o || !data.writable_namespaces.includes(o.meta.namespace) || !title || !message) { q('contribution-status').textContent = 'Renseignez un titre et un message.';return; }
    if (!prepared) {
      const unique = crypto.randomUUID(), now = new Date().toISOString();
      prepared = {idempotency_key:'workbench-' + unique, object:{meta:{id:'urn:air:contribution:' + unique, type:'air.Contribution', revision:1, name:title,
        description:message, namespace:o.meta.namespace, owner:data.identity, classification:{level:'INTERNAL'}, lifecycle:'DRAFT', recorded_at:now,
        validity:{start:now,end:null}, provenance:{recorded_by:data.identity,method:'Prepared offline with AIR Workbench',source_refs:o.meta.provenance.source_refs}},
        body:{author:data.identity,target:[{id:o.meta.id,revision:o.meta.revision}],kind:q('contribution-kind').value,message}}};
    }
    const blob = new Blob([JSON.stringify(prepared, null, 2) + '\n'], {type:'application/json'}), url = URL.createObjectURL(blob), a = make('a');
    a.href = url;a.download = 'air-contribution.json';document.body.append(a);a.click();a.remove();setTimeout(() => URL.revokeObjectURL(url), 60000);
    q('contribution-status').textContent = 'Fichier préparé. Transmettez-le à votre IDE pour dépôt dans AIR. Aucun enregistrement effectué ici.';
  });
  q('js-status').textContent = 'Consultation hors ligne prête';
  if (data.objects.length) select(data.objects[0].meta.id, false); else list();
})();
