# Tranche 04 - Exigence, fonction, contrat et unité de construction

Version 0.4.0.dev1. Profil expérimental `air.construction/0.4`, fondé sur les
catalogues A.3, A.5, A.6, A.9/A.10 et les contrôles C du white paper.
Le profil contient les six types de connaissance de foundation/0.2 et neuf types
supplémentaires. Baseline et ChangeSet restent les objets techniques du registre.

## Exécuter le parcours

Depuis la racine avec Python du venv :

```bat
.venv\Scripts\python.exe scripts\demo_construction.py
```

Le script utilise une SQLite temporaire pour les trois dossiers de la même
entreprise. Il importe les graphes, fige les baselines, calcule la traçabilité,
restaure les contenus à empreintes identiques, refuse un contrat incomplet puis
propose une nouvelle estimation avec les révisions exactes de son unité.
Le rapport est écrit dans `tmp/demo-asteria/construction.json`. L’instance .air
reste inchangée. Les sources métier fictives ne sont pas modifiées.

Pour charger un dossier dans une installation de démonstration choisie :

```bat
scripts\air.cmd bundle-put fixtures\enterprise\asteria\dossiers\sav\construction.json
scripts\air.cmd baseline-create fixtures\enterprise\asteria\dossiers\sav\construction-baseline-request.json
```

La réponse donne id, revision et digest. Enregistrer ces trois valeurs exactes
dans une demande `{"baseline":{"id":"…","revision":1,"digest":"sha256:…"}}`, puis :

```bat
scripts\air.cmd construction-validate demande-construction.json
```

La CLI appelle `POST /v1/construction/validations`, accessible à reader/editor/admin.
Le résultat est HTTP 200 et un rapport ; la CLI retourne 1 lorsque la porte est
BLOCKED. Une demande mal formée retourne 422, une empreinte différente 409 et
une absence d’identité 401. Les jetons sont chargés par la CLI sans être affichés.
Les imports et baselines continuent d’exiger editor/admin. Aucun nouvel effet externe.

## Modèle livré

Les schémas exécutables sont dans `src/air/construction_schema.py`, publiés par
`GET /v1/schemas/air.NomDuType`. Chaque objet conserve l’enveloppe meta/body,
les révisions immuables, la provenance et l’état DRAFT. Les champs sont stricts.

| Type | Contenu et restrictions de cette tranche |
| --- | --- |
| Requirement | Énoncé, kind FUNCTIONAL/QUALITY/CONSTRAINT, priorité MUST/SHOULD/COULD, applicabilité textuelle, réceptions et sources Source/Assertion exactes |
| AcceptanceCriterion | Condition textuelle, méthode TEST/ANALYSIS/INSPECTION/SIMULATION/REVIEW, identité d’autorité déclarée, cas de vérification |
| Function | Nature BUSINESS/SOFTWARE/HUMAN/PHYSICAL, paramètres nommés, pré/postconditions, effets, erreurs FailureMode, atomicité et références satisfies vers Requirement |
| Actor | Nature humaine, organisationnelle, logicielle, agent, dispositif, machine ou robot ; frontière Scope ; roles vide tant que Role n’est pas implémenté |
| FailureMode | Déclencheur, effet, détection, réponse et condition de reprise textuels |
| SemanticContract | Opérations nommées liées aux Function, participants Actor avec rôle textuel, autorisation, effets, erreurs et politique de compatibilité ; quality vide |
| ConstructionUnit | Function/SemanticContract réalisés, nature du travail, livrables attendus, réception, justification par Requirement, Estimate exact ; resource_demand vide |
| VerificationCase | Cible exacte, méthode, entrées, oracle, réception et base d’indépendance textuels ; aucun résultat d’exécution auto-déclaré |
| Estimate | Cible ConstructionUnit, effort en person_day ou durée en second, valeur décimale non négative, bases textuelles, hypothèses et classe de calibration |

ParameterSpec = name/data_type/description. Le data_type est ici un nom documentaire,
sans résolution de schéma métier. EffectSpec = kind/description, avec STATE_CHANGE,
EVENT, HUMAN_ACTION ou PHYSICAL_ACTION. OperationSpec = name/function exact.
ParticipantSpec = actor exact/role textuel. ErrorSpec = code/failure_mode exact/response.
ArtifactSpec = name/kind/description : un livrable prévu, pas un artefact construit.
EstimateValue = value/unité : point décimal de 18 chiffres entiers et six décimales
maximum ; distributions, coûts et conversions ne sont pas pris en charge.

Le champ `Function.satisfies` est le binding de relation retenu par ce sous-profil
pour tracer les exigences. Les types Goal, Constraint et les autres cibles possibles
du catalogue complet restent exclus. Les listes de références sont normalisées
comme ensembles pour les digests ; les listes de records gardent leur ordre.
Les noms de paramètres, opérations, livrables et codes d’erreur doivent être uniques
dans leur liste. Les conditions textuelles ne sont jamais exécutées comme du code.

## Contrôles réellement exécutés

La fermeture typée AIR-V003 est appliquée dans le profil déclaré. Un objet de
construction ne peut pas être placé dans une baseline foundation/0.2. Le lockfile
enregistre le profil exact, y compris après proposition ou restauration.

L’évaluation de construction vérifie ensuite :

- Présence d’au moins une exigence, fonction, contrat et unité ; aucune réussite à vide.
- Chaque exigence MUST possède une chaîne complète, avec Function.satisfies,
  opération de contrat, unité réalisant explicitement les deux et justification.
- Chaque fonction possède un contrat et une réalisation ; chaque contrat réalisé
  par une unité a toutes ses opérations explicitement réalisées par cette unité.
- Les erreurs et effets annoncés par les fonctions figurent dans leur contrat.
- La réception de l’unité comprend celle de l’exigence réalisée. Les critères
  possèdent des cas de même méthode ; les cas de chaque chaîne ciblent cette chaîne.
- L’estimation cible la révision exacte de son unité ; mesure et unité concordent.

Une incohérence de conception peut être conservée dans une baseline fermée pour
être revue : fermeture et réception structurelle sont deux opérations distinctes.
Le rapport de construction exposera alors ses diagnostics et construction_ready=false.
Le rapport est limité à 4 096 chemins ; une demande qui les dépasse est refusée
explicitement, sans couverture tronquée présentée comme complète.

Ces contrôles sont annoncés comme `construction-structure/0.4`. Ils préparent les
règles AIR-V015/016/017/019/023/026 sans revendiquer leur réception normative complète.
L’analyse textuelle du besoin, l’exhaustivité des scénarios, la compatibilité
fournisseur-consommateur et les bindings d’implémentation ne sont pas vérifiés.

## Rapports et autorité

Le rapport inclut la baseline et son digest, les chemins de traçabilité, références
de critères/cas/estimations, diagnostics, inconnues, couverture et son propre digest.
Le rejeu d’une même baseline est déterministe et n’écrit ni objet ni audit.

`construction_ready=true` signifie que les contrôles structurels ci-dessus passent.
Chaque VerificationCase reste NOT_EXECUTED/UNKNOWN : ce sont des spécifications.
La porte reste BLOCKED pour vérification et autorité non réalisées, ainsi que pour
les inconnues BLOCK ou assertions CONTESTED éventuelles. decision_ready et
authorization_granted restent false. Une identité acceptance_authority déclarée
ne prouve ni mandat ni signature. Aucune approbation, réservation ou action métier.

La porte foundation-review de la tranche 03 reste réservée aux baselines foundation.
Elle refuse une baseline de construction pour éviter de laisser croire qu’elle
vérifie ces obligations supplémentaires.

## Trois dossiers et limites de réception

Chaque dossier comprend 24 objets (neuf de connaissance et 15 de construction),
une chaîne principale et trois cas décrits :

| Dossier | Opération | Réception nominale et erreurs prévues |
| --- | --- | --- |
| SAV | SubmitClaim | Dépôt/doublon, demande pour un autre client, persistance indisponible ; enregistrement distinct de garantie |
| Atelier | ProposeInspection | Proposition humaine, mesure périmée, collecteur ou unité invalide ; aucune commande physique |
| Identités | ProposeAccessRevocation | Proposition sans action IAM, dates contradictoires, compte non rapproché |

Les estimations sont pédagogiques et non calibrées. Aucun ERP, équipement, IAM ou
code métier de ces dossiers n’a été exécuté par cette recette. La recette teste
le système AIR et les liens de conception, sans fabriquer de preuves métier.

M1-CONTRACT est vérifié dans ce sous-profil. DEMO-METIER-1 reste NOT_READY : revue
authentifiée, permissions fines, impact inter-dossiers et vue métier sont encore
nécessaires. La prochaine tranche vise le diff explicable, l’impact des actifs
partagés et une vue de traçabilité dérivée. L07 reste partiellement implémenté.

SQLite/local restent les valeurs par défaut. Aucun changement de schéma SQL ni
nouvelle dépendance. Les empreintes des anciennes baselines sont comparées à la
preuve enregistrée de la tranche 02. PostgreSQL, IdP réel et autres plateformes
restent à qualifier séparément. Preuves de cette tranche (document historique ou livrable local non inclus).
