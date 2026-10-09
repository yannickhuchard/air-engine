# Architecture de solution livrable : acceptation, conformité, estimation IA, feuilles de route, présentation - tranche 33

**Correctifs P01/P02 (non publiés)** : une simulation enregistrée et son niveau de preuve restent déclaratifs
dans les présentations. Les calculs refusent les additions et comparaisons entre devises différentes sans
conversion explicite : main-d'œuvre/abonnement, alternative/référence, total d'abonnements et agrégats de deck.
Un deck homogène affiche sa devise réelle. Le plan financier par devise conserve ses groupes séparés.
Ces changements et leurs limites sont suivis dans la [roadmap de production](ROADMAP_PRODUCTION.md).

La tranche 32 dit si un dossier est prêt à construire. Celle-ci ajoute ce qu’il manquait pour **remettre et vendre**
une architecture de solution :

- les scénarios qui servent à la fois à simuler, à tester l’acceptation et à fonder la non-régression ;
- les contrôles de conformité et les exigences non fonctionnelles reçus en entrée et reliés aux blocs qui les
  implémentent ;
- l’estimation avec et sans IA agentique ;
- des feuilles de route alternatives comparables ;
- la présentation de direction bilingue.

Le profil reste `air.delivery/0.32`, étendu de six types DRAFT, sans table SQL.

## Nouveaux types

| Type | Déclare | Contrôles |
| --- | --- | --- |
| `AcceptanceScenario` | Un objectif de persona joué sur une `NavigationMap` : étapes (écran, action, transition `via`, opération, résultat attendu), contexte des gardes, suites `ACCEPTANCE`, `REGRESSION`, `SMOKE`, priorité, cas de conception (ANALYSIS) et cas d’acceptation (TEST) | étapes uniques ; chaque écran existe dans la carte |
| `QualityRequirement` | Une exigence non fonctionnelle : catégorie (13), énoncé, priorité, cible chiffrée typée, méthode de vérification | cible typée |
| `ComplianceMapping` | Pour un contrôle ou une exigence : les unités, blocs, composants, équipements, connexions ou zones qui l’implémentent, le mécanisme, les cas qui le vérifient | `NOT_APPLICABLE` exige une décision ; sinon au moins un implémenteur |
| `AgenticToolPlan` | Un outil agentique : éditeur, offre, prix par poste et par mois, politique de données | - |
| `DeliveryEstimate` | L’effort d’une unité par activité (12 activités), sans IA et avec IA quand elle s’applique, l’équipe et les postes | effort avec IA donné exactement quand l’IA s’applique et jamais supérieur ; un plan et au moins un poste |
| `Roadmap` | Une stratégie de réalisation : phases datées, unités, dépendances, équipe, critères de sortie, taux journalier, statut `PROPOSED`, `RECOMMENDED`, `SELECTED` ou `REJECTED` | phases uniques ; une phase dépendante ne commence pas avant la fin de la précédente ; une feuille de route avec IA nomme son plan |

## Marche des scénarios - air.acceptance-walk/0.33

`air_walk_scenarios` (CLI `scenarios-walk`, `POST /v1/acceptance/walk`) rejoue chaque scénario d’une baseline sur sa
carte de navigation, sans rien construire. Pour chaque scénario, elle vérifie :

- le premier écran est une entrée ;
- une transition existe entre deux écrans successifs ;
- les gardes sont décidées sur le contexte du scénario ;
- chaque opération est offerte par l’écran et existe dans le contrat ;
- le persona est un utilisateur déclaré de la carte.

Elle rend :

- un verdict `PASS`, `FAIL` ou `INCONCLUSIVE` par scénario ;
- la couverture de chaque carte : écrans, transitions et opérations non couverts, impasses ;
- les opérations de parcours clients qu’aucun scénario n’exerce ;
- le socle de non-régression ;
- des brouillons de `VerificationRun` (méthode et niveau `ANALYSIS`) pour les scénarios liés à un cas de conception.

Elle n’écrit rien : les exécutions entrent par le parcours habituel, sur décision de l’architecte.

Sur le pilote, la marche a trouvé deux défauts de navigation avant toute construction :

- une page de paiement sans issue ;
- un dialogue d’explication du score sans retour vers le dossier.

## Conformité reçue en entrée - critère COMPLIANCE

La porte `air.readiness-gate/0.32` passe à douze critères. COMPLIANCE est tenu quand chaque contrôle et chaque
exigence non fonctionnelle a un `ComplianceMapping` possédé par le projet. Cela vaut pour les sujets du projet, ceux
qu’il emprunte, et ceux de tout noyau partagé qu’il emprunte, même non cités. Un noyau partagé est une baseline sans
bloc ni exigence. Pour un projet qui ne construit rien, le critère est `NOT_APPLICABLE`.

## Estimation avec et sans IA, feuilles de route

`air.delivery_calc` calcule par unité :

- l’effort sans IA et avec IA, l’écart et le ratio ;
- la durée selon l’équipe ;
- le coût d’abonnement : prix × postes × mois avec IA.

Pour chaque feuille de route, il calcule :

- le calendrier et le chemin critique par les dépendances ;
- l’effort, avec ou sans IA selon la stratégie ;
- la main-d’œuvre, les abonnements sur les postes-mois des phases et le coût total ;
- l’écart par rapport à la feuille de route sans IA du même projet.

Il retient une feuille de route par projet : `SELECTED`, sinon `RECOMMENDED`. Les réductions par activité sont des
hypothèses déclarées ; les livrables et le deck le disent.

## Livrables 32 à 37 et présentation de direction

Le dossier compte désormais 37 documents et un deck :

| Document | Contenu |
| --- | --- |
| 32 scénarios d’acceptation | Scénarios par carte, verdict de la marche, couverture et impasses |
| 33 tests de non-régression | Socle de non-régression numéroté (NR-###) |
| 34 matrice de conformité | Contrôles et exigences × unités de construction, implémenteurs, vérification, sujets non reliés |
| 35 exigences non fonctionnelles | Par catégorie, cible et méthode |
| 36 estimation IA | Effort sans et avec IA par unité et par activité, histogramme, abonnements, hypothèses |
| 37 feuilles de route | Programme (une par projet), puis par projet : comparaison à la référence sans IA, recommandation, gantt par feuille de route |
| 00 présentation de direction | Deck HTML autonome, français et anglais, sélecteur FR/EN |

`air_compile_presentation` (CLI `presentation … --output deck.html`, `POST /v1/presentations/compile`) compile le deck
depuis des baselines épinglées. La structure est celle d’un cabinet de conseil :

1. la synthèse en tête, avec la décision demandée, puis l’état de la porte prêt-à-construire ;
2. la situation et la complication ;
3. le métier : chaînes de valeur, capacités, parcours ;
4. la solution : blocs, événements et simulation, interfaces et scénarios, sécurité et conformité, technologies ;
5. la réalisation : feuilles de route, gantt du programme, gain de l’IA, RACI ;
6. les finances et les risques ;
7. les décisions et les épingles.

Chaque titre est une conclusion calculée ; aucune formule n’est propre à un pilote. Une simulation sur modèle déclaré,
un critère non tenu ou une mesure absente est dit tel quel. `audience` restreint le deck :

- `SPONSOR` : 10 diapositives ;
- `STEERING` : 16 ;
- `CONTRACT` : 21.

Par défaut, l’outil MCP ne rend que le plan (ghost deck) ; le HTML est pour les personnes et s’écrit par la CLI.

## Corrections issues de la passe ChatGPT 7

Deux sessions de ChatGPT sur le pilote, avec la même demande de comité de pilotage, ont conduit à :

- `air_guide` porte un bloc `delivery` : scénarios et couverture, conformité (dont exigences déléguées),
  effort avec et sans IA, feuilles de route comparées. Les instructions du serveur MCP y renvoient avant toute
  lecture d’objets bruts. La première session avait lu environ 750 Ko d’objets pour recalculer ces chiffres.
- Un `ComplianceMapping` `NOT_APPLICABLE` nomme le projet qui implémente l’exigence (`delegated_to`) ; la vue
  programme le confirme quand ce projet l’implémente.
- Le critère EXTERNAL_DEPENDENCIES compte les emprunts que leur propriétaire a révisés depuis (`behind_latest`,
  informatif). Le deck demande le réalignement dans la synthèse, la porte et les décisions.
- Le deck :
  - dit « date cible » tant que les estimations sont à calibrer ;
  - qualifie en tête une simulation sur modèle déclaré ;
  - dit « affecté » et non « implémenté » pour une correspondance prévue ;
  - dit « passe la marche de conception » et non « conforme » ;
  - présente le gain de l’IA comme une prévision ;
  - sépare le personnel dans l’OPEX ;
  - donne l’état de la porte par projet juste après la synthèse.

## Dépendances entre projets et responsabilité des exigences (0.33.1)

Les deux constats restés ouverts après la passe 7 sont fermés.

- **F96.** Une phase de feuille de route déclare `external_depends_on` vers une phase de la feuille de route d’un
  autre projet, avec un type de lien (`FINISH_TO_START`, `START_TO_START`, `FINISH_TO_FINISH`). La validation du
  graphe refuse des dates incompatibles (`AIR_ROADMAP_EXTERNAL`). `delivery_calc.programme` :
  - vérifie chaque dépendance entre les feuilles de route retenues ;
  - signale une dépendance vers une feuille de route que l’autre projet n’a ni recommandée ni retenue ;
  - trace le chemin critique du programme à travers les projets.

  Le livrable 37 et le gantt du deck le montrent. Sur le pilote, les trois feuilles de route de la fraude commençaient
  avant les phases de la plateforme dont elles dépendent : sept conflits. L’observation, par exemple, démarrait avant
  la fin du MVP sinistres. Elles ont été recalées ; la date de fin du programme est inchangée.
- **F97.** Chaque correspondance est classée par projet :
  - bloc métier ou unité ;
  - composant technique ;
  - les deux.

  `accountable` nomme le rôle responsable. Le livrable 34, le deck et `air_guide` listent les exigences portées
  seulement par l’infrastructure et celles sans responsable. Sur le pilote : 16 correspondances techniques, toutes avec
  un rôle.
- En empruntant les feuilles de route de la plateforme, la fraude recevait par fermeture un contrôle propre à la
  plateforme, et la porte le lui imposait. Le critère COMPLIANCE ne retient désormais que :
  - les sujets du projet ;
  - ceux qu’il cite lui-même ;
  - les entrées des noyaux partagés.

## Skills portables

AIR embarque deux Agent Skills au format ouvert (`SKILL.md` avec frontmatter, `references/`) :

- `air-architecte` : compléter un dossier de solution jusqu’au prêt-à-construire ;
- `air-presentation` : construire, critiquer et mettre à jour le deck.

`air skills-export --target <dépôt> --layout agents|claude|chatgpt [--apply]` les écrit, selon la disposition :

- `agents` : dans `.agents/skills/`, lu par Codex, Cursor, Antigravity, OpenCode, Gemini CLI et d’autres ;
- `claude` : dans `.claude/skills/`, lu par Claude Code ;
- `chatgpt` : en archives zip reproductibles, à téléverser dans ChatGPT ou Claude.ai.

`ide-setup` les ajoute au référentiel, avec les parcours `air-accepter` et `air-presenter`.

## Limites

- La marche vérifie la conception, pas le système construit : les cas TEST des scénarios s’exécutent après la
  construction.
- Les réductions d’effort par l’IA et le prix des postes sont des hypothèses à calibrer sur les premières itérations.
- Le deck est un support : il n’approuve, ne signe et n’engage rien.
- Les noms d’objets restent dans la langue du modèle.
