# Transfert du registre SQLite et PostgreSQL

Le transfert logique préserve toutes les révisions, identités, baselines fermées, événements d’audit et reçus de service. Il s’adresse à l’opérateur du système, depuis une exportation de confiance. Les empreintes détectent une altération ; elles ne certifient pas l’identité d’un expéditeur. Ce n’est pas un mécanisme de fédération ou de publication de packages.

## Exporter

~~~sh
.venv/Scripts/python.exe -m air --home .air registry-export .air-transfer-001
~~~

Le dossier doit être nouveau. Son accès est restreint au compte système courant et, sur Windows, à SYSTEM. La lecture de toutes les tables utilise un même snapshot SQL, y compris si des écritures continuent. Le manifeste est écrit en dernier. Chaque fichier JSONL porte taille, nombre de lignes et SHA-256. Aucun jeton en clair ni URL de base n’est exporté. Les empreintes de jetons, données internes et historiques restent confidentiels.

Pour une bascule, arrêter les écritures applicatives avant l’export final. Une exportation en ligne est cohérente mais ne contient pas les écritures intervenues après son snapshot. Ne pas ouvrir simultanément la source et la destination en écriture pendant une migration.

## Importer vers SQLite

~~~sh
.venv/Scripts/python.exe -m air --home .air-restored registry-import .air-transfer-001
.venv/Scripts/python.exe -m air --home .air-restored doctor
~~~

Le home doit être nouveau. Le schéma, les empreintes des objets et reçus, les références et les fermetures de baselines sont vérifiés dans la transaction d’import. Une erreur annule les tables et données créées. Une base contenant déjà une table est refusée. Les anciennes identités d’auteurs sont conservées ; tous les anciens jetons sont révoqués dans la destination. Un nouvel identifiant d’installation et un nouveau jeton local-admin sont créés, dans credentials.json protégé, sans affichage.

La politique de namespaces est conservée avec une nouvelle version : les revues historiques doivent être réévaluées. Les permissions du sujet local-admin restent celles de la politique importée ; l’opérateur peut les configurer explicitement avec policy-set. L’authentification initiale de la destination est locale. OIDC se configure séparément selon installation.md.

## Importer vers PostgreSQL

Installer l’extra postgres, créer une base vide et fournir son URL via une variable d’environnement privée nommée AIR_TARGET_DATABASE_URL. Ne pas inclure son contenu dans une commande enregistrée, un journal ou le dépôt.

~~~sh
.venv/Scripts/python.exe -m air --home .air-postgres registry-import .air-transfer-001 --target-database-env AIR_TARGET_DATABASE_URL
~~~

AIR_DATABASE_URL doit être absente pendant l’import pour éviter toute confusion avec la source. Après import, fournir AIR_DATABASE_URL via le gestionnaire de secrets du processus cible, puis exécuter doctor et démarrer cette installation. Le marqueur database_backend=postgresql interdit tout retour silencieux vers une base SQLite vide si la variable manque. L’URL n’est pas écrite dans config.json.

Le chemin inverse utilise registry-export depuis PostgreSQL, puis registry-import dans un nouveau home SQLite. L’export logique vérifié complète les procédures natives de sauvegarde de l’entreprise ; il ne fournit ni PITR ni réplication.

## Reprise et limites

L’import du registre est atomique dans une base. La création du home et du nouveau jeton intervient ensuite. Si le processus s’interrompt après le commit SQL, les données restent dans la cible et le home privé .pending-* conserve les éléments déjà créés. Un nouvel import dans cette base est refusé. Diagnostiquer ce home et terminer la configuration ou choisir une autre base vide ; ne pas supprimer une cible existante automatiquement.

La source reste intacte. Le retour arrière consiste à conserver la source arrêtée et ses secrets jusqu’à réception de la destination, puis à décider explicitement de la reprise. Les écritures réalisées séparément après la bascule ne sont pas fusionnées automatiquement.

Qualification réelle : PostgreSQL 18.6 sous Windows, cluster jetable indépendant du service PostgreSQL de la machine. Les 188 tests de la tranche registre/packages passent sur ce moteur et SQLite. Les tests comprennent SQLite → PostgreSQL et PostgreSQL → SQLite, conservation des révisions et auteurs, révocation des anciens jetons et rollback sur altération. Voir traceability/verification-registre-packages.json. Les autres versions et systèmes ne sont pas déclarés qualifiés.

Le schéma 6 ajoute artifact_blob et artifact_chunk. Les colonnes binaires sont représentées par un objet contenant uniquement base64, en encodage canonique. L’import vérifie les octets contre les manifestes de service avant commit ; un bloc orphelin, manquant ou altéré annule tout le transfert. Les transferts des schémas 2 à 5 restent lisibles.
