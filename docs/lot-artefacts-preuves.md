# Pièces jointes conservées - tranche 18

Binding expérimental air.artifact/0.18, schéma SQL 6. L03/L04/L06/L16 restent partiels. Le registre conserve les octets avec leurs manifestes authentifiés ; le catalogue demeure à 32 types persistables et aucune preuve n’est automatiquement qualifiée.

SQLite et PostgreSQL utilisent le même stockage transactionnel : blocs de 256 KiB, empreinte SHA-256, manifestes distincts par dépôt. L’installation Python seule reste inchangée. Un fichier partagé peut être dédupliqué sans donner accès aux namespaces des autres équipes.

## Déposer et relire

Exemples à exécuter avec le Python de l’installation et un compte autorisé sur le namespace :

~~~sh
python -m air artifact-upload constat.json --namespace asteria.sav --media-type application/json --idempotency-key constat-sav-001
python -m air artifact-describe lookup.json
python -m air artifact-download lookup.json --output constat-relu.json
~~~

lookup.json contient seulement artifact, avec id et digest copiés du reçu de dépôt. Le digest de cette référence désigne le manifeste ; content_digest désigne les octets. Conserver les deux dans les pièces de recette. Ne pas les intervertir.

Le dépôt accepte de 1 octet à 16 MiB. Le même compte réutilisant la même clé dans le même namespace avec le même contenu/type reçoit le même manifeste ; tout changement est refusé. Les écritures concurrentes et les erreurs annulent ou conservent ensemble blocs et reçus. Le téléchargement vérifie les octets avant de créer exclusivement la destination ; un fichier existant n’est jamais écrasé.

Pour les clients distants, utiliser les options --url et --ca-file du transport HTTPS. Les credentials restent dans le fichier protégé de l’installation. Le type MIME est déclaré et ne déclenche ni exécution ni analyse.

## API et MCP

POST /v1/artifacts/upload reçoit les octets avec Content-Type: application/octet-stream, X-AIR-Namespace, X-AIR-Media-Type et Idempotency-Key. POST /v1/artifacts/download prend la référence exacte du manifeste en JSON et renvoie une pièce jointe, Cache-Control: no-store et X-Content-Type-Options: nosniff. X-AIR-Content-SHA256 contient les 64 caractères hexadécimaux de l’empreinte.

Les commandes artifact-import, artifact-describe, artifact-read correspondent à /v1/artifacts/import, /describe, /read. Le JSON d’import ajoute content_base64 à namespace, media_type et idempotency_key. Les outils MCP air_import_artifact, air_describe_artifact et air_read_artifact partagent ces contrats. L’import et la lecture base64 sont limités à 512 KiB d’octets ; utiliser la CLI binaire au-delà.

Une Source peut référencer l’identifiant du manifeste dans locator et l’empreinte des octets dans source_revision. Cette association est déclarative ; elle n’ajoute pas de preuve indépendante. Le descripteur artifact_reference du service n’élargit pas les schémas ArtifactRef des profils historiques, limités à application/json.

## Conservation et reprise

Arrêter le serveur vérifié, sauvegarder puis réinstaller pour migrer du schéma 5 au schéma 6. La migration conserve révisions, baselines et jetons. La restauration vers une nouvelle installation révoque les anciens jetons, conserve les manifestes historiques et revient au transport local.

La sauvegarde SQLite contient les blocs. Le transfert logique SQLite/PostgreSQL encode les colonnes binaires en base64 canonique ; empreintes, ordres, tailles, liens aux manifestes et absence de blocs orphelins sont contrôlés avant commit. Une restauration SQLite refuse également un contenu incohérent avant publication du répertoire cible.

## Recette

Exécuter scripts/demo_business.py puis scripts/demo_knowledge.py si leurs données ne sont pas présentes, puis scripts/demo_artifacts.py. La dernière commande restaure une copie isolée des trois dossiers Astéria, y conserve un document fictif par dossier, compare CLI et MCP, refuse l’accès SAV vers IAM et restaure les octets. Les nouvelles baselines contiennent 49 objets ; les anciennes restent intactes. Rapport : tmp/demo-asteria/artifacts.json.

Les tests tests/test_artifacts.py vérifient concurrence, idempotence, rollback, droits, révocation, limites, altération, transfert et migrations. Les rapports de qualification distinguent ces contrôles des neuf VerificationCase métier, toujours NOT_EXECUTED.

Limites : pas de stockage externe/S3, collecte distante, fichiers supérieurs à 16 MiB, antivirus spécialisé, effacement ou rétention légale automatisée. Aucun contenu n’est envoyé à un service tiers. Les octets sont conservés ; leur sens et leur qualification restent à examiner.
