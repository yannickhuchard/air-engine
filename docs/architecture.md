# Architecture cible AIR

Statut : architecture cible ; SQLite/local est accepté (ADR-19). Référence principale : white paper §§3, 5, 8, 12–18 et annexes A–F. La première tranche livrée est détaillée dans [l’état de réalisation](etat-implementation.md) ; le reste reste cible.

## 1. Frontières du produit

AIR Core est une bibliothèque déterministe utilisable sans réseau ni modèle IA. Les services applicatifs l’exposent aux adaptateurs CLI, HTTP, MCP et Workbench. Ces adaptateurs ne réimplémentent pas les règles. Un module d’extension possède schéma, version, relations, cycle de vie, règles, mappings, effets autorisés et fixtures.

Le monolithe modulaire initial contient noyau, connaissance, contrats, validation, compilation, packages, fédération, collaboration et observation. Les calculs sont exécutés dans des workers isolés. Admission et activation partagent les services d’autorité et le même registre des engagements. L’isolation du registre peut être logique au démarrage et physique selon le domaine de cohérence ; il ne dépend jamais de l’index de recherche.

Le fournisseur IA est branché via une interface de génération optionnelle. Le moteur fonctionne avec les productions déposées depuis l’IDE ; il n’exige pas une deuxième souscription IA ni un modèle spécifique. La génération côté serveur, si activée, applique les mêmes classifications et conserve GenerationRun.

## 2. Autorités de données

| Donnée | Autorité | Projection / conséquence |
| --- | --- | --- |
| Modèles édités, règles, recettes et templates | Dépôt versionné, propriétaires identifiés | Graphe normalisé et vues dérivées |
| Version distribuée d’un package | Registre de publication et manifeste immuable | Un commit Git seul n’est pas une release publiée |
| Décisions d’aménagement | Objets versionnés approuvés par autorité de composition | Pas une simple union des projets |
| Approbations effectives | Service d’autorité, digest et identité vérifiés | Un fichier est une référence, jamais la preuve auto-déclarée |
| Offre de ressources | Sources métier autorisées, snapshots datés | Une donnée en cache n’est pas une réservation |
| Réservations, admissions, autorisations de lancement | Registre transactionnel compétent | Sauvegarde distincte de Git et reconstruction d’index |
| Artefacts volumineux et preuves | Fichiers locaux ; stockage d’objets ou source externe gouvernée optionnels | Références, digests, ACL et conservation |
| Secrets | Répertoire local protégé ; coffre d’entreprise optionnel | Référence opaque et résolution au moment autorisé |
| Recherche et graphe consultable | Projection reconstruisible | Fraîcheur, couverture et restrictions affichées |

Règle de cohérence : un objet possède un couple identité/révision canonique. Une correction produit une nouvelle révision. Les services ne permettent pas d’éditer arbitrairement les colonnes d’état pour contourner une transition. Les réservations possèdent un état opérationnel courant et un historique de transitions ; les snapshots publiés de cet historique sont immuables.

## 3. Représentation et registres

SQLite est obligatoire comme backend initial de tous les modules ; PostgreSQL est un backend optionnel partageant contrats et tests. Les premières migrations utilisent SQLAlchemy et des payloads canoniques texte, sans dépendance à JSONB. SQLite utilise WAL sur disque local, foreign keys et BEGIN IMMEDIATE pour les écritures ; PostgreSQL dispose de transactions et stratégies de verrouillage adaptées. La sémantique reste commune ; la concurrence et la disponibilité possibles diffèrent. Aucun partage NFS/SMB de SQLite. Voir [ADR-19](adr/0019-sqlite-et-identite-locale.md).

L’enveloppe meta/body de D.2 est conservée. JSON est le format d’échange ; YAML est une syntaxe d’édition contrôlée. Valider explicitement formats URI et date-time, propriétés inconnues, types, limites numériques, unités et cardinalités. Les structures embarquées doivent avoir un schéma strict avant usage de production. JSON Schema 2020-12 est le dialecte choisi par le paper, pas une prétention de couvrir la sémantique du graphe. [Spécification JSON Schema](https://json-schema.org/draft/2020-12).

Avant empreinte : normaliser les ensembles selon leur clé déclarée, conserver l’ordre des séquences et sérialiser selon le profil canonique. Les décimales exactes sont des chaînes typées. Le digest du manifeste se trouve dans une enveloppe externe pour éviter l’auto-référence. JCS définit la canonicalisation JSON ; la normalisation métier reste à spécifier par AIR. [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785).

Le registre logique proposé reprend D.4/§18.4 : object_revision, relationship_revision, baseline_member, package_release, context_source, validation_report, experiment_run, change_set, approval, capacity_reservation, admission_receipt et outbox_event. Le produit ajoute conceptuellement idempotency_record, job, inbox_checkpoint, execution_episode, activation_decision et audit_event. Ces noms décrivent des responsabilités, pas des migrations livrées.

Privilégier colonnes typées pour identité, version, entreprise, autorité, états, temps et invariants ; payload canonique JSON pour corps extensibles ; index des relations dans les deux sens ; artefacts lourds hors base. Les clés de rattachement incluent la frontière d’entreprise applicable. Les requêtes et politiques ne doivent pas permettre une référence croisée non autorisée. Séparer rôle de migration et rôle d’exécution ; protéger l’isolation en base lorsque plusieurs périmètres partagent une instance, en complément des politiques métier.

Les requêtes bitemporelles distinguent « valide dans le monde à T » et « connu dans le registre à K ». Les corrections ne réécrivent pas le contenu historique. Les migrations de structure conservent une lecture des profils antérieurs ou une conversion explicite vers une nouvelle baseline, avec rapport de pertes.

## 4. Chaîne de compilation et de décision

Entrée → parsing sûr → validation de schéma → résolution → normalisation → validation de graphe → règles applicables → linking → génération → vérification de préservation → artefacts et mappings.

Chaque étape référence baseline, profils, versions de règles, outils et sources. Le mode diagnostic peut rendre un rapport incomplet ; le mode constructible refuse les pertes obligatoires. L’AST AIR-Expr est pur, borné et sans accès réseau, fichier ou LLM. Une extension de calcul est isolée et qualifiée séparément.

Le rapport sépare trois axes : exécution du contrôle, résultat de la propriété et décision de la porte. Une panne de contrôle n’est pas une violation empirique ni une satisfaction ; elle empêche de conclure et produit un diagnostic. Les dérogations conservent le résultat original et l’autorité qui autorise exceptionnellement un passage. Une obligation non dérogeable reste bloquante.

Une approbation couvre une baseline ou demande exacte. Modifier le plan après approbation impose une nouvelle évaluation et, lorsque nécessaire, une nouvelle approbation. Le Workbench, la CLI et MCP n’ont pas de chemin alternatif.

## 5. Planification, simulation et coûts

Le planner reçoit tâches, dépendances, profils, identités sous-jacentes, calendriers, offre nette, engagements et objectifs. Les quantités restent séparées par unité ; les calendriers distinguent temps de travail et durée écoulée. La couverture est un problème d’affectation, pas la somme de scores de compétences.

OR-Tools est un candidat pour le solveur : sa documentation de job shop formalise précédences et ressources exclusives. Les profils, calendriers, capacités cumulées, supervision et mandats AIR doivent être ajoutés et testés ; la bibliothèque ne les fournit pas implicitement. [OR-Tools Job Shop](https://developers.google.com/optimization/scheduling/job_shop).

Le solveur expose statut et limites. Figer l’algorithme et le départage pour un recalcul strict ; conserver le plan sélectionné pour un replay historique. Une simulation publie ses simplifications, données, répétitions et enveloppe de validité. Les coûts distinguent build, run, migration, retrait, intégration, supervision et transitions ; aucune obligation forte n’est compensée par un meilleur score économique.

## 6. Admission transactionnelle

Une admission authentifie le principal, vérifie son mandat et prend un verrou sur la clé d’idempotence et les scopes d’invariants concernés. Dans une transaction courte : relire les versions d’autorité, contrôler approbations et conditions, recalculer les engagements sur les périodes, créer réservations/reçu/résultat idempotent/outbox puis commit.

Les simulations et appels externes longs sont hors transaction ; leurs entrées sont revalidées au commit. Verrouiller une ligne de réservation inexistante ou uniquement chaque objet ne protège pas une somme sur plusieurs allocations. Choisir des verrous de scopes toujours pris dans le même ordre et/ou l’isolation sérialisable avec reprise complète bornée. PostgreSQL sérialisable impose de gérer les échecs de sérialisation ; ce choix seul ne dispense pas de tester l’invariant applicatif. [Isolation PostgreSQL](https://www.postgresql.org/docs/current/transaction-iso.html).

Pour plusieurs autorités : coordinateur durable, préparation expirante, confirmations, manifeste et compensation. Aucun appel distant ne maintient une transaction SQL ouverte. Un quota préalablement délégué doit rester non chevauchant. Le service ne rend ADMITTED qu’après toutes les confirmations ; il expose les engagements partiels et leur traitement.

Une répétition retrouve l’état durable après une réponse perdue. Même clé et contenu différent est une collision. Le périmètre d’unicité lie autorité, demandeur, opération et clé selon l’ADR. Les décisions historiques demeurent consultables même si la validité courante change.

## 7. Revalidation et lancement

ExecutionEpisode possède un plan et des unités exacts. RevalidationPolicy relie déclencheurs, fraîcheur, délai de mobilisation, marge et contrôles. N(u) − L(u) − M(u) est évalué selon calendrier ; les expirations plus proches avancent la revue. Une échéance dépassée crée une instruction immédiate avec impact, sans réservation fictive.

Calculer le besoin restant à partir des réceptions, protéger les travaux en cours, qualifier les offres et comparer P0/P0-décalé/P1. Les réservations toujours valides sont comptées une fois ; celles expirées ne sont pas recréées.

prepare crée un workflow de préparation ; reassess calcule ; authorize décide sous mandat. L’exécuteur vérifie encore fenêtre, versions et conditions au lancement. Il doit consommer une autorisation liée à cet épisode via une transition protégée contre deux départs concurrents ; un simple document « autorisé hier » ne suffit pas. Une condition perdue bloque les nouveaux départs concernés, sans arrêter brutalement un processus déjà lancé.

## 8. Contrats de service et événements

Les 18 opérations figurent dans operations.json. Préserver les noms sémantiques de D.5/F.5 ; déclarer tout alias nécessaire à un client MCP. Les routes des trois opérations d’activation sont des propositions d’implémentation à arrêter en L00.

Bindings HTTP et MCP partagent identité, validation et erreurs. Les jobs longs rendent un identifiant et une progression vérifiable. L’annulation d’un job n’annule pas implicitement un engagement. Pagination liée à un checkpoint ; erreurs AIR stables ; 409 pour conflits, 422 pour invalidité, 403/404 selon divulgation, 429 pour quotas, 503 pour indisponibilité ; réponses d’authentification adaptées au transport.

Événements de D.6 et F.5 : identifiant unique, producteur, agrégat/révision, date d’occurrence et d’enregistrement, référence/digest de payload, version de schéma et trace. Livraison au moins une fois ; inbox et révisions empêchent régression ; snapshot et replay réparent les projections. Une notification déclenche une analyse, jamais une autorisation implicite.

## 9. Sécurité et exploitation

Le premier démarrage génère un jeton local protégé et révocable ; aucun IdP n’est nécessaire. OIDC peut être activé avec SQLite ou PostgreSQL sans repli automatique. Le serveur initial est local et mono-organisation ; les permissions fines ci-dessous sont une cible L04, non une propriété déjà démontrée du bootstrap.

Appliquer l’autorisation avant recherche, traversée, contexte IA, export et génération. Partager les caches seulement selon une clé d’autorisation et de politique compatible ; invalider lors d’une révocation. Filtrer les métadonnées et erreurs qui révéleraient un objet confidentiel.

Sources et sorties d’outils restent non fiables ; téléchargements bornés, archives protégées contre traversée de chemins, accès réseau filtré et plugin non exécuté lors d’un simple import. Secrets et données interdites ne sont pas envoyés aux modèles. Une URL d’artefact n’est pas une autorisation permanente.

Les workers disposent d’un environnement éphémère, quotas, réseau refusé par défaut et aucune identité de production. Les outils MCP distants appliquent les exigences d’autorisation, dont audience des jetons et absence de transfert aveugle vers un autre service. [MCP Authorization](https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization), [MCP Security](https://modelcontextprotocol.io/docs/2025-11-25/tutorials/security/security_best_practices).

Plan de panne : index indisponible → recherche limitée signalée ; source critique absente → UNKNOWN ; registre indisponible → pas de nouveaux engagements ; fournisseur IA indisponible → validation déterministe utilisable ; worker arrêté → job récupéré selon sa recette. La restauration des engagements nécessite leur sauvegarde d’autorité, jamais seulement Git.

## 10. Organisation du code proposée

- packages/air-core : types, parsing, références, temporalité, expressions.
- packages/air-validation et air-compiler : règles, portes, linking, générateurs.
- services/air-server : services de domaine, API, MCP, jobs, identité.
- services/air-ledger : module d’engagement, isolable en déploiement selon autorité.
- workers/ : expériences, calculs et compilation isolée.
- apps/workbench/ et apps/cli/ : interfaces.
- spec/ : registres versionnés, schémas, états, protocoles et profils.
- templates/ et integrations/ : projets, skills, adaptateurs et connecteurs.
- conformance/ et examples/ : fixtures et scénarios.
- deploy/ et operations/ : distribution, migration, reprise et exploitation.

Cette arborescence est une cible d’évolution. La première tranche utilise src/air (core, parsing, storage, auth, api, cli), scripts, tests, examples et .agents/skills pour éviter une fragmentation prématurée. Elle distingue le dépôt du produit AIR des dépôts solution-air générés pour les entreprises ; ces derniers suivent le template D.1.
