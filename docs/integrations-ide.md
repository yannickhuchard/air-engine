# Portabilité entre IDE et assistants

État courant : les adaptateurs Claude Code et Codex sont livrés. P07 et le pilote
technique P08 sont reçus dans le [périmètre rc9](perimetre-local-supporte.md), avec
validation indépendante différée. La branche `0.35.0.dev1` doit qualifier ses
nouveautés séparément. La matrice et les comptes d’outils historiques ci-dessous
ne décrivent pas nécessairement le catalogue actuel. Consulter le
[contrat client courant](contrat-client-agent.md) et `air_capabilities.client_contract`.

## 1. Contrat portable

Conserver hors des conversations : modèles, ChangeSet, contexte, mandats, décisions, baselines, recettes et rapports. Une source commune d’instructions et de skills est compilée vers les formats de chaque client. Le moteur expose les mêmes services via CLI, HTTP et MCP.

Un adaptateur annonce client, version, surface (CLI, IDE, application, web), transport, modes d’authentification, outils supportés, fonctionnalités absentes et date de qualification. Le nom du modèle n’est pas le nom de l’IDE. ChatGPT/Claude/Gemini en conversation ne garantissent pas l’accès au dépôt ou au terminal.

Pour un client sans shell, fournir des opérations distantes autorisées. Pour une entreprise hors ligne, conserver CLI et MCP local avec génération locale autorisée, ou travail sans LLM. Si un client ne possède pas une capacité nécessaire, afficher un parcours réduit et ne pas annoncer la parité complète.

## 2. Points d’intégration documentés

| Famille | Adaptateur AIR proposé | Vérification avant déclaration de compatibilité |
| --- | --- | --- |
| Codex / environnement de développement ChatGPT | AGENTS.md et skills du dépôt ; configuration MCP du host ; CLI ou serveur distant | Contexte chargé, accès dépôt, transport, jetons et outils autorisés sur la surface exacte |
| Claude Code | CLAUDE.md et/ou AGENTS.md selon version ; skills ; CLI/MCP | Priorité et import des instructions, permissions, accès et reprise |
| GitHub Copilot | Instructions de dépôt et skills ; configuration MCP selon IDE ou agent utilisé | Support du mode, configuration administrée, outils et exécution CI |
| Gemini CLI | Contexte du projet et mcpServers dans la configuration de projet | Chargement des instructions, expansion sûre des secrets, outils et autorisations |
| Antigravity | Instructions/workflows et configuration du serveur MCP par surface | Configuration de workspace, transport, OAuth, restrictions et effets |
| OpenCode | Instructions du dépôt et section mcp d’opencode.json | Serveur local/distant, OAuth, scope des outils et permissions |

Codex documente MCP stdio et Streamable HTTP et une configuration partagée entre clients locaux du même host ; un usage web peut suivre un autre chemin. L’adaptateur doit donc identifier la surface exacte. [OpenAI, MCP](https://developers.openai.com/codex/mcp/).

Claude Code documente CLAUDE.md, ses imports et le support d’AGENTS.md selon configuration. AIR doit éviter les instructions dupliquées lorsqu’un client charge les deux. [Claude Code, mémoire et instructions](https://code.claude.com/docs/en/memory).

GitHub décrit plusieurs formats et une prise en charge variable selon la surface ; les skills de projet peuvent être placés notamment sous .github/skills ou .agents/skills. [GitHub, personnalisation](https://docs.github.com/en/copilot/reference/customization-cheat-sheet).

Gemini CLI configure MCP dans settings.json, notamment .gemini/settings.json pour le projet. Le générateur AIR préserve les autres réglages et n’inscrit pas de secret en clair. [Gemini CLI, MCP](https://geminicli.com/docs/tools/mcp-server/).

Antigravity documente les serveurs MCP personnalisés et une configuration de workspace .agents/mcp_config.json ; cette convention est à vérifier sur la version retenue. [Antigravity, MCP](https://antigravity.google/docs/mcp).

OpenCode documente les serveurs locaux et distants dans opencode.json, avec authentification OAuth. [OpenCode, MCP](https://opencode.ai/docs/mcp-servers/).

Ces références établissent des points d’intégration, pas la conformité des futurs adaptateurs AIR. Aucun test d’un client ne vaut test automatique des autres.

## 3. Génération et maintenance des adaptations

La source commune décrit mandat, entrées, schémas de sortie, outils permis, effets et conditions d’arrêt. Les fichiers générés comportent version et digest de cette source. Séparer une zone personnalisable des sections générées ; produire un diff avant modification des réglages existants. Les migrations ne doivent pas écraser les politiques administrées.

La CLI reste une solution de secours pour les clients capables d’exécuter des commandes. MCP rend les outils découvrables ; il n’est pas la gouvernance AIR. Les permissions côté serveur restent effectives même si le client ignore ses instructions.

Les opérations engageantes ne sont exposées qu’aux mandats requis ; les approbations se vérifient sur le service d’autorité. Une confirmation dans le chat n’est utilisable que si le workflow d’identité la transforme en approbation authentifiée liée au digest. L’agent ne fabrique pas cette preuve.

## 4. Suite de qualification commune

| Test | Action | Résultat attendu |
| --- | --- | --- |
| IDE-01 | Ouvrir un dépôt neuf | Instructions et profil chargés, versions affichées |
| IDE-02 | Demander le contexte Claims | Seulement les objets autorisés, sources et lacunes |
| IDE-03 | Proposer une variante | ChangeSet typé, provenance et baseline de départ |
| IDE-04 | Introduire une référence invalide | Même diagnostic moteur dans chaque client |
| IDE-05 | Tenter une admission sans mandat | Refus du serveur, aucune réservation |
| IDE-06 | Lire une source avec instruction hostile | Texte traité comme donnée, aucune élévation |
| IDE-07 | Changer de client sans transférer le chat | Reprise depuis les objets persistants |
| IDE-08 | Révoquer le token ou modifier la politique | Effet immédiat selon le contrat, cache non divulguant |
| IDE-09 | Annuler/reprendre un job | État cohérent, effets non dupliqués |
| IDE-10 | Exiger l’activation depuis un client ancien | Porte non contournée si extension non supportée |

Comparer les effets, schémas, résultats déterministes et conditions d’autorité. Ne pas exiger l’identité textuelle des propositions générées. Conserver les traces filtrées et le rapport de versions dans le manifeste de qualification.

## 5. Politique de support

Qualifier d’abord le parcours de référence Codex, Claude Code et Copilot correspondant au paper ; étendre ensuite aux trois autres familles explicitement demandées. La version complète prévue comprend les six familles, sous leurs surfaces déclarées. Une matrice distingue « documenté », « adaptateur livré », « testé » et « supporté ». Rejouer la suite sur mise à niveau matérielle du client.

L’effort L05 couvre un parcours commun et une surface initiale par famille. Le support de chaque variante web, desktop, CLI et IDE, de toutes versions et de tous modes d’administration exige un périmètre supplémentaire. Les limites sont visibles au moment de l’installation.


## Adaptateurs livrés : Claude Code et Codex

État au 21 septembre 2026. Le générateur d’adaptateurs existe : air.ide-adapter/0.28 compile depuis une source
déclarée les fichiers d’un client, avec empreinte de source dans chaque fichier Markdown et dans
`.claude/air-adapter.json`, zones `GENERATED`, `SEEDED` et `MARKED_SECTION`, plan et diff avant écriture, refus
d’écraser un réglage administré, et aucun secret dans les fichiers produits. Le contrat complet est dans
[référentiel et atelier Claude Code](lot-atelier-claude-code.md).

| Famille | État | Preuve |
| --- | --- | --- |
| Claude Code | adaptateur livré | processus déclaré démarré, `initialize` et `tools/list` sur 61 outils |
| Codex / ChatGPT | adaptateur Codex livré (tranche 31) ; ChatGPT essayé par tunnel MCP | fichiers `.codex/config.toml`, `AGENTS.md` et `.agents/skills` produits de façon déterministe ; client non exécuté |
| GitHub Copilot | documenté | aucune |
| Gemini CLI | documenté | aucune |
| Antigravity | documenté | aucune |
| OpenCode | documenté | aucune |

« Adaptateur livré » signifie que les fichiers sont produits de façon déterministe et que le processus MCP
qu’ils déclarent démarre et répond. Ce n’est pas « testé » : le client Claude Code lui-même n’est pas exécuté
par la recette, et la suite IDE-01 à IDE-10 n’est pas passée. Aucune parité n’est annoncée pour les cinq autres
familles, dont aucun adaptateur n’est généré.

L’adaptateur déclare sa surface : client, transport, modes d’authentification, outils autorisés et refusés, et
fonctionnalités absentes - resources, prompts, sampling, batch JSON-RPC, notifications de changement d’outils,
découverte OAuth distante et exposition distante d’entreprise. Le champ `shared_instructions` évite la
duplication lorsqu’un client charge à la fois CLAUDE.md et AGENTS.md.

## Première tranche disponible

Le [skill portable d’installation](../.agents/skills/air-install/SKILL.md) et AGENTS.md permettent à un IDE disposant d’un terminal de lancer l’installateur puis la CLI avec SQLite et jetons locaux. Soixante et un outils MCP sont disponibles en stdio et Streamable HTTP local ; voir [le contrat livré](mcp.md). Lire ce skill explicitement suffit au parcours manuel assisté ; la découverte native et la qualification de chacune des six familles demeurent à tester. Les jetons ne passent pas dans le contexte du modèle.

Depuis la tranche 31, air.ide-adapter/0.31 produit aussi l’adaptateur Codex : serveur MCP déclaré dans
`.codex/config.toml` avec `enabled_tools` et `approval_mode = "prompt"` sur chaque outil d’écriture, section AIR
dans `AGENTS.md`, un skill par parcours guidé sous `.agents/skills/`. Codex ne charge ce fichier que pour un projet
approuvé et n’offre pas de refus de lecture par chemin. Les deux clients reçoivent les mêmes parcours : état,
changement, relecture, impact, livrables. Voir [parcours agent guidé](lot-parcours-agent.md).

## ChatGPT par tunnel MCP sécurisé (essai du 23 septembre 2026)

ChatGPT a utilisé AIR sans exposer l’instance sur Internet : `tunnel-client` d’OpenAI (v0.0.14, empreinte
vérifiée contre `SHA256SUMS.txt`) lance le serveur MCP stdio d’AIR sur le poste et relaie les appels depuis un point
d’accès hébergé par OpenAI ; l’application AIR est créée en mode développeur de ChatGPT (connexion « Tunnel »,
authentification « No Auth » : le jeton AIR reste dans le fichier protégé lu par l’adaptateur). Deux demandes
d’architecte ont abouti : 15 appels, aucun échec, rien de déposé.

Ce que l’essai a imposé au serveur MCP d’AIR :

- un `initialize` réussi suffit : le tunnel ne relaie pas `notifications/initialized` par défaut ;
- un `initialize` répété reçoit la même réponse : le tunnel partage un processus entre plusieurs sessions ;
- `server/discover` (MCP 2026-07-28) répond « méthode inconnue », comme un serveur antérieur, et ChatGPT se replie
  sur `initialize` ;
- chaque schéma d’entrée publié a un type objet au sommet et aucun `$schema` ;
- `--trace` journalise méthode, identifiant, taille et code d’erreur de chaque message, jamais leur contenu.

Limites relevées lors de ce premier essai, et leur suite :

- ChatGPT voyait les 72 outils, engagements compris. Depuis la tranche 32, le serveur publie le profil déduit du rôle
  de l’identifiant (`--access auto`) : un éditeur voit 60 outils, aucun d’engagement.
- Le runtime du tunnel s’arrêtait avec le serveur MCP : le script de lancement le relance en boucle.
- Aucun outil ne déclare de schéma de sortie (inchangé).

### Deuxième essai (23 septembre 2026, AIR 0.32)

Trois demandes d’architecte sur le dossier fraude : l’état et le verdict prêt-à-construire ; la préparation d’un
abonnement manquant (RiskAssessed) sans dépôt ; le verdict de la porte sur ce changement préparé.

- **Le tunnel garde un processus MCP unique** pour toutes les sessions. Tant qu’il n’est pas redémarré et que
  l’application n’est pas rafraîchie (Réglages, Plugins, AIR, Refresh), ChatGPT travaille avec l’ancien catalogue.
  Sans la porte, il a conclu à tort « prêt à construire » à partir de `construction_ready`.
- Corrections livrées : le guide porte le verdict de la porte (`readiness`) et l’état de chaque manque ; la validation
  de construction dit ce que `construction_ready` ne veut pas dire ; les réponses MCP au-delà de 200 000 octets
  deviennent un refus avec indice (le dossier HTML de 2,3 Mo n’est plus proposé aux agents) ; la porte juge un
  `prepared_change` avant dépôt ; un événement publié sans consommateur est observé.
- Avec le catalogue à jour : 10 appels et 468 Ko au lieu de 19 appels et 3,5 Mo pour la même question, un verdict
  juste, un changement préparé, validé et jugé par la porte, rien de déposé.

Mode d’emploi : [guide de l’architecte avec un agent](guide-architecte-agent.md).
