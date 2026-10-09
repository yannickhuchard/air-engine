# Prêt à construire, preuve par simulation et livrables - tranche 32

**Correctifs de production P01/P02/P03 (non publiés)** : ce contrat est précisé ci-dessous. Une exécution déposée
est une déclaration, y compris avec `proof_level: CALIBRATED_SIMULATION`. Elle ne produit plus `VERIFIED`.
Le [binding P03 de conception](lot-qualification-preuves.md) permet une qualification explicite, indépendante
et limitée au design ou au modèle ; il ne qualifie aucun test externe.

La revue du 23 septembre 2026 ([jalon](jalons/2026-09-23-revue-objectifs.md)) a jugé AIR bon socle de conception,
mais pas encore capable de dire qu’un dossier est prêt à construire, ni de prouver par simulation, ni de remettre à
une équipe de réalisation un dossier opposable. Cette tranche traite ses deux premiers points et ajoute le dossier de
livrables. Elle ajoute le profil `air.delivery/0.32`, trois services et un compilateur, sans table SQL.

## Profil air.delivery/0.32

Il contient tous les types du profil architecture/0.26 et vingt types DRAFT :

| Famille | Types | Ce qu’ils déclarent |
| --- | --- | --- |
| Preuve | `VerificationRun`, `PerformanceModel`, `SimulationScenario` | L’exécution d’un cas avec son niveau de preuve ; la durée de chaque étape d’un processus ; une population, une mesure et une cible |
| Exécution | `Environment`, `NetworkZone`, `RuntimeComponent`, `Connection`, `Technology`, `PhysicalTable`, `Device` | Ce qui tourne pour construire et tester, pour livrer et en production ; où ; avec quoi ; quels flux ; quelles tables ; sur quels équipements et machines |
| Pilotage | `CostItem`, `Milestone`, `RaciAssignment`, `RiskAssessment` | CAPEX et OPEX ; jalons et critères de sortie ; qui est responsable, qui décide ; cotation, résiduel et journal des risques |
| Métier | `ValueStream`, `CustomerJourney`, `ArchitecturePrinciple`, `ConceptRelation`, `ContextRelation`, `NavigationMap` | Chaîne de valeur ; parcours et points de contact ; principes ; ontologie ; carte des contextes ; écrans et navigation d’une interface |

Contrôles propres au profil : le niveau de preuve d’une exécution doit correspondre à sa méthode et à celle de son cas ;
un test ou une simulation cite un rapport ; un modèle de performance ne décrit que des étapes de son processus ;
un composant est dans une zone de son environnement ; chaque activité RACI a exactement un A ; chaque écran d’un graphe de
navigation est atteignable depuis une entrée et n’appelle que des opérations de son contrat ; un équipement n’héberge que
des composants de son environnement.

Un dossier passe au profil par `air_rebase_drafts` ou `air_validate_drafts` avec `profile: "air.delivery/0.32"`,
refusé si le profil demandé ne contient pas tous les types du profil courant.

## Porte « prêt à construire » - air.readiness-gate/0.32

`air_assess_readiness` (CLI `readiness`, `POST /v1/readiness/assess`) rend onze critères pour une baseline exacte,
chacun MET ou NOT_MET, avec ce qui le ferme et à qui cela revient :

| Critère | Tenu quand |
| --- | --- |
| REFERENCE_CLOSURE | Toutes les références sont dans la baseline |
| STRUCTURE | Aucune violation MECE ou DDD |
| CONSTRUCTION_CHAIN | La chaîne exigence → fonction → contrat → unité → cas du projet est complète |
| EXTERNAL_DEPENDENCIES | Chaque objet emprunté est complet dans une baseline de son projet propriétaire qui en fixe les mêmes révisions |
| KNOWLEDGE | Aucune inconnue bloquante ni assertion contestée |
| GAPS | Chaque manque déclaré est levé, ou accepté par une décision qui le cite et qu’une revue humaine de la révision a approuvée |
| VERIFICATION | Chaque cas de conception possède une qualification explicite effective selon P03 ; chaque test est planifié comme acceptation d’une unité, sans être déclaré exécuté |
| PLANNING | Chaque unité est estimée ; des coûts et des jalons sont déclarés |
| RUNTIME | Chaque bloc du projet a un composant de production |
| SECURITY_ZONES | Aucune traversée de zone en clair ni chemin public → restreint direct |
| INDEPENDENT_REVIEW | Acceptation indépendante effective de cette révision et de son digest, sous politique et mandat courants ; aucun rejet effectif ni revue inaccessible |

Un projet qui ne possède ni bloc ni exigence (un noyau partagé, un dépôt de stratégie) ne construit rien :
CONSTRUCTION_CHAIN, PLANNING et RUNTIME y sont `NOT_APPLICABLE` et ne bloquent pas.

Le résultat est `READY_TO_BUILD` seulement si aucun critère n’est `NOT_MET`. Ce n’est ni une garantie de
comportement, ni une signature, ni une admission. Les tests ne s’exécutent qu’après construction : avant, la porte
vérifie qu’ils sont planifiés, pas qu’ils ont passé.

## Preuve par simulation - air.scenario-simulation/0.32

Une condition de processus peut porter une garde AIR-Expr (`air.workflow-flow/0.32`). `air_simulate_scenario`
parcourt le processus pour chaque classe de la population, depuis l’étape de départ qu’elle nomme (`start_step`)
ou depuis toutes, décide chaque garde sur le contexte de la classe, tire
les durées d’étape du modèle (FIXED, UNIFORM, TRIANGULAR, LOGNORMAL par médiane et p95), avec une graine : même
entrée, même rapport. Il rend les percentiles, les chemins, et un verdict PASS, FAIL ou INCONCLUSIVE contre la cible.

Le modèle est **numériquement calibré** quand chaque étape cite des observations de durée de la baseline
(p50, p90, p95, p99 ou median, en `Quantity[ms]` ou `Quantity[s]`) et s'accorde avec chacune à 20 % près.
Une référence absente, une unité incompatible, une statistique ambiguë ou une valeur non finie/négative
empêche la calibration. Zéro contre zéro est un accord ; zéro contre une valeur positive est un désaccord,
avec écart relatif `null`. Le champ `proof_level` vaut alors `CALIBRATED_SIMULATION`, sinon
`DECLARED_MODEL_SIMULATION` ; aucun des deux ne qualifie automatiquement une preuve dans la porte.
Provenance, fraîcheur, périmètre et représentativité des mesures restent à qualifier.

Un percentile porte sur les seuls parcours atteignant les deux extrémités de mesure. `population` expose
les effectifs demandés, mesurés et exclus. `conditional_verdict` conserve la comparaison calculée sur ce
sous-ensemble ; `verdict` est INCONCLUSIVE si une garde est indécidable, une durée absente ou aucun parcours
mesuré. `inconclusive_reasons` en donne les raisons. Une exclusion décidée par une garde connue reste visible
sans invalider la mesure conditionnelle. La cible est comparée au percentile avant arrondi d'affichage.

`air_record_simulation` exécute le scénario, range le rapport comme artefact et rend le brouillon de
`VerificationRun` qui le cite. Rien n’entre dans le modèle sans dépôt.

## Livrables de l’équipe de réalisation - air.deliverables/0.32

`air_compile_deliverables` (CLI `deliverables --workspace <dépôt> [--apply]`, `POST /v1/deliverables/compile`)
compile, depuis une à seize baselines épinglées, un dossier Markdown avec diagrammes Mermaid :

graphe du dossier ; chaîne de valeur ; parcours clients ; processus métier ; rôles ; organisation de réalisation,
RACI et décideurs ; organisation d’exploitation ; architectures construire-tester, livrer et production ; séquences ;
états ; arbres de décision ; hypothèses ; traçabilité exigences / construction ; carte des capacités ; analyse
d’écarts ; risques cotés, carte de chaleur et journal ; plan CAPEX / OPEX ; ontologie ; modèles logique et physique ;
infrastructure et réseau ; sécurité par zones de confiance ; objectifs stratégiques ; principes ; ADR ; registre des
technologies ; jalons ; préparation à la construction ; diagramme des événements (publication, canal, garantie,
consommation, lus dans les ports et liaisons de canal) ; graphe de navigation de chaque interface ; équipements
physiques et machines par environnement, avec les composants qu’ils hébergent.

Chaque document cite ses objets exacts. Un document sans objet le dit : c’est un manque. Le compilateur n’invente
rien. Objectifs et principes sont lus comme des entrées, qu’un projet peut emprunter à un espace partagé. Le dossier
porte la porte « prêt à construire » de chaque projet et dit ce qu’il n’est pas : ni preuve au-delà des cas vérifiés,
ni approbation, ni document juridique.

## Emprunts entre projets

Une première référence à l’objet d’un autre projet est intégrée par `air_rebase_drafts` : la révision exacte et sa
fermeture sont empruntées (`borrowed_added`), sans rien écrire dans l’espace du propriétaire.

## Régénération

Le `manifest.json` du dossier de livrables liste chaque fichier et son empreinte. Une régénération remplace les
fichiers qu’elle a produits et signale en conflit ceux qui ont été modifiés à la main.

## Pilote assurance santé (passe 5)

Noyau partagé r2, plateforme r8 et fraude r7 : chaîne de construction fermée, exécution, zones, coûts, jalons et
organisation déclarés. Les trois restent `NOT_READY`. Il manque les inspections et revues de conception croisées, la
calibration de la simulation de fraude (PASS sur modèle déclaré, p95 1 034 ms pour 2 000 ms) et les revues humaines
qui approuvent aussi les décisions acceptant des manques. Voir le retour de passe du dépôt de portefeuille du pilote.

## Usage par ChatGPT (deuxième essai)

Le serveur MCP publie un catalogue selon le rôle de l’identifiant (`--access auto` : lecture, contribution, ou tout
pour un administrateur) ; ses instructions annoncent le nombre d’outils pour qu’un agent détecte un catalogue
périmé. Le guide porte le verdict de la porte et l’état des manques ; `air_assess_readiness` accepte un
`prepared_change` ; une réponse MCP au-delà de 200 000 octets devient `AIR_OUTPUT_TOO_LARGE` avec un indice ;
`air_compile_deliverables` accepte `only`. Voir le [guide de l’architecte avec un agent](guide-architecte-agent.md).

## Limites

- La simulation est un modèle : elle ne prouve que ce que ses durées et sa population représentent. Sans
  calibration, elle ne vérifie rien.
- Les gardes sont décidées par classe ; aucun état n’est propagé d’une étape à l’autre.
- Les coûts récurrents sans fin sont comptés sur 36 mois, et signalés.
- Les 45 diagrammes du pilote ont passé le parseur Mermaid 11 ; la recette automatique ne lance pas ce parseur.
- Aucune revue humaine, signature ou admission n’est produite par ces services.
