"""Four project participation states, all names and staffing needs are fictional."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('stakeholder_reference', Path(__file__).resolve().parents[1] / 'build_design/model.py')
model = importlib.util.module_from_spec(spec); spec.loader.exec_module(model)


def additions():
    obj, ref = model.obj, model.ref
    roles = [obj('Role', name, {'responsibilities': [responsibility], 'required_competencies': []}) for name, responsibility in [
        ('architecture-lead', 'Concevoir la solution et expliciter ses décisions'),
        ('security-reviewer', 'Challenger les risques et les contrôles'),
        ('operations-lead', 'Préparer la reprise et les conditions de support'),
        ('accessibility-expert', 'Examiner les usages et les barrières d’accès')]]
    for role, name in zip(roles, ['Architecte solution', 'Référente sécurité', 'Responsable exploitation', 'Expertise accessibilité']): role['meta']['name'] = name
    concern = obj('Concern', 'delivery-concern', {'scope': ref('scope'), 'question': 'Qui garantit la clarté du dossier et la préparation de sa réalisation ?', 'addressed_by': []})
    people = [obj('Stakeholder', name, {'identity_or_group': 'urn:fictional:person:' + name,
        'concerns': [ref('delivery-concern')], 'participation_role': role}) for name, role in [('camille', 'Architecture solution'), ('samira', 'Sécurité')]]
    people[0]['meta']['name'] = 'Camille Martin, exemple fictif'; people[1]['meta']['name'] = 'Samira Benali, exemple fictif'
    records = []
    for name, role, person, state, action, reason, responsibility, plan in [
        ('design', 'architecture-lead', 'camille', 'INVOLVED', 'NONE', 'Relier les besoins de devis aux contrats et aux décisions.', 'Maintenir le dossier et préparer les arbitrages d’architecture.', 'Participer aux ateliers de conception et aux revues de décisions.'),
        ('security', 'security-reviewer', 'samira', 'TO_INVOLVE', 'NONE', 'Examiner les contrôles avant de baseliner les contrats.', 'Conduire la revue des menaces et documenter les réserves.', 'Planifier un atelier de sécurité avec la responsable identifiée.'),
        ('operations', 'operations-lead', None, 'MISSING', 'RECRUIT', 'Le projet ne dispose pas encore du rôle nécessaire pour préparer le support.', 'Définir les scénarios de reprise et les responsabilités d’exploitation.', 'Valider la fiche de poste et le budget de recrutement avant la phase de réalisation.')]:
        body = {'scope': ref('scope'), 'role': ref(role), 'state': state, 'reason': reason,
            'responsibilities': [responsibility], 'architecture_links': [ref('quote-contract'), ref('control')],
            'engagement_plan': plan, 'coordination_owner': 'urn:fictional:person:camille', 'staffing_action': action, 'needed_by': '2026-11-16'}
        if person: body['stakeholder'] = ref(person)
        records.append(obj('StakeholderParticipation', 'participation-' + name, body))
    raci = obj('RaciAssignment', 'architecture-accountable', {'activity': 'Décisions de conception', 'phase': 'DELIVERY', 'role': ref('architecture-lead'), 'responsibility': 'A'})
    return roles + [concern] + people + records + [raci]
