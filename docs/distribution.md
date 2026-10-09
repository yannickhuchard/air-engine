# Distribuer AIR : paquet, serveur MCP, agents et skills

La branche principale publique fournit désormais les sources 0.35.0.dev1 de
développement. La release rc9 reste disponible sur son tag, avec ses preuves
propres. Voir [l’état courant](etat-implementation.md) et [sa validation](validation.md).

Pour l’historique de la distribution libre à des architectes sans accès au dépôt privé, lire
l’[évaluation et les lots D01–D06](distribution-publique-chatgpt.md). Le plugin
et le moteur rc9 sont publics ; le parcours d’annuaire ChatGPT reste à recevoir.
Voir [la distribution livrée et validée](distribution-publique-livree.md).

Le [plugin officiel AIR Local](plugin-air-local.md), développé par Yannick Huchard,
regroupe les parcours d'installation et de conception pour les postes autonomes.
Sa distribution est indépendante du moteur et des connexions privées par projet.

La candidate 0.34.0rc9 suit le [contrat P05](lot-distribution-reproductible.md), avec artefacts et
preuves rattachés au commit exact. Voir le [périmètre local publié](perimetre-local-supporte.md)
pour la distribution effectivement testée et les limites de réception des clients natifs.

Ce guide installe AIR depuis sa roue Python et branche chaque agent sur le même serveur MCP local. Les jetons ne
figurent jamais dans une configuration : le processus MCP lit lui-même son fichier d’identifiant sous le répertoire
AIR (`--credential <nom>.json`).

## 1. Construire et installer le paquet

Depuis le dépôt du moteur :

~~~sh
python scripts/build_release.py --output-dir dist/candidate
~~~

Sur le poste cible, avec Python 3.11 ou plus :

~~~sh
python -m venv .venv
.venv/Scripts/python.exe -m pip install -c constraints.txt <wheel-AIR-verifie>   # Unix : .venv/bin/python
.venv/Scripts/python.exe -m air --home .air bootstrap
.venv/Scripts/python.exe -m air --home .air doctor
~~~

Le paquet installe deux commandes :

- `air` : CLI et serveur HTTP ;
- `air-mcp` : serveur MCP en stdio.

Il embarque les skills portables et les ressources du dossier HTML. Pour les options indépendantes
`postgres`, `oidc` et `proofs`, utiliser l’installateur livré : `--wheel <wheel-verifie> --extras postgres,oidc`.
Le mode `--wheelhouse` prépare une installation sans index depuis les dépendances déjà présentes.

Identifiant de l’agent (lecture seule par défaut) :

~~~sh
air --home .air token-create --subject <agent> --role reader --name <agent>.json
~~~

## 2. Serveur MCP commun

Commande à déclarer dans chaque client, avec des chemins absolus :

~~~text
<python> -m air.mcp --home <.air> --credential <agent>.json [--access auto|read|contribute|guided|all]
~~~

`--access auto`, le défaut, expose les actions accordées par le rôle **et** la politique courante.
Un administrateur ne reçoit pas implicitement les mandats métier. `read`, `guided`, `contribute` et `all`
ne peuvent pas augmenter ses droits. Les contrôles sur les namespaces, preuves et propriétaires restent
exécutés par le serveur à chaque appel ; voir [P04](lot-identites-mcp.md).

## 3. Brancher chaque agent

| Agent | Fichier | Forme |
| --- | --- | --- |
| Claude Code | `.mcp.json` à la racine du dépôt | `{"mcpServers": {"air": {"command": "<python>", "args": ["-m", "air.mcp", "--home", "<.air>", "--credential", "<agent>.json"]}}}` |
| Codex | `.codex/config.toml` | `[mcp_servers.air]` avec `command` et `args` ; `air ide-setup` le produit avec `AGENTS.md` et `.agents/skills/` |
| Cursor | `.cursor/mcp.json` | même forme que Claude Code |
| OpenCode | `opencode.json` | `{"mcp": {"air": {"type": "local", "command": ["<python>", "-m", "air.mcp", "--home", "<.air>", "--credential", "<agent>.json"], "enabled": true}}}` |
| Antigravity | `mcp_config.json` de l’utilisateur (voir la [documentation MCP d’Antigravity](https://antigravity.google/docs/mcp/)) | `{"mcpServers": {"air": {"command": "<python>", "args": [...]}}}` |
| ChatGPT | connecteur MCP distant par tunnel sécurisé | voir [intégrations IDE](integrations-ide.md#chatgpt-par-tunnel-mcp-sécurisé-essai-du-23-septembre-2026) ; profil `--access guided` ou `read` |

Pour un référentiel d’architecture, préférer `air ide-setup` : il produit la configuration, les permissions, le
skill du référentiel, les parcours guidés et les skills portables de façon déterministe
([atelier Claude Code](lot-atelier-claude-code.md)).

## 4. Installer les skills portables

~~~sh
air skills-export --target <dépôt> --layout agents --apply    # .agents/skills : Codex, Cursor, Antigravity, OpenCode, Gemini CLI
air skills-export --target <dépôt> --layout claude --apply    # .claude/skills : Claude Code
air skills-export --target <dossier> --layout chatgpt --apply # un zip par skill : ChatGPT, Claude.ai
~~~

Sans `--apply`, la commande affiche le plan (`CREATE`, `UPDATE`, `UNCHANGED`) et n’écrit rien. Les skills sont :

- `air-architecte` : compléter un dossier de solution jusqu’au prêt-à-construire ;
- `air-presentation` : deck de direction bilingue, critique, clôture contractuelle.

## 5. Vérifier une installation

1. `air doctor` est vert et `air --home .air serve` répond sur `http://127.0.0.1:8740/health`.
2. L’agent liste les outils `air_*`, dont `air_guide`, `air_walk_scenarios` et `air_compile_presentation`.
3. `air_guide` sur une baseline rend son verdict `readiness`.
4. Après une mise à jour d’AIR, redémarrer le processus MCP et rafraîchir le catalogue du client.

## Ce qui n’est pas couvert

- Les binaires et installateurs natifs (MSI, Homebrew) ne sont pas produits.
- Les formats de configuration et parcours par pont MCP ne qualifient pas les clients natifs.
  La réception ChatGPT, Claude Code, Claude.ai et Codex reste P07, avec une preuve distincte par client.
