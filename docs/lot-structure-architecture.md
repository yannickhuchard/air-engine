# Structure d’architecture - tranche 26

Contrat expérimental air.architecture/0.26 réceptionné dans ce sous-périmètre : 437 tests passaient alors sur SQLite et PostgreSQL 18.6. Il ajoute ArchitectureBlock, TechnicalBinding, Port, DataFlow, RequiredOutput et ArchitectureGap, selon les pages 46–47 du white paper. Les 51 types de données précédents restent disponibles ; les anciens profils restent figés. Aucun changement du schéma SQL 6.

## Modèle et contrôles

ArchitectureBlock distingue SYSTEM, SUBSYSTEM, MODULE, ADAPTER, GATEWAY, STORE et EXTERNAL_SYSTEM. Fonctions, contrats fournis/requis et états possédés sont des références exactes. Les responsabilités et collections de références sont canonicalisées comme ensembles.

Port déclare une direction PROVIDED ou REQUIRED, un bloc, un contrat et ses bindings. Le contrat exact doit figurer dans la collection correspondante du bloc ; chaque binding doit viser le même contrat exact. Les objets absents ou de mauvais type sont refusés à la fermeture.

TechnicalBinding utilise ici le protocole HTTP, versions 1.1, 2 ou 3, et le record air.http-json-mapping/0.26. Chaque mapping nomme une opération du contrat, une méthode GET/POST/PUT/PATCH/DELETE, un chemin littéral, un DataSchema de réponse et un statut 200/201/202 ; le DataSchema de requête est facultatif mais, lorsqu’il est présent, request_required doit déclarer explicitement si le corps est obligatoire. GET/DELETE avec corps de requête, routes paramétrées, segments relatifs, doublons de route et opérations dupliquées sont hors de ce binding. L’origine facultative est une URL HTTP(S) déclarée, sans identifiants, requête, fragment ou variables. Aucun endpoint n’est contacté.

Ce record local prépare des descriptions d’API, mais ne constitue pas encore un générateur OpenAPI. Les notions de chemin et d’opération sont vérifiées dans la [spécification OpenAPI 3.1.1](https://spec.openapis.org/oas/v3.1.1.html). La sécurité technique ne se déduit pas du texte d’un Control.

DataFlow relie des blocs, ports, acteurs ou entités de données à un DataSchema. Ses transformations sont une liste ordonnée de fonctions exactes, non exécutée ; ses contrôles restent déclarés. RequiredOutput fixe livrable attendu, critères d’acceptation, porte et éventuelle unité de construction. ArchitectureGap conserve manque, périmètre, impact, responsable et éventuel livrable attendu.

## Inspection

architecture-inspect / POST /v1/architecture/inspect / air_inspect_architecture relisent une baseline exacte entièrement autorisée. Le rapport présente blocs, ports, bindings, flux, livrables et lacunes. Il expose les opérations mappées et non mappées ; une couverture structurelle complète ne prouve aucune compatibilité de comportement. Les artefacts de schéma ne sont pas validés par cette seule inspection.

Les collections sont bornées à 128 éléments ; contexte et rapport à 1 MiB. Le service ne déploie rien, ne construit pas le livrable, ne vérifie pas la sécurité externe et ne crée aucune autorisation. La recette exécutée utilise les trois dossiers fictifs avec 88 objets chacun. Elle vérifie cohérence des ports, mappings exacts, droits, CLI/API/MCP et restauration. Voir docs/traceability/verification-architecture.json.
