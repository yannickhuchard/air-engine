# Packages locaux et composition exacte - contrat de développement

Référence : white paper §§12.1–12.5, pages 24–25 ; L11.1/L11.2. Le premier binding conserve les packages dans le même registre SQL. Il ne revendique pas encore un transport entre entreprises, une signature d’autorité distante ou une compatibilité sémantique prouvée.

Une préparation authentifiée référence une baseline fermée, un identifiant de package, une version entière, une interface exportée et des imports exactement épinglés. La préparation expire et reste invisible aux lecteurs du registre des publications. La publication exige le mandat publish sur tous les namespaces inclus, la même politique et un manifeste intact. Elle inscrit le manifeste complet, le reçu idempotent et l’événement dans une transaction. Un paquet publié partage la visibilité de toute sa fermeture : aucune projection partielle ne révèle un contexte interne interdit.

Une publication est un partage de conception DRAFT ; elle ne signifie ni validation métier, ni admission, ni déploiement. Les imports révoqués ou dont le mandat de publication n’est plus valable restent consultables historiquement, mais bloquent un nouvel usage. Chaque import fixe une empreinte ; aucune résolution latest ou plage flottante n’est acceptée. La composition refuse la récursion d’un package dans sa propre descendance. Un numéro de version ne prouve pas une compatibilité de contrat.

La révocation est un événement immuable. L’historique conserve le manifeste et ses références exactes. Les vérifications de nouvel usage et les mutations publication/révocation sont sérialisées dans le registre, avec un verrou SQL unique dans ce premier binding. Les anciennes lectures ne constituent aucune réservation de capacité.

Critères à vérifier : préparation invisible, corruption refusée, publication complète malgré panne injectée, concurrence et idempotence, ACL de toute la fermeture, mandat modifié, import révoqué, récursion, historique préservé ; SQLite et PostgreSQL.

## Bindings livrés

CLI : package-prepare, package-publish, package-read et package-revoke ; chaque commande reçoit un fichier JSON et --credential/--port comme les autres services. API : POST /v1/packages/prepare, /publish, /read, /revoke. MCP : air_package_prepare, air_package_publish, air_package_read, air_package_revoke. Les schémas exacts sont retournés par tools/list et définis dans src/air/packages.py.

La recette `python scripts/demo_packages.py` crée une installation SQLite isolée, publie les trois dossiers et leur composition, vérifie la révocation d’une dépendance, puis exporte et restaure le registre. Elle utilise la CLI, HTTP réel et un client MCP via API. Aucun système métier externe n’est appelé. Le rapport est tmp/demo-asteria/packages.json.
