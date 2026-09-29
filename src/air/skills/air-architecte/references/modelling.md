# Modèles de corps d'objets (profil air.delivery/0.32)

Les références sont exactes : `{"id": "<urn>", "revision": <n>}`. Les montants et efforts sont des chaînes
décimales. `air_describe_type` fait foi si ce document diverge.

## AcceptanceScenario

```json
{"navigation": {"id": "urn:…:navigation:member-app", "revision": 1},
 "persona": {"id": "urn:…:actor:member", "revision": 1},
 "journey": {"id": "urn:…:journey:submit-claim", "revision": 1},
 "goal": "Envoyer une demande de remboursement",
 "suites": ["ACCEPTANCE", "REGRESSION"], "priority": "CRITICAL",
 "context": {"amount": {"type": "Integer", "value": 120}},
 "preconditions": ["L'adhérent est authentifié"],
 "steps": [
   {"id": "s1", "screen": "home", "action": "Ouvrir l'application", "expected": "Accueil affiché"},
   {"id": "s2", "screen": "claim-form", "via": "new-claim", "action": "Saisir et envoyer",
    "operation": {"contract": {"id": "urn:…:contract:claims", "revision": 2}, "name": "SubmitClaim"},
    "expected": "Demande acceptée, numéro affiché"}],
 "design_case": {"id": "urn:…:case:walk-submit", "revision": 1},
 "acceptance_case": {"id": "urn:…:case:uat-submit", "revision": 1}}
```

## QualityRequirement

```json
{"category": "PERFORMANCE", "statement": "Accusé de réception d'une demande en moins de 2 s au 95e centile",
 "priority": "MUST", "target": {"operator": "LTE", "value": {"type": "Integer", "value": 2000}, "unit": "ms"},
 "source": "Charte de service", "verification_method": "SIMULATION"}
```

Catégories : PERFORMANCE, AVAILABILITY, RECOVERABILITY, SCALABILITY, SECURITY, PRIVACY, ACCESSIBILITY, USABILITY,
OPERABILITY, MAINTAINABILITY, PORTABILITY, COMPLIANCE, SUSTAINABILITY.

## ComplianceMapping

```json
{"subject": {"id": "urn:…:control:encryption-at-rest", "revision": 1}, "status": "PLANNED",
 "implemented_by": [{"id": "urn:…:unit:claims-service", "revision": 1}, {"id": "urn:…:runtime:claims-db", "revision": 1}],
 "mechanism": "Chiffrement AES-256 géré par le KMS ; clés tournées tous les 90 jours",
 "verification": [{"id": "urn:…:case:kms-inspection", "revision": 1}]}
```

`NOT_APPLICABLE` exige `decision` et nomme le projet qui implémente (`delegated_to`, par exemple `"health.fraud"`) ;
tout autre statut exige `implemented_by`. Quand les implémenteurs ne sont que des composants, équipements, connexions ou
zones (portée technique), nommer le rôle responsable : `"accountable": {"id": "urn:…:role:security-officer", "revision": 1}`.

## AgenticToolPlan

```json
{"vendor": "<éditeur>", "product": "<IDE agentique>", "plan": "Team", "price": {"value": "40", "currency": "EUR"},
 "per": "SEAT_MONTH", "data_policy": "Pas d'entraînement sur le code client ; hébergement UE", "status": "TRIAL"}
```

## DeliveryEstimate

```json
{"unit": {"id": "urn:…:unit:claims-service", "revision": 1}, "plan": {"id": "urn:…:agentic-plan:ide", "revision": 1},
 "team": {"workers": 4, "ai_seats": 4, "days_per_month": 20}, "confidence": "MEDIUM", "basis": "Services comparables 2025–2026",
 "activities": [
   {"activity": "CODE", "effort_pd": "80", "ai_applicable": true, "ai_effort_pd": "45", "rationale": "Adaptateurs et mappings générés, relus"},
   {"activity": "UNIT_TEST", "effort_pd": "30", "ai_applicable": true, "ai_effort_pd": "15", "rationale": "Tests générés à partir des contrats"},
   {"activity": "REVIEW", "effort_pd": "15", "ai_applicable": false, "rationale": "La revue humaine reste entière"}]}
```

Activités : ANALYSIS, DESIGN, CODE, UNIT_TEST, INTEGRATION_TEST, ACCEPTANCE_TEST, DOCUMENTATION, REVIEW, DEPLOYMENT,
DATA_MIGRATION, INFRASTRUCTURE, SECURITY_HARDENING. AIR calcule le delta, la durée et le coût d'abonnement
(prix × postes × mois avec IA).

## Roadmap

```json
{"strategy": "MVP d'abord avec IA agentique, puis extension", "uses_ai": true,
 "plan": {"id": "urn:…:agentic-plan:ide", "revision": 1}, "day_rate": {"value": "750", "currency": "EUR"},
 "phases": [
   {"id": "mvp", "name": "MVP", "objective": "Remboursement de bout en bout", "start": "2027-01-04", "end": "2027-04-30",
    "units": [{"id": "urn:…:unit:claims-service", "revision": 1}], "team_size": 5, "exit_criteria": ["Suite ACCEPTANCE verte"]},
   {"id": "scale", "name": "Extension", "objective": "Fraude temps réel", "start": "2027-05-03", "end": "2027-08-31",
    "depends_on": ["mvp"], "team_size": 6}],
 "status": "RECOMMENDED", "rationale": "Valeur en 4 mois ; abonnements amortis par 30 % d'effort en moins"}
```

Une phase qui attend une phase d'un autre projet le déclare, avec le type de lien (`FINISH_TO_START` par défaut,
`START_TO_START`, `FINISH_TO_FINISH`) ; AIR refuse des dates incompatibles et signale une dépendance vers une feuille de
route que l'autre projet n'a pas retenue :

```json
"external_depends_on": [{"roadmap": {"id": "urn:…:platform:roadmap:claims-first-ai", "revision": 1}, "phase": "claims-mvp"}]
```

AIR calcule le calendrier, le chemin critique, l'effort (avec ou sans IA selon `uses_ai`), la main-d'œuvre et les
abonnements. Une seule feuille de route passe `SELECTED`, par une `Decision`.
