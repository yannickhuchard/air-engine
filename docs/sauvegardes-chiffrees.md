# Sauvegardes SQLite chiffrées - P06

L'option `backup` ajoute `cryptography` ; l'installation SQLite/local par défaut reste inchangée.
Installer avec `python scripts/install.py --extras backup` ou ajouter `backup` aux extras déjà retenus.
Pour une installation hors ligne, préparer aussi ses wheels dans le répertoire de dépendances.

Avec le Python de l'environnement AIR :

```text
python -m air backup-keygen <nouveau-dossier-de-cle-prive>
python -m air --home <home> backup <nouvelle-sauvegarde>
python -m air backup-encrypt <sauvegarde> <nouveau-dossier-chiffre> --key-file <dossier-de-cle/backup.key>
python -m air backup-decrypt <dossier-chiffre> <nouvelle-sauvegarde-dechiffree> --key-file <dossier-de-cle/backup.key>
python -m air --home <nouveau-home> restore <sauvegarde-dechiffree>
```

La clé aléatoire de 32 octets reste dans un fichier protégé, hors de la sauvegarde. Aucune commande
ne l'affiche ou ne l'inclut dans l'archive. Sous Unix, les permissions ne doivent accorder aucun droit
au groupe ou aux autres comptes ; sous Windows, seules les autorisations du compte courant et de
SYSTEM sont acceptées. Les liens et fichiers avec plusieurs liens physiques sont refusés pour la clé.
Conserver une copie de secours de la clé sous la responsabilité de l'exploitant, séparée des archives,
avec un accès contrôlé. Sa perte empêche la restauration. Le transfert de clé vers un autre compte
requiert de rétablir ces permissions ; ne jamais copier la clé dans une conversation, un dépôt ou un rapport.

L'enveloppe `AIR-ENCRYPTED-BACKUP/1` utilise AES-256-GCM avec un tag de 16 octets, un nonce aléatoire
de 12 octets et une clé dérivée par HKDF-SHA256 avec un sel aléatoire de 32 octets par archive.
L'en-tête est authentifié. Le contenu est lu par blocs ; seules les quatre entrées connues au maximum
sont acceptées, avec taille et SHA-256 vérifiés. La limite de contenu est de 16 Gio, hors petit catalogue.
Ce format est propre à AIR ; aucune certification cryptographique ou conformité réglementaire n'est revendiquée.

Le déchiffrement stocke temporairement les octets dans un fichier privé, mais ne les interprète qu'après
vérification du tag. Clé erronée, modification ou troncature font échouer la commande sans publier de
sauvegarde finale. Les destinations doivent être neuves ; les dossiers `.pending-*` d'un échec restent
privés et ne constituent pas une sauvegarde reçue. Une panne pendant l'extraction peut y laisser du
contenu en clair. Les sauvegardes sources et déchiffrées restent également en clair : prévoir espace,
permissions, rétention et chiffrement du volume selon le déploiement. Aucun effacement sécurisé n'est promis.

Pour renouveler la clé, générer une nouvelle clé, rechiffrer une sauvegarde vérifiée dans une nouvelle
destination, puis déchiffrer/restaurer et contrôler les digests avant de retirer les copies anciennes.
Ne retirer une clé qu'après traitement de toutes les archives qui en dépendent. Le stockage hors site,
la fréquence, la rétention, la garde des clés et les objectifs RPO/RTO restent à réceptionner par le groupe.
Cette commande concerne SQLite ; la sauvegarde PostgreSQL suit le dispositif de sa plateforme.

Tests : `tests/test_backup_crypto.py` et aller-retour chiffré de `scripts/qualify_operations.py`.
La revue indépendante de sécurité reste ouverte. Référence :
[API GCM et authentification avant utilisation](https://cryptography.io/en/latest/hazmat/primitives/symmetric-encryption/#cryptography.hazmat.primitives.ciphers.modes.GCM).
