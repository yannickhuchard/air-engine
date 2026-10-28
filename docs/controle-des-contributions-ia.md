# Contrôler les contributions IA et les exports de contexte

Candidate locale 0.35.0.dev8. Les contrôles complètent le mandat technique et
les revues existantes ; aucune réception native ou conformité générale n'est déduite.

## Modifications conséquentes

Une modification d'un contrôle existant, de son mécanisme, d'une contrainte,
d'une obligation, d'un objectif qualité mesuré, d'un critère de réception ou
d'un oracle exige l'approbation de la proposition exacte. Changer le propriétaire
ou la classification d'un objet existant exige aussi cette approbation.
L'autorité utilise `completion-authorize` et `approved_prepared`, après lecture
du candidat. Un type autorisé dans le mandat ne suffit pas pour ces changements.
Les références réépinglées à la même identité ne déclenchent pas seules cette
protection. Les nouvelles révisions de leurs contenus restent contrôlées.

Le compteur d'absence de progrès suit la fermeture des critères de readiness,
sans régression d'un critère acquis. Une empreinte différente ou une suppression
de critère ne constitue pas un progrès. Cette mesure reste grossière : elle ne
mesure ni la vérité du besoin ni la qualité rédactionnelle. Un travail utile
qui exige plusieurs cycles dans le même critère peut nécessiter un nouveau mandat.

## Préparer un export autorisé

Le propriétaire installe une politique `access-policy.json`. Pour le sujet
concerné, `read` autorise la lecture ; `export_context` autorise séparément les
namespaces qui peuvent entrer dans l'export. `context_destinations` fixe un
destinataire, des finalités, les classifications admises et une expiration.

```json
{
  "version": "context-1",
  "subjects": {
    "architect": {
      "read": ["solution", "shared"],
      "export_context": ["solution", "shared"],
      "context_destinations": [{
        "id": "modele-approuve",
        "purposes": ["conception"],
        "classifications": ["PUBLIC", "INTERNAL"],
        "expires_at": "2027-01-01T00:00:00Z"
      }]
    }
  }
}
```

L'opérateur choisit une expiration adaptée ; la date d'exemple n'est pas un
mandat. Les quatre niveaux disponibles sont PUBLIC, INTERNAL, CONFIDENTIAL et
RESTRICTED. Leur présence ne configure aucun droit automatiquement.

Une requête fournit `baseline`, `roots`, `destination`, `purpose` et
`idempotency_key`. Chaque baseline et racine porte id, revision, digest.
`air context-export requete.json --credential architect.json` ou
`air_prepare_context_export` prépare la fermeture exacte des racines et de
leurs dépendances, limitée à 4096 objets et 1 MiB. Une seule dépendance non
autorisée refuse l'ensemble. Les objets sans lien avec les racines sont omis.
Un reçu conserve l'auteur authentifié, la politique, la destination, la finalité,
les références et l'empreinte du contenu. Une répétition identique est idempotente.

AIR n'ouvre aucune connexion vers le destinataire. Le contexte est renvoyé au
client authentifié, qui peut le transmettre à son modèle. Le destinataire est
un identifiant de politique, pas une URL à ouvrir ni une attestation du transport
ou du fournisseur. L'export ne détecte ni ne masque les secrets arbitraires.
Un fichier déjà reçu reste accessible à son destinataire après révocation.
Les lectures de fichiers et les autres API de lecture des clients gardent leurs
propres frontières : ce workflow ne constitue pas une interception globale des
sorties du poste vers un fournisseur de modèle.

Les règles s'appliquent à chaque dépendance, y compris dans les namespaces
partagés. Les refus n'accordent aucune qualification ou nouvelle autorité.

Pour un sujet dédié à un modèle, `model_context` lie les lectures AIR à la
destination et à la finalité configurées par l'opérateur. Les lectures via
ScopedStore et celles des artefacts appliquent aussi les classifications admises.
Les anciens artefacts non classifiés sont traités comme RESTRICTED pour ce sujet.
Le [guide de correction](audit-remediation-2026-10-24.md) précise la configuration
et ses limites ; elle ne contrôle pas les accès directs du client aux fichiers.
