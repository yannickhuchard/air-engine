# Audit UX du projet d’architecture AIR et du travail avec les agents

Audit du 3 octobre 2026, destiné à Yannick Huchard et aux responsables du produit AIR.

AIR possède une base de consultation fiable, sourcée et portable. Le site présente
encore principalement les catégories du modèle ; il doit devenir un outil pour
comprendre, décider et préparer la réalisation. La priorité est de rendre une
réponse utile accessible à chaque public, avec ses sources et ses limites. Le
design visuel et l’animation doivent renforcer cette compréhension.

Le parcours du plugin a un blocage observé : le connecteur refuse une référence
URN valide avant son arrivée au moteur. Il répond pourtant à l’identité et aux
capacités. Ce problème est prioritaire pour l’usage agentique.

## Portée et méthode

Inspection du site généré depuis les trois dossiers fictifs Asteria : SAV,
maintenance connectée et arrivées/mobilités/départs. La génération comporte
185 pages HTML et 48 diagrammes. 38 pages distinctes ont été examinées à 390 et
1440 pixels, soit **76 observations navigateur**. Captures d’écran, inspection
du contenu et du code, parcours du récit, contrôles de navigation et consultation
des guides d’installation, du plugin, de l’adaptateur et du travail avec l’agent.

Le navigateur de test Edge utilise un contexte isolé et les fichiers générés.
Ce n’est pas l’observation d’une session de travail du propriétaire du navigateur.
La commande de Computer Use sur le navigateur existant a échoué à l’initialisation.
Les appels au plugin AIR connecté ont été réalisés dans Codex ; ils ne constituent
pas une nouvelle recette native ChatGPT ou Claude.

**Zéro participant humain observé.** Il s’agit d’un audit expert et d’un plan de
recherche, pas de résultats d’entretiens ou de tests utilisateurs. Les besoins
des publics sont des hypothèses de travail à confronter aux participants.
Les priorités et objectifs chiffrés ci-dessous sont proposés. Aucun score global
d’utilisabilité, certificat WCAG ou benchmark de performance n’est annoncé.

Le site audité appartient au développement 0.35.0.dev1. La réception locale rc9,
les versions du plugin et la maturité d’un dossier de solution sont trois états
distincts. Les trois portes de la démonstration sont NOT_READY ; le dossier
décrit un design destiné à une réalisation ultérieure.

## Ce qui fonctionne déjà

- Aucune erreur JavaScript ni requête réseau externe sur les 76 observations.
- Aucun débordement horizontal du document aux deux largeurs examinées.
- Navigation mobile repliable ; liens explicites vers les diagrammes et sources.
- Baselines et modèles exacts exportés ; les versions ne sont pas fusionnées.
- Récit en six chapitres, lecture volontaire, pause et navigation par chapitre.
  Le chapitre choisi par son lien reste sélectionné après rechargement.
- Graphe typé, filtres, voisinage, zoom, miniature et accès aux sources.
- La préférence de mouvement réduit donne un défilement immédiat dans la portée
  contrôlée. La recette PWA antérieure reste une preuve distincte : cet audit
  n’a pas rejoué une installation système ou la synchronisation des caches.
- L’agent dispose d’un parcours existant : orienter, changer, relire, examiner
  les impacts, vérifier et livrer. Validation et préparation précèdent le dépôt.

Ces observations établissent une base technique utile. Elles ne mesurent pas
encore si un directeur ou un ingénieur trouve la bonne réponse sans assistance.

## Questions à servir pour chaque public

Les durées sont des **cibles proposées pour les tests**, pas des résultats mesurés.

| Public | Question principale | Réponse attendue dans le site | Premier parcours proposé |
| --- | --- | --- | --- |
| COMEX | Pourquoi investir, quel changement, quelles décisions nous reviennent ? | Valeur attendue, options, coût et horizon avec leurs hypothèses, risques majeurs, arbitrages et décision demandée | Une synthèse de décision, puis les preuves ; réponse essentielle en 90 secondes |
| Direction métier et senior managers | Que change le projet dans mon activité, pour mes équipes et mes partenaires ? | Avant/après, parcours, exceptions, responsabilités, dépendances métier, indicateurs et changements organisationnels | Parcours métier illustré, puis conséquences et décisions |
| DSI | Que devons-nous engager et maîtriser pour livrer puis exploiter ? | Coûts, trajectoire, dépendances SI, sécurité, qualité de service, exploitation, capacités d’équipe et points bloquants | Vue de réalisation, risques et exploitation |
| Architecte d’entreprise | Le projet respecte-t-il les capacités, principes et frontières du groupe ? | Capacités impactées, domaines, dépendances partagées, standards, propriétaires et écarts | Carte du programme, comparaison et décisions transverses |
| Architecte de solution | Comment les mécanismes, contrats et données répondent-ils aux exigences ? | Parcours sourcés, contrats, modèles logiques/physiques, hypothèses, contraintes, diagnostics et alternatives | Question métier, chemin du mécanisme, sources exactes |
| Équipes de réalisation | Que faut-il implémenter, dans quel ordre, avec quels critères de réception ? | Unités de construction, interfaces, responsabilités, dépendances, scénarios, NFR, risques et tests planifiés | Dossier de réalisation par équipe et composant ; réponse en cinq minutes |

L’équipe de réalisation regroupe des besoins différents : développeurs, chef de
projet, QA, sécurité et exploitation. Une simple vue « technique » ne suffit pas.
Les vues par public doivent rester des lectures de la même baseline. Elles ne
constituent pas un système de contrôle d’accès.

## Constats et priorités

P0 : blocage d’un parcours essentiel. P1 : risque de mauvaise décision ou tâche
essentielle difficile. P2 : amélioration de compréhension ou de finition.
L’importance est un jugement d’audit ; la fréquence auprès des utilisateurs
n’est pas encore mesurée.

| ID | Priorité | Observation et preuve | Conséquence probable, à valider | Recommandation |
| --- | --- | --- | --- | --- |
| UX-F01 | P0 | Le plugin répond à `whoami` et `capabilities`, puis `list_revisions` refuse un identifiant AIR URN issu d’un reçu P07 avec `INVALID_ARGUMENT`, avant le moteur | L’architecte peut croire à un problème d’identité ou inventer une autre référence | Tester le contrat publié et le catalogue réellement chargé ; fournir un diagnostic ciblé, sans contourner la validation |
| UX-F02 | P1 | 71 outils AIR sont chargés ; le compilateur de branding est absent et le schéma de livrables chargé n’expose pas `branding`, `website` ou `comparisons` | Les nouvelles tâches peuvent être impossibles ou perdre leurs paramètres | Montrer la compatibilité moteur/plugin/catalogue ; vérifier les outils et paramètres requis, au-delà du numéro de version |
| UX-F03 | P1 | Accueil : namespace, nombre de sujets/diagrammes, NOT_READY et « Explorer le graphe » ; aucune entrée explicite par public | Le lecteur non architecte doit décider seul où chercher sa réponse | Entrées « Décider », « Comprendre le changement », « Préparer la réalisation », « Explorer l’architecture » |
| UX-F04 | P1 | Le dossier offre 37 sujets et 43 liens de navigation, regroupés par facette | La structure demande de connaître le classement du modèle | Navigation principale par questions ; catalogue complet accessible comme niveau de détail |
| UX-F05 | P1 | Sur le graphe, le canevas commence vers y=927 px à 1440 px de large et y=1529 px à 390 px de large, dans une fenêtre haute de 1000 px | Une page de visualisation présente d’abord beaucoup de commandes | Montrer immédiatement un diagramme focalisé ; filtres avancés repliés, scénarios et voisins comme actions contextuelles |
| UX-F06 | P1 | NOT_READY, DRAFT, SYNTHETIC_UNCALIBRATED, namespaces et codes de critères apparaissent dans la lecture | Le niveau de préparation et le niveau de preuve peuvent être confondus | Libellé humain, raison et prochaine action ; conserver le code exact dans les détails |
| UX-F07 | P1 | Dans la démo : aucun CostItem ou Milestone, pas de matrice RACI d’exploitation ni de NFR dans les pages examinées | Le site ne peut pas répondre au COMEX, à la DSI ou aux équipes sur ces points | « Non renseigné », question précise, responsable à désigner et conséquence ; ne pas inventer un budget ou un calendrier |
| UX-F08 | P1 | `_detail` transforme toute présence de `reason` en « rien à construire dans ce projet ». Pour COMPLIANCE, la vraie raison est l’absence de contrôle/exigence qualité applicable | Une explication de critère peut contredire l’existence d’une unité de construction | Traduire la raison par code et état, avec conservation du détail exact ; vérifier la restitution des cas sans objet |
| UX-F09 | P2 | L’HTML affiche `_Aucun élément._` et « Racine d’organisation non déclarée ... None » | La présentation expose des restes techniques au lieu d’aider à compléter | États vides structurés, aucune valeur Python ni marque Markdown visible |
| UX-F10 | P2 | L’accueil de dossier répète la même phrase sous intention, résultat attendu et valeur ; c’est aussi présent dans les données fictives | Les trois concepts semblent équivalents | Signaler les informations trop similaires dans l’atelier éditorial ; ne pas fabriquer une différenciation par reformulation |
| UX-F11 | P2 | Le récit SAV compte 742 mots visibles à l’ouverture ; son lecteur dure 24 secondes et déroule six phases | Le teaser peut être pris pour le mode de lecture de tout le dossier | Lecture normale par défaut ; teaser séparé, scénarios animés ciblés, tempo réglable et transcript |
| UX-F12 | P1 | Le site a des recherches de dossiers, objets et parcours, mais pas de recherche couvrant questions, décisions, risques et livrables | Trouver une réponse nécessite de choisir d’abord le bon type de page | Index statique transversal, termes métier et ontologie ; distinguer correspondance trouvée et réponse manquante |
| UX-F13 | P1 | Pas de transfert de question du site vers l’agent avec contexte épinglé dans la navigation examinée | Copie manuelle, baseline oubliée ou confusion entre dossiers | Bouton « Préparer une question pour mon agent », avec projet, baseline, sujet et références exactes |
| UX-F14 | P1 | Le guide agent parle de 31 documents ; le catalogue actuel en contient 37. Installation et intégrations indiquent encore P07 en qualification/ouvert, tandis que le périmètre rc9 reçu indique sa clôture | Un nouveau venu doit arbitrer entre plusieurs états présentés comme courants | Guide de démarrage canonique par version et surface ; dater et ranger les preuves historiques sans les effacer |
| UX-F15 | P1 | La description commune des outils connectés parle d’un pilote fictif d’assurance santé alors que le site consulté est Asteria Industrie ; l’authentification est celle du banc P07 | Risque de croire que le plugin est connecté au projet affiché | Bandeau de contexte visible : entreprise, home logique, namespace, rôle, baseline et surface du client ; identité graphique distincte de l’isolation des données |
| UX-F16 | P2 | Les pages réutilisent principalement texte, tables, cartes et contrôles ; le récit est une succession de chapitres, pas une explication animée du mécanisme | La promesse visuelle reste faible malgré une bonne lisibilité | Une direction artistique centrée sur la carte de transformation et des diagrammes de focus, avec animations explicatives contrôlées |

Les manques du jeu de démonstration ne prouvent pas l’absence de ces types dans
AIR. CostItem, Milestone, RaciAssignment et QualityRequirement existent. Le
problème associe données incomplètes, restitution et aide à la collecte.

Le rejet URN observé ne prouve pas que le moteur refuse cet identifiant. Le code
`published_schema` retire déjà le format URI trop restrictif du schéma publié,
et les tests locaux existent. La cause exacte entre catalogue conservé et
contrainte de plateforme reste à confirmer. Aucun contournement par changement
d’identifiant n’a été tenté.

L’identifiant de cet appel provient du reçu synthétique P07 de transmission
ChatGPT vers Codex. Le rejet intervient avant la lecture du registre : son
existence actuelle dans le registre connecté n’a donc pas été revérifiée.
Ce registre de test est distinct des baselines du site Asteria audité.

## Architecture de l’information recommandée

Une entrée de projet montre d’abord : le changement voulu, les dossiers concernés,
les questions importantes, les décisions attendues et ce qui empêche d’avancer.
Le lecteur choisit ensuite une intention. Il peut changer de public sans perdre
son dossier, sa version ou le sujet en cours.

```text
Projet d’architecture
  Comprendre le changement : valeur, avant/après, parcours, conséquences
  Décider : options, arbitrages, coûts, risques et décisions demandées
  Préparer la réalisation : composants, responsabilités, ordre, critères et tests
  Explorer l’architecture : capacités, domaines, contrats, données et graphes
  Voir ce qui change : comparaison de baselines et calendrier déclaré
  Examiner les preuves : sources, hypothèses, inconnues et vérifications
```

Les 37 sujets restent accessibles en deuxième niveau. Chaque page de focus suit
le même contrat éditorial : **question, réponse courte, diagramme, mécanisme,
choix, conséquences, prochaine action, sources**. Une réponse manquante l’indique
au même endroit qu’une réponse disponible.

Exemple réel de question SAV : « Comment éviter deux propositions pour une même
demande ? ». L’Unknown sur la clé ERP, l’hypothèse sur l’identifiant de soumission
et la conséquence déclarée de déduplication complémentaire alimentent la réponse.
Le site doit montrer ce qui reste à confirmer plutôt qu’annoncer une garantie
de déduplication déjà obtenue.

Les états éditoriaux proposés sont : renseigné, partiel, non renseigné, hors
périmètre explicitement déclaré et contradictoire. Ils accompagnent les codes
du moteur sans les remplacer. Zéro poste de coût signifie absence de postes
déclarés, pas coût nul. Une approbation est montrée uniquement si son reçu existe.

## Direction artistique et animation

Je recommande un univers de **carte de transformation**, lisible comme un dossier
de direction et précis comme un plan d’architecture. Un seul élément visuel fort
par écran : une carte annotée ou un parcours. Les panneaux techniques apparaissent
à la demande ; les tableaux restent disponibles pour le travail de détail.

Palette de référence à adapter au branding : encre `#10343d`, papier `#f5f8f9`,
accent `#75d7c4`. Couleurs d’ontologie conservées : composants bleus, données
violettes, fonctions vertes et décisions/risques ambre, avec libellés et légende.
Ces choix sont une proposition ; les paramètres de l’entreprise font autorité.

Titres nets, hiérarchie de trois niveaux, paragraphes courts, alignement à gauche,
espaces qui séparent les étapes du raisonnement. Police locale de la marque avec
repli système ; une police embarquée n’est pas présentée comme déjà prise en
charge par AIR. Corps recommandé de 16 à 18 pixels pour la lecture, à vérifier
au zoom ; le site audité utilise actuellement 15 pixels.

| Interaction | Animation proposée | Information rendue compréhensible |
| --- | --- | --- |
| Ouvrir une question | Apparition brève de sa réponse et du diagramme focalisé | Où commencer et ce qui répond à la question |
| Lire un parcours | Mise en évidence étape par étape, seulement après lancement | Qui porte chaque étape, quel contrat et quelle donnée circulent |
| Examiner une décision | Alternative et conséquence mises en regard | Ce que le choix change et ce qu’il sacrifie |
| Comparer deux baselines | Ajouter/retirer/modifier avec texte et légende | Ce qui a changé dans le design, sans prétendre observer la production |
| Découvrir le projet | Trailer BRAG volontaire de 20 à 25 secondes | Donner envie d’examiner le dossier ; aucune preuve de maturité implicite |

Une impulsion de parcours est une explication, pas la simulation d’une transaction
réelle. Pas de musique automatique, défilement imposé, caméra permanente ou effet
3D décoratif. La 2D est la vue par défaut. Une future 3D doit aider à lire une
dimension définie ; le temps sépare historique du design, dates de validité et
calendrier prévu. Ces vues ne sont pas déclarées livrées par cet audit.

Transitions proposées de 150 à 220 ms ; les animations de parcours sont
pilotables, réversibles et arrêtables. Préférence de mouvement réduit : état
final immédiat et explication textuelle. WCAG 2.2.2 est de niveau A ; 2.3.3 sur
les animations déclenchées par interaction est de niveau AAA. Viser WCAG 2.2 AA
et ajouter ce contrôle de mouvement est une cible de conception, pas une
certification de l’existant. [W3C pause](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html),
[W3C animation](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html).

## Dossier de travail et coopération avec ChatGPT ou Claude

Le registre reste la source d’autorité ; le dépôt conserve les demandes, brouillons,
reçus et livrables utiles. La conversation devient le poste de travail temporaire.
Le site est la lecture partagée d’un instantané. Il ne devient pas un registre
modifiable ou un système de collaboration en temps réel sans une évolution reçue.

Structure cible compatible avec les conventions existantes :

```text
AGENTS.md                        règles communes et lecture initiale
air-workspace.json               domaines, namespaces et conventions
branding/                        identité de présentation
domains/<code>/dossier.json      baseline et périmètre du dossier
domains/<code>/brief.md          question, objectifs et frontières
domains/<code>/sources/          références et imports autorisés
domains/<code>/drafts/           changements préparés, encore non déposés
domains/<code>/questions/        questions ouvertes proposées, liées aux sources
domains/<code>/reviews/          demandes et reçus de revue, statut explicite
domains/<code>/handoff/          attentes des équipes et réponses épinglées
docs/livrables.request.json      requête de génération versionnée
livrables/site/                  consultation générée
```

`questions/`, `reviews/` et `handoff/` sont des extensions proposées, pas des
artefacts déjà automatiquement créés. Les homes privés, identités et jetons
restent séparés du dépôt. Un consultant utilise un contexte isolé par client ;
changer de logo n’isole ni les données ni la connexion.

Le parcours guidé recommandé :

1. **Vérifier le contexte** : identité, entreprise, domaine, rôle, version du
   moteur, catalogue requis et baseline. Afficher les écarts avant de répondre.
2. **Poser une question métier** : demander les sources nécessaires et les
   absences, plutôt qu’exporter tout le registre.
3. **Proposer un changement borné** : objets concernés, hypothèses et impacts.
4. **Valider et préparer** : diagnostics, références, comparaison et readiness
   de la proposition ; aucun statut de succès déduit de la qualité de la prose.
5. **Présenter le résultat à l’architecte** : changement, conséquences, reste à
   décider et prochaine action. Employer l’autorisation déjà reçue pour ce
   résultat ; ne pas demander des confirmations répétées sans raison.
6. **Déposer, figer et régénérer** selon le workflow autorisé. Un reçu indique
   baseline, état et fichiers ; les modifications locales sont protégées.
7. **Transmettre aux équipes** : lecture par rôle, contrats, tests planifiés,
   responsabilités et limites ; demandes de clarification ramenées dans AIR.

ChatGPT conversationnel sans terminal peut demander une compilation mais ne
matérialise pas, par cela seul, un pack HTML sur le poste. Le guide doit séparer
lecture MCP, préparation du pack et écriture locale par un IDE/CLI autorisé.
Claude Code et Claude conversationnel sont aussi des surfaces distinctes.
Le support d’un adaptateur ne vaut pas recette de l’interface native. Claude
reste retiré des clients requis P07 ; sa présence dans le plan de recherche
n’annule pas cette décision.

Exemple de question préparée depuis le site :

> Dans le dossier SAV Asteria et sur la baseline exacte fournie, explique le
> chemin de la mise à jour de l’adresse de correspondance. Sépare les étapes
> déclarées, les composants et contrats associés, les conditions non évaluées
> et les informations manquantes. Cite les révisions. Ne modifie aucun objet.

La capsule à copier/exporter contient la référence exacte réelle, la question,
les sources sélectionnées et la politique de lecture. Elle ne contient ni
jeton ni chemin privé. Si la connexion ne reconnaît pas cette baseline, elle
doit s’arrêter avec un diagnostic de contexte, sans inventer un autre identifiant.
Un lien vers ChatGPT ou Claude ne peut pas garantir à lui seul le bon plugin,
l’identité, la connexion ou l’import du contexte.

Une vue destinée au COMEX doit appliquer une politique d’export avant génération
si certaines informations sont restreintes. Masquer un panneau ou sélectionner
un public n’empêche pas la lecture du JSON exact livré avec le site actuel.
Les variantes expurgées autorisées sont donc un travail distinct à concevoir.

## Recherche avec de vrais utilisateurs

Recommandation : deux vagues formatives, **16 participants au total**. Deux COMEX,
deux managers métier, deux DSI, deux architectes d’entreprise, deux architectes
de solution et six personnes de réalisation couvrant développement, projet,
qualité, sécurité/exploitation. Adapter le recrutement à la disponibilité sans
présenter une couverture inexistante. Cette taille n’établit pas une validation
statistique générale.

Entretiens de 20 à 30 minutes : dernière décision ou transmission réelle,
documents utilisés, question la plus difficile, mécanisme de confiance et
informations sensibles. Éviter « aimez-vous ce design ? » comme question principale.
Ensuite, séances de 35 à 45 minutes avec tâches et verbalisation. Utiliser des
dossiers distincts et contrebalancer actuel/prototype pour limiter l’apprentissage.

| Tâche | Public principal | Critère proposé |
| --- | --- | --- |
| Expliquer la valeur, un risque et une décision à prendre | COMEX/métier | Bonne réponse ou absence reconnue en 90 s ; sources retrouvables |
| Trouver la trajectoire, un coût manquant et la responsabilité de le préciser | DSI/projet | Aucun coût nul ou délai inventé ; prochaine action compréhensible |
| Suivre le changement d’adresse et identifier un contrat | Solution/développement | Chemin sourcé ou absence expliquée en 3 min ; aucune causalité fictive |
| Identifier le propriétaire d’une capacité ou donnée partagée | Entreprise/solution | Référence exacte et bonne frontière de responsabilité |
| Préparer un changement puis reprendre dans une nouvelle conversation | Architecte | Même baseline et mêmes diagnostics ; changement non perdu |
| Refuser une connexion sur le mauvais client ou un catalogue incompatible | Architecte/consultant | Aucun dépôt dans le mauvais contexte, aucune reference de remplacement inventée |
| Trouver ce qui doit être construit et testé pour un composant | Développement/QA/ops | Critères, contrats et inconnues retrouvés en 5 min |
| Lire et partager un focus sur mobile et au clavier | Tous | Navigation sans assistance ; conservation du contexte et accès aux sources |

Mesurer réussite, temps, erreurs de compréhension, aide nécessaire et facilité
perçue après tâche. **Cible proposée : au moins 85 % de réussite des tâches
critiques sans assistance ; aucune fausse déclaration « prêt à construire » ni
écriture dans le mauvais client.** Présenter les effectifs par tâche/public,
pas un pourcentage agrégé qui masquerait un petit échantillon. Le zéro incident
observé ne prouve pas un risque nul.

Pas de télémétrie centralisée obligatoire. Recueillir les résultats dans un
protocole local, avec accord des participants et uniquement les données utiles.
Inclure une revue clavier/zoom/lecteur d’écran et des contrastes sur les marques
retenues. La recette automatisée reste un complément aux séances.

## Lots recommandés

| Lot | Priorité et résultat | Critère de sortie proposé |
| --- | --- | --- |
| UX00 | P0, contrat client et démarrage : URN, catalogue, contexte, guide courant | Trois lectures réelles par le plugin avec refs exactes ; paramètres requis conservés ; panne expliquée sans identifiant inventé |
| UX01 | P1, contenu et navigation par questions/publics | Six parcours de lecture, réponses/missing states sourcés ; coût absent distinct de zéro ; 37 sujets conservés |
| UX02 | P1, design et diagrammes de focus | Une carte utile au premier écran ; modèle responsive, clavier et mouvement réduit ; couleurs ontologiques préservées |
| UX03 | P1, transmission aux équipes | Dossier par composant/équipe avec responsabilités, contrats, dépendances, critères et tests ; limites visibles |
| UX04 | P1, coopération site/agent et reprise | Capsule de question épinglée, dépôt protégé, reçus, reprise interconversation et isolation par client vérifiés |
| UX05 | Réception formative et publication du périmètre | Deux vagues d’utilisateurs, corrections prioritaires, recette des trois dossiers, versions et surfaces explicitement reçues |

Commencer UX00 et UX01 ensemble. Le travail de contenu peut avancer pendant la
résolution du catalogue. UX02 s’appuie sur leurs contrats, puis UX03/UX04, avec
tests formatifs intermédiaires avant UX05. Pas d’estimation en jours sans
cadrage des personnes disponibles. Aucune CI déclenchée par cet audit.

Une maquette de lecture (document historique ou livrable local non inclus) rend concrète la
direction proposée. Elle est exploratoire et explicitement séparée du générateur
livré. Elle montre des informations Asteria fictives et leurs manques ; elle
ne qualifie aucune nouvelle fonction du plugin ou du moteur.

## Sources et preuves

Inspection : `src/air/architecture_site.py`, `src/air/deliverables.py`,
`src/air/readiness.py`, assets du site, `src/air/mcp.py`, `src/air/agent.py`,
`docs/guide-architecte-agent.md`, `docs/installation.md`,
`docs/integrations-ide.md`, `docs/perimetre-local-supporte.md`,
`plugins/air-local/README.md`. Le périmètre des fonctions reste décrit dans
`docs/etat-implementation.md`.

Reçu synthétique : audit UX (document historique ou livrable local non inclus).
Reproduction optionnelle, après génération des dossiers fictifs :

```text
node scripts/audit_architecture_ux.cjs <site-demo.json> <sortie-privee> <navigateur-test> <module-playwright>
```

Node, Edge et Playwright sont des outils de cet audit, pas des dépendances
obligatoires d’installation AIR. Les captures et rapports complets du banc
restent dans `tmp/ux-audit-final-20261003` ; les quatre captures illustratives
sélectionnées dans `docs/assets/ux-audit-20261003` contiennent seulement Asteria.

Références de méthode : l’audit applique une inspection heuristique et la
divulgation progressive des détails, sans convertir ces références en preuves
sur AIR. [NN/g heuristiques](https://www.nngroup.com/articles/ten-usability-heuristics/),
[NN/g divulgation progressive](https://www.nngroup.com/articles/progressive-disclosure/),
[NN/g tests utilisateurs](https://www.nngroup.com/articles/usability-testing-101/).
La cible d’accessibilité utilise [WCAG 2.2](https://www.w3.org/TR/WCAG22/).

!Accueil actuel du projet sur bureau (document historique ou livrable local non inclus)

!Premier écran actuel du graphe (document historique ou livrable local non inclus)
