# Deux équipes qui reçoivent le même design

Le fournisseur de devis et son consommateur utilisent le contrat JSON/HTTP de
la référence [build_design](../build_design/README.md). Chaque équipe fictive
possède un rôle de réalisation R et un rôle responsable A, avec un sujet exact.

Depuis la racine du dépôt, dans l'environnement Python AIR installé :

```text
python scripts/demo_builder_handoff.py --output tmp/builder-reception
```

Le dossier de sortie doit être nouveau. Le script crée une installation SQLite
isolée, des identités fictives et des mandats de réception limités aux rôles.
Il produit un paquet par CLI, ouvre une question, reçoit les quatre rôles,
retire explicitement la question et compare la lecture CLI avec le MCP. Une
nouvelle version perd les réceptions antérieures et montre l'unité exclue.
Le script arrête son serveur à la fin et ne modifie aucun dossier métier.

Ouvrir `project/livrables/site/index.html`, puis « Préparer la réalisation ».
Le paquet exporté se trouve dans `packet/` : modèle fermé, manifeste et suite de
contrat. Les accès et journaux de `.air/` restent privés. Ne pas les publier.

Cette recette vérifie un protocole technique avec deux équipes fictives.
Elle ne remplace aucune acceptation humaine ni revue indépendante.
