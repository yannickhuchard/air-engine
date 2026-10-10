---
name: air-architecte
description: "Mener une architecture de solution AIR jusqu'au prêt-à-construire, avec un agent : scénarios d'acceptation rejoués sur la conception, socle de non-régression, contrôles et exigences non fonctionnelles reçus en entrée et reliés aux blocs, estimation avec et sans IA agentique, feuilles de route alternatives. Utiliser pour compléter, vérifier ou livrer un dossier de solution, ou pour préparer son passage au comité."
license: Apache-2.0
metadata:
  engine: air 0.35
  compatibility: "Agent Skills avec MCP AIR ou CLI air. La connexion et la qualification restent propres à chaque client."
---

# Architecture de solution prête à construire

Commencer par `air_assess_completeness` sur la baseline exacte. Choisir avec
l'architecte les contextes numérique, données, physique, organisationnel ou
réglementé. `profiles` dans cet appel est une prévisualisation ; enregistrer
DossierContext via la contribution habituelle pour conserver le choix.
Utiliser le profil de modèle `air.build-design/0.35` pour les nouveaux objets.
Ses treize critères incluent la complétude contextuelle ; les anciens profils
conservent leurs douze critères. Les exclusions exigent une décision exacte et
une revue effective de la baseline pour être reconnues, pas un champ ACCEPTED.

Pour chaque interface JSON/HTTP, décrire InterfaceSpecification et les schémas
actuels. Les copies doivent égaler les artefacts du binding. Prévoir conditions
AIR-Expr, exemples valides/invalides, autorisation, idempotence, concurrence,
délai, retry et compensation. Compiler `air_compile_interface_suite`, puis
vérifier les échanges fournis avec `air_verify_interface_exchange`.
Le PASS porte sur les formes JSON et les prédicats purs, pas sur l'exécution
des politiques ou du système métier. Pour les tables, décrire
DataLifecycleSpecification : propriété, clés uniques, index, rétention,
migration, retour arrière et cas prévus. Le site conserve les questions
contextuelles et les suites téléchargeables dans `completeness.html`.

Pour chaque CustomerJourney, renseigner les phases, actions, pensées,
touchpoints, acteurs, systèmes exacts, frontstage, backstage et support.
Émotion UNKNOWN sans score ; HYPOTHESIS avec justification ; OBSERVED avec
sources exactes. Examiner les opportunités et les dimensions d’expérience
manquantes, distinctes de readiness. Lire les cartes HTML et les processus
BPMN descriptifs exportés ; aucune exécution BPMN n’est reçue par ce rendu.

Présenter chaque parcours avec sa page `journey-map-*.html`, son SVG portable
et ses données exactes. La carte permet sélection, filtres, zoom et lecture
guidée ; la matrice et les fiches gardent les détails complets. Cette visite
suit l’ordre déclaré et ne vaut ni simulation métier ni recherche utilisateur.

Un dossier de solution est prêt à construire quand AIR le dit (`air_assess_readiness` → `READY_TO_BUILD`), pas
avant. Ce skill dit quoi modéliser pour y arriver et comment le vérifier. Le parcours d'écriture reste celui
d'AIR : valider à blanc, préparer, montrer, puis déposer et figer après accord explicite de l'architecte.

## 1. Orienter

Vérifier `air_whoami`, `air_capabilities` et le contexte exact `{id, revision, digest}`
du manifeste. Le branding du plugin ne prouve pas le registre connecté. Le contrat
`client_contract`, lorsqu’il est disponible, décrit des catalogues supportés ;
comparer la découverte réelle au profil autorisé. Rafraîchir un catalogue divergent
avant de reprendre la même URN, sans substitution d’identifiant. La CLI locale
`air client-contract-check` compare une observation fournie, sans qualifier le client.

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

Le site complet fournit `handoff.html` et `handoff.json` par dossier : fiches par
composant et équipe, sources exactes, contrats, responsabilités, critères, tests
prévus et résultats consignés séparés. Les RACI sans sujet restent générales.
Discuter les manques avec les équipes avant de consigner une nouvelle révision.
La compilation MCP en `DIGESTS` ne matérialise pas les pages sur le poste ;
utiliser la CLI ou l’IDE autorisé pour appliquer le pack. Ne pas présenter ce
développement local comme une nouvelle recette native ChatGPT ou Claude.

- `air_compile_deliverables` (`DIGESTS`, puis `only`) : notamment 32 scénarios, 33 non-régression,
  34 matrice de conformité, 35 ENF, 36 estimation IA, 37 feuilles de route.
- `air_compile_presentation` : le plan du deck de direction ; le HTML bilingue se produit à la CLI. Pour le
  construire et le critiquer, suivre le skill `air-presentation`.

## Ce que l'agent ne fait jamais

- Déclarer une conformité, une revue humaine ou une mesure qui n'existe pas dans AIR.
- Transformer `NOT_MET`, `UNMAPPED`, `INCONCLUSIVE` ou `NOT_EXECUTED` en résultat.
- Admettre, activer, renouveler, clore ou signer : ce sont des actes humains authentifiés.
- Lire, afficher ou recopier un jeton.

## Reprendre une question épinglée

Dans le développement courant, `cooperate.html` permet de préparer une capsule
avec namespace, baseline et sources exactes. Lire `air_whoami` et `air_capabilities`,
puis appeler `air_resume_question` avec `{capsule}`. Conserver le reçu et présenter
`{capsule, previous_receipt}` à la prochaine conversation : AIR revérifie identité,
installation, rôle, politique et sources. Un reçu non signé ne donne aucun droit.
Le site ne configure ni ne connecte le client ; un outil absent ou un identifiant
refusé exige un diagnostic du catalogue, sans inventer d’URL.

Un `prepared_change` peut être joint pour vérifier son auteur, sa baseline et son
namespace. Dépôt et fermeture restent les appels explicites existants, après
présentation du changement et selon l’autorisation de la session. Ne pas prendre
un contrôle de contexte pour une réservation atomique ou une approbation métier.
Après fermeture, régénérer les livrables et une capsule pour la nouvelle baseline.
La CLI `question-resume ... --output <nouveau-fichier>` conserve la reprise sans
écraser un document. Ranger les métadonnées dans `questions/`, les clarifications
dans `reviews/` et les échanges de réalisation dans `handoff/`, par domaine.
Une capsule contient des données internes : sa diffusion suit leur périmètre.
Le branding et le public choisi ne cloisonnent pas les registres des clients.

## Parcours, personas et usages

Dans chaque dossier, décrire les schémas courants `JourneyCatalog`,
`CustomerJourney`, `Touchpoint` et `UsagePoint` avec `air_describe_type`.
Inventorier les personas (Actor ou Stakeholder), justifier les exclusions et
les contextes requis DIGITAL, PHYSICAL, GEOGRAPHIC. Inclure les parcours
nominal, assistance, exceptions, exploitation et gouvernance pertinents.
Pour chaque étape, déclarer un `touchpoint_ref`, les intervenants, les usages
et lieux proposés, puis les références exactes vers fonctions, contrats,
blocs, données, exigences, contrôles ou livrables. Les villes, dépôts et
corridors proposés ne deviennent pas des sites autorisés ou mesurés.
Régénérer le site puis lire `journeys.json`, ses lacunes et les cinq contrôles
de couverture documentaire dans `progress.json`. Leur satisfaction ne vaut
ni recherche utilisateur validée, ni conformité réglementaire, ni passage
des douze critères `readiness`. Ne pas déclarer « tous les parcours » au-delà
du périmètre et du roster explicitement définis dans le catalogue.

## Synthèse et pilotage de transformation

Lire le Management Summary en tête du dossier. Il est calculé depuis la même
baseline que readiness et régénéré avec les livrables après chaque évolution.
Un export reste figé jusqu'à sa régénération ; aucune approbation n'est inférée.
Utiliser `only: ["00-management-summary"]` pour sa lecture ciblée par MCP.

Décrire `TransformationProgramme`, `ArchitectureProject`, `ArchitectureTask`
et `SourcingStrategy` avec `air_describe_type` avant de contribuer. Les programmes
peuvent s'imbriquer et relier plusieurs projets avec leurs tâches, responsables
et dépendances. Les statuts sont déclarés. Un projet COMPLETED ou CANCELLED
requiert une décision et une date, sans tâche active. DONE et CANCELLED restent
distincts ; ni le score 12/12 ni l'implémentation métier ne sont déduits de la clôture.
Ne pas inventer de preuve de clôture ou de reçu indépendant.

Interroger `air_query_transformation` avec les baselines exactes autorisées,
les filtres `types`, `statuses` et `owner`, puis suivre `next_offset`.
Les totaux portent tous les pins autorisés, avant filtrage ; les relations de la
page ne couvrent pas les objets omis. Pour le site global : épingler les projets
avec `air_index_portfolio` et lire `transformation.html/json`, puis régénérer.
Une seule instance est indexée ; les dossiers de clients ou installations
indépendants ne sont pas fédérés ni fusionnés automatiquement.

La stratégie RFI/RFP, ou le choix de ne pas consulter, fait partie des décisions
architecturales (ADR/ADA). Relier `SourcingStrategy` à la `Decision`, au périmètre,
au jalon, aux critères de sélection et aux blocs concernés. DRAFT et READY_TO_LAUNCH
ne valent ni consultation envoyée, ni fournisseur retenu. Un lancement déclaré
nécessite des sources exactes ; le moteur ne réalise aucun envoi externe.

## Actualiser News et vidéos

Pour une demande de mise à jour, lire `air_query_project_updates` sur la baseline exacte.
Les News sont des déclarations sourcées, pas une preuve de livraison ou d’approbation.
Régénérer le site par `air_compile_deliverables` ; préserver les questions ouvertes.
Si le catalogue expose `air_refresh_videos`, commencer par DIGESTS, puis obtenir
les fichiers FULL pour l’atelier autorisé. Le MCP prépare sans écrire ni rendre
sur le serveur. La CLI `videos-refresh --apply --render` rend localement avec
Hyperframes/Chromium/FFmpeg facultatifs. Sans cet atelier, annoncer NOT_RENDERED.
Une ancienne vidéo n’est pas courante par simple changement de son étiquette :
contrôler la baseline, le source_digest, le branding et le reçu du rendu réel.
Aucune publication externe implicite. Les fonctions nécessitent le moteur courant
qui les expose ; ne pas les supposer disponibles dans la distribution rc9.
