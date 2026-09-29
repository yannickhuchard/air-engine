# Asteria : trois dossiers d’architecture reproductibles

Les personnes, chiffres, sources et systèmes sont entièrement fictifs. Les trois
dossiers restent ensemble pour démontrer les dépendances d’une même entreprise.
Ils sont livrés avec le moteur pour être testés sur la même version.

| Dossier | Brief | Données | Résultat initial attendu |
| --- | --- | --- | --- |
| D01 SAV | [besoin](dossiers/sav/brief.md) | `dossiers/sav/` | UNKNOWN : confirmation ERP manquante |
| D02 Atelier | [besoin](dossiers/atelier/brief.md) | `dossiers/atelier/` | VIOLATED : mesure périmée |
| D03 Identités | [besoin](dossiers/identites/brief.md) | `dossiers/identites/` | CONFLICTING : contradiction de sources |

Lire [company.md](company.md) et les briefs avant les JSON. `shared.bootstrap.json`
porte le socle partagé. Chaque dossier contient bootstrap, fondation, construction,
requêtes de baseline et cas de validation. `manifest.json` décrit le jeu et ses
oracles/historique ; il n’est pas le reçu d’une nouvelle exécution.

Depuis la racine du dépôt après installation :

```text
.venv/Scripts/python.exe scripts/demo_metier.py --output tmp/demo-asteria
```

Sur Unix : `.venv/bin/python`. Le rapport calculé est `tmp/demo-asteria/report.json` ;
ouvrir aussi `D01.html`, `D02.html`, `D03.html` dans ce dossier. Les sous-répertoires
de travail contiennent état privé et identités synthétiques : ils restent ignorés par Git.
Relancer avec un autre dossier de sortie permet de comparer deux essais.

Pour les trois preuves externes synthétiques signées, installer l’extra `proofs` puis :

```text
.venv/Scripts/python.exe scripts/demo_metier.py --output tmp/demo-asteria-proofs --qualify-external-proofs
```

Ce parcours vérifie les refus d’accès, la traçabilité, la reprise MCP, les impacts
d’un changement partagé et la restauration. Les trois preuves Python synthétiques
ne sont pas les neuf tests des systèmes métier futurs. Ceux-ci restent NOT_EXECUTED.
PASS_SCOPED signifie que la recette de conception s’est déroulée comme prévu,
avec des portes métier bloquées conservées.

Pour explorer les plans, estimations et livrables plus avancés, les scripts
`scripts/demo_*.py` proposent des parcours spécialisés ; consulter leur aide et
préserver leur caractère isolé. Aucun exemple ne se connecte à un vrai ERP/IAM/atelier.
