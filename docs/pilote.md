# Conduire un pilote : trois ou quatre projets, un portefeuille

Ce guide installe un pilote réel avec AIR 0.29 : une installation AIR partagée, un dépôt git par projet
d’architecture de solution, un dépôt pour le socle partagé, et un dépôt central de portefeuille qui indexe les
projets et donne la vue holistique. Il décrit ce qui est livré et ce que la recette `scripts/demo_pilote.py`
vérifie ; les étapes que la recette ne rejoue pas sont marquées **(non rejouée)**, et ce qui n’est pas livré
est dit tel quel dans [Limites](#limites).

## Conventions de ce guide

- `<installation>` est le répertoire où AIR est installé (celui de `scripts/install.py`) ; `<travail>` est le
  répertoire parent des dépôts du pilote.
- `air` désigne `<installation>/.venv/Scripts/python.exe -m air` (Unix : `.venv/bin/python -m air`). Définir
  `AIR_HOME=<installation>/.air` dans l’environnement, ou passer `--home <installation>/.air` à chaque commande.
- Toute commande qui parle au serveur prend `--credential <sujet>.json` : le nom du fichier d’identifiant du
  sujet qui agit. **Jamais `credentials.json`** : c’est l’identifiant d’administration locale, il n’est pas
  déclaré dans la politique du portefeuille et sera refusé une fois celle-ci installée.
- Sur un serveur d’équipe, ajouter `--url https://<hôte>:<port>` et, avec une autorité privée, `--ca-file` ;
  déclarer les mêmes valeurs (`url`, `ca_file`) dans les requêtes `ide-setup`.

## Architecture du pilote

| Élément | Où | Produit par |
| --- | --- | --- |
| Registre AIR : objets, révisions, baselines, jetons, politique | `<installation>/.air` | `scripts/install.py` |
| Dépôt central du portefeuille | `<travail>/portefeuille` | `air portfolio-init` |
| Dépôt de chaque projet et du socle | `<travail>/<code>` | `air workspace-init` depuis `projects/<code>/workspace.request.json` |
| Configuration Claude Code de chaque dépôt | `.mcp.json`, `.claude/`, section de `CLAUDE.md` | `air ide-setup` depuis `claude-code.example.json` complété |
| Vue holistique | `portfolio-index.json`, `docs/portefeuille.md` du dépôt central | `air portfolio-index` |

Une seule instance AIR porte tous les projets. Le dépôt central n’est pas un second registre : il conserve la
déclaration des projets, la politique d’accès, la charte et l’index compilé depuis le registre. La fédération
entre plusieurs instances n’est pas implémentée.

## 1. Installer l’instance partagée

Suivre [installation.md](installation.md). Pour un pilote à plusieurs postes, configurer le
[serveur d’équipe HTTPS](installation.md#serveur-déquipe-https-facultatif) **(non rejouée)** ; sur un seul poste,
l’écoute locale suffit. Vérifier :

~~~sh
air doctor
~~~

`capabilities.portfolio.engine` doit valoir `air.portfolio/0.29`.

## 2. Déclarer le portefeuille

Copier `examples/portfolio.json` dans `<travail>/portfolio.json` et l’adapter : organisation, projets (code,
titre, finalité, namespace, segment d’URN), socle partagé, sujets - un par architecte, avec ses projets en
écriture, les projets qu’il relit (`reviews`) et, pour l’architecte du portefeuille, `shared_write` -, profils
visés, règle de revue. Les codes deviennent les noms des dépôts.

~~~sh
air portfolio-init <travail>/portfolio.json --workspace <travail>/portefeuille --credential portfolio-architect.json
air portfolio-init <travail>/portfolio.json --workspace <travail>/portefeuille --credential portfolio-architect.json --apply
~~~

Le premier appel affiche le plan sans rien écrire. Le second produit onze fichiers communs et trois par dépôt
(projets et socle) : manifeste et requête conservée, conventions, politique d’accès installable, workflow de
contrôle, charte du pilote à compléter, requête d’index vide, un exemple de requête client par dépôt, et pour
chaque dépôt sa requête `workspace.request.json`.

La commande ci-dessus a besoin d’un identifiant : à ce stade la politique n’est pas encore installée, donc
n’importe quel jeton éditeur convient - le plus simple est de créer d’abord celui de l’architecte du
portefeuille (étape 3).

## 3. Créer un identifiant par sujet et installer la politique

Un jeton par sujet déclaré, jamais partagé, jamais recopié. Le nom de sujet doit être exactement celui du
manifeste ; le nom de fichier est `<sujet>.json`. La durée par défaut est de 30 jours : choisir `--days` sur la
durée du pilote, ou prévoir un renouvellement (`token-create` à nouveau, puis `token-revoke` de l’ancien).

~~~sh
air token-create --subject portfolio-architect --role editor --days 120 --name portfolio-architect.json
air token-create --subject architect-D01 --role editor --days 120 --name architect-D01.json
~~~

Sur un serveur d’équipe, les jetons se créent sur le serveur et se remettent à chaque architecte par un canal
privé **(non rejouée)** ; le fichier va dans le répertoire `.air` du poste de l’architecte, sans jamais transiter
par un dépôt ou une conversation.

Installer ensuite la politique produite, sous revue :

~~~sh
air policy-set <travail>/portefeuille/policies/access-policy.json
~~~

À partir de là, chaque sujet déclaré lit tous les namespaces déclarés, écrit dans ses projets, relit ceux où
il est déclaré relecteur ; un sujet non déclaré est refusé sur tout ce qui touche un namespace. La politique
n’accorde jamais les actions engageantes (publication, admission, activation, capacité) : une administration les
ajoute à la main, sujet par sujet, si le pilote le décide. La recette vérifie qu’un architecte de projet ne peut
pas écrire dans le socle, qu’il compile l’index de tout le portefeuille, et qu’un sujet inconnu est refusé.

L’identifiant d’administration locale (`credentials.json`) n’est pas un sujet déclaré : une fois la politique
installée, il ne lit plus le registre. Pour qu’un opérateur garde une lecture de tout le portefeuille, le déclarer
comme sujet sans projet en écriture. Une sauvegarde (`air backup`) ne contient aucun identifiant en clair : après
une restauration, recréer les jetons.

## 4. Créer les dépôts de projet et du socle

Depuis la racine du dépôt central, pour chaque code déclaré, socle compris :

~~~sh
air workspace-init projects/sav/workspace.request.json --workspace <travail>/sav --credential portfolio-architect.json --apply
air workspace-init projects/socle/workspace.request.json --workspace <travail>/socle --credential portfolio-architect.json --apply
~~~

La requête vient du manifeste du portefeuille : namespaces, bases d’URN et identifiants de baseline sont
cohérents entre le central et les dépôts. Chaque dépôt reçoit exactement son domaine ; les objets du socle
vivent dans le dépôt du socle et sont référencés par les projets, jamais recopiés.

## 5. Brancher Claude Code

Chaque dépôt a reçu un `claude-code.example.json` (dans `projects/<code>/` pour un projet, à la racine du
central pour le portefeuille) où tout est renseigné sauf les chemins du poste. Le copier, remplacer
`REMPLACER-PAR-UN-CHEMIN-ABSOLU` par l’interpréteur et la racine `.air` du poste, ajuster le port ou l’origine,
puis :

~~~sh
air ide-setup <travail>/claude-code-sav.json --workspace <travail>/sav --credential architect-D01.json --apply
air ide-setup <travail>/claude-code-portefeuille.json --workspace <travail>/portefeuille --credential portfolio-architect.json --apply
~~~

Un dépôt de projet reçoit le skill, trois commandes et un relecteur ; le dépôt central reçoit le skill de
portefeuille, la commande `/air-portefeuille` qui compile et présente la vue holistique, une commande de relecture
par baseline épinglée et le relecteur - et aucune commande de proposition. Les seize outils engageants restent
refusés par toutes ces configurations. La recette démarre le processus MCP exactement déclaré par le `.mcp.json`
central et obtient les soixante-trois outils ; elle n’exécute pas le client Claude Code lui-même.

## 6. Travailler par dépôt, fermer une baseline, obtenir ses trois valeurs

Dans le dépôt du projet : brouillons typés dans `domains/<code>/drafts` (un squelette valide est dans le README
du répertoire), puis :

~~~sh
air validate domains/sav/drafts/lot-1.json --credential architect-D01.json
air bundle-put domains/sav/drafts/lot-1.json --credential architect-D01.json
~~~

Fermer une baseline avec l’identifiant conventionnel du domaine (`domains/<code>/dossier.json` le donne). La
requête est un objet `air.Baseline` avec `profile`, `members` (chaque objet du lot, identifiant et révision) et
`parent_baselines` ; `fixtures/enterprise/asteria/dossiers/sav/baseline-request.json` en est un exemple complet
**(non rejouée : la recette épingle des baselines déjà fermées)** :

~~~sh
air baseline-create domains/sav/baseline-request.json --credential architect-D01.json
~~~

La réponse porte `baseline.meta.id`, `baseline.meta.revision` et `digest` : ce sont les trois valeurs à épingler.
Pour une baseline déjà fermée, `air baseline-export` les redonne. Une baseline n’est jamais fermée si un objet
membre référence une révision absente du lot.

## 7. Compiler la vue holistique

Dans `portfolio-index.request.json` du dépôt central, épingler la baseline fermée de chaque dépôt :

~~~json
{"baselines": [{"project": "sav", "baseline": {"id": "urn:air:asteria:sav:baseline", "revision": 1, "digest": "sha256:…"}}]}
~~~

Ce fichier ne porte que les épingles ; la CLI y joint la déclaration conservée dans `air-portfolio.request.json`,
si bien qu’un projet ajouté plus tard peut être épinglé sans rien recopier. Puis :

~~~sh
air portfolio-index portfolio-index.request.json --workspace <travail>/portefeuille --credential portfolio-architect.json --apply
~~~

L’index écrit `portfolio-index.json` et `docs/portefeuille.md` : baselines épinglées, objets par type de la
chaîne périmètre → exigence → fonction → contrat → unité → bloc → port → binding → flux, identités partagées avec
accord ou divergence de révision, dépendances entre dépôts comptées une fois par objet référençant, et écarts. Un
projet non épinglé, une baseline épinglée dans le mauvais namespace, un namespace hors déclaration et une
divergence sont bloquants ; un type de chaîne absent est une information. Le résultat vaut `CONSISTENT_AT_PINS` ou
`REVIEW_REQUIRED`.

Pour rafraîchir après de nouvelles baselines, mettre à jour les épingles puis relancer avec
`--apply --replace-generated` : sans cela, le plan montre le diff des deux fichiers de l’index et sort en code 1.
Rien n’est corrigé automatiquement ; une divergence est un point de revue entre les architectes concernés.

## 8. Ajouter un quatrième projet

Ajouter le projet et ses sujets dans `air-portfolio.request.json`, puis régénérer le central, réinstaller la
politique, créer le dépôt, brancher le client, épingler sa baseline :

~~~sh
air portfolio-init air-portfolio.request.json --workspace <travail>/portefeuille --credential portfolio-architect.json --apply --replace-generated
air policy-set <travail>/portefeuille/policies/access-policy.json
air workspace-init projects/<code>/workspace.request.json --workspace <travail>/<code> --credential portfolio-architect.json --apply
~~~

`README.md`, `AGENTS.md`, la charte, les exemples client et la requête d’index appartiennent à l’équipe et sont
conservés ; les fichiers produits sont régénérés. La recette vérifie cette conservation **(sans quatrième projet)**.

## 9. Rythme et versionnement

- Chaque architecte travaille dans son dépôt ; l’architecte du portefeuille relit l’index.
- Toute décision se note dans `docs/charte-pilote.md`, avec ses références exactes.
- Chaque dépôt se versionne séparément dans git ; `.mcp.json` et `.claude/settings.local.json` restent hors du
  dépôt, tout le reste se partage. Aucun jeton, aucun fichier d’identifiant, aucune sauvegarde d’instance dans un
  dépôt.
- Les opérations engageantes (admission, activation, renouvellement, clôture) restent des gestes humains
  authentifiés ; aucun agent ne les détient, même sur l’instance du pilote.
- Sauvegarder l’instance avant chaque changement de politique ou de version : `air backup`.

## Ce que la recette vérifie

`scripts/demo_pilote.py`, enchaînée après `demo_atelier.py`, rejoue ce guide sur les trois dossiers Asteria :
dépôt central compilé identiquement par CLI, API et MCP ; politique installée par `policy-set` ; sujet inconnu
refusé ; architecte de projet refusé en écriture sur le socle mais indexant tout le portefeuille ; quatre dépôts
(trois projets et le socle) produits depuis le manifeste ; adaptateurs Claude Code produits depuis les exemples
complétés, celui du central avec la commande de portefeuille et sans commande de proposition ; processus MCP
déclaré démarré ; index aux trois baselines fermées de projet sans divergence ; puis un objet commun révisé par le
portefeuille, suivi par un projet et pas par l’autre dans deux nouvelles baselines fermées, détecté comme
divergence ; rafraîchissement refusé sans `--replace-generated` ; régénération du central conservant la requête
d’index de l’équipe ; index identique après sauvegarde et restauration. Voir
preuve de réception (document historique ou livrable local non inclus).

## Limites

- Une seule instance AIR ; pas de fédération, pas d’index entre instances.
- L’index est exact aux baselines épinglées ; il ne suit pas les brouillons et ne se rafraîchit pas seul.
- Un accord de révision n’est pas une compatibilité sémantique ; celle-ci n’est pas exécutée.
- Le client Claude Code n’est pas qualifié ; les autres familles d’IDE n’ont pas d’adaptateur.
- Les scénarios métier restent décrits, non exécutés ; aucune conformité AIR n’est revendiquée.
- Windows et PostgreSQL 18.6 sont qualifiés ; les autres systèmes, un IdP réel et un proxy d’entreprise ne le sont pas.
- Aucun pilote réel n’a encore été conduit avec cette version.
