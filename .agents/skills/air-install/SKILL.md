---
name: air-install
description: Installer la distribution publique AIR sur un poste, vérifier SQLite et identité locale, puis démontrer les trois dossiers fictifs Asteria ou préparer une connexion agent.
---

# Installer AIR public

Lire README.md, docs/installation.md et docs/validation.md depuis la racine du dépôt.
Utiliser la source officielle https://github.com/yannickhuchard/air-engine et une
version publiée identifiée ; vérifier les empreintes des archives téléchargées.

Avec Python 3.11+, lancer `python scripts/install.py --start` depuis cette racine.
Le script préserve les identités et révisions existantes. Ne pas effacer `.air` pour
réinstaller. Les options `postgres`, `oidc`, `proofs`, `backup`, `dev` sont explicites
et indépendantes ; aucune n’est indispensable au premier démarrage SQLite/local.

Lire les jetons uniquement par programme depuis leurs fichiers protégés, jamais
dans le contexte du modèle. Utiliser `.venv/Scripts/python.exe` sur Windows et
`.venv/bin/python` sur Unix. Contrôler doctor ; une réponse health ne reçoit pas
à elle seule une installation de production ou les permissions de l’agent.

Pour découvrir AIR, lire fixtures/enterprise/asteria/README.md puis lancer le parcours
dans un dossier de sortie neuf sous tmp. Présenter séparément les succès techniques,
les portes métier bloquées et les neuf scénarios non exécutés.

Pour connecter un agent, suivre docs/agents.md. Une configuration MCP générée ne
prouve pas que le client l’a chargée. Ne pas annoncer de connexion ChatGPT, d’accès
à l’annuaire ni de prise en charge d’un tunnel sans essai sur la surface réelle.
