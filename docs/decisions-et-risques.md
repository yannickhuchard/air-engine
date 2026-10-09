# Décisions de conception et risques

Les points ci-dessous sont des travaux de formalisation du produit. Les solutions sont proposées, sauf ADR-19 SQLite/local explicitement ACCEPTED ; le white paper reste inchangé. Le PDF contient une spécification de référence et des exemples ; ses instructions d’atelier ne donnent pas d’autorisation d’action externe dans cette analyse.

## 1. Décisions nécessaires

| ADR | Sujet et observation | Proposition à formaliser | Lot / responsable |
| --- | --- | --- | --- |
| ADR-01 | Périmètre de « complet » et profils (§3.4) | Matrice types/règles/portes/effets ; cinq profils et activation ; manifeste de conformité par version | L00 / produit |
| ADR-02 | Records et enums partiellement décrits (A, D.2) | Schémas stricts de tous les records, valeurs inconnues explicites et limites ; aucune structure libre en production | L00–L01 / langage |
| ADR-03 | Relations compactes Ref et liens explicites (A.1, B.1) | Registre de mapping champ → relation, identité déterministe et règle de priorité ; conflit signalé | L01 / langage |
| ADR-04 | Temporalité (§5.4) | Modèle de correction et reconstruction bitemporelle ; validité métier séparée de recorded_at | L01 / noyau |
| ADR-05 | Expression incomplètement formalisée (D.4) | Grammaire d’AST, types, unités, erreurs, propagation des conflits et budgets ; pas d’eval libre | L02 / langage |
| ADR-06 | UNKNOWN bloquant en B.2, traitement permis au §6.2 | Résultat UNKNOWN conservé ; politique de porte séparée, exceptions uniquement là où autorisées ; jamais pour une obligation non dérogeable | L02 / assurance |
| ADR-07 | Portes nommées Core/Construct/Build/Publish/Publication etc. (C) | Identifiants canoniques, alias documentaires et mapping profil/porte ; pas d’assimilation tacite | L02 / langage |
| ADR-08 | Approbation/mandat (D.2, D.7) | Objet signé ou référence vérifiable liée à digest, principal, scope, version et validité ; révocation et séparation des fonctions | L04 / sécurité |
| ADR-09 | États de reçus : prose évoquant expiration/révocation, B.2 donnant un autre jeu | Distinguer validité du reçu, état d’admission et état de réservation ; transitions explicites, historique intact | L13 / gouvernance |
| ADR-10 | Recalcul strict du planning (§10.4) | Plan sélectionné persisté ; configuration solveur et départage ; comparaison de faisabilité si identité non garantie | L10 / calcul |
| ADR-11 | Coordination inter-autorités (§13.4, D.7) | Préparations expirantes et coordinateur durable ; compensations, timeouts et reprise documentés ; pas d’atomicité globale supposée | L13 / backend |
| ADR-12 | Autorisation et départ effectif (F.5) | Transition de lancement liée à épisode/plan/fenêtre, protégée contre TOCTOU et double départ ; pas de déploiement implicite | L14 / backend |
| ADR-13 | Droit d’accès versus contexte historique (§15) | Reproduction de données autorisées seulement ; autorisations actuelles appliquées ; pièces effacées signalées | L04–L15 / sécurité |
| ADR-14 | Modèle de publication Git/registre (§3.2, D.6) | Git pour édition ; manifeste publié comme frontière de distribution ; état projet distinct de l’engagement | L03–L11 / noyau |
| ADR-15 | Noyau relationnel ou graphe spécialisé (§18.1) | SQLite par défaut et PostgreSQL optionnel selon ADR-19 ; moteur spécialisé uniquement après benchmark | L00 / architecture |
| ADR-16 | Déploiement et licence | Self-hosted initial, distributions portables ; licence et modèle de maintenance à choisir avant redistribution publique | L00–L16 / produit |
| ADR-17 | Sérialisation et canonicalisation (D.2) | Chaînes décimales exactes, ensembles normalisés, test de vecteurs interlangages, digests externes | L01 / noyau |
| ADR-18 | Confiance fédérée | Registre d’autorités, ancres de confiance, rotation/révocation, namespaces, visibilité et compatibilité des profils | L04–L11 / sécurité |
| ADR-19 | Installation sans friction, demande explicite de l’utilisateur | SQLite et jetons locaux par défaut ; PostgreSQL/OIDC indépendants ; SKILL.md et installation automatisée ; décision [ACCEPTED](adr/0019-sqlite-et-identite-locale.md) | L00, L04, L16 |

## 2. Points précis à rapprocher dans les annexes

- A.3 utilise Evidence.supports_or_refutes tandis que B.1 distingue supports et refutes. Le schéma doit enregistrer le sens de chaque lien ; une liste non signée serait ambiguë.
- A.6 permet DataSchema.represents vers DataEntity/Message alors que la relation represents de B.1 cible Concept pour « DataEntity ou schéma ». Décider une normalisation documentée ou des relations distinctes ; ne pas inventer une équivalence de types.
- AIR-V019 demande état et responsable de réalisation d’une fonction, au-delà des champs spécifiques explicitement listés dans Function. Définir le mapping vers état, allocation et owner/autorité plutôt que laisser le validateur deviner.
- Les Activity/Agent de provenance, IdentityRef, PermissionSpec, ApprovalRef, ClassificationRecord, TemporalRecord et les records de planning nécessitent une définition exécutable complète.
- Ref peut créer des cycles légitimes de connaissance ou de composition référentielle ; seuls les graphes explicitement acycliques doivent être refusés. Le bootstrap des TypeDefinition et des packages du noyau doit être défini.
- Le versionnement d’une règle, d’un profil, d’un schéma, d’un package et d’une implémentation ne doit pas partager un compteur unique.
- Les corps des trois API F.5, leurs bindings HTTP, la gestion des erreurs et le contrôle du déclencheur d’exécution restent à préciser.
- Les cinq types d’activation s’ajoutent aux 138 de l’annexe A ; les records, projections et valeurs de kind ne sont pas des types autonomes supplémentaires.

Ces observations motivent L00. Elles n’empêchent pas le découpage, mais conditionnent une réalisation fidèle et testable.

## 3. Risques de réalisation et réponses

| Risque | Impact | Réponse et preuve attendue |
| --- | --- | --- |
| Tout modéliser avant le premier usage | Délai sans apprentissage | Tranche Claims de bout en bout en I1 ; sous-périmètre explicite |
| Schémas créés mais comportements absents | Faible valeur avec fausse impression de complétude | Tests par règle, transition et contrat ; manifeste sans succès fictif |
| Données capacitaires peu fiables | Planning inapplicable | Sources datées, qualification, confirmation par responsables et UNKNOWN |
| Compromission par source ou plugin | Fuite ou action non autorisée | Isolation, contrôle des effets et tests négatifs de bout en bout |
| Double réservation / double activation | Engagement incohérent | Tests concurrents réels, verrous de scopes, idempotence et reprise |
| Dépendance à un seul IDE ou LLM | Perte de portabilité | Interfaces communes et même suite sur six familles |
| Recherche révélant des objets cachés | Divulgation de stratégie | Filtrage avant recherche, couverture restreinte, caches et erreurs contrôlés |
| Trop de microservices | Charge d’exploitation | Monolithe modulaire ; séparation justifiée par mesure |
| Multiplication des forks d’entreprise | Maintenance divergente | Configuration et extensions versionnées, tests de compatibilité |
| Automatisation de revues qualitatives | Décisions non fondées | Protocole humain conservé, preuve et autorité |
| Promesse de productivité non mesurée | Budget et calendrier fragiles | Estimations sans multiplicateur IA, mesure du coût de supervision |
| Restauration partielle du ledger | Reprise sur de faux engagements | Recette intégrée et rapprochement ; gel des admissions si doute |
| Gouvernance trop lourde | Abandon par les équipes | Parcours par rôle, seuils adaptés et mesure de la charge de décision |
| Maintenance des actifs sans propriétaire | Dette après projet | Transfert explicite à SolutionAsset et budget de bibliothèque |

## 4. Hypothèses retenues pour cette analyse

Le développement a démarré sans code existant ; une première tranche bootstrap est maintenant livrée ; le produit vise l’installation privée et la portabilité ; les cinq profils et activation appartiennent à la cible ; une surface par famille IDE est qualifiée initialement ; les exemples sont synthétiques ; les choix technologiques sont proposés, non imposés aux entreprises utilisatrices.

L’équipe de référence est dimensionnée pour calculer une enveloppe de réalisation. Les noms des entreprises pilotes, leurs IdP, contraintes réseau, volumes réels, outils de ressources et tarification de charge ne sont pas connus. Ces informations seront nécessaires pour engager un déploiement réel, mais pas pour produire cette analyse.

Le lot L00 doit arbitrer les choix de produit et de langage. Le profil de chaque entreprise renseigne ses autorités, classifications, conservation et obligations avec ses fonctions compétentes. Le présent dossier ne se substitue pas à cette décision d’entreprise.


## Formalisation de la tranche 02

[ADR-20](adr/0020-profils-fondation-et-fermeture.md) formalise le sous-profil expérimental de six types de données, les liens de preuve orientés, les baselines fermées et les propositions de changement. Cette implémentation partielle ne ferme pas les autres ADR de langage, d’autorité et de publication.
