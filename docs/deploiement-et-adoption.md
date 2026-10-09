# Installation, exploitation et adoption en entreprise

Statut : cible L16/L17 actualisée avec SQLite/local par défaut. La [recette installable actuelle](installation.md) et l’[état de réalisation](etat-implementation.md) distinguent livré et cible.

## 1. Distributions

| Mode | Contenu | Usage et qualification |
| --- | --- | --- |
| Local | Installateur Python, SQLite, fichiers locaux, jetons locaux, CLI et API ; templates, vues et MCP stdio à compléter | Architecte, formation, CI ; fonctionnement sans cloud et sans registre transverse |
| Équipe | SQLite/local par défaut sur un hôte ; PostgreSQL et OIDC au choix ; Workbench et OCI à compléter | Pilote et petite installation ; sauvegarde, TLS et droits obligatoires avant données réelles |
| Entreprise | PostgreSQL et OIDC optionnels pour services répliqués selon SLO ; workers, registres par autorité et stockages d’entreprise ; Kubernetes optionnel | Portefeuille, engagements et exploitation ; haute disponibilité qualifiée |
| Réseau restreint / hors ligne | Mêmes binaires signés, dépendances et images en miroir, schémas et docs embarqués, identité locale d’entreprise | Installation sans accès Internet ; modèles locaux ou agentique désactivée selon politique |

Le mode local ne peut pas confirmer des engagements sur des ressources partagées dont il ne possède pas le registre. Un serveur mono-instance peut avoir des garanties transactionnelles sans avoir de haute disponibilité : la recette doit distinguer ces propriétés.

L’installation self-hosted constitue la cible initiale. Un SaaS mutualisé est une extension commerciale distincte nécessitant une qualification supplémentaire d’isolation et d’exploitation. Un fournisseur d’infrastructure n’est pas imposé.

## 2. Paquet remis à l’administrateur

Livrer binaires/images et digests, SBOM et licences, fichiers de déploiement versionnés, configuration documentée, matrice de versions supportées, scripts de prérequis, diagnostics, recettes de mise à niveau/restauration et jeux de test sans données sensibles.

La configuration d’entreprise contient : identifiant et namespaces ; autorités et délégations ; classifications/compartiments ; sources faisant foi ; profils et versions ; règles de validation locales ; calendriers et unités ; politiques de fraîcheur/rétention ; bibliothèques ; fournisseurs IA autorisés ; budgets ; stockage ; endpoints ; références de secrets ; exigences de disponibilité. Les noms de ces fichiers seront fixés en L00 ; les secrets ne sont pas des valeurs versionnées.

bootstrap, doctor, serve, capabilities, validate, put/get et administration locale des jetons sont disponibles dans la première tranche. export et migrate ne sont pas livrés. Voir la recette exacte dans installation.md.

## 3. Parcours d’installation réceptionnable

1. Vérifier OS, architecture, stockage, DNS, TLS, proxy, certificats, identité et accès au miroir de packages.
2. Choisir le mode et dimensionner base, objets, calculs et rétention à partir d’un jeu de charge.
3. Déployer avec un bootstrap administrateur à usage borné ; fermer tout accès anonyme non prévu.
4. Tester identités et révocation locales ; raccorder un IdP seulement si OIDC est choisi, puis qualifier ses claims, comptes de service et départs de collaborateurs.
5. Charger le profil d’entreprise ; faire valider les mandats par les personnes compétentes.
6. Brancher les sources en lecture ; vérifier provenance, classification, couverture et qualité.
7. Initialiser un projet, configurer un IDE et jouer le scénario de prise en main.
8. Exécuter les contrôles de séparation des droits et de restauration.
9. Activer les fonctions engageantes uniquement dans les périmètres où registre, autorités et recette sont opérationnels.
10. Transférer l’exploitation et enregistrer une baseline d’installation.

Objectif de recette proposé : installation automatisée d’un environnement d’essai en moins d’une heure lorsque les prérequis sont déjà fournis. Le raccordement réel à l’identité, aux données et à la gouvernance est un travail d’intégration distinct, mesuré séparément.

## 4. Connecteurs

Contrat commun : identité de source, révision/checkpoint, mapping, périodes, fraîcheur, couverture, classification, droits, suppressions, débit, pagination, reprise et diagnostics. Commencer en lecture ; chaque écriture externe possède un mandat et un effet explicites.

| Famille | Première réalisation attendue | Évolution |
| --- | --- | --- |
| Dépôt et CI | Git local/distant, fichiers, rapports CI portables | Adaptateurs aux forges retenues par les pilotes |
| Architecture et documentation | JSON/YAML/Markdown/PDF autorisés, OpenAPI/AsyncAPI | Catalogues EA, CMDB et espaces documentaires avec mapping approuvé |
| Capacité | Import de calendrier/offre structuré et interface de confirmation par responsable | Outil portefeuille, RH ou fournisseur désigné par l’entreprise |
| Identité | Jetons locaux expirables/révocables ; OIDC optionnel | Provisioning complémentaire selon le SI |
| Observations | Import de signaux et référence aux services/baselines | Télémétrie et catalogue de déploiement de l’entreprise |
| Réalisation | Recette exportable et reçu de résultat | Connecteurs de livraison explicitement autorisés |

Aucun connecteur ne confond synchronisation et transfert d’autorité. Importer un planning ne signifie pas qu’AIR possède le droit de réserver l’équipe.

## 5. Responsabilités et décisions

| Décision / livrable | Responsable de réalisation | Autorité de réception | Contributeurs |
| --- | --- | --- | --- |
| Sémantique AIR et versions | Responsable langage | Responsable produit AIR | Architectes, assurance |
| Besoin, parcours, acceptation | Produit et métier | Sponsor / autorité métier | UX, utilisateurs, opérations |
| Modèle de solution | Architecte solution | Autorité locale du projet | Ingénierie, données, sécurité |
| Concepts et qualité des sources | Data steward | Autorité de données | Métiers, intégrations |
| Contrats et bibliothèques partagés | Responsable d’actif | Autorité du domaine | Consommateurs, architecture entreprise |
| Aménagement transverse | Architecture entreprise | Autorité de composition mandatée | Domaines et portefeuille |
| Offre et disponibilité | Responsable de ressources | Autorité du pool | Managers, RH, partenaires |
| Engagement de ressources/budget | Portefeuille et registre | Autorités concernées | Finance, achats, ressources |
| Autorisation d’un épisode | Responsable du lot | Autorité d’activation | Ressources, sécurité, exploitation |
| Mise en production et continuité | Équipe de réalisation/exploitation | Autorité de changement | Sécurité et métier |
| Formation et communication | Conduite du changement | Responsable métier | Formateurs, communication |
| Maintien après projet | Responsable SolutionAsset | Propriétaire opérationnel | Support et ingénierie |

Une personne peut tenir plusieurs rôles dans une petite structure. Les mandats et règles de séparation restent explicites. L’architecture entreprise coordonne la cohérence ; elle ne reçoit pas automatiquement le droit de disposer des ressources de tous les domaines.

## 6. Déploiement organisationnel

Première étape : un projet et un parcours bornés, deux architectes pilotes, ingénierie et métier. Modéliser l’existant utile à la décision ; éviter d’attendre l’inventaire complet de l’entreprise.

Deuxième étape : deux ou trois projets avec un actif partagé et une vraie source capacitaire. Mesurer chevauchements, délai de revue, décisions manquantes et effort de collecte. Réceptionner admission et activation sur données de test avant engagement réel.

Troisième étape : second domaine, autre type de solution et seconde installation. Vérifier que l’adaptation est une configuration ou une extension, sans fork. Former administrateurs, architectes, contributeurs non techniques et responsables d’autorité avec exercices par rôle.

Quatrième étape : extension contrôlée du portefeuille, catalogue de bibliothèques avec mainteneur, capacité de support et processus de demande d’évolution. La généralisation suit la disponibilité des responsables et des données, pas le nombre de licences installées.

## 7. Exploitation, support et réversibilité

Mesurer disponibilité API/registre, latence, erreurs, saturation, durée des jobs, coût de génération, âge des index, échéances d’offres et réservations en préparation. Les seuils et escalades appartiennent au profil d’entreprise. Les notifications ne divulguent pas de projet interdit.

Sauvegarder base d’autorité, artefacts et clés/configurations nécessaires ; tester la restauration ensemble. Conserver un journal cohérent avec les reçus et confirmations externes. Si la restauration perd des engagements récents, geler les nouvelles admissions jusqu’au rapprochement ; ne jamais supposer que Git reconstitue le registre.

Mises à niveau : compatibilité annoncée par profil, test d’anciennes baselines, migration en préproduction, sauvegarde vérifiée, plan de retour ou compensation documentée. Les changements de sémantique publient un nouveau profil. Prévoir politique de vulnérabilités, versions supportées et retrait des plugins compromis.

Export : packages et lockfiles, décisions, preuves autorisées, recettes, rapports et historique des engagements. Décrire les pièces absentes pour cause de conservation. La suppression légitime d’une source peut limiter le replay ; l’export ne contourne pas cette limite.

## 8. Coûts et mesure de valeur

Le coût total comprend réalisation du produit, contribution des équipes pilotes, intégrations, infrastructure, inférence, supervision, exploitation et maintenance des bibliothèques. Appliquer le tarif interne validé aux jours-personnes du plan ; ne pas transformer une estimation de charge en budget financier sans ce tarif.

Suivre : décisions structurantes redécouvertes, exigences traçables avec dénominateur, réutilisations acceptées, délais de revue, conflits détectés avant engagement, taux de replay par classe, erreurs prévision/réel et coût de correction agentique. Fixer les cibles après une mesure initiale. Aucun gain de productivité chiffré n’est présumé.
