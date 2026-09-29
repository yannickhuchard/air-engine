# Installation et reprise

La commande `python scripts/install.py --start` installe le code source dans un
environnement isolé `.venv`. Elle prépare `.air` et vérifie SQLite et l’identité locale.
Sous Windows, utiliser un volume avec ACL persistantes, par exemple NTFS.

Pour une release, télécharger source, wheel et `release-set.json` depuis le même tag.
Vérifier taille/SHA-256 de chaque fichier avec ce manifeste obtenu de la source officielle.
Extraire la source dans un dossier neuf puis exécuter :

```text
python scripts/install.py --wheel <chemin-du-wheel-verifie> --start
```

Les chemins entre chevrons sont à remplacer, pas des commandes prêtes à copier.
Le constructeur `scripts/build_release.py` produit le manifeste de la source et
le manifeste des artefacts. Les hashes détectent des modifications ; ils ne sont
pas une signature du développeur.

`--home`, `--venv` et `--work-root` permettent de choisir les répertoires.
Pour un autre port, ajouter `--port 8741`. `--stop` vérifie le processus avant arrêt.
Le serveur initial écoute sur loopback. Ne pas l’exposer directement sans le profil
de transport et d’autorisation approprié.

Extras optionnels : `--extras postgres,oidc` ou `--extras proofs,backup,dev`.
Pour l’installation hors ligne : fournir un wheel AIR et un wheelhouse compatible
avec l’OS/Python/extras, puis `--wheel <wheel> --wheelhouse <dossier>`.
Les dépendances tierces sont téléchargées par pip ; leurs licences restent applicables.
Un wheelhouse n’est pas inclus dans la release publique initiale.

Avant mise à jour : arrêter le serveur, sauvegarder avec `air --home <home> backup
<nouveau-dossier>`, conserver l’ancien wheel, puis installer et vérifier doctor.
Une restauration utilise `air --home <nouveau-home> restore <sauvegarde>` et renouvelle
les identités. Reconnecter les agents après restauration. Le retour arrière restaure
la sauvegarde antérieure avec l’ancien moteur ; il ne rétrograde pas une base modifiée.
Utiliser l’interpréteur `.venv` avec `-m air` si la commande `air` n’est pas dans le PATH.

Le script `scripts/qualify_release.py <dossier-release> --output <rapport>` exerce
installation neuve/hors ligne, réinstallation et restauration dans un espace isolé.
Le rapport peut contenir des chemins privés : ne pas le publier sans revue.
