# Installer AIR

La première cible de production est le [poste de l'architecte](production-poste-architecte.md),
avec SQLite et identité locale. Le serveur centralisé et sa réception sont reportés.

Le périmètre local G1 reçu est celui de **0.34.0rc9**, avec P06, P07 et pilote
technique P08 terminés dans leur portée. La branche `0.35.0.dev1` ajoute des
fonctions qui restent à qualifier dans les clients natifs. Lire le
[périmètre local](perimetre-local-supporte.md) et le [contrat client courant](contrat-client-agent.md).
Pour les clients natifs et leurs limites, lire le [contrat P07](lot-clients-natifs.md).
Après installation, `python -m air --home <home> workstation-check` vérifie le profil du poste.
Lire le [contrat local et la reprise après perte du poste](lot-poste-local.md).
Pour borner le serveur entier et préparer la réception, lire le [profil d'exploitation rc7](lot-exploitation-cloture.md).
Lire les [fonctions disponibles et limites](etat-implementation.md) avant utilisation.
La réception technique P05 est conservée par commit dans la traçabilité ; chaque nouvelle candidate est requalifiée.

Lire le [contrat de distribution](lot-distribution-reproductible.md) pour installer un wheel vérifié,
utiliser un répertoire de dépendances hors ligne et qualifier une mise à niveau. Sous Windows, le home
privé doit être sur un volume avec ACL persistantes ; FAT/exFAT est refusé.

## Installation initiale

L'option de preuves externes signées P03 s'installe séparément avec `python -m pip install -c constraints.txt ".[proofs]"`.
Elle ne change ni SQLite/local par défaut ni les options indépendantes PostgreSQL/OIDC. Lire le
[parcours d'attestation](lot-preuves-externes.md) pour créer des clés protégées et enregistrer leur mandat.
Pour une équipe ou un client MCP, appliquer les [règles d'identité P04](lot-identites-mcp.md).

Prérequis : Python 3.11+ avec venv/pip, un répertoire local inscriptible et un accès
au registre de packages Python ou au miroir de l’entreprise. Python 3.12 sur Windows
est la plateforme testée localement. Windows/Linux et Python 3.11/3.12 sont reçus en CI
sur les commits et artefacts indiqués dans la [traçabilité](traceability/verification-production-p06-http-limits.json).
Aucun Node, Docker, serveur SQL,
compte cloud, fournisseur IA ou serveur d’identité n’est nécessaire.

Depuis la racine du dépôt :

```sh
python scripts/install.py --start
```

Le script crée .venv, installe les dépendances contraintes par constraints.txt,
protège .air, crée SQLite et le premier jeton administrateur, exécute doctor et
valide l’exemple. Le serveur démarre en arrière-plan, sans fenêtre supplémentaire,
sur http://127.0.0.1:8740. /health indique la disponibilité de l’API. Le
[site du dossier](site-architecture-statique.md) et le Workbench sont des
livrables à générer depuis un modèle ; ils ne remplacent pas cette API.
Un IDE peut suivre le [skill d’installation](../.agents/skills/air-install/SKILL.md).

Si Python n’est pas dans le PATH, l’IDE utilise le chemin absolu d’un interpréteur
3.11+ qu’il a détecté. Après installation, l’interpréteur de .venv suffit.

Sous Windows, le raccourci scripts/air.cmd évite d’activer l’environnement :

```bat
scripts\air.cmd doctor
scripts\air.cmd validate examples\scope.json
scripts\air.cmd put examples\scope.json
scripts\air.cmd get urn:air:example:scope:claims 1
```

Sous Linux/macOS, remplacer `scripts\air.cmd` par `.venv/bin/air`. L’exemple est
un brouillon synthétique ; put enregistre sa révision et ne publie pas un package.
Rejouer put avec un contenu équivalent retrouve le même digest ; un contenu différent
au même id/revision reçoit 409. Créer une nouvelle révision pour corriger un objet.

Réexécuter l’installateur conserve base, configuration et jeton. `--skip-install`
réutilise les dépendances existantes. `--port 8741` change le port ; les commandes
put/get prennent aussi `--port`. Le mode `--start` retrouve une instance déjà active :
il ne la met pas à jour à chaud. Après modification du code, arrêter puis redémarrer.

```sh
python scripts/install.py --stop
python scripts/install.py --start --skip-install
```

Pour un processus au premier plan : `.venv/Scripts/python.exe -m air serve` sur
Windows, `.venv/bin/air serve` sur Unix. L’installateur et la CLI ignorent les proxies
HTTP pour leurs appels à l’interface locale. Les variables pip habituelles permettent
d’utiliser un miroir ; les sorties pip ne sont pas imprimées par l’installateur pour
éviter de révéler une URL de miroir contenant des identifiants. Un paquet hors ligne
complet et signé reste à produire en L16.

## Données et authentification légère

| Fichier | Usage |
| --- | --- |
| .air/config.json | Version de configuration, identité d’instance et mode d’authentification |
| .air/air.db, air.db-wal, air.db-shm | Base SQLite et fichiers de fonctionnement WAL |
| .air/credentials.json | Premier jeton administrateur, réservé au compte OS installateur |
| .air/server.json | PID vérifié et port du serveur lancé par le script |
| .air/server-events.jsonl et .1 à .5 par défaut | Événements serveur privés à rotation bornée, sans messages libres ni access log HTTP |

Le répertoire .air est exclu de Git. Sur Windows, le bootstrap retire l’héritage
des ACL et donne l’accès au compte courant et à SYSTEM. Sur Unix, le répertoire est
en 0700 et les nouveaux fichiers de configuration/identifiants en 0600. Utiliser
un répertoire dédié ; ne pas désigner un répertoire personnel partagé comme AIR home.
Le propriétaire OS reste administrateur de confiance : il contrôle base et fichiers.

Les jetons possèdent 256 bits d’aléa, une expiration de 30 jours par défaut, un rôle
et un identifiant révocable. Seule leur empreinte SHA-256 est stockée dans la base.
La CLI lit le secret depuis le fichier protégé ; ne pas copier ce fichier dans une
conversation, un dépôt ou une ligne de commande. Toutes les routes de données et
OpenAPI exigent un jeton. /health est public et ne retourne aucun objet métier.

| Rôle | Droits actuels |
| --- | --- |
| reader | Lire tous les objets de l’installation, les schémas et capacités ; valider un brouillon, évaluer une expression ou une porte de diagnostic |
| editor | Droits reader + enregistrer des révisions de brouillons |
| admin | Droits editor + consulter les 100 derniers événements d’audit |

L’administration des jetons passe par la CLI sur la machine de confiance. Exemple :

```bat
scripts\air.cmd token-create --subject architecte-2 --role editor --name architecte-2.json
scripts\air.cmd put examples\scope.json --credential architecte-2.json
scripts\air.cmd token-revoke IDENTIFIANT_DU_JETON
```

La sortie affiche l’identifiant, jamais le jeton. L’expiration et la révocation sont
relues à chaque requête. Pour renouveler le premier jeton : créer un fichier neuf
avec token-create et le rôle admin, révoquer l’ancien identifiant, puis remplacer
credentials.json par le nouveau fichier dans le répertoire protégé. Le bootstrap
refuse de renouveler silencieusement un jeton expiré ou de changer de base derrière
des identifiants existants. Un changement de mode OIDC désactive tous les jetons locaux.

Sans politique explicite, la lecture est commune à l’organisation. Une politique de
namespaces peut désormais compartimenter les accès, y compris les dépendances dans
les exports, vues et contextes MCP. Les labels PUBLIC/INTERNAL ne constituent pas
des ACL. Voir [politiques et revues](lot-collaboration-projections.md). Les contrôles
par champ/aspect et délégations restent dans L04. Le serveur reste limité à 127.0.0.1 ; l’exposition réseau avec TLS,
quotas et identité d’équipe fera l’objet d’une tranche de déploiement dédiée.

## PostgreSQL optionnel, indépendant de l’identité

L’implémentation SQLAlchemy utilise les mêmes tables, empreintes et transactions
pour SQLite et PostgreSQL/psycopg. SQLite reste le backend par défaut de tous les
futurs modules. Son WAL exige un disque local et conserve un seul écrivain à la fois.
L’ajout de PostgreSQL vise concurrence, exploitation et haute disponibilité, sans
changer la sémantique AIR. [SQLite WAL](https://www.sqlite.org/wal.html).

Installer le pilote : `python scripts/install.py --extras postgres`.
Pour une **nouvelle base vide et un AIR home distinct**, fournir AIR_DATABASE_URL
par le gestionnaire de secrets ou l’environnement du processus :

```text
postgresql+psycopg://<user>:<password>@<host>:5432/<database>
```

Puis exécuter `python scripts/install.py --home .air-pg --extras postgres`.
Ne pas écrire une vraie URL avec mot de passe dans l’historique du shell ni dans
config.json versionné. Exclure également le home personnalisé de Git ; le .gitignore
fourni couvre .air et .air-*. L’installateur applique le schéma initial versionné,
et le serveur refuse une version de schéma inconnue. Le compte bootstrap nécessite
les droits DDL sur ce schéma. La séparation automatisée des comptes migration/runtime
reste dans L16. L’API ne crée pas de tables au démarrage.

**Changer la connexion ne transfère pas les données.** Utiliser les commandes registry-export et registry-import décrites dans [le transfert vérifié](transfert-registre.md). Elles conservent les révisions et audits, vérifient les digests et refusent une cible non vide. PostgreSQL 18.6 est qualifié sur des clusters locaux jetables distincts du service existant. Les nombres de tests et versions reçues sont conservés dans [l’état d’implémentation](etat-implementation.md) et ses rapports, sans modifier le démarrage SQLite par défaut.

## OIDC optionnel, avec SQLite ou PostgreSQL

Installer l’extra : `python scripts/install.py --extras oidc`.
Arrêter le serveur, conserver les autres champs de .air/config.json, puis remplacer auth :

```json
{
  "mode": "oidc",
  "oidc": {
    "issuer": "https://id.example.org/realms/company",
    "audience": "air-api",
    "jwks_url": "https://id.example.org/realms/company/protocol/openid-connect/certs",
    "subjects": {
      "subject-stable-fourni-par-idp": "editor"
    }
  }
}
```

Relancer doctor puis le serveur. Les URL sont choisies par l’administrateur ; aucune
URL provenant d’un jeton n’est utilisée pour découvrir ses clés. Le vérificateur
accepte RS256/ES256, contrôle signature, issuer exact, audience, exp, iat et sub,
et attribue le rôle depuis le mapping local. Un subject inconnu est refusé. Les
attributs de rôle auto-déclarés dans le jeton n’accordent pas de droits.

Cette tranche implémente le côté **resource server** pour des access tokens JWT
obtenus par un client autorisé de l’IdP. Elle n’implémente pas encore de connexion
interactive navigateur, PKCE, SCIM, introspection ou logout global. Configurer des
jetons d’accès de courte durée et une audience propre à l’API AIR ; doctor ne teste
pas un IdP en direct. Les clés publiques sont mises en cache jusqu’à cinq minutes ;
la révocation OIDC dépend ici des durées de jeton/clé et du mapping chargé au démarrage.
Les tests locaux vérifient réellement les signatures et les rejets de claims ; la
qualification avec l’IdP de l’entreprise reste nécessaire. [PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html).

## Vérifier et sauvegarder

```bat
scripts\air.cmd doctor
.venv\Scripts\python.exe -m pytest -q
```

Les profils expérimentaux restent incomplets. /v1/capabilities et chaque rapport
précisent la couverture. validate vérifie les brouillons ; validate --closed contrôle
également les références typées et AIR-V003 dans le périmètre de six types. Les 83
autres règles restent non exécutées dans ce parcours. Une baseline fermée ne prouve
ni qualification humaine des preuves, ni conformité AIR complète, ni autorisation
de publier/admettre/activer. Voir [la tranche connaissance/baselines](lot-connaissance-baselines.md).

Pour SQLite, la CLI utilise une sauvegarde cohérente incluant le WAL :

~~~sh
python -m air backup .air-backup-01
python -m air --home .air-restored restore .air-backup-01
python -m air --home .air-restored doctor
~~~

Les destinations doivent être nouvelles. La sauvegarde contient la base, la configuration,
la politique éventuelle et un manifeste de digests ; aucun jeton en clair. Elle reste privée.
La restauration vérifie empreintes et intégrité SQLite, migre le schéma, crée une nouvelle
identité d’instance, révoque tous les anciens jetons et crée un nouveau jeton local. Une
politique restaurée change de version : les revues historiques nécessitent revalidation.
AIR_DATABASE_URL doit être absent pour restaurer dans la SQLite isolée. Ni une base
existante ni ses fichiers ne sont écrasés. Pour PostgreSQL, utiliser l’export logique vérifié ou les procédures natives de l’entreprise. La reprise d’engagements reste à réceptionner lorsque le service d’admission sera disponible.

Pour passer du schéma 1 au schéma 2 : sauvegarder, arrêter AIR, relancer l’installateur
sans --skip-install puis démarrer. La migration ajoute les reçus de service et conserve
les révisions, digests et jetons. Vérifier doctor après redémarrage. Ne pas lancer une
ancienne version contre le schéma 2.


## Vérifier les expressions et les portes

Exécuter `.venv/Scripts/python.exe scripts/demo_validation.py` sous Windows, ou
`.venv/bin/python scripts/demo_validation.py` sous Unix. Les trois dossiers sont
vérifiés dans une SQLite isolée, sans changer .air. Voir [le contrat de tranche](lot-expressions-portes.md)
pour expr-evaluate, gate-validate, les codes de sortie et les limites des rapports.
Un résultat PASSED ne constitue aucune autorisation métier.


Pour vérifier la construction : exécuter `python scripts/demo_construction.py`
avec Python du venv. La recette isolée vérifie les trois chaînes et leur restauration.
Voir [le contrat de construction](lot-construction.md) pour construction-validate.
Les cas de réception demeurent des spécifications non exécutées.

## Jobs et migration vers le schéma 3

Le serveur 0.9 démarre son worker de calcul automatiquement. Aucun service supplémentaire n’est nécessaire. --no-worker au lancement et worker-once permettent une exécution séparée. Voir lot-jobs-durables.md.

Avant migration d’une installation en schéma 1 ou 2 : sauvegarder, arrêter son serveur, relancer l’installation sans --skip-install et redémarrer. Le schéma 3 ajoute job_state et son index ; les anciens objets, reçus et identifiants sont conservés. Les exports de registre 2 et 3 sont importables ; les sauvegardes SQLite 1/2/3 sont restaurables. La restauration crée une autre instance et ne renouvelle pas l’autorisation des anciens jobs.

Pour qualifier en conservant les fichiers temporaires sur le disque du projet : .venv/Scripts/python.exe scripts/check.py -q (ou .venv/bin/python sur Unix). La version 0.9 a passé 207 tests sur SQLite et PostgreSQL 18.6 sous Windows, une reprise après arrêt brutal de worker, M1 sur trois dossiers et une migration réelle 2→3 de l’instance locale.

## Schéma 4 : autorité et engagements locaux

La tranche 0.10 ajoute le registre de politique, les offres de capacité et les projections de réservation/activation. Arrêter le service avant sa migration, conserver une sauvegarde, réinstaller puis vérifier doctor. Les anciennes révisions et identités restent conservées. Une installation neuve engage la politique initiale ; les droits métier restent absents par défaut.

Pour activer ces usages, décrire les sujets et mandats dans un fichier de politique, puis appliquer `python -m air policy-set chemin/politique.json`. Cette opération locale engage une nouvelle génération de politique dans SQL. Modifier seulement access-policy.json provoque un refus des décisions métier jusqu’à synchronisation. Lire lot-admission-locale.md pour le parcours complet.

## Schéma 5 : renouvellement et clôture

La version 0.11 ajoute une tête d’autorisation par admission et conserve les chaînes de renouvellement. Les clôtures restent des reçus immuables. Arrêter, sauvegarder puis réinstaller avant de redémarrer. Les anciennes admissions sans renouvellement utilisent leur reçu initial. Les anciennes sauvegardes des schémas 1 à 4 restent restaurables dans un nouveau home.

Pour préparer une archive locale des sources : `python scripts/build_release.py`. Le dossier dist/version contient l’archive et son empreinte. L’archive inclut documentation, skill, exemples et tests ; elle exclut les bases, identifiants, environnements Python et temporaires de développement. La qualification depuis l’archive utilise `python scripts/qualify_release.py chemin/archive.zip --output tmp/release-qualification.json`. Elle crée une installation neuve et arrête son serveur. La distribution reste une préversion privée ; aucun choix de licence publique n’est présumé.

## Serveur d’équipe HTTPS facultatif

Le démarrage local reste inchangé. Pour configurer un certificat, une origine et des clients distants, suivre [le contrat HTTPS](lot-transport-https.md). La commande server-configure préserve la configuration de stockage et d’identité. PostgreSQL et OIDC restent indépendants. La restauration revient au transport local ; les clés TLS sont reconfigurées sur l’hôte cible.

## Migration du stockage d’artefacts - schéma 6

Arrêter le serveur avec scripts/install.py --stop, sauvegarder vers un nouveau répertoire, puis réinstaller et redémarrer avec scripts/install.py --start. Doctor doit annoncer le schéma 6. Les données et jetons sont conservés lors de la migration ; une restauration dans une nouvelle installation révoque les anciens jetons. Les blobs sont inclus dans la sauvegarde SQLite et le transfert logique PostgreSQL. Voir [pièces jointes](lot-artefacts-preuves.md).

## Vues conservées et organisations

Les bindings air.view/0.20 et air.organization/0.21 utilisent le schéma 6 existant. Pour mettre à jour : arrêter le serveur vérifié, sauvegarder, réinstaller et vérifier doctor. Les captures historiques conservent leur générateur et leurs gardes de contexte ; les équipes et autorités DRAFT ne modifient aucune permission effective. Voir [vues conservées](lot-vues-conservees.md) et [organisations](lot-organisations-autorites.md).

Sauvegardes SQLite chiffrées optionnelles : [procédure, clés et limites](sauvegardes-chiffrees.md), extra `backup`.

Limites HTTP : [concurrence par identité et délai de réception](lot-limites-http.md). Les valeurs se configurent avant démarrage ; elles ne modifient pas les droits.

Quotas durables, budgets OS des jobs, sonde `monitor`, export d'audit et comparaison de charge :
[contrat et réception P06](lot-exploitation-reception.md). Les valeurs par défaut préservent le démarrage
Python seul ; les plafonds CPU/mémoire des jobs ne constituent pas un budget du service entier.
Configurer les mêmes `AIR_QUOTA_*` dans les processus partageant le registre. L'export d'audit conserve
la source ; aucune suppression SQL n'est autorisée par cette commande. Pour le poste autonome,
la [réception technique P06](lot-poste-local.md) distingue les contrôles livrés du pilote indépendant
P08. Les objectifs et la réception de la plateforme centrale sont différés vers P09/G2.
