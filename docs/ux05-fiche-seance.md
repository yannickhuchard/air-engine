# UX05 : fiche de séance à remplir après observation

Copier cette fiche dans `reviews/` du dossier de travail, hors du dépôt publié.
Une fiche vierge, un parcours automatisé ou une simulation par un agent ne
constitue pas une séance avec un participant. Ne publier que la synthèse
expurgée. Le [protocole](ux05-recette-utilisateurs.md) définit la modération et
les critères de décision.

## Contexte

| Champ | Valeur à observer |
| --- | --- |
| Statut | `NOT_EXECUTED` tant que la séance n’a pas eu lieu |
| Identifiant anonyme | À renseigner, sans nom ni adresse |
| Accord pour la séance et les notes | À recueillir avant observation |
| Vague | 1 ou 2 |
| Responsabilités couvertes | COMEX, métier, DSI, architecture entreprise, architecture solution, réalisation |
| Dossier | SAV, atelier ou identités Asteria |
| Baseline | Copier `{id, revision, digest}` depuis le manifeste du site |
| Version du site | Empreinte du pack et commit de développement |
| Client | Surface exacte et version, connexion effectivement constatée |
| Lecture | Écran, clavier/tactile, navigateur, réseau/hors ligne |
| Modérateur | Identifiant interne, à conserver uniquement dans les notes privées |

Contrebalancer dossiers et ordre des tâches entre les séances. Ne pas demander
à une personne qui a conçu la fonction de représenter seule son public cible.
Une même personne couvrant plusieurs responsabilités ne compte qu’une fois
dans l’effectif des participants.

## Tâches

Donner l’objectif sans annoncer le bouton ni la page à utiliser. Pour chaque
tâche, noter ce qui s’est réellement passé. Un obstacle de connexion se
consigne comme obstacle ; le remplacer par un test API ne reçoit pas la tâche.

| Tâche donnée | Résultat autonome / aidé / échec / non exécuté | Temps réellement observé | Sources retrouvées | Reformulation, erreur ou aide donnée |
| --- | --- | --- | --- | --- |
| Expliquer l’intention du dossier et un bénéfice attendu | À observer | À mesurer | À observer | À observer |
| Suivre un mécanisme jusqu’au contrat et au composant | À observer | À mesurer | À observer | À observer |
| Retrouver une décision et une information manquante | À observer | À mesurer | À observer | À observer |
| Préparer une transmission aux équipes de réalisation | À observer | À mesurer | À observer | À observer |
| Préparer une question sourcée et vérifier son contexte dans le client | À observer | À mesurer | À observer | À observer |
| Reconnaître un contexte incompatible et arrêter l’écriture | À observer | À mesurer | À observer | À observer |
| Retrouver le même focus sur mobile et hors ligne | À observer | À mesurer | À observer | À observer |

Pour le COMEX : arbitrage, valeur et risque. Pour le métier : résultat et
changement de travail. Pour la DSI : qualité, engagements et exploitation.
Pour l’architecture entreprise : capacités, principes et trajectoire. Pour
l’architecture solution : mécanismes et données. Pour la réalisation :
interfaces, dépendances, responsabilités, critères et vérifications.

## Décision après la séance

| Élément | Observation et décision |
| --- | --- |
| Citation expurgée | À consigner uniquement si réellement prononcée |
| Difficulté de compréhension ou d’accès | À décrire avec la tâche et sa source |
| Gravité et portée | Mauvais dossier, divulgation, dépôt indu, preuve mal comprise ou difficulté d’accès |
| Correction proposée | À relier à l’observation, avec responsable et priorité |
| Nouveau parcours requis | Tâche, public, dossier et version à rejouer |
| Tâches non exécutées | À conserver explicitement |

La synthèse donne les effectifs et les résultats **par tâche, public et vague**.
La cible de 85 % proposée dans l’audit ne devient un résultat qu’après mesure ;
elle ne doit pas masquer un petit échantillon. Les deux vagues et les 16
participants proposés restent une cible de recrutement, pas une preuve reçue.
La préparation technique actuelle ne reçoit ni UX05, ni une certification
d’accessibilité, ni les neuf tests métier Asteria.
