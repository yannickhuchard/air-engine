# Livrer par périmètre et travailler sans référentiel obligatoire

Incrément du 19 octobre 2026, moteur source `0.35.0.dev6`, plugin source `0.1.13`.
Ces versions candidates ne sont pas une publication ou une recette ChatGPT native.

## Ce qui a été vérifié avant de compléter AIR

L'erreur 429 ne démontrait pas une absence de fonctionnalités. Le code possédait
déjà le suivi typé de transformation, les revues authentifiées et révocables,
les artefacts retenus, les résultats de vérification, la matrice de réalisation,
le Sankey, les exports de registre et les dossiers statiques. Cet incrément les
complète par des projections ciblées, trois types et une enveloppe de session.

| Demande | Fondations réutilisées | Complément livré |
| --- | --- | --- |
| Gates par périmètre | Baselines exactes, revues et readiness | ScopeGate, membres explicites, prérequis récursifs, revue propre à chaque gate |
| Dashboard | ArchitectureProject et ArchitectureTask | Équipe, membres, calendrier, blocages et filtres CLI/MCP/site |
| Couverture | Exigences, règles, données, contrats, tests, résultats | TraceabilityLink, six couches ordonnées et témoins exacts |
| Preuves opérationnelles | Import d'artefacts et VerificationRun | OperationalEvidence pour CI/CD, reprise, RTO/RPO et astreinte |
| Export de suivi | Objets versionnés et projections | CSV sécurisé et Excel OOXML déterministe, sans dépendance supplémentaire |
| ChatGPT sans MCP | Plugin de skills et exports locaux | Session éditable par fichiers, artefacts retenus, reprise et conflits explicites |

Le chapitre 12 du dossier My Help / My Health n'a pas été retrouvé dans les
fichiers accessibles lors de ce travail. La recette livrée est fictive et ne
constitue pas l'audit ou la validation de ce dossier réel.

## Des critères indépendants avec un socle commun

Déclarer un `air.ScopeGate` par périmètre avec :

- `scope`, `purpose`, `members` et `requirements` exacts ; les exigences sont membres ;
- `depends_on` vers les autres ScopeGate dont les critères sont prérequis ;
- `verification_policy: DESIGN_CONTRACTS` pour documenter la chaîne jusqu'aux tests ;
  `RECORDED_TESTS` exige aussi chaque branche de preuve, un résultat PASS enregistré
  et les octets du rapport retenu accessibles et conformes à leur empreinte ;
- `review_required` pour demander une revue indépendante de ce gate exact.

Exemple d'organisation : My Help dépend de Socle commun ; My Health dépend de
Socle commun ; aucun des deux ne dépend implicitement de l'autre. Ces noms ne
sont pas réservés et ne constituent pas un profil sectoriel imposé par AIR.

`air_assess_scope_gates` calcule les prérequis avant chaque gate. Un prérequis
bloqué bloque ses dépendants. Les cycles sont interdits. Une revue du socle ne
remplace pas une revue My Help. Une acceptation globale n'est pas réinterprétée
comme une acceptation ciblée. Une revue porte sur baseline + gate + preuves exacts,
avec contrôle de l'auteur de toute la fermeture de dépendances du périmètre.
Révocation, expiration, rejet effectif et changement de politique restent pris en compte.

`PASS_SCOPED_GATE` signifie que ces critères explicites sont satisfaits. Ce n'est
ni une autorisation de lancement ni une qualification automatique des rapports.
Lorsqu'un dossier déclare des ScopeGate, `air_assess_readiness` ajoute le critère
`SCOPED_GATES` et conserve ses autres contrôles. Les anciens dossiers sans ces
objets gardent leurs critères historiques. Un design ne doit pas exiger des
tests de l'application future déjà exécutés : choisir sa politique en conséquence.

## Lire le travail et les ruptures de traçabilité

Les champs optionnels d'ArchitectureTask sont `team` (URI d'équipe), `members`
(acteurs, parties prenantes ou rôles exacts), `start`, `due`, `blockers` et
`blocker_reason`. L'ancien `owner` reste le responsable déclaré.

`air_delivery_dashboard` prend `baselines`, une date `as_of`, puis éventuellement
`team`, `member`, `week` au format ISO `2026-W42`, `late`, `blocked`, `offset` et
`limit`. Une semaine sélectionne les intervalles start/due qui la recouvrent.
Sans date, la tâche n'est pas supposée appartenir à une semaine. Une dépendance
absente, non terminée ou annulée reste un prérequis non satisfait. DONE et
CANCELLED ne sont pas en retard ; une annulation n'est pas un achèvement.
Les totaux filtrés précèdent la pagination. Ils suivent le design déclaré,
pas l'avancement réel d'une construction. Plusieurs baselines sélectionnées
conservent chaque révision exacte de tâche, sans fusion implicite.

Le site ajoute `delivery-dashboard.html`, ses projections JSON et `checklist.csv`.
La page d'accueil et la navigation y conduisent. Les filtres fonctionnent sans
réseau. La date initiale vient de la baseline pour une génération reproductible ;
le lecteur peut changer la date de suivi. Au-delà de 1000 tâches, la page signale
sa limite et la pagination API/CLI/MCP permet de poursuivre.

Un `air.TraceabilityLink` exprime `source`, `target` et `rationale` entre couches
adjacentes, dans cet ordre :

1. Requirement ou QualityRequirement ;
2. BusinessRule, Constraint, Policy ou Control ;
3. DataEntity, DataSchema ou PhysicalTable ;
4. SemanticContract ou InterfaceSpecification ;
5. VerificationCase ;
6. VerificationRun ou OperationalEvidence.

`air_traceability_coverage` retourne les chaînes, les liens exacts et les ruptures
par branche. La preuve finale doit citer le test du chemin. Un résultat PASS ne
masque pas une branche manquante ou un échec. La correction sémantique n'est pas
déduite de la présence d'une relation. Le Sankey existant vers les blocs livrés et
les produits/services reste complémentaire. Les liens des anciens dossiers ne
sont pas inventés automatiquement pour améliorer un score.

## Attacher les preuves et exporter

Importer les octets JSON par `air_import_artifact`, puis préparer et valider
`air.OperationalEvidence` avec `case`, `kind`, `result`, `executed_at`, `executor`,
`environment`, `report`, `summary` et `metrics` :

- `CI_CD` exige aussi `run_url` et `source_revision` ;
- `RECOVERY_TEST` porte le rapport de l'essai de reprise ;
- `RTO_RPO` exige les deux mesures et leurs objectifs en secondes ;
- `ON_CALL_EXERCISE` porte le rapport d'exercice et peut déclarer le délai d'acquittement.

Un PASS dont une mesure dépasse l'objectif est refusé. Le moteur ne lance pas
une CI, un test de reprise ou une astreinte. Les rapports sont des déclarations
retenues ; leur indépendance et leur qualité ne sont pas inférées de leur import.
Les mécanismes existants de qualification des VerificationRun restent distincts.

`air_export_checklist` ou `air checklist-export requete.json --output suivi.xlsx`
prend `baseline`, `as_of` et `format: XLSX` ou `CSV`. Le fichier contient les
gates, ruptures, tâches et objets avec leurs identifiants, révisions et empreintes.
Les cellules CSV neutralisent les préfixes de formule ; XLSX utilise des chaînes
explicites, sans macros, formules ou liens externes. Le classeur conserve en-tête
figé, filtres, largeur des colonnes et retours à la ligne. SQLite/Python suffisent.

## Une conversation normale peut rester le lieu de travail

Le référentiel AIR est préféré par défaut (`enabled: true`) et optionnel
(`required: false`). Aucune adresse centrale ni identité n'est imposée. Cette
préférence ne crée pas une connexion ou un hébergement. Elle peut être désactivée
et réactivée à tout moment.

Avec MCP, `air_export_portable_session` produit `session.json`, `schemas.json` et
`AIR-SESSION.md`. Le fichier conserve l'origine immuable, les objets exacts et
les octets des artefacts retenus dans la limite de réponse. Les nouvelles
propositions restent dans `drafts`, les questions dans `questions`.
Sans moteur et sans MCP, le plugin fournit un modèle de session pour commencer
le design immédiatement. Conserver et joindre ce fichier à la prochaine conversation.
Lorsque le client ne peut pas générer une pièce jointe, le JSON reste copiable.
La disponibilité du plugin et des outils d'exécution dépend du client et du compte.

```powershell
air session-new --title "My Help" --project-id reference.my-help --output session.json
air session-check session.json
air session-configure session.json --repository enabled --endpoint https://air.example.invalid/mcp --output session-connected.json
```

Ces trois commandes fonctionnent sans serveur. `session-check` vérifie l'intégrité
de la source et les schémas des drafts. Sans exécution effective du moteur, les
contrôles sont `NOT_EXECUTED`, la readiness `UNKNOWN`. La discussion ne crée pas
une revue authentifiée, un mandat ou une révision enregistrée. Si Python n'est pas
disponible dans ChatGPT, poursuivre la rédaction et conserver les contrôles en attente.

À la reconnexion, `air_reconcile_portable_session` prépare un rebase sur la dernière
baseline explicite de ce projet. Une modification concurrente d'un objet proposé
provoque un refus à résoudre ; aucun écrasement automatique. Sans base, le service
prépare un premier import si les identités n'existent pas et les droits le permettent.
Les artefacts embarqués doivent être réimportés et leurs nouveaux descripteurs reliés
dans cette nouvelle installation avant dépôt. Les outils habituels assurent ensuite
dépôt, gel et contrôles. Pas de fédération, synchronisation ou fusion Git automatique.
Les fichiers transportent des données privées : les partager dans le périmètre autorisé.

## Ce que le 429 permet réellement de conclure

Le 19 octobre, l'appel natif disponible `air_capabilities` a échoué avant toute
réponse AIR : `MCP SSE probe returned 429 from openai.org`. Cela confirme un
obstacle de transport dans cette session, sans établir sa cause profonde ni
prouver que les schémas AIR sont absents. Le client distingue désormais le 429
générique `AIR_RATE_LIMITED` du refus AIR codé `AIR_QUOTA_EXCEEDED`.

Le mode portable évite que cette indisponibilité bloque la rédaction. Il ne
répare pas une limitation de la plateforme OpenAI. La documentation officielle
prévoit des plugins constitués uniquement de skills et un MCP optionnel :
[connexion et test des plugins](https://developers.openai.com/apps-sdk/deploy/connect-chatgpt).
Ce n'est pas une preuve de disponibilité du paquet AIR installé sur chaque compte.
Les captures fournies montrent aussi un refus de publication d'un paquet qui
omet le MCP déjà déclaré sur sa fiche existante : changer le code ou le ZIP ne
supprime pas cette contrainte de publication. La distribution et la recette
dans ChatGPT normal restent des opérations séparées, non réalisées par cet incrément.

## Rejouer la recette

```powershell
.venv/Scripts/python.exe -m pytest -q tests/test_delivery_assurance.py --basetemp tmp/pytest-assurance-local
.venv/Scripts/python.exe scripts/demo_delivery_assurance.py --output tmp/demo-assurance-local
.venv/Scripts/python.exe scripts/demo_metier.py --output tmp/demo-asteria-assurance
```

La recette My Help / My Health est fictive : les rapports simulés servent à tester
le rattachement de preuves, pas à attester une CI ou une application métier réelle.
Elle compare les réponses CLI et MCP par HTTP local, exporte Excel/CSV, reprend la
session portable et génère le site. La recette Asteria conserve les trois parcours
DEMO-METIER-1. Aucun déclencheur CI n'est activé.
