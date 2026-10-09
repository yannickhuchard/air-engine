# ADR-19 - SQLite et identité locale par défaut

Statut : ACCEPTED. Date : 19 septembre 2026. Décision explicite de l’utilisateur.
Cette décision remplace la proposition PostgreSQL/OIDC obligatoire au premier démarrage.

## Décision

Distribuer AIR comme un monolithe modulaire initialement installable avec Python,
SQLite embarqué et un répertoire local protégé. Authentifier par jetons locaux
générés automatiquement, expirables, révocables et associés à des rôles. L’IDE
lit documentation et SKILL.md puis lance l’installation sans configuration d’IdP,
de conteneur, de cloud ou de serveur de base.

PostgreSQL et OIDC sont des options indépendantes. SQLite/local, SQLite/OIDC,
PostgreSQL/local et PostgreSQL/OIDC doivent être des configurations explicites.
Aucun backend de secours silencieux, aucune identité anonyme par défaut.

## Conséquences pour tous les lots

- Même couverture fonctionnelle cible et mêmes invariants sur les deux bases.
  Le backend définit une enveloppe d’exploitation, pas les droits métier.
- SQL portable ; pas d’obligation JSONB, pgvector, extension PostgreSQL ou Redis.
  Les accélérateurs éventuels ont une implémentation de référence SQLite.
- SQLite : disque local, WAL, foreign keys, transactions courtes, un écrivain à
  la fois, BEGIN IMMEDIATE pour les transactions qui vérifient puis modifient
  les invariants. Les futures admissions ne devront pas dépendre d’un verrou
  mémoire propre au processus.
- PostgreSQL : transactions, verrous de scopes et reprises de sérialisation
  adaptés aux invariants. Ne pas traduire mécaniquement un verrou SQLite en
  verrou de ligne qui ne protégerait pas un agrégat capacitaire.
- Pas de multi-instance partageant un fichier SQLite par NFS/SMB. Le passage
  à PostgreSQL relève de la concurrence/HA/exploitation demandée et mesurée.
- Migrations de schéma versionnées et transfert SQLite → PostgreSQL avec
  contrôle des digests, comptes, audit et invariants avant bascule. Aucun simple
  changement d’URL ne vaut transfert de données.
- Les secrets restent hors Git et hors contexte du modèle. Les rôles locaux
  seront complétés par les mandats et permissions d’objet/aspect de L04.
- L16 commence immédiatement : installation, diagnostic, mise à niveau,
  sauvegarde et skill sont développés avec chaque fonction.

## Réception cible

1. Un poste avec Python installe et vérifie AIR par une commande idempotente.
2. Le parcours complet est automatisable par un IDE ayant lu la documentation.
3. Réinstaller préserve les données et identités ; restaurer rend les mêmes digests.
4. Les mêmes tests métier passent sous SQLite et PostgreSQL.
5. OIDC n’est jamais exigé en mode local et un échec OIDC n’active pas le mode local.
6. Une bascule de base testée conserve identités, références, audit et engagements.

État réel de réception : voir [état de réalisation](../etat-implementation.md).
Les capacités de la première tranche ne suffisent pas à réceptionner tous ces critères.

Références techniques : [SQLite WAL](https://www.sqlite.org/wal.html),
[SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html),
[PyJWT](https://pyjwt.readthedocs.io/en/stable/usage.html).
