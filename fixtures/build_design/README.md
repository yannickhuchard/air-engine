# Deux composants construits sur le même contrat

Cette référence fictive Asteria illustre le lot B. Un consommateur demande un
devis de 1 à 100 unités ; un fournisseur calcule 125 centimes EUR par unité.
Les deux prototypes utilisent seulement la bibliothèque standard Python et
n'importent ni AIR ni le code de l'autre composant.

Le modèle `model.py` déclare le contrat, ses fonctions, ses unités, ses ports et
ses schémas. La recette conserve les schémas en artefacts locaux avant de créer
une baseline exacte. L'InterfaceSpecification contient des préconditions,
postconditions, un invariant, les règles d'idempotence et des contre-exemples.

Depuis le dépôt installé :

```text
python scripts/demo_build_design.py --output tmp/ma-recette-contrats
```

Le répertoire de sortie doit être neuf. La recette démarre deux processus de
prototype et une API AIR isolée, applique la suite par CLI, vérifie les échanges
sur HTTP loopback, compile le site et arrête ses serveurs. Les jetons restent
dans le sous-dossier privé `.air` et ne sont pas imprimés.

Le dossier conserve volontairement des questions ouvertes : budget, risques,
parcours, responsabilités et autres dimensions de projet. Aucun verdict
« prêt à construire » n'est déduit de cette petite intégration. Le cache en
mémoire du prototype ne reçoit ni fenêtre d'expiration, ni persistance, ni
concurrence, ni sécurité de production. Les limites sont dans le reçu.
