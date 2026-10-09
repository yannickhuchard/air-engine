# AIR · Architecture Workspace

<img src="assets/logo.png" alt="Logo AIR" width="112">

**Votre assistant vous accompagne du besoin métier au dossier d’architecture vérifiable.**

Plugin officiel AIR, créé par **Yannick Huchard**, sous Apache-2.0. Il apporte deux skills : installer/connecter le moteur, puis concevoir et faire évoluer votre dossier. Le moteur reste sur le poste ou dans l’environnement choisi par votre organisation.

## Commencer en quatre étapes

1. **Installer le moteur :** [air-engine](https://github.com/yannickhuchard/air-engine), Python 3.11+, puis `python scripts/install.py --start`. SQLite et identité locale sont les valeurs par défaut.
2. **Installer ce plugin :** télécharger le paquet depuis [les releases](https://github.com/yannickhuchard/air-plugin/releases) ou utiliser la marketplace de votre client.
3. **Connecter votre projet :** demander au skill `air-local-setup` de configurer la connexion MCP. Installer un plugin ne connecte pas automatiquement ChatGPT à votre poste.
4. **Construire le dossier :** décrire votre besoin, puis laisser l’assistant vous guider sur les informations et preuves manquantes.

> « Utilise AIR pour concevoir ce projet. Pose les questions une par une, conserve les choix et leurs conséquences, vérifie la préparation et génère le site du dossier. »

## Comment le plugin vous guide

L’assistant lit la version réelle du dossier, identifie les écarts, prépare les objets et vous aide à décider. Le moteur vérifie le modèle. Les sources et révisions restent traçables ; une conversation seule n’est pas le référentiel.

Avec un moteur disposant des fonctions récentes, vous pouvez aussi demander :

> « Actualise les News, les points de décision et les questions ouvertes, puis prépare les vidéos de cette version. »

`air_query_project_updates` lit ces informations ; `air_compile_deliverables` régénère le site ; `air_refresh_videos` prépare les compositions sourcées. Le rendu MP4 utilise un atelier optionnel via `air videos-refresh ... --apply --render`. Ces fonctions nécessitent le moteur 0.35 de développement ; elles ne sont pas ajoutées à rc9 par l’installation du plugin. Vérifier le catalogue du serveur avant de les appeler.

## Choisir votre client

| Client | Connexion |
| --- | --- |
| Codex | Plugin et MCP du projet ; ouvrir une nouvelle conversation après installation |
| Claude Code | Skills et MCP du projet ; format de plugin Claude disponible dans ce paquet |
| ChatGPT | Skills et connexion MCP distante autorisée ; le moteur local doit être accessible au client |
| Autre IDE agentique | CLI/MCP et skills portables, selon les capacités du client |

Pour Claude Code, charger le dossier en développement avec `claude --plugin-dir ./plugins/air-local`. Une marketplace propre au projet permet aussi la distribution. Voir le README à la racine du dépôt public pour les commandes. Ce format n’établit pas une présence dans la marketplace officielle Anthropic ni une recette native de Claude.

## Versions, données et support

Paquet source **0.1.8** ; moteur et plugin ont des versions indépendantes. Le dossier ProxiBot et les fonctionnalités récentes restent des exemples de développement. L’[annuaire ChatGPT](https://github.com/yannickhuchard/air-plugin/blob/main/submission/README.md) a sa propre revue ; distribution GitHub et approbation de plateforme sont distinctes.

Un freelance conserve une installation, une identité et un référentiel séparés par client. Les installations ne se synchronisent pas automatiquement. Les extraits envoyés à un modèle cloud suivent les règles de ce fournisseur et de votre organisation. Aucun jeton ni endpoint privé n’est inclus dans ce plugin.

[Moteur](https://github.com/yannickhuchard/air-engine) · [Plugin public](https://github.com/yannickhuchard/air-plugin) · [Support](https://github.com/yannickhuchard/air-plugin/issues) · [Confidentialité](https://github.com/yannickhuchard/air-plugin/blob/main/PRIVACY.md) · [Licence](LICENSE)
