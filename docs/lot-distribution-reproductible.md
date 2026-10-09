# P05 - Distribution, installation et mise à niveau

Candidates **0.34.0rc1 / 0.34.0rc2**, schéma SQL 6. Réception technique P05 **RECEIVED_SCOPED**
sur les commits b709928 puis bbc421f : preuves et limites (document historique ou livrable local non inclus).
SQLite/local reste
le socle ; PostgreSQL, OIDC et preuves externes sont des extras indépendants.

## Produits et provenance

`scripts/build_release.py --output-dir <nouveau-dossier>` exige un dépôt Git propre et produit
une archive de sources, un wheel, `constraints.cdx.json` et `release-set.json`. L'archive et le
wheel sont construits à partir d'un même instantané en mémoire, identifié par un inventaire SHA-256
et le commit. Les fichiers du package compilé sont comparés aux octets des sources ; les horodatages
ZIP sont normalisés, y compris le système créateur inscrit dans les en-têtes. La documentation et ses illustrations sont incluses dans l'archive.

`--allow-dirty` produit seulement une WORKING_TREE_PREVIEW, explicitement non reçue. Aucun produit
existant n'est remplacé. Les `.air`, `.venv`, journaux et fichiers de secrets réservés sont exclus.
L'inventaire CycloneDX recense les versions contraintes, y compris les extras et outils de développement ;
la recette produit séparément le SBOM des composants réellement installés. Ce n'est pas un audit de
vulnérabilités ni une attribution automatique de licence. Depuis la décision explicite
du 28 septembre 2026, le logiciel AIR est sous Apache-2.0 : les nouveaux paquets
conservent `LICENSE`, `NOTICE` et les métadonnées SPDX. Les anciens manifestes
`NOT_ASSIGNED` restent historiques ; le [complément rc9](licence-rc9.md) donne la
concession applicable sans réécrire leurs empreintes.

Les empreintes détectent une altération relativement au manifeste approuvé. Elles ne constituent pas
une signature d'éditeur : obtenir le manifeste et son commit par le canal approuvé de l'entreprise.

```text
python scripts/build_release.py --output-dir <build-A>
python scripts/build_release.py --output-dir <build-B>
python scripts/compare_releases.py <build-A> <build-B>
```

Les deux constructions doivent rendre exactement les mêmes empreintes pour l'archive, le wheel et
l'inventaire sur chaque couple OS/Python testé. Les métadonnées générées par le backend
de packaging peuvent différer entre OS ; l'identité de l'inventaire source est vérifiable séparément.
La recette compare les octets après vérification de chaque manifeste.

## Installation reçue

Depuis l'archive vérifiée, dans un environnement Python correspondant au déploiement :

```text
python scripts/install.py --wheel <wheel-AIR> --home <home> --venv <venv> --start
python scripts/install.py --wheel <wheel-AIR> --wheelhouse <dependances-locales> --home <home> --venv <venv> --start
```

Le deuxième parcours utilise `--no-index` et uniquement les wheels du répertoire local ; préparer
ce répertoire sur le même OS et la même version Python avec les contraintes livrées. Pour un miroir,
les variables pip standard restent disponibles et leurs secrets ne sont pas affichés. Le téléchargement
préalable des dépendances n'est pas une opération hors ligne ; seule l'installation avec ce jeu déjà
présent l'est. La CLI et le serveur sont chargés depuis le wheel installé, sans import du checkout.

Le home doit être privé et sur un stockage adapté. Sous Windows, AIR vérifie la capacité
FILE_PERSISTENT_ACLS avant de créer des identifiants ; FAT/exFAT est refusé. Les répertoires de
qualification qui contiennent des homes et clés temporaires doivent aussi satisfaire cette condition.
`--work-root` ou `AIR_WORK_ROOT` permet de choisir un volume disposant d'espace libre.

## Recette automatisée

```text
python scripts/qualify_release.py <build-A> --work-root <espace-prive> --previous-wheel <ancien-wheel> --output <rapport.json>
```

La recette vérifie les empreintes avant extraction, refuse chemins traversants, collisions de noms,
liens et archives surdimensionnées. Elle installe un environnement neuf depuis le wheel, prépare
les dépendances contraintes, installe sans index, dépose une révision, réinstalle puis vérifie identité,
digest, serveur et assets. Elle sauvegarde et restaure dans un nouveau home, en vérifiant le retrait
de l'ancien jeton. Le serveur de recette est arrêté avec vérification d'identité.

Avec `--previous-wheel`, elle installe la version précédente, sauvegarde une révision et son identité,
met à niveau le package et la base puis vérifie leur conservation. Le retour arrière utilise l'ancien
wheel et la sauvegarde antérieure, dans un home neuf ; aucune rétrogradation en place n'est annoncée.
Sans cette option, le contrôle de mise à niveau est NOT_EXECUTED.

La recette PostgreSQL crée une base explicitement jetable. `--stop-timeout` contrôle le délai d'arrêt ;
le rapport distingue `test_status` de `cleanup`. PASS exige les tests réussis **et** STOPPED_VERIFIED.
Un dépassement de délai reste enregistré même si l'arrêt est ensuite confirmé. Aucun processus étranger
n'est arrêté et aucune base métier n'est réinitialisée.

## Matrice et limites

La CI définit SQLite Windows/Linux sur Python 3.11/3.12, PostgreSQL Windows/Linux sur ces deux versions,
et distribution/reproductibilité/installation hors ligne sur les quatre couples OS/Python.
PostgreSQL Windows utilise un cluster natif isolé et vérifie son arrêt. macOS n'est pas qualifié.
La présence du workflow ne vaut pas réception : conserver les URL de runs, commit, versions et résultats
réels dans la traçabilité. La qualification entreprise exige ensuite P06–P09, dont charge, exploitation,
clients natifs, équipe indépendante et IdP réel. Aucun feu vert de production n'est déduit de ce seul lot.

La matrice bbc421f est entièrement verte (12 tâches). L'installation a été exercée par les scripts
de recette sur des machines CI neuves, avec téléchargement préalable puis installation sans index.
Le parcours d'un agent natif ne disposant que de la documentation et du skill, le miroir propre au
groupe et l'opérateur indépendant ne sont pas qualifiés par cette CI et restent à recevoir avec P07–P09.

Références : [installation pip hors ligne](https://pip.pypa.io/en/stable/cli/pip_download/),
[schéma CycloneDX 1.6](https://github.com/CycloneDX/specification/blob/master/schema/bom-1.6.schema.json),
[capacité ACL Windows](https://learn.microsoft.com/fr-fr/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationw).
