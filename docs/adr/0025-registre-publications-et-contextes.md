# ADR 0025 - Registre local, publications et contextes historiques

Statut : accepté pour les sous-ensembles expérimentaux 0.7/0.8.

La migration entre moteurs transporte des tables et historiques vérifiés dans une cible vide ; elle ne publie pas une architecture. Les secrets sont réémis et la politique importée change de version. Les formats de transfert sont privés, destinés à un opérateur de confiance.

La publication locale conserve des manifestes immuables dans le registre des reçus. Un verrou SQL partagé sérialise publications, révocations et observations de contexte. Il privilégie la simplicité d’installation et la correction transactionnelle ; les périmètres de verrouillage fins restent un travail de montée en charge. Les événements de publication sont atomiques avec le manifeste, mais leur distribution distante et la reconstruction d’index distribués ne sont pas encore livrées.

Le contexte épingle les publications explicitement consultées. Son observation ne change jamais ; les droits courants restent obligatoires pour le lire. La découverte utilise des snapshots de références et curseurs opaques conservés dans le registre, avec budgets, plutôt qu’une pagination susceptible de sauter ou répéter des publications lors d’écritures concurrentes.

Les rapports de divergence conservent leurs mappings et digests. Une différence de version n’est pas une preuve d’incompatibilité. Aucune opération de cette tranche ne modifie automatiquement les sources ni ne réserve des ressources. Les modèles normatifs PackageManifest, ContextSnapshot et ReconciliationCase complets restent à réceptionner ; les contrats livrés sont des services versionnés.
