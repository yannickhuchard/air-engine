# ADR 43 - Structure d’architecture et bindings HTTP explicites

Décision du 20 septembre 2026 : ajouter six types DRAFT dans air.architecture/0.26, sans migration SQL. Les anciens profils conservent leur fermeture.

Les blocs déclarent fonctions, contrats fournis/requis et données possédées. Les ports doivent reprendre le contrat exact dans la bonne direction ; leurs bindings doivent désigner le même contrat. Les mappings HTTP/JSON décrivent explicitement opération, méthode, route littérale, schémas, statut de réponse et présence obligatoire ou facultative du corps de requête.

L’inspection conserve opérations non mappées, lacunes et livrables attendus. Les transformations de flux restent ordonnées et non exécutées. Aucun endpoint n’est contacté ; sécurité, compatibilité de comportement et implémentation restent à qualifier.

Ce socle prépare la compilation de descriptions d’API. Le binding n’invente pas de routes, de mécanismes de sécurité ou de traitement d’erreur à partir du texte. La suite de compilation devra déclarer les transformations et pertes.
