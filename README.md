# AIR · Architecture Workspace

**Transformez une intention métier en un projet d’architecture que les équipes peuvent comprendre, vérifier et réaliser.**

AIR signifie *Architecture Intermediate Representation*. Créé par Yannick Huchard, AIR relie les besoins, parcours, composants, données, décisions et preuves dans un même modèle versionné. Votre assistant agentique vous aide à le construire ; le moteur AIR vérifie les déclarations et garde leurs sources.

[Installer AIR](docs/installation.md) · [Découvrir trois dossiers](fixtures/enterprise/asteria/README.md) · [Utiliser le plugin](plugins/air-local/README.md) · [Voir ce qui est livré](docs/etat-implementation.md)

## Ce que vous gagnez

| Votre besoin | Ce qu’AIR apporte |
| --- | --- |
| Expliquer la solution au management | Un Management Summary, les choix, leurs conséquences et les questions encore ouvertes |
| Concevoir avec les équipes métier | Des parcours par persona, touchpoints, usages et Customer Journey Maps interactives |
| Transmettre aux équipes de réalisation | Paquets versionnés, contrats, responsabilités R et A, questions et réception explicite du périmètre |
| Vérifier la cohérence | Contrôles déterministes, traçabilité et simulations sur le design déclaré |
| Piloter plusieurs dossiers | Programmes, projets, tâches et dépendances aux versions explicitement sélectionnées |
| Partager un dossier lisible | Un site « Projet d’architecture », responsive, personnalisable et conservable hors ligne |

Les plans servent à construire les futurs systèmes. AIR n’exécute pas à leur place les activités métier décrites.

## Votre premier parcours

**1. Installez le moteur sur votre poste.** Python 3.11+ suffit. SQLite et une identité locale sont configurés par défaut ; Docker, Node, cloud et fournisseur d’identité ne sont pas requis.

```text
python scripts/install.py --start
```

**2. Découvrez les exemples.** Les [trois dossiers Asteria](fixtures/enterprise/asteria/README.md) montrent SAV, maintenance et identités dans une même entreprise fictive.

**3. Connectez votre assistant.** Le [plugin AIR](plugins/air-local/README.md) apporte les skills d’installation et de conception. CLI et MCP utilisent les mêmes services. Codex et Claude Code peuvent utiliser une connexion locale ; ChatGPT exige une connexion distante autorisée à votre installation.

> « Utilise AIR pour m’aider à construire ce dossier. Montre les informations manquantes, pose les questions une par une et vérifie le modèle avant de produire les livrables. »

**4. Progressez jusqu’à un dossier complet.** L’assistant lit la version exacte, prépare les modifications, conserve les décisions et régénère les vues. La barre de progression ouvre chaque partie du dossier, ses manques et le travail déclaré. Checklist, kanban, News et questions ouvertes complètent cette lecture. Les vidéos courtes sont un atelier optionnel.

## Choisir la bonne version

| Distribution | Pour qui ? | État |
| --- | --- | --- |
| [Release rc9](https://github.com/yannickhuchard/air-engine/releases/tag/v0.34.0rc9) | Installer la distribution de référence | 0.34.0rc9 ; périmètre et validations propres à cette release |
| Branche principale de ce dépôt public | Explorer et contribuer aux capacités courantes | 0.35.0.dev3, version de développement ; PWA, parcours interactifs, News, finances, transformation et vidéos |
| [Plugin public air-plugin](https://github.com/yannickhuchard/air-plugin) | Guider l’installation et le travail avec un agent | Distribution de skills séparée du moteur ; disponibilité dans un annuaire à vérifier séparément |

[Distributions 0.35 de développement](https://github.com/yannickhuchard/air-engine/releases) : installation et qualifications propres à chaque version.

**Les sources récentes sont publiques. La branche principale est une version de développement, sans qualification globale de production.** Pour installer rc9, télécharger sa release ou sélectionner son tag ; ses archives restent inchangées. Une installation locale ne signifie pas synchronisation entre entreprises. PostgreSQL et OIDC sont des options indépendantes.

## Guides selon votre objectif

- **Architecte :** [travailler avec un agent](docs/guide-architecte-agent.md), [dossier et parcours](docs/parcours-personas-et-usages.md).
- **Constructeurs :** [paquets et réception des équipes](docs/lot-c-transmission-equipes.md), [recette de deux équipes](fixtures/builder_handoff/README.md), [profils et contrats vérifiables](docs/lot-b-profils-et-contrats.md), [deux prototypes indépendants](fixtures/build_design/README.md).
- **Équipe projet :** [lire le site](docs/site-architecture-statique.md), [processus et cartes d’expérience](docs/diagrammes-processus-et-experience.md).
- **Management :** [synthèse et transformation](docs/synthese-et-pilotage-transformation.md), [finances et traçabilité](docs/etat-implementation.md).
- **Communication :** [branding](docs/branding-dossiers.md), [récit et vidéos](docs/architecture-story.md), [actualiser les News et vidéos](docs/actualiser-news-videos.md).
- **Installation et exploitation :** [installation](docs/installation.md), [production sur poste architecte](docs/production-poste-architecte.md).

## Contribuer et utiliser librement

AIR est sous [Apache-2.0](LICENSE), avec [avis et licences tierces](NOTICE). Voir le [guide de contribution](CONTRIBUTING.md) pour proposer une amélioration. La licence du logiciel ne publie pas les données d’architecture de ses utilisateurs. Protégez les identifiants et choisissez les données autorisées avant leur transmission à un modèle cloud.

Pour développer : `python scripts/install.py --extras dev,proofs,backup`, puis `.venv/Scripts/python.exe -m pytest -q` (Unix : `.venv/bin/python`). Les tests locaux accompagnent les changements ; aucune CI push/PR n’est activée.

[État de réalisation](docs/etat-implementation.md) et [validation publique](docs/validation.md) séparent capacités livrées, critères ouverts et validations non exécutées. AIR ne revendique ni conformité normative totale ni compatibilité reçue avec tous les clients mentionnés.
