# D03 — Arrivées, mobilités et départs des collaborateurs

Source fictive : atelier RH, IAM, managers, support et sécurité. Date de référence :
21 septembre 2026. Les délais proposés sont des objectifs internes synthétiques,
sans prétention de conformité à une obligation légale.

## Besoin et existant

Le SIRH décrit les salariés ; les prestataires sont suivis par leurs sponsors.
L’annuaire et plusieurs applications nécessitent des opérations manuelles.
Une mobilité peut laisser des droits de l’ancien poste ; une prolongation de mission
peut être connue après la création d’une demande de désactivation.

Le pilote coordonne création, modification et retrait des accès à trois applications.
Les dates et statuts salariés proviennent du SIRH. Les comptes prestataires nécessitent
un sponsor identifié et une échéance. Le rôle RH, le rôle d’approbateur métier et
le rôle d’exécution IAM sont distincts dans le scénario.

## Périmètre, alternatives et contrats à construire

Comparer une orchestration avec validations manuelles et des connecteurs de
provisionnement ciblés. Le remplacement du SIRH et une refonte générale de l’annuaire
sont hors périmètre. Le projet réutilise le service d’identité utilisé par D01 et D02.

Le contrat RequestAccessChange précise personne, événement RH exact, droits demandés,
date d’effet, approbateur et preuves. La proposition, l’approbation et l’exécution
restent trois étapes. Un agent ne peut pas s’accorder des droits en inscrivant
approved: true. Une erreur de connecteur laisse un état partiel visible, jamais
« tous les accès retirés » sans confirmation des systèmes concernés.

## Parcours à démontrer

1. Distinguer données faisant foi, déclarations de sponsors et décisions d’accès.
2. Traiter une arrivée, une mobilité et un départ synthétiques sans contacter un annuaire réel.
3. Signaler un prestataire dont la date de fin est inconnue ; attribuer sa résolution.
4. Refuser une approbation auto-déclarée et conserver la décision avec son digest exact.
5. Modifier la politique d’identité partagée et montrer les impacts possibles sur
   les accès clients de D01 et les comptes collecteurs de D02, sans leur appliquer
   automatiquement une règle destinée aux salariés.

## Inconnues et critères attendus

La correspondance salarié/prestataire/compte et les délais de propagation doivent
être qualifiés. Une révocation demandée et une révocation confirmée sont distinctes.
La vue RH ne doit pas exposer un secret technique ; le technicien atelier ne doit
pas récupérer des données RH. Ces permissions fines sont une réception à construire,
pas une propriété du rôle reader global de la version bootstrap.

Besoin capacitaire synthétique : 1 ETP d’intégration pendant les semaines 1–4,
soit 4 ETP-semaines. Le besoin partagé total dépasse l’offre initiale de l’équipe ;
le dossier seul ne doit pas annoncer que toute l’offre est disponible pour lui.
