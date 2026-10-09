# P03 - Qualification explicite des preuves de conception

Contrat `air.design-proof/0.34`, reçu dans le périmètre de conception P03a, non publié. Aucun nouveau type métier, table
SQL ou service obligatoire. Les reçus de revue existants portent une extension optionnelle.

Réception du 25 septembre 2026 (document historique ou livrable local non inclus) : 644 tests SQLite,
87 tests ciblés PostgreSQL 18.6, trois parcours Asteria PASS_SCOPED. Ce résultat historique couvre P03a.
L'[extension des attestations externes](lot-preuves-externes.md) complète désormais le parcours TEST ;
les résultats de réception courants sont dans l'[état d'implémentation](etat-implementation.md).

Une revue acceptée de la baseline peut contenir `proof_assessments` (au plus seize éléments), chacun avec
`run` (id, révision et digest exacts), `scope` et `rationale`. Le relecteur doit être indépendant de tous
les auteurs de la baseline et de ses membres, disposer du mandat `review` et lire tout le contexte.
Cette action reste `air review` / `POST /v1/reviews` ; elle n'est pas ajoutée au catalogue d'outils agentiques.
CLI/API créent le même reçu ; MCP lit son effet dans `air_assess_readiness`.

| Méthode du cas | Portée | Conditions et effet |
| --- | --- | --- |
| ANALYSIS, INSPECTION, REVIEW | DESIGN_ONLY | Rapport exact stocké, cas et exécution PASS épinglés, références de preuve dans la baseline ; avis indépendant enregistré comme QUALIFIED_DESIGN_REVIEW |
| SIMULATION | MODEL_ONLY | Rapport JSON exact, reproduit par le moteur supporté sur les entrées historiques inchangées ; qualification numérique CALIBRATED et avis indépendant donnent QUALIFIED_MODEL_REPLAY |
| SIMULATION déclarée | MODEL_ONLY | Rejeu enregistré comme REPLAYED_DECLARED_MODEL ; ne ferme pas VERIFICATION |
| TEST | EXECUTED_TEST | Rapport importé par l'adaptateur externe signé, challenge exact et mandat effectif, puis revue indépendante ; VERIFIED_EXTERNAL_TEST |

Les deux statuts QUALIFIED ferment les cas de **conception** concernés. Ils ne sont pas un statut VERIFIED
de comportement réel : ils n'incrémentent pas `verified_cases`, `qualified_design_cases` les compte séparément,
et leur `runtime_execution_attested` reste faux. Seuls les TEST externes signés et qualifiés sont comptés
comme exécutés ; les autres restent planifiés pour la construction.

Le reçu fixe les digests de baseline, cas, oracle/acceptation/entrées, exécution, rapport, preuves et éventuel
environnement. Le serveur enregistre l'identité du relecteur et celle du déposant du rapport. Pour les avis
de conception, `executor` reste déclaratif. Pour TEST, seul le contrat externe vérifie que ce champ
correspond à la clé mandatée et au challenge signé.
Le rapport est lu avec contrôle d'accès et contrôle des octets, dans une limite de 512 Kio.

À chaque lecture effective : politique, mandat, expiration, révocation, disponibilité et intégrité du rapport
sont réévalués. Un moteur de simulation incompatible ou un résultat modifié invalide la qualification.
Un changement de baseline exige une nouvelle revue. Un rejet effectif oppose un veto. Des revues effectives
choisissant des exécutions différentes du même cas donnent CONFLICTING_QUALIFICATIONS ; aucun horodatage
fourni par un client ne tranche le conflit ni ne supplante un choix qualifié.

La calibration reste un accord numérique. Sa provenance, sa fraîcheur et sa représentativité ne sont pas
automatiquement qualifiées ; le relecteur doit examiner ces limites. Une opinion humaine ne devient jamais
un test exécuté. L'adaptateur externe unittest est décrit dans son [contrat](lot-preuves-externes.md).
Les autres adaptateurs, la fédération de confiance et la représentativité statistique des mesures restent
hors de ce binding de conception ; ils ne sont pas implicitement qualifiés.

Les anciens reçus sans `proof_assessments` continuent d'avoir leur rôle de revue ; ils ne qualifient aucun
cas automatiquement. Les révisions et reçus restent immuables, idempotents et transférables avec le registre.

## Préparer une revue de conception

1. Épingler le cas `VerificationCase` et préparer ce rapport JSON (remplacer l'identifiant et le digest par
   ceux calculés sur la révision réelle). Le rapport décrit l'avis ; il ne fait aucune action externe.
2. Le stocker avec `air artifact-upload` ou `/v1/artifacts/import`, en `application/json`. Copier la référence
   exacte retournée dans `VerificationRun.body.report`, puis conserver le cas et le run dans une nouvelle
   baseline `air.delivery/0.32` fermée, avec les références de preuve et l'éventuel environnement.
3. Le relecteur indépendant utilise sa propre identité pour `air review`, avec la même épingle de baseline
   dans `baseline` et `target`, `outcome: ACCEPTED`, les preuves de la baseline, une expiration et
   `proof_assessments: [{"run": {…}, "scope": "DESIGN_ONLY", "rationale": "…"}]`.
   `air readiness` et `air_assess_readiness` exposent ensuite la portée et les reçus effectifs.

```json
{
  "format": "air.design-proof/0.34",
  "case": {"id": "urn:entreprise:case:inspection", "revision": 1, "digest": "sha256:<empreinte exacte>"},
  "method": "INSPECTION",
  "scope": "DESIGN_ONLY",
  "result": "PASS",
  "summary": "Constats de la revue et limites de cet avis de conception.",
  "runtime_execution_attested": false
}
```

Pour SIMULATION, employer le rapport exact produit par `air scenario-record`, conserver ses entrées et
ajouter le run à une nouvelle baseline. L'évaluation explicite porte `scope: MODEL_ONLY`. Le serveur rejoue
le calcul ; une simulation sur modèle seulement déclaré reste non qualifiante, même après avis favorable.
Une ancienne baseline de simulation doit rester accessible pour ce rejeu.

Recette entièrement automatisée, avec entreprise et identités fictives :

```sh
.venv/Scripts/python.exe scripts/demo_metier.py --output tmp/demo-p03 --qualify-design-proofs
```

Elle ajoute un cas d'inspection de conception à chacun des trois dossiers. Elle contrôle revue indépendante,
idempotence, révocation, nouvelle revue, même digest CLI/HTTP/MCP, citation du reçu dans les livrables et
restauration. La recette courante contrôle la perte d'effectivité sous la politique réellement restaurée,
qui a changé ; elle ne réutilise plus la politique historique du banc de test. Les neuf cas métier d'origine
ne sont ni remplacés ni déclarés exécutés.
