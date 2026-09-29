---
name: air-architecte
description: "Mener une architecture de solution AIR jusqu'au prêt-à-construire, avec un agent : scénarios d'acceptation rejoués sur la conception, socle de non-régression, contrôles et exigences non fonctionnelles reçus en entrée et reliés aux blocs, estimation avec et sans IA agentique, feuilles de route alternatives. Utiliser pour compléter, vérifier ou livrer un dossier de solution, ou pour préparer son passage au comité."
license: Apache-2.0
compatibility: "Fonctionne avec tout agent qui lit les Agent Skills (Claude Code, Claude, ChatGPT, Codex, Cursor, Antigravity, OpenCode, Gemini CLI). Requiert le serveur MCP AIR (outils air_*) ou la CLI `air`."
metadata:
  engine: air 0.33
---

# Architecture de solution prête à construire

Un dossier de solution est prêt à construire quand AIR le dit (`air_assess_readiness` → `READY_TO_BUILD`), pas
avant. Ce skill dit quoi modéliser pour y arriver et comment le vérifier. Le parcours d'écriture reste celui
d'AIR : valider à blanc, préparer, montrer, puis déposer et figer après accord explicite de l'architecte.

## 1. Orienter

1. `air_guide` avec la baseline du projet : état, verdict `readiness`, écarts ouverts, prochaine action.
2. `air_assess_readiness` : chaque critère `NOT_MET` dit ce qui le ferme et s'il revient à un humain.

## 2. Compléter le dossier de réalisation

Les formes exactes sont dans [les modèles](references/modelling.md) ; `air_describe_type` donne le schéma à jour.

| Besoin | Type AIR | Vérifié par |
|---|---|---|
| Parcours testables dès la conception | `AcceptanceScenario` (suites ACCEPTANCE, REGRESSION, SMOKE) sur une `NavigationMap` | `air_walk_scenarios` |
| Exigences non fonctionnelles | `QualityRequirement` (catégorie, cible chiffrée, méthode de vérification) | critère COMPLIANCE |
| Contrôles de conformité | `Control` (souvent reçu du noyau partagé) | critère COMPLIANCE |
| Qui implémente quoi | `ComplianceMapping` : sujet → blocs, unités, composants ; ou NOT_APPLICABLE avec une `Decision` | critère COMPLIANCE |
| Coût de l'outillage agentique | `AgenticToolPlan` (prix par poste et par mois, politique de données) | calculs d'estimation |
| Effort avec et sans IA | `DeliveryEstimate` par unité de construction, par activité | `AIR_ESTIMATE_AI` |
| Chemins de réalisation | 2 à 3 `Roadmap` (ex. séquentielle sans IA, MVP avec IA, parallèle avec IA), une RECOMMENDED puis SELECTED par `Decision` | `AIR_ROADMAP_*` |

Règles de modélisation :

- **Contrôles et ENF sont des entrées.** Ceux d'un noyau partagé (baseline sans bloc ni exigence) s'appliquent à
  chaque projet qui l'emprunte, même s'il ne les cite pas : la porte exige un `ComplianceMapping` possédé par le
  projet pour chacun.
- **Un scénario par objectif de persona**, pas par écran. Les étapes suivent des transitions existantes
  (`via` si plusieurs), les opérations sont offertes par l'écran, le `context` fixe les entrées des gardes.
  Un scénario `REGRESSION` fait partie du socle de non-régression. Lier `design_case` (ANALYSIS, joué par la
  marche) et `acceptance_case` (TEST, joué après la construction).
- **Estimation honnête.** `ai_effort_pd` seulement là où l'IA s'applique (code, tests, documentation, analyse) ;
  la revue humaine et les décisions restent entières. `basis` et `confidence` sont obligatoires ; le prix de
  l'abonnement est une hypothèse datée.
- **Feuilles de route comparables** : mêmes unités, mêmes jalons, un taux journalier déclaré ; les phases
  dépendantes ne se chevauchent pas. Une phase qui attend un autre projet le déclare (`external_depends_on`) : le
  chemin critique du programme traverse alors les projets.
- **Responsabilité nommée.** Une exigence portée seulement par l'infrastructure (composants, équipements, zones) nomme
  son rôle responsable (`accountable`) ; un contrôle emprunté par transitivité reste l'obligation de son propriétaire.

## 3. Vérifier avant de montrer

1. `air_validate_drafts` sur les brouillons ; corriger chaque diagnostic.
2. `air_rebase_drafts` pour préparer le changement ; `air_assess_readiness` avec `{"prepared_change": ...}` pour
   juger la baseline candidate sans rien déposer.
3. `air_walk_scenarios` sur la baseline : chaque scénario `PASS`, aucun écran ou transition non couvert sans
   raison, aucune impasse. Un `FAIL` est un défaut de conception : corriger la navigation ou le scénario.
4. Montrer à l'architecte le diff, les verdicts, les écarts restants. Déposer et figer seulement après son accord.

## 4. Livrer

- `air_compile_deliverables` (`DIGESTS`, puis `only`) : notamment 32 scénarios, 33 non-régression,
  34 matrice de conformité, 35 ENF, 36 estimation IA, 37 feuilles de route.
- `air_compile_presentation` : le plan du deck de direction ; le HTML bilingue se produit à la CLI. Pour le
  construire et le critiquer, suivre le skill `air-presentation`.

## Ce que l'agent ne fait jamais

- Déclarer une conformité, une revue humaine ou une mesure qui n'existe pas dans AIR.
- Transformer `NOT_MET`, `UNMAPPED`, `INCONCLUSIVE` ou `NOT_EXECUTED` en résultat.
- Admettre, activer, renouveler, clore ou signer : ce sont des actes humains authentifiés.
- Lire, afficher ou recopier un jeton.
