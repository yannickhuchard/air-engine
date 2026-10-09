# Portefeuille de projets et pilote - tranche 29

Contrat de service expérimental air.portfolio/0.29, intégré et réceptionné dans le sous-périmètre de la recette
`scripts/demo_pilote.py`. Il répond au besoin d’un pilote réel : trois ou quatre architectures de solution, chacune
dans son dépôt, et un dépôt central qui les indexe et donne la vue holistique. Il n’ajoute ni type persistable ni
table SQL ; il ne crée aucun objet, aucune baseline et aucun droit. Tous les projets partagent une même instance
AIR : la fédération entre instances (L11) reste non implémentée.

## Dépôt central - `compile_portfolio`

La requête déclare l’organisation (nom, préfixe d’URN, préfixe de namespace), le portefeuille (nom, description),
un à soixante-quatre projets, un socle partagé facultatif, des sujets facultatifs (jusqu’à 256 : sujet
authentifié d’un motif sûr, libellé, projets en écriture, projets relus, écriture sur le socle), les profils
visés et la règle de revue. Codes, namespaces et segments d’URN sont uniques entre projets et socle ; chaque
namespace commence par le préfixe de l’organisation ; un sujet ne peut nommer qu’un projet déclaré, deux sujets
ne diffèrent pas seulement par la casse, et `shared_write` exige un socle déclaré.

Le produit compte onze fichiers communs et trois par dépôt - chaque projet et le socle ont le leur :

| Fichier | Zone | Contenu |
| --- | --- | --- |
| `air-portfolio.json` | GENERATED | manifeste : projets avec bases d’URN, identifiants conventionnels et dépôt, socle, sujets, profils, drapeaux |
| `air-portfolio.request.json` | GENERATED | la requête exacte, pour ajouter un projet ou un sujet puis régénérer |
| `docs/conventions-portefeuille.md` | GENERATED | une instance, plusieurs dépôts ; table des projets ; vue holistique ; politique d’accès ; sujets |
| `policies/access-policy.json` | GENERATED | politique installable : chaque sujet déclaré lit tous les namespaces déclarés, écrit dans ses projets, relit ceux déclarés et, s’il y est autorisé, écrit dans le socle ; aucune action engageante |
| `.github/workflows/air-check.yml` | GENERATED | contrôle que les manifestes sont du JSON et qu’aucune clé `access_token` n’apparaît dans un JSON versionné |
| `projects/<code>/workspace.request.json` | GENERATED | requête `workspace-init` du dépôt : exactement son domaine, mêmes conventions que le portefeuille |
| `projects/<code>/README.md` | SEEDED | comment produire le dépôt et le brancher |
| `projects/<code>/claude-code.example.json`, `claude-code.example.json` | SEEDED | requêtes `ide-setup` où tout est renseigné sauf les chemins du poste ; refusées telles quelles |
| `README.md`, `AGENTS.md`, `.gitignore` | SEEDED | parcours, règles d’agent, versionnement, exclusions ; aucun projet n’y est cité pour ne pas devenir faux |
| `docs/charte-pilote.md` | SEEDED | charte à compléter : objectif, périmètre, mandats, cas interdits, oracles, journal des décisions, critères d’arrêt |
| `portfolio-index.request.json` | SEEDED | les épingles seules (`{"baselines": []}`) ; la CLI y joint la déclaration du dépôt central, jamais périmée |

Sans sujet déclaré, la politique produite reste un exemple non installable, comme dans le référentiel de projet.
La politique produite est vérifiée par le test comme chargeable par `AccessPolicy` ; elle n’accorde rien tant
qu’une administration ne l’installe pas avec `policy-set`. Le rapport indique la politique **effective de
l’appelant** sur chaque projet, sans en créer.

## Vue holistique - `index_portfolio`

La requête porte la déclaration du portefeuille et, par dépôt - projet ou socle -, une baseline épinglée
exactement : identifiant, révision et empreinte. Par la CLI, le fichier d’épingles peut omettre la déclaration :
elle est jointe depuis `air-portfolio.request.json` du dépôt central. Un dépôt épinglé deux fois ou inconnu est
refusé ; une empreinte différente de la baseline exportée est un conflit. Chaque baseline est lue à travers la
politique de l’appelant : un sujet sans droit de lecture sur un namespace rencontré est refusé pour l’ensemble,
jamais servi partiellement.

Par dépôt indexé, l’index rapporte la baseline (nom, namespace, profils), le nombre d’objets et leur répartition
par type, les namespaces observés et ceux hors déclaration, la couverture de la chaîne de conception (`Scope`,
`Requirement`, `Function`, `SemanticContract`, `ConstructionUnit`, `ArchitectureBlock`, `Port`, `TechnicalBinding`,
`DataFlow`), les inconnues bloquantes et les assertions contestées. Une baseline enregistrée est fermée par
construction : le registre refuse d’en créer une autre. Entre dépôts, il calcule les identités partagées - un
même identifiant dans au moins deux baselines épinglées - en accord (même révision et même empreinte) ou en
divergence, et les dépendances : références exactes d’un objet vers un objet d’un autre namespace, comptées une
fois par objet référençant, quel que soit le nombre de baselines qui le contiennent. Les écarts sont typés :
`NO_BASELINE_DECLARED`, `BASELINE_NAMESPACE_MISMATCH`, `NAMESPACE_OUTSIDE_DECLARATION`,
`SHARED_IDENTITY_VERSION_DIVERGENCE` (bloquants, revue requise) et `CHAIN_TYPE_ABSENT` (information). Le résultat
vaut `CONSISTENT_AT_PINS` ou `REVIEW_REQUIRED`.

L’index est une fonction pure du registre aux épingles et de la requête : aucune horloge, aucune lecture de
brouillon, et son empreinte ne dépend pas du poste ni de la chaîne de génération, rapportée à part ; la recette
vérifie qu’une copie restaurée de l’instance produit la même empreinte d’index. Il produit deux fichiers
`GENERATED` - `portfolio-index.json` et `docs/portefeuille.md` - que la CLI écrit par le même plan que les autres
produits : un index périmé est un `CONFLICT` avec diff, code de sortie 1, et se remplace avec
`--apply --replace-generated`.

## CLI, API, MCP et client

`air portfolio-init` et `air portfolio-index` prennent `--workspace`, `--apply` et `--replace-generated` avec les
codes de sortie de la tranche 28. L’API expose `POST /v1/portfolios/compile` et `POST /v1/portfolios/index` ; le
catalogue MCP compte 63 outils avec `air_compile_portfolio` et `air_index_portfolio`, tous deux en lecture. Le
test de partition de l’adaptateur couvre ces deux outils.

L’adaptateur Claude Code accepte `workspace.kind` : `project` (défaut) ou `portfolio`. Pour un dépôt central, le
skill décrit le parcours du portefeuille - manifeste, épingles, index, approfondissement par dépôt, rapport des
écarts sans correction -, la commande `/air-portefeuille` compile et présente la vue holistique, la commande de
relecture et le relecteur partent de la baseline épinglée, et aucune commande de proposition ni de dossier de
domaine n’est produite. La section générée de `CLAUDE.md` renvoie au manifeste. Les règles de refus de
`.claude/settings.json` ne portent aucun chemin du poste, pour que le fichier se partage. Les seize outils
engageants restent refusés.

## Recette

`scripts/demo_pilote.py`, enchaînée après `demo_atelier.py`, rejoue le pilote sur une copie de l’instance Asteria :
dépôt central compilé identiquement par CLI, API et MCP, politique installée par `policy-set`, sujet inconnu
refusé à l’index, architecte de projet refusé en écriture sur le socle et indexant tout le portefeuille, quatre
dépôts - trois projets et le socle - produits depuis le manifeste avec leur namespace conventionnel, adaptateurs
produits depuis les exemples complétés (projet en `contribute`, central en `portfolio` sans commande de
proposition), processus MCP déclaré démarré et listant 63 outils, index aux trois baselines d’architecture
(88 objets chacune, valeur observée) - trois projets indexés, chaîne complète, toutes les identités partagées en
accord, `CONSISTENT_AT_PINS` -, puis un objet commun créé par le portefeuille et révisé, suivi par le projet `atelier` et
non par `sav` dans deux nouvelles baselines fermées, détecté comme divergence unique avec `REVIEW_REQUIRED` ;
plan de rafraîchissement en `CONFLICT` avec code 1, remplacement explicite, requête d’index de l’équipe conservée
par la régénération, anciennes baselines inchangées, index identique après sauvegarde et restauration. Voir
preuve de réception (document historique ou livrable local non inclus) et le guide [pilote.md](pilote.md).

## Limites visibles

Une seule instance ; aucune fédération, aucun index entre instances. L’index ne suit pas les brouillons. Un accord
de révision n’est pas une compatibilité sémantique, qui n’est pas exécutée. La politique produite n’est effective
qu’installée. Le client Claude Code n’est pas exécuté par la recette ; les autres familles d’IDE n’ont pas
d’adaptateur. Les scénarios métier ne sont pas exécutés ; aucune conformité AIR n’est revendiquée. Les contenus
produits sont en français.
