# Mapping AMASE pour discussion

Source : checklist AMASE fournie, une page, 48 contrôles dans 16 familles, puis certification. Son empreinte figure dans le mapping machine (document historique ou livrable local non inclus).

**Aucun profil AMASE n’est intégré.** Les types candidats permettent des déclarations ; leur présence ne prouve pas la satisfaction du contrôle. Tous les évaluateurs AMASE restent NOT_IMPLEMENTED.

Avant intégration, discuter : applicabilité, preuve suffisante, responsable, contrôles calculables, exceptions et règles de réception. Adapter CI/CD et référentiels réglementaires au contexte. Compléter migrations/coexistence/retour arrière, qualité et cycle de vie des données, performance, accessibilité et fin de vie.

| Contrôle | Question | Types candidats | Preuve attendue / lacune |
| --- | --- | --- | --- |
| AMASE-01-01 - Gouvernance | Demande issue du portefeuille | Intent, Source | Référence de demande, périmètre et sponsor. |
| AMASE-01-02 - Gouvernance | Travail inscrit au backlog architecture | Intent, Source | Identifiant du travail et équipe responsable. |
| AMASE-01-03 - Gouvernance | Décisions, raisons, impacts et propriétaires | Decision | Options, raison, conséquences et propriétaire exacts. |
| AMASE-01-04 - Gouvernance | Décision attendue du comité | Decision, Stakeholder | Question à décider, mandat et participants. |
| AMASE-02-01 - Métier | Liens aux exigences métier | Requirement, Function | Chaîne besoin → fonction → contrat. |
| AMASE-02-02 - Métier | Liens aux exigences non fonctionnelles | QualityRequirement, ComplianceMapping | Cible et mécanismes de conception reliés. |
| AMASE-02-03 - Métier | Processus ou parcours actuels | Workflow, CustomerJourney | Baseline explicitement identifiée comme existant. |
| AMASE-02-04 - Métier | Processus ou parcours cibles | Workflow, CustomerJourney | Baseline cible exacte et écarts au départ. |
| AMASE-02-05 - Métier | Impact sur les capacités | Capability, ChangeSet | Capacités affectées et justification des changements. |
| AMASE-03-01 - UI | Wireframes ou designs référencés si changement UI | NavigationMap, Source | Artefact UX exact et correspondance écrans/parcours. |
| AMASE-04-01 - Applications | Architecture applicative actuelle | ArchitectureBlock, RuntimeComponent | Vue existante avec responsabilités et dépendances. |
| AMASE-04-02 - Applications | Architecture applicative cible | ArchitectureBlock, RuntimeComponent | Vue cible, composants et contrats exacts. |
| AMASE-04-03 - Applications | Disponibilité selon score A | QualityRequirement, ComplianceMapping | Échelle explicite, cible, scénario de défaillance et mécanismes. |
| AMASE-05-01 - Intégration | Inventaire actuel API, queues, topics, RPC | Port, TechnicalBinding, DataFlow | Noms fonctionnels et bindings dans la baseline existante. |
| AMASE-05-02 - Intégration | Inventaire cible API, queues, topics, RPC | Port, TechnicalBinding, DataFlow | Inventaire cible et compatibilité prévue ; RPC non qualifié par analogie. |
| AMASE-06-01 - Données | Modèle logique actuel, relations entités | Concept, ConceptRelation, DataEntity | Entités, identités, cardinalités exactes dans l’existant. |
| AMASE-06-02 - Données | Modèle logique cible | Concept, ConceptRelation, DataEntity | Modèle cible et mappings sans relations inventées. |
| AMASE-06-03 - Données | Impact données personnelles et DPIA | QualityRequirement, Control, Source | Catégories, flux, traitements et analyse de conception documentés. |
| AMASE-06-04 - Données | Confidentialité selon score C | QualityRequirement, Control | Échelle explicite, restrictions, zones et responsabilités. |
| AMASE-06-05 - Données | Intégrité selon score I | QualityRequirement, Constraint | Invariants et vérifications de conception ; ne pas confondre avec intégrité du registre AIR. |
| AMASE-07-01 - Infrastructure | Infrastructure actuelle, tous environnements | Environment, RuntimeComponent, Device | Environnements attendus, couverture et informations absentes. |
| AMASE-07-02 - Infrastructure | Infrastructure cible, tous environnements | Environment, RuntimeComponent, Device | Implantation, capacités, dépendances et changements. |
| AMASE-08-01 - Réseau | Architecture réseau actuelle | NetworkZone, Connection | Zones et connexions de la baseline existante. |
| AMASE-08-02 - Réseau | Architecture réseau cible | NetworkZone, Connection | Zones, protocoles, ports, protections et écarts. |
| AMASE-09-01 - Sécurité | Modèle de menaces actuel | Risk, Control, Source | Actifs, frontières, menaces et hypothèses liés ; pas de type ThreatModel dédié. |
| AMASE-09-02 - Sécurité | Modèle de menaces cible | Risk, Control, Source | Menaces et traitements de la cible, reste à accepter. |
| AMASE-09-03 - Sécurité | Standards minimaux d’authentification | Control, Policy | Standard exact applicable et mécanismes du design ; auth AIR distincte. |
| AMASE-09-04 - Sécurité | Impacts IAM évalués | Control, Role, AuthorityScope | Identités, droits, séparation des responsabilités et changements du système conçu. |
| AMASE-10-01 - Engineering | Outillage développement/test/livraison à changer | Technology, RuntimeComponent | Inventaire et delta des outils. |
| AMASE-10-02 - Engineering | Livraison des composants par CI/CD | RuntimeComponent, Control | Processus de livraison adapté au contexte ; pas une autorisation de lancer la CI AIR. |
| AMASE-11-01 - Résilience | Standards minimaux de logs | QualityRequirement, Control | Événements, conservation, données sensibles et accès prévus. |
| AMASE-11-02 - Résilience | Monitoring, health checks et métriques | Metric, QualityRequirement, Control | Signaux, cibles, alertes, responsables et actions. |
| AMASE-11-03 - Résilience | Reprise après sinistre | QualityRequirement, Control, Source | RTO/RPO, dépendances, plan de reprise et vérifications prévues. |
| AMASE-11-04 - Résilience | Stratégie de sortie et moyens associés | ArchitecturePrinciple, Decision, ConstructionUnit | Portabilité, contrats, export des données, coûts et étapes de sortie. |
| AMASE-12-01 - Changement | Évolutions organisationnelles | OrganizationUnit, Role, RaciAssignment | Organisation actuelle/cible et impacts. |
| AMASE-12-02 - Changement | Compétences nécessaires livraison/exploitation | Role | Écarts aux compétences disponibles et méthodes d’évaluation. |
| AMASE-12-03 - Changement | Modèle de support cible évalué | OperatingModel, Role, Source | Responsabilités, escalade, horaires et engagements proposés. |
| AMASE-12-04 - Changement | Formations recommandées | Role, Source, Milestone | Plan de formation, publics, contenus, coût et jalons. |
| AMASE-13-01 - Finance | Efforts estimés avec les équipes IT | Estimate, DeliveryEstimate | Bases et provenance des estimations, pas uniquement un chiffre généré. |
| AMASE-13-02 - Finance | Delta des achats/retraits logiciel/matériel | Technology, Device, CostItem | Existant/cible, licences, capacité, achat/retrait et coûts. |
| AMASE-13-03 - Finance | Coûts de changement, formation, coaching, conseil | CostItem | Hypothèses, période, devise, responsables et confiance. |
| AMASE-14-01 - Delivery | Blocs livrables et WBS | ConstructionUnit | Unités, dépendances, livrables et critères d’acceptation. |
| AMASE-14-02 - Delivery | Séquence de construction et roadmap | Roadmap, Milestone | Phases, dépendances et critères de sortie. |
| AMASE-15-01 - Réglementation | Patterns/références GDPR applicables | Obligation, Control, ComplianceMapping | Référence versionnée, applicabilité, mécanisme et preuve de portée. |
| AMASE-15-02 - Réglementation | Patterns/références DORA applicables | Obligation, Control, ComplianceMapping | Référence versionnée, applicabilité et contrôles ; aucune conformité automatique. |
| AMASE-16-01 - Communication | Décideurs et direction associés aux décisions | Stakeholder, AuthorityScope, Decision | Parties prenantes, décision attendue et revue habilitée. |
| AMASE-16-02 - Communication | Légende de chaque diagramme | Viewpoint, View | Sémantique des symboles, relations et niveau de preuve ; légende de site livrée. |
| AMASE-16-03 - Communication | Impacts et nature des changements sur les diagrammes | ChangeSet, View | Création/modification/suppression/consommation explicitement distinguées. |

La certification finale doit conserver les droits, avis humains, exceptions et empreinte de la baseline. Le site HTML améliore la lecture ; il ne produit ni attestation ni approbation.
