# Vues conservées et provenance du générateur - tranche 20

Le binding expérimental air.view/0.20 implémente une capture du type View de A.12, page 52 du white paper. Une capture conserve ensemble la baseline exacte, le Viewpoint, le générateur observé au démarrage, le HTML et les mappings JSON. SQLite et authentification locale restent les valeurs par défaut ; aucun stockage externe n’est requis et le schéma SQL reste 6.

## Contrat

View est un objet DRAFT géré par le service, comme Baseline et ChangeSet. Il est extérieur aux membres des baselines de données : inclure le rendu dans sa propre source créerait une dépendance circulaire. Les sept profils de baseline et leurs empreintes historiques restent inchangés. Une importation ordinaire de brouillon View est refusée ; un transfert de registre doit conserver et vérifier ses reçus et artefacts associés.

POST /v1/views/capture, la CLI view-capture et MCP air_capture_view partagent le même service. La requête contient id, revision, name, baseline et viewpoint exacts (id, revision, digest), puis idempotency_key. Le namespace est déduit du Viewpoint ; le serveur fixe auteur, provenance, date et générateur. Exemple de fichier de requête, avec les empreintes réelles obtenues par export :

~~~json
{"id":"urn:company:view:sav:business","revision":1,"name":"SAV - vue métier conservée","baseline":{"id":"urn:company:baseline:sav","revision":1,"digest":"sha256:<empreinte exacte>"},"viewpoint":{"id":"urn:company:viewpoint:sav:business","revision":1,"digest":"sha256:<empreinte exacte>"},"idempotency_key":"sav-business-capture-1"}
~~~

Exécuter avec l’interpréteur installé : python -m air view-capture capture.json. Relire avec view-read et un fichier contenant {"view":{"id":"…","revision":1,"digest":"sha256:…"}} ; API POST /v1/views/read et MCP air_read_captured_view sont équivalents. Les réponses donnent le View, le reçu de capture et les deux manifestes. Utiliser artifact-download pour conserver les octets localement ; la destination doit être nouvelle.

## Atomicité et répétition

La compilation bornée précède la transaction. Celle-ci contrôle à nouveau l’identité et la politique, puis dépose deux artefacts, le View, deux gardes de contexte et les reçus d’identité et d’idempotence. Toute erreur annule l’ensemble. Une identité de View/révision ou une clé d’auteur/namespace déjà utilisée pour une autre demande provoque un conflit. Une répétition équivalente relit le produit historique sans appeler le générateur courant ; elle ne remplace ni la provenance ni la date de création.

La ToolchainSpec air.toolchain/0.20 décrit la version AIR, Python, les dépendances de validation/canonicalisation et les empreintes des modules AIR observés au démarrage. Ce relevé local ne constitue ni une signature de distribution, ni une qualification de modèle IA, ni une preuve de vérité des informations rendues.

## Lectures et reprise

Les manifestes dérivés utilisent air.artifact/0.20 avec contexte source obligatoire ; les artefacts génériques historiques restent air.artifact/0.18. Lire ou télécharger un produit dérivé exige aussi la lecture de toute sa baseline source. Un droit sur le seul namespace de destination ne suffit pas. Une garde absente, incohérente ou orpheline est refusée ; un ancien lecteur qui ne comprend pas le nouveau format le refuse.

Les vérifications de reprise et de transfert contrôlent la bijection View/reçus, les références exactes, les octets et leurs empreintes, les mappings objets/contexte, les ancres HTML et l’absence de contenu actif. Elles relisent les produits historiques sans les régénérer. Le HTML reste borné à 4 MiB, le mapping à 1 MiB, le contexte de compilation à 1 MiB ; les plafonds d’artefacts restent applicables.

## Recette

scripts/demo_view_capture.py reprend le résultat de scripts/demo_audience.py dans une installation isolée. Il capture les six vues métier/ingénierie des dossiers SAV, atelier connecté et IAM ; compare les octets aux vues de tranche 19 ; vérifie les replays CLI/MCP, les refus entre namespaces et la restauration exacte des six View et douze artefacts. Les baselines restent à 52 objets. Les neuf cas métier restent NOT_EXECUTED et les portes de construction BLOCKED.

Les tests ciblés couvrent la concurrence, les refus après révocation, l’annulation transactionnelle, les droits sur le contexte source, les gardes manquantes, les transferts entre moteurs et la restauration. Le périmètre reste partiel : pas de masquage de champs, de déclassification, de politique de rétention ni de conformité AIR complète.
