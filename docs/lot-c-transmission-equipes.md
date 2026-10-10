# Lot C : transmettre un périmètre aux constructeurs

L'architecte prépare un paquet depuis une baseline exacte et des unités de
construction sélectionnées. Le constructeur retrouve les livrables, interfaces,
données, critères, cas de vérification, responsabilités et dépendances. Il peut
accepter ce périmètre pour préparer la réalisation, ou demander des changements.
Le management voit les réceptions manquantes sans les confondre avec le lancement.

## Parcours et choix d'interface

La page « Préparer la réalisation » reste l'entrée. Une section « Réception des
paquets » présente version, unités, responsables, questions et réceptions.
Les détails sont accessibles sans JavaScript, au clavier et sur mobile. Un site
statique montre l'état au moment de son export : il ne reçoit aucune approbation
depuis un bouton et doit être régénéré après une nouvelle réception.

## Contrat de livraison

- Paquet immuable identifié par URI, version, empreinte et baseline exacte.
- Export autonome du modèle fermé, manifeste, fiches et contrats disponibles.
- Responsabilités R et A de DELIVERY sur chaque unité exacte, avec rôles et équipes
  explicitement reliés. Le propriétaire d'un objet ne remplace jamais un RACI.
- Droit `receive` explicite et `builder_roles` dans la politique d'accès : le
  serveur rattache l'identité authentifiée aux rôles exacts, jamais à un nom inventé.
- Acceptation ou demande de changements par rôle, rationale et questions. Une
  acceptation exige un paquet sans manque bloquant et aucune question ouverte.
- Réceptions expirables et révocables, idempotence et conflits de version. Un
  changement de baseline exige une nouvelle réception. Une politique changée ou
  un mandat retiré rend la réception ineffective et conserve son historique.
- CLI, API et MCP partagent les mêmes services. Les outils engageants ne sont pas
  activés automatiquement dans les adaptateurs IDE de contribution.

La réception concerne la compréhension et l'acceptation du périmètre de design.
Elle ne prouve ni exécution des tests prévus, ni livraison du logiciel, ni avis
indépendant, ni financement, ni autorisation de déployer.

## Recette prévue

Exercer deux équipes fictives avec mandats distincts : export, questions,
acceptation, changement de version, retrait, politique modifiée, concurrence et
refus d'usurpation. Vérifier les adaptateurs et le site, puis rejouer les trois
parcours Asteria. Les résultats calculés sont enregistrés dans la traçabilité.

## Utiliser CLI et MCP

Les commandes prennent un fichier JSON puis les options de connexion. Exemple :

```text
air --home .air handoff-compile packet-request.json --workspace transmission --apply --credential architect.json
air --home .air handoff-create creation-request.json --credential architect.json
air --home .air handoff-assess baseline-request.json --credential architect.json
air --home .air handoff-receive reception-request.json --credential builder.json
air --home .air handoff-revoke withdrawal-request.json --credential builder.json
```

`packet-request.json` fournit `package_id`, `version`, `baseline` et `units`.
Le champ facultatif `title` donne un nom compréhensible au paquet dans le site.
Chaque référence contient `id`, `revision`, `digest`. La création ajoute
`idempotency_key`. La réception fournit la référence du paquet retournée par
la création, le rôle exact, `outcome`, `rationale`, `questions`, `expires_at`
en UTC terminant par Z et une clé d'idempotence. Les schémas complets sont dans
le catalogue MCP des six outils `air_*_builder_*` et dans `builder_handoff.py`.

La politique `access-policy.json` du poste déclare, pour chaque représentant,
les namespaces `read` et `receive`, ainsi que `builder_roles`, liste des
références exactes de rôles. Un rôle RACI et une équipe ne configurent pas seuls
ces droits. Le détenteur de l'installation doit attribuer le mandat voulu ;
les jetons se lisent depuis les fichiers protégés et ne sont jamais exportés.

Une acceptation accompagnée de questions est refusée. `CHANGES_REQUESTED`
exige au moins une question. Une acceptation nouvelle ne ferme pas implicitement
une objection : son auteur retire celle-ci explicitement. L'historique reste
lisible. La synthèse retient la version la plus haute de chaque identité de
paquet dans la baseline interrogée ; les anciennes versions sont signalées
comme remplacées. Les réceptions expirées, retirées ou sans mandat ne comptent pas.

## Périmètre et limites

Au plus 1000 objets, 64 unités par paquet, 32 MiB de snapshot, 48 MiB d'export,
4 MiB de manifeste,
2000 enregistrements par famille et namespace. Aucun résultat de réception
n'est calculé sur un catalogue tronqué. Cette livraison fournit les suites
HTTP/JSON d'AIR ; elle ne revendique aucun compilateur universel de protocoles.
Les artefacts externes restent dans le registre autorisé ; le modèle JSON est
fermé, mais l'archive n'est pas une migration complète de ces artefacts.

Le MCP conserve son budget de réponse de 8 MiB : demander `content: DIGESTS`
d'abord, puis FULL pour un petit périmètre ou utiliser le CLI pour l'export
complet. Le CLI possède un budget de transport adapté aux fichiers et à
l'échappement JSON ; ces limites n'augmentent pas le budget du modèle sélectionné.

Le site exporte aussi les identités et rationales des réceptions lisibles par
son auteur. Choisir le destinataire et protéger les fichiers avant diffusion.
Un filtre d'audience n'est pas un contrôle d'accès. L'état est observé à la
génération, pas synchronisé en temps réel avec un autre poste.
