# Contribuer à AIR

Merci de contribuer à un outil qui rend les dossiers d’architecture plus faciles
à comprendre, à vérifier et à transmettre aux équipes de réalisation.

Commencez par le [README](README.md), l’[état de réalisation](docs/etat-implementation.md)
et les [trois exemples Asteria](fixtures/enterprise/asteria/README.md). La branche
principale est en développement ; la release rc9 reste accessible sur son tag.

Pour un problème ou une proposition, ouvrez une issue avec le besoin utilisateur,
la version, les étapes de reproduction et un exemple fictif minimal. Ne joignez
pas de dossier client, secret ou journal privé. Les vulnérabilités suivent
[SECURITY.md](SECURITY.md).

Pour proposer du code :

1. Créez une branche depuis `main`.
2. Installez avec `python scripts/install.py --extras dev,proofs,backup`.
3. Effectuez la modification et les tests locaux pertinents avec
   `.venv/Scripts/python.exe scripts/check.py -q` (Unix : `.venv/bin/python`).
4. Expliquez dans la pull request le besoin, le résultat, les contrôles exécutés
   et les limites restantes. Les changements qui touchent les dossiers doivent
   aussi être vérifiés avec les trois exemples Asteria.

Préservez l’installation Python seule, SQLite/local par défaut et les révisions
immuables. CLI, API et MCP appellent les mêmes services. Un contrôle prévu n’est
pas une preuve exécutée et un modèle ne constitue pas une réalisation métier.
Suivez [AGENTS.md](AGENTS.md), y compris le nom Projet d’architecture et la règle
rédactionnelle sur la ponctuation. Aucune CI push/PR n’est activée pour ce cycle.

Le logiciel et sa documentation propre sont sous Apache-2.0. Conservez les
licences des composants tiers et vérifiez les droits des nouveaux fichiers.
La licence du logiciel n’autorise pas à publier les données de ses utilisateurs.
