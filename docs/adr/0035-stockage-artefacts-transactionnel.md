# ADR 0035 - Octets d’artefacts dans le registre transactionnel

Statut : accepté pour le binding expérimental air.artifact/0.18. L03, L04, L06 et L16 restent partiels.

Les références de documents ne suffisent pas à préserver les octets nécessaires au replay. Le premier stockage doit suivre les transactions et sauvegardes SQLite, sans imposer un serveur de fichiers ou un service cloud, et fonctionner aussi sous PostgreSQL.

Le schéma SQL 6 ajoute artifact_blob et artifact_chunk. Le contenu SHA-256 est immuable et dédupliqué globalement. Des manifestes de service distincts portent le namespace, l’identité authentifiée, la politique lors du dépôt et la clé d’idempotence. Une empreinte seule ne permet aucun téléchargement : une référence exacte de manifeste et le droit de lecture courant sont exigés. Les manifestes ne sont pas de nouveaux types normatifs.

Un dépôt contient de 1 octet à 16 MiB, en blocs de 256 KiB. Le JSON/MCP est limité à 512 KiB d’octets, encodés en base64. Le type MIME est déclaré, sans paramètres ; AIR ne le détecte pas et n’exécute pas le contenu. L’identité et la politique sont revérifiées après acquisition du verrou transactionnel. Le reçu et tous les blocs sont validés ou annulés ensemble.

Les téléchargements vérifient le nombre de blocs, leur ordre, leur taille et l’empreinte globale. L’API force une pièce jointe et interdit la détection de type par le navigateur. La CLI vérifie taille et empreinte avant création exclusive du fichier de destination. Aucun chemin fourni dans le contenu ne commande une écriture locale.

Le transfert logique du schéma 6 encode les colonnes binaires dans un objet base64 explicite et canonique. L’import refuse les blobs orphelins, manifestes incohérents et empreintes incorrectes avant commit. La restauration SQLite vérifie aussi ces invariants avant de rendre la nouvelle installation visible. Les anciens schémas restent importables ; les révisions existantes ne sont pas réécrites.

Conséquences : une seule sauvegarde cohérente et aucune dépendance additionnelle. En contrepartie, les gros fichiers et le nettoyage automatique ne sont pas pris en charge. La rétention effective est conservatoire ; les textes access_policy/retention_policy ne constituent pas un moteur juridique ou une programmation d’effacement. Une Source peut indiquer le locator de manifeste et l’empreinte de contenu ; ce lien textuel reste déclaratif, sans validation automatique de vérité. Le binding ArtifactRef normatif existant reste limité à application/json dans les profils historiques : un descripteur de service d’un autre type MIME ne l’élargit pas.
