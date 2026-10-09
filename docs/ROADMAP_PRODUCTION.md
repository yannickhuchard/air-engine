# Roadmap AIR vers la production

Date : 25 septembre 2026. Point de départ : 0.33.1, commit `f8bf3e1c145ee538651c6a6cc32d290bdcd9f9df`.
Cette roadmap complète le [plan normatif L00–L17](AIR_PLAN_DEVELOPPEMENT.md) ; elle ne le remplace pas.
Les anomalies initiales et les preuves sont dans l'[audit de production](audit-production-0.33.1.md).
Le statut exécutable des lots et les résultats de réception sont conservés dans
production-roadmap.json (document historique ou livrable local non inclus).

**Décision du 28 septembre 2026 :** le périmètre courant P07 exige **Codex et ChatGPT**.
Claude est retiré des critères requis, la validation indépendante est différée.
P07 et le pilote technique P08 sont désormais [terminés localement](cloture-p07-p08-local.md) ;
La demande suivante reçoit G1 dans ce périmètre : [décision](g1-reception-locale.md),
support communautaire publié et licence Apache-2.0 confirmée. La
[décision versionnée](decision-p07-p08-local.md) prévaut sur les critères historiques
ci-dessous ; le [contrat P08 local](lot-pilote-local.md) définit les travaux exécutables.

## Résultat attendu et portes de sortie

**G1 - production pour la conception d'architecture sur poste** : chaque architecte peut installer AIR
avec Python, SQLite et identité locale, utiliser les clients effectivement qualifiés, conserver et restaurer
ses décisions et preuves. Le pilote reçoit aussi les échanges contrôlés entre postes. Les limites sémantiques
restent affichées. G1 exige P01–P08 reçus dans ce périmètre et un support publié ; elle ne signifie ni
conformité complète au white paper ni exécution de la solution métier conçue. Décision utilisateur du
26 septembre 2026 : [installations autonomes d'abord, serveur centralisé plus tard](production-poste-architecte.md).

**G2 - déploiement d'entreprise étendu** : G1 et P09 reçus pour la combinaison choisie. PostgreSQL et OIDC
restent indépendants ; aucune option d'entreprise ne doit devenir un prérequis du démarrage local.
La réception centralisée est différée jusqu'à une décision liée à l'adoption multi-entreprise.

**G3 - AIR complet** : G1, P10–P14 et toutes les obligations applicables L00–L17 reçus, avec la matrice des
types, règles, opérations, transitions et profils testés. Un type portant le même nom qu'un type normatif,
un test de schéma ou une démonstration illustrative ne constitue pas sa conformité.

L'ordre ci-dessous donne les dépendances de réception. La documentation, la sécurité et les tests font partie
de chaque lot. Une date de livraison exige une capacité d'équipe et des objectifs de charge convenus ; les
lots ne sont pas convertis artificiellement en semaines ni en pourcentage d'achèvement.

## Lots de sécurisation et de mise en production

### P01 - Revues effectives et statut honnête des preuves

Propriétaire : noyau et assurance ; dépendance : aucune. Rattachement : L02, L04, L07 ; AUD-01, AUD-02.

- Relire chaque reçu avec le service d'autorité : cible et digest exacts, acceptation, expiration, révocation,
  politique courante, mandat et accès aux éléments de la revue. Un rejet effectif empêche l'acceptation,
  même s'il existe une autre revue positive ; sa levée passe par un geste explicite et traçable.
- Appliquer le même résultat aux écarts acceptés par décision et à la revue indépendante.
- Empêcher un `VerificationRun` déclaratif de s'auto-attribuer le statut `VERIFIED`. Une pièce jointe, un
  nom d'exécuteur ou un champ `proof_level` ne sont pas une attestation d'exécution.
- Corriger les formulations des livrables et de la présentation qui confondent résultat déclaré et preuve.

Réception : acceptation valide, rejet, conflit de revues, expiration, révocation, perte de mandat,
changement de politique, cible différente et preuve auto-déclarée testés. La lecture doit échouer sans
accorder la porte si son budget de reçus est dépassé. Révisions historiques préservées.

**Limite volontaire de cet incrément** : les succès déclarés deviennent `PASS_UNVERIFIED` (ou restent
`PASS_ON_DECLARED_MODEL`). La porte VERIFICATION reste ouverte pour ces cas, y compris si une personne
a revu la baseline. Le mécanisme positif de qualification arrive en P03 ; supprimer un faux positif ne
vaut pas fournir ce mécanisme.

### P02 - Simulation et montants sans faux succès

Propriétaire : moteur de calcul ; dépendance : P01 pour l'interprétation des preuves. Rattachement : L02,
L09, L10 ; AUD-03, AUD-04, AUD-05.

- Calibration : accepter uniquement des quantités de durée explicites, finies et non négatives ; convertir
  secondes et millisecondes. Refuser unités inconnues, statistiques ambiguës et références inutilisables.
  Toutes les observations citées doivent convenir, pas seulement le sous-ensemble exploitable.
- Simulation : conserver le résultat conditionnel sur les parcours mesurés, mais déclarer INCONCLUSIVE
  lorsqu'une garde est indécidable ou une durée d'étape absente. Exposer la population mesurée et exclue.
- Monnaie : ne jamais additionner ou comparer deux devises sans conversion explicite. À ce stade, refuser
  les agrégats mixtes avec un diagnostic ; aucune conversion implicite. Afficher la devise réelle des decks.
- Tester les contre-exemples de l'audit et les cas valides afin de conserver l'utilité du calcul.

Réception : résultats déterministes ; compteurs réconciliés ; zéro sérialisable sans NaN/Infinity ; unités
incompatibles non calibrées ; inconnues non PASS ; montants homogènes inchangés et mixtes refusés.
La calibration reste un accord numérique sur des observations déclarées, sans attestation de provenance,
de représentativité, de fraîcheur ou de comportement réel. Ces obligations passent à P03 et P11.

### P03 - Qualification positive des preuves

Propriétaires : assurance, noyau, architectes ; dépendances : P01, P02. Rattachement : L02, L04, L07, L09.

Livrer un contrat de preuve distinguant déclaration, revue humaine, calcul AIR et exécution externe.
Lier chaque qualification aux digests du cas, de l'oracle, des entrées, de l'environnement, du moteur et
du rapport intègre ; vérifier l'identité de l'exécuteur, son mandat, la portée et la validité temporelle.
Définir les qualifications admises par critère, leur expiration et leur invalidation après changement.
Un avis humain atteste un avis, pas un test logiciel. Réexécuter ou authentifier le calcul AIR ; importer
les rapports externes par des adaptateurs explicitement qualifiés. Arbitrer les exécutions concurrentes et
les dates déclarées sans faire du dernier horodatage fourni par le client une autorité.

Réception : un parcours positif ferme VERIFICATION au niveau publié ; rapport falsifié, ancien oracle,
autre environnement, replay, rapport illisible, signature invalide et identité retirée sont refusés.
CLI/API/MCP et livrables montrent la même justification. Aucune migration ne réécrit une ancienne preuve.

**Réception P03 dans le périmètre publié** : le [binding de conception](lot-qualification-preuves.md)
est complété par les [attestations externes](lot-preuves-externes.md), adaptateur `air.python-unittest/1`.
Clé Ed25519 mandatée, challenge exact, fraîcheur, import idempotent, revue indépendante et invalidations
sont vérifiés. Les avis de conception et les tests exécutés restent comptés séparément. D'autres adaptateurs
et la représentativité des mesures de simulation ne sont pas qualifiés ; cette dernière relève de P11.
Preuves P03/P04 (document historique ou livrable local non inclus).

### P04 - Identités, autorisations et exposition MCP

Propriétaires : sécurité et intégrations ; dépendances : P01, P03. Rattachement : L04, L05 ; audit catalogue MCP.

Aligner les catalogues stdio/HTTP par rôle et capacité ; vérifier les droits au moment de l'appel, dans les
résultats, pièces jointes, caches, jobs, exports et journaux. Associer chaque utilisateur à son identité AIR ;
documenter et isoler les connexions utilisant une identité de service. Tester révocation en session, rotation,
accès entre namespaces, arguments malveillants et injections dans les sources importées.

Réception : matrice lecteur/éditeur/relecteur/administrateur et deux équipes antagonistes passée sur les
deux transports ; aucune élévation depuis le texte d'un document ou un paramètre client ; aucun secret
dans les fichiers produits ni dans les erreurs. Un tunnel partagé n'est pas annoncé comme SSO individuel.

**Réception P04 dans le périmètre publié** : [contrat des identités MCP](lot-identites-mcp.md),
matrice de quatre rôles et deux équipes sur stdio/HTTP, révocation et rotation, caches et artefacts,
autorité revérifiée dans les transactions et avant émission des résultats, traces et diagnostics protégés.
La connexion utilise son identité authentifiée ; les clients natifs et IdP réels restent P07/P09.

### P05 - Distribution reproductible et mise à niveau

Propriétaire : Developer Experience ; dépendances : P01–P04. Rattachement : L00, L03, L16, L17.

Corriger la préparation des dossiers temporaires de CI PostgreSQL et le suivi du nettoyage : distinguer
le résultat des tests d'un délai d'arrêt dépassé, rendre ce délai configurable et vérifier l'arrêt effectif.
La recette P01/P02 a passé ses tests mais son checkpoint d'arrêt a pris 106,740 s, au-delà du délai de 60 s ;
l'arrêt a ensuite été confirmé. Exécuter toute la suite sur SQLite
et PostgreSQL, Windows et Linux, et qualifier macOS avant de le déclarer supporté. Construire archive et
wheel depuis le même commit, avec inventaire, empreintes, dépendances épinglées et SBOM. Qualifier installation
Python seule, réinstallation, installation sans accès public avec miroir, sauvegarde, mise à niveau et retour
à la sauvegarde. Aligner README, skill d'installation, capacités et documentation sur les résultats présents.

Réception : installation sur machine propre par un agent ayant uniquement lu la documentation et SKILL.md,
sans étape secrète ; données et identités conservées ; restauration vérifiée ; matrice CI entièrement verte
pour la version publiée. Une ancienne qualification ne couvre pas une nouvelle archive.

### P06 - Exploitation, sécurité et limites de service

Propriétaires : exploitation et sécurité ; dépendances : P04, P05. Rattachement : L04, L16, L17.

Pour G1, appliquer le [profil poste](production-poste-architecte.md). Définir les volumes et objectifs
locaux supportés, puis mesurer imports, baselines, requêtes, simulation, jobs et pièces jointes.
Préserver les ressources du poste, les quotas et la reprise ; tester arrêt brutal, manque d'espace,
verrouillage SQLite et restauration vers une installation vierge. Livrer diagnostics locaux sans secrets,
journaux bornés, procédures de sauvegarde/reprise, vulnérabilité et support.

Réception locale : seuils écrits atteints, restauration avec digests identiques et anciennes identités
révoquées, protection des données/jetons et isolation locale vérifiées. Documenter la reprise après perte
du poste et les limites de conservation. Faire exercer les procédures par une autre personne et revoir
la sécurité du profil local lors du pilote indépendant P08. La livraison technique P06 inclut le
diagnostic, les recettes, les procédures et leur vérificateur ; sa réception technique ne reçoit pas
ces interventions indépendantes ni G1. Le [profil rc8](lot-poste-local.md) distingue les reçus locaux
des reçus serveur ; aucun libellé PASS ne remplace un contrôle effectué.

La candidate rc7 ajoute les [limites du service et le vérificateur du dossier](lot-exploitation-cloture.md).
Les plafonds Windows sont exercés localement ; le contrôle cgroup Linux reste à exercer sur la cible.
Le dossier serveur historique conserve l'exploitation étendue. Pour le futur serveur centralisé, différer
les objectifs de charge agrégée, seuils SQLite/PostgreSQL, PKI, notification d'entreprise, sauvegarde
institutionnelle hors site et réception infrastructure ; ces critères seront repris avec P09/G2.
La CI est réservée à la réception de la version de production complète ; les tests locaux restent actifs.

### P07 - Clients agentiques réellement qualifiés

**Statut : techniquement complet dans le périmètre local décidé.** Le
dossier courant (document historique ou livrable local non inclus)
réunit dix cas natifs Codex, dix cas ChatGPT et les six parcours transversaux requis.
Son contrôle donne `LOCAL_TECHNICAL_EVIDENCE_COMPLETE`, sans anomalie.
Les versions clientes sont indiquées par cas ; la qualification est cumulative.

Propriétaires : intégrations et architectes ; dépendances : P03–P06. Rattachement : L05, L16.

Les preuves antérieures (document historique ou livrable local non inclus),
le complément du 27 septembre (document historique ou livrable local non inclus)
et le dossier partiel du 28 septembre (document historique ou livrable local non inclus)
conservent leurs résultats historiques. Leurs anciens blocages ne décrivent plus
l'état courant. Claude est retiré des clients requis ; la revue indépendante et
la réception sur un second poste physique sont différées par décision utilisateur.
Les clients non testés ne sont pas qualifiés par analogie ; aucune synchronisation
ou fédération automatique n'est annoncée.

### P08 - Pilote technique local terminé ; validation indépendante différée

Propriétaires : responsable produit, équipe d'architecture cliente, exploitation ; dépendances : P01–P07.
Rattachement : L00, L16, L17.

**Statut : techniquement complet.** Le contrôle courant (document historique ou livrable local non inclus)
recalcule les preuves du pilote et la dépendance P07 : aucune anomalie restante.
Les [critères de clôture](lot-pilote-local.md#critères-de-clôture-p08) couvrent les trois
parcours Asteria, l'installation neuve hors ligne, la réinstallation, la mise à niveau,
la restauration, le retour arrière et les procédures de support/déploiement local.

Les trois dossiers conservent leurs diagnostics de conception et leurs neuf cas
métier non exécutés. Ces plans sont destinés aux équipes de réalisation ; exécuter
les applications métier futures n'est pas un prérequis de cette clôture.

La validation par une équipe indépendante, les mesures de prise en main humaine,
le second poste physique, la licence et les responsables nominatifs non attribués
restent explicitement différés ou à décider pour la réception organisationnelle.
Aucun procès-verbal, engagement de support, avis sécurité ou acceptation de risque
n'est inventé. La clôture technique P08 ne prononce pas G1 ; la demande suivante
le reçoit séparément, avec le choix explicite d'Apache-2.0.

### P09 - Options d'entreprise et décision G2

Propriétaires : plateforme, identité et exploitation ; dépendances : P05, P06 ; G2 dépend aussi de G1.
Rattachement : L04, L14, L17.

Phase de réception différée : le serveur centralisé sera envisagé après adoption multi-entreprise.
Les options déjà implémentées restent disponibles ; leur réception ne conditionne pas le G1 local.

Qualifier PostgreSQL avec concurrence, migrations, permissions, sauvegarde/restauration et observabilité ;
qualifier OIDC avec un IdP réel, discovery/JWKS, audiences, rotation, groupes et comptes désactivés. Réaliser
le flux OAuth requis par chaque client distant, au lieu d'assimiler validation d'un JWT et connexion
interactive complète. Tester les quatre combinaisons SQLite/local, SQLite/OIDC, PostgreSQL/local,
PostgreSQL/OIDC. Publier les topologies supportées, PKI, proxy, exploitation hors ligne et exigences HA.

Réception : preuves sur la combinaison choisie ; failover si HA revendiquée ; identité individuelle vérifiée
de bout en bout. Les assets de présentation sont épinglés et disponibles sans CDN si le mode hors ligne
est annoncé. Un déploiement local G1 ne dépend pas de la réception de ces options.

## Lots de complétude du white paper

### P10 - Spécification normative et noyau complet

**En cours, 0.35.0.dev1 :** reconstruction bitemporelle, extension d'unités et inventaire
normatif généré. Voir les [incréments et limites](lot-normatif-increments.md).

Propriétaires : produit, langage et noyau ; dépendances : P01–P03 ; rattachement : L00–L03, L06.
Résoudre les ambiguïtés du white paper dans des ADR ; compléter records, types, relations, unités, temporalité,
transitions, connaissance sourcée, inférences, conflits et imports reproductibles. Générer la traçabilité à
partir du registre de spécification et des tests ; conserver les règles non exécutées comme telles.
Réception : chaque exigence normative a sa source, son code et ses cas positifs/négatifs ; profils versionnés
testés, compatibilité et migrations démontrées. Aucun pourcentage dérivé du seul nombre de noms communs.

### P11 - Conception, construction, expériences et planification complètes

**En cours, 0.35.0.dev1 :** synchronisation ALL/ANY avec replay de preuve et conversion
monétaire sourcée. Les critères complets ci-dessous restent ouverts.

Propriétaires : architecture, compilateurs et calcul ; dépendances : P03, P10 ; rattachement : L07–L10.
Compléter contrats sémantiques, contrôles, workflows et états, mappings, compilateurs et pertes explicites,
expériences, simulation et planification capacitaire. Traiter synchronisation, propagation d'état,
représentativité et fraîcheur de calibration. Compléter provenance des estimations, contraintes de ressources,
monnaies et conversion versionnée si nécessaire. Relier hypothèses, coûts et risques aux décisions.
Réception : oracles indépendants, cas limites, comparaisons attendues et profils sémantiques réellement
exécutés ; le résultat d'un modèle n'est jamais présenté comme une mesure du système livré.

### P12 - Publication, fédération et engagement distribué

**En cours, 0.35.0.dev1 :** [outbox et checkpoints signés](publications-signees.md),
avec échange explicite entre deux registres. Aucune admission distribuée reçue.

Propriétaires : noyau distribué et sécurité ; dépendances : P04, P09–P11 ; rattachement : L11–L14.
Compléter packages, compatibilité, découverte, réconciliation, négociation, admission distribuée et activation.
Tester autorité, signatures, mandats, réservations, concurrence, idempotence, partitions, reprise, retrait,
renouvellement et clôture entre instances indépendantes. Ne pas assimiler le binding expérimental local à
un protocole distribué reçu.
Réception : scénarios multi-instances et effets contrôlés sans double engagement, preuves d'autorité et
historique cohérent après interruption, révocation ou changement de politique.

### P13 - Runtime, connecteurs et Workbench complets

**En cours, 0.35.0.dev1 :** connecteur d'observations JSON lié à un artefact exact.
La mesure reste déclarée ; le SDK complet et les autres adaptateurs restent ouverts.

Propriétaires : runtime, intégrations et expérience utilisateur ; dépendances : P09–P12 ; rattachement : L15, L16.
Relier instances, observations, drift, incidents et remédiations à des connecteurs qualifiés ; respecter les
mandats avant tout effet externe. Compléter Workbench, vues, accessibilité, contributions et collaboration.
Réception : effets réels uniquement dans des bancs de test autorisés, incidents et dérives détectés,
reprise/retrait testés, connecteurs documentés avec leurs versions, aucune exécution externe implicite.

### P14 - Réception normative et décision G3

**Préparation en cours :** inventaire généré des exigences et régressions locales.
G3 n'est pas reçu. La présence de code ou de tests ne ferme pas une exigence normative.

Propriétaires : assurance indépendante et responsable produit ; dépendances : G1, P10–P13 ; rattachement : L00–L17.
Fermer chaque obligation du plan initial avec sa preuve, traiter chaque diagnostic restant et publier les
profils conformes exacts. Refaire distribution, sécurité, charge, trois dossiers, restauration et matrice
client sur la release candidate. Produire manuel d'architecture, exploitation, support et évolution du langage.
Réception G3 : aucune obligation normative applicable ouverte ; contre-exemples refusés ; conformité
reproductible depuis la distribution. Tout écart accepté reste une limite publiée et interdit de revendiquer
la conformité du profil concerné.

## Discipline de livraison

Pour chaque lot : contrat et risques → code et tests adverses → tests pertinents SQLite/PostgreSQL →
démonstration Asteria si concernée → documentation et preuves → réception. La qualification exhaustive de
distribution reste distincte des tests ciblés d'un correctif. Ne pas publier une version sur la seule base de
tests unitaires. Les essais locaux utilisent des bases jetables ; aucune base métier n'est réinitialisée.

Les lots P01/P02 sont reçus dans leur périmètre correctif ; leurs
preuves historiques (document historique ou livrable local non inclus) sont conservées.
Le premier binding P03a (document historique ou livrable local non inclus) est prolongé par la
réception P03/P04 (document historique ou livrable local non inclus) : 686 tests SQLite,
111 tests ciblés PostgreSQL et trois dossiers Asteria avec tests fictifs signés.
La recette actuelle de restauration invalide les qualifications sous la nouvelle politique ; elle corrige
l'ancienne assertion qui réutilisait artificiellement la politique d'avant restauration.
**P05 et P06 sont reçus dans leur périmètre technique**, P06 sur le profil local Windows/SQLite
qualifié en rc8. P07/P08 sont techniquement complets sur rc9 ;
le [dossier G1](g1-reception-locale.md) reçoit ce périmètre local sous Apache-2.0.
P09 reste différé pour les options G2. Voir [les étapes restantes pour le groupe](preparation-production-groupe.md#ordre-des-étapes-restantes)
et les preuves courantes (document historique ou livrable local non inclus).
La nouvelle branche 0.35.0.dev1 exige sa propre qualification native et de distribution.
La production générale et les portes G2/G3 restent ouvertes.
