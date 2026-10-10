"""Deterministic reading routes; declared objects are never inferred approvals."""
from air.core import digest
from air.expr import artifact_digest

ENGINE = 'air.site-questions/1'
ROLES = [
    ('comex', 'COMEX', 'Arbitrer la valeur, les risques et la préparation', ['23', '02', '25', '16', '17', '27', '28']),
    ('metier', 'Managers métier', 'Comprendre les résultats et les changements de travail', ['23', '03', '04', '14', '05', '32']),
    ('dsi', 'DSI', 'Examiner les engagements, les moyens et l’exploitation', ['08', '07', '21', '22', '26', '35', '17', '37', '28']),
    ('entreprise', 'Architecture entreprise', 'Relier capacités, principes et trajectoires', ['14', '18', '24', '15', '25', '34', '37']),
    ('solution', 'Architecture solution', 'Vérifier les mécanismes, les données et les preuves', ['01', '09', '10', '11', '19', '20', '29', '30', '12', '13', '28']),
    ('realisation', 'Équipes de réalisation', 'Préparer les responsabilités et les critères de livraison', ['06', '08', '13', '26', '27', '31', '32', '33', '35', '36']),
]
GATE_LABELS = {'NOT_READY': 'Préparation à la construction incomplète',
               'READY_TO_BUILD': 'Critères de préparation satisfaits dans leur portée',
               'INCONCLUSIVE': 'Préparation non déterminée'}
DIMENSIONS = {
    '06': [('air.RaciAssignment', 'Responsabilités RACI de réalisation'), ('air.OrganizationUnit', 'Organisation de réalisation')],
    '07': [('air.RaciAssignment', 'Responsabilités RACI d’exploitation'), ('air.OrganizationUnit', 'Organisation d’exploitation')],
    '03': [('air.CustomerJourney', 'Parcours par persona'), ('air.JourneyCatalog', 'Inventaire des personas et périmètre'), ('air.Touchpoint', 'Points de contact typés'), ('air.UsagePoint', 'Usages numériques, physiques et géographiques')],
    '17': [('air.CostItem', 'Postes de coûts CAPEX et OPEX'), ('air.FinancialPlan', 'Enveloppe, horizon et statut de financement')],
    '27': [('air.Milestone', 'Jalons de réalisation')],
    '35': [('air.QualityRequirement', 'Exigences de qualité et leurs cibles')],
    '36': [('air.DeliveryEstimate', 'Estimations de l’effort de réalisation')],
}
STATEMENT_FIELDS = {
    'air.Intent': [('desired_change', 'Changement souhaité')],
    'air.Goal': [('outcome', 'Résultat attendu')],
    'air.ValueStream': [('value', 'Valeur attendue')],
    'air.CustomerJourney': [('goal', 'Objectif du parcours')],
    'air.Decision': [('rationale', 'Raison du choix')],
    'air.Risk': [('scenario', 'Scénario de risque')],
    'air.Assumption': [('statement', 'Hypothèse'), ('impact_if_false', 'Conséquence si elle est fausse')],
    'air.Unknown': [('question', 'Question ouverte')],
    'air.ArchitectureGap': [('impact', 'Impact du manque')],
    'air.Concept': [('definition', 'Définition')],
    'air.QualityRequirement': [('statement', 'Exigence de qualité')],
    'air.ArchitecturePrinciple': [('rationale', 'Raison du principe')],
}


def project(export, gate, topics, questions):
    from air.deliverables import _criterion_row
    meta = export['baseline']['meta']
    pin = {'id': meta['id'], 'revision': meta['revision'], 'digest': export['digest']}
    projected = []
    for topic in topics:
        used = {(o['meta']['id'], o['meta']['revision']): o for o in topic['used']}
        entries = [{'reference': {'id': o['meta']['id'], 'revision': o['meta']['revision'], 'digest': digest(o)},
                    'name': o['meta']['name'], 'type': o['meta']['type'],
                    'description': o['meta']['description'], 'lifecycle': o['meta']['lifecycle'],
                    **({'declared_state': o['body']['state'], 'resolution_owner': o['body']['resolution_owner']}
                       if o['meta']['type'] == 'air.Unknown' else {}),
                    'statements': [{'label': label, 'field': field, 'text': o['body'][field]}
                        for field, label in STATEMENT_FIELDS.get(o['meta']['type'], [])
                        if isinstance(o['body'].get(field), str)]}
                   for _, o in sorted(used.items())]
        number = topic['name'][:2]
        missing = [label for kind, label in DIMENSIONS.get(number, [])
                   if not any(o['meta']['type'] == kind and
                              (number not in ('06', '07') or kind != 'air.RaciAssignment' or
                               o['body']['phase'] == ('DELIVERY' if number == '06' else 'OPERATIONS'))
                              for o in used.values())]
        projected.append({'id': number, 'question': questions[number][0],
                          'purpose': questions[number][1], 'topic': topic['name'] + '.html',
                          'state': 'CALCULATED' if number in ('15', '28') else 'PARTIAL' if entries and missing else 'SOURCES_PRESENT' if entries else 'NOT_DOCUMENTED',
                          'missing_dimensions': missing,
                          'sources': entries, 'complete_or_approved': False})
    result = {'engine': ENGINE, 'baseline': pin, 'gate': {'code': gate['result'],
              'label': GATE_LABELS.get(gate['result'], gate['result'])},
              'roles': [{'id': r, 'label': label, 'purpose': purpose, 'questions': ids}
                        for r, label, purpose, ids in ROLES],
              'questions': projected, 'audience_is_access_control': False,
              'design_tasks': [{'reference': {'id': o['meta']['id'], 'revision': o['meta']['revision'], 'digest': digest(o)},
                  'name': o['meta']['name'], 'status': o['body']['status'], 'owner': o['body']['owner'],
                  'purpose': o['body']['purpose'], 'deliverables': o['body']['deliverables']}
                  for o in sorted(export['objects'], key=lambda o: (o['meta']['id'], o['meta']['revision']))
                  if o['meta']['type'] == 'air.ArchitectureTask' and o['meta']['namespace'] == meta['namespace']],
              'calculated_criteria': [{'code': c['code'], 'status': c['status'],
                  'label': _criterion_row(c)[0], 'detail': _criterion_row(c)[2],
                  'next_action': _criterion_row(c)[3]} for c in gate['criteria']],
              'source_scope': 'TOPIC_SOURCE_OBJECTS_NOT_SEMANTIC_COMPLETENESS'}
    return {**result, 'projection_digest': artifact_digest(result)}
