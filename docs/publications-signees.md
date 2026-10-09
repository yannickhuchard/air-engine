# Publications signées entre postes

Contrat de développement `air.federated-checkpoint/1`, moteur 0.35.0.dev1.
Il permet d'échanger une projection signée d'un manifeste de conception publié.
Il ne réserve aucune ressource, n'importe aucun objet canonique chez le destinataire
et n'autorise aucune activation. L'extra `proofs` est optionnel ; le reste d'AIR
continue à fonctionner sans bibliothèque cryptographique.

## Préparer l'émetteur

Le package doit avoir été préparé puis publié avec les commandes habituelles.
L'identité locale utilisée pour l'export doit être son propriétaire et conserver
son mandat `publish`. Le service relit les exports depuis la publication exacte :
le fichier de demande ne peut pas les substituer.

Créer une clé dédiée dans un **nouveau** répertoire privé, hors dépôt partagé :

```powershell
air federation-keygen D:/air-private/publication-keys
```

La commande produit `publication.key` et `public-key.json`. Seule la clé publique
est affichée. Ne jamais partager la clé privée. La lecture contrôle les ACL sous
Windows, les permissions sous Unix et le caractère régulier du fichier.

Préparer `export.json` suivant `air.federation_sender.REQUEST` :

```json
{
  "idempotency_key": "publication-001",
  "publication": {"id": "urn:air:package:EXACT_ID", "digest": "sha256:EXACT_DIGEST"},
  "peer": "urn:entreprise:architecture:poste-a",
  "key_id": "publication-2026-01",
  "audience": "INSTANCE_ID_DU_DESTINATAIRE",
  "expires_at": "2026-09-29T12:00:00Z"
}
```

Remplacer les valeurs illustratives par le reçu exact et une échéance future
inférieure à sept jours. Le destinataire peut imposer une fraîcheur plus courte.

```powershell
air --home D:/air-home federation-export export.json --key-file D:/air-private/publication-keys/publication.key --output-directory D:/air-private/envoi-001
```

La commande consomme le fichier de credentials local sans afficher son jeton.
Elle écrit `checkpoint.json` dans un nouveau répertoire protégé. Aucun réseau
n'est contacté. Une nouvelle tentative avec la même clé d'idempotence retrouve
le même message ; choisir un autre répertoire de sortie pour le récupérer.
Une sortie disque interrompue ne fait pas perdre le message enregistré dans l'outbox.

## Enregistrer la confiance du destinataire

L'opérateur du destinataire vérifie la clé publique et l'identité du pair par un
canal convenu. Il prépare un document conforme à `air.federation.TRUST` : `peer`,
`key_id`, `subject`, `public_key`, `namespaces`, `not_before`, `expires_at` et
`max_age_seconds`. Le `subject` doit posséder le mandat courant `publish` pour
les namespaces concernés dans la politique locale.

```powershell
air --home D:/air-recepteur federation-trust confiance.json
air --home D:/air-recepteur federation-receive checkpoint.json
```

La seconde commande appelle le serveur local authentifié. L'importateur doit
avoir le droit d'écriture dans le namespace. Le destinataire signé doit correspondre
à son `instance_id`. La confiance et sa révocation sont des commandes d'opérateur,
absentes des outils MCP ; un document importé ne peut pas les accorder.

Pour lire la projection, `federation-read` ou `air_read_checkpoint` attendent
`peer`, `aggregate` et `namespace`. Le service utilise la plus haute séquence reçue,
revérifie mandat, signature, confiance et fraîcheur, puis expose la décision
`new_use_allowed`. Ce champ décrit uniquement la publication annoncée : il ne
reçoit ni contrat sémantique, ni plan de construction, ni engagement distribué.

## Retrait, reprise et limites

Après `package-revoke`, refaire l'export avec une **nouvelle** clé d'idempotence :
le message `REVOKED` reçoit une nouvelle séquence. Transmettre ce message aux
destinataires concernés. Sans transport automatique, un destinataire ne connaît
un retrait que lorsqu'il reçoit le message ; l'expiration borne l'usage d'une
ancienne publication. Une coupure ne garantit donc pas une révocation immédiate.

Les doublons sont sans effet ; les messages désordonnés ne font pas reculer la
projection. Une contradiction entre ordre des séquences et révisions est refusée.
Une séquence déjà reçue avec un autre contenu est une erreur. Une clé expirée,
révoquée ou privée de mandat ne permet pas de revenir à un ancien résultat favorable.

La confiance d'une clé ne peut pas être réécrite. Utiliser un nouvel identifiant
pour une rotation, enregistrer la nouvelle clé chez les destinataires puis révoquer
l'ancienne avec `federation-revoke`. Après restauration dans une nouvelle instance,
la confiance et l'identité de signature doivent être réétablies explicitement.

Le plafond est 4 096 checkpoints par namespace et autant pour l'outbox ; le service
refuse de sélectionner silencieusement une tête dans un index tronqué. Les historiques
restent conservés. Ce contrat ne couvre pas la synchronisation automatique des
modèles, la négociation ni la coordination multi-autorités de P12.
