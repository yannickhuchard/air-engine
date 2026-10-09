# UX04 : reprendre une question avec un agent

Plan du 4 octobre 2026, après la fusion de UX03 par la
[PR #12](https://github.com/yannickhuchard/air/pull/12), commit
`0b30ab2713f7dc5483661f138e00b7790de6a8eb`.

Le site doit permettre de choisir une question, son public et ses sources,
puis de télécharger une capsule JSON ou de copier une demande explicite.
La capsule conserve namespace, baseline et sources avec révision et empreinte.
Elle ne contient ni connexion, ni identité présumée, ni jeton, ni chemin privé.
La préparation fonctionne hors ligne et ne contacte aucun assistant.

Le service partagé CLI/API/MCP vérifie cette capsule contre le registre
actuellement authentifié. Il produit un reçu de contexte déterministe avec
l'identité liée à l'installation, le rôle et la politique observée. Un reçu est une
observation exportable, sans signature ni mandat. À chaque nouvelle conversation,
AIR relit les sources et vérifie le reçu, sans faire confiance à sa prose.

Une préparation de changement peut être attachée à cette reprise : vérifier
son auteur, sa baseline et ses namespaces, puis relire les protections existantes
avant dépôt et fermeture. Ces deux écritures restent des appels explicites aux
services existants, avec leurs contrôles de droits, immutabilité et idempotence.
La vérification de contexte seule n'est pas une transaction de dépôt.

Le squelette de travail ajoute `questions/`, `reviews/` et `handoff/` par domaine.
Ses fichiers d'accueil sont amorcés et préservés ; la CLI peut sauvegarder un
reçu dans un nouveau fichier, sans écraser un document existant. Les capsules
contiennent des métadonnées internes : partager uniquement avec les destinataires
autorisés. Changer le branding ne constitue pas un cloisonnement par client.

Réception prévue : altération de pin et de reçu, source hors baseline, mauvaise
identité/installation, namespace et accès refusés, préparation étrangère ou
obsolète, reprise entre deux sessions, dépôt et fermeture idempotents, préservation
des fichiers locaux. Trois dossiers Asteria sur mobile et bureau, sans JavaScript
et hors ligne. La qualification native du connecteur et les séances utilisateurs
restent distinctes, respectivement UX00 et UX05.


## Utiliser les capsules

Ouvrir `cooperate.html` dans le dossier exact, ou « Discuter cette question »
dans l’un des six parcours. Le JSON téléchargé est une requête `{capsule}`.
La copie comporte une demande à vérifier avec l’agent et ce même JSON. Les
sources restent consultables par leurs définitions ; l’éditeur n’envoie rien.
Une capsule de départ par sujet est disponible même sans JavaScript.

Lire `air_whoami`, `air_capabilities`, puis `air_resume_question`. Conserver
`{capsule, previous_receipt}` pour reprendre ; joindre éventuellement l’identifiant
`prepared_change` du rebase. Le même contexte produit le même reçu. Un autre
acteur, installation, rôle, politique, namespace, pin ou source exige un
nouveau diagnostic explicite. La capsule reste une donnée modifiable : son
empreinte ne prouve pas une origine authentifiée ni l’approbation de son texte.

La CLI authentifiée `question-resume question.json --output reprise.json`
sauvegarde un nouveau fichier, sans remplacer l’existant. Les capsules, les
reçus et les notes sont propres au domaine. Le squelette `workspace-init` amorce
les répertoires `questions`, `reviews` et `handoff`, puis préserve les notes.
Son workflow reste manuel, sans déclencheur push ou PR.

La politique locale par défaut permet une lecture large. Le cloisonnement
entre clients exige des identités/homes propres et une politique de namespaces
explicite. Des clones conservant le même identifiant d’installation et les mêmes
pins ne sont pas distingués par une empreinte de capsule : gérer les identités
opérationnelles des installations reste nécessaire.

## Réception locale du 4 octobre 2026

UX04 est reçu dans sa portée locale. La suite de 111 tests est passante, puis
les huit tests de capsule repassent après l’ajout du rôle au reçu. Elle vérifie
les pins altérés, les changements d’identité/installation/rôle/politique, les
sources et namespaces, les préparations étrangères ou obsolètes, le dépôt et
la fermeture explicites idempotents, ainsi que la préservation des fichiers.

Les trois dossiers Asteria proposent 111 capsules de départ. Douze lectures
navigateur couvrent 320, 390, 768 et 1 440 pixels, avec question modifiée,
sélection de sources, téléchargement, empreinte, liens exacts et navigation
clavier. Les trois pages gardent leurs capsules sans JavaScript. Les 111 capsules
et les 12 téléchargements sont vérifiés et repris par l’API authentifiée avec
trois identités en lecture seule. Six lectures entre namespaces sont refusées
avec une politique explicite. Ces opérations ne modifient aucune révision
d’architecture ; les identifiants de recette sont révoqués après utilisation.

La PWA conserve 513 ressources épinglées. Coopération, fiches de transmission,
graphes, récits et dossiers fonctionnent hors ligne. La première recette a
détecté une présélection de question inaccessible hors ligne ; le worker accepte
désormais uniquement les paramètres `topic` et `audience` de `cooperate.html`,
pour les mêmes octets épinglés. Les autres requêtes paramétrées ne sont pas
ajoutées au cache. Mise à jour explicite, refus de génération incomplète et
effacement limité au périmètre restent vérifiés.

Les 242 pages, leurs liens et fragments et les 513 empreintes sont vérifiés.
Modèle, graphe, questions, récit et projection de transmission restent identiques
à UX03. Voir les preuves (document historique ou livrable local non inclus) et les captures
mobile (document historique ou livrable local non inclus) et
bureau (document historique ou livrable local non inclus).

Reproduction locale, dans un répertoire de démonstration neuf sous `tmp/` :

```powershell
python scripts/demo_architecture_site.py --output tmp/ux04-reception
```

Lancer `scripts/qualify_question_capsules.cjs` avec ce `site-demo.json`, un
répertoire `browser`, Edge et Playwright installés pour le développement, puis
`python scripts/qualify_question_context.py tmp/ux04-reception/site-demo.json`.
Le script API refuse une base fournie par `AIR_DATABASE_URL` et une politique
préexistante. `scripts/qualify_architecture_pwa_browser.cjs` reçoit aussi le
manifeste de cette démonstration. Edge, Node et Playwright restent des outils de
recette optionnels ; l’installation et la génération AIR utilisent Python seul.

Aucune CI, recette native ChatGPT/Claude, certification WCAG, séance avec un
participant ou installation PWA au niveau du système d’exploitation. UX00
reste ouvert pour le connecteur, UX05 pour la réception formative. Les gates
Asteria restent `NOT_READY` et leurs neuf tests métier originaux non exécutés.
Les réussites techniques du site ne les remplacent pas. La distribution publique
rc9 et le plugin installé ne sont pas requalifiés par cet incrément.

Le [protocole UX05](ux05-recette-utilisateurs.md) prépare les séances suivantes,
sans présenter un participant ni un résultat humain fictif.

Changements livrés dans la [PR #13](https://github.com/yannickhuchard/air/pull/13).
Le reçu local conserve son état observé avant publication.
