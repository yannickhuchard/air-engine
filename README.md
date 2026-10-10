# AIR Â· Architecture Workspace

**Transformez une intention mÃ©tier en un projet dâ€™architecture que les Ã©quipes peuvent comprendre, vÃ©rifier et rÃ©aliser.**

AIR signifie *Architecture Intermediate Representation*. CrÃ©Ã© par Yannick Huchard, AIR relie les besoins, parcours, composants, donnÃ©es, dÃ©cisions et preuves dans un mÃªme modÃ¨le versionnÃ©. Votre assistant agentique vous aide Ã  le construire ; le moteur AIR vÃ©rifie les dÃ©clarations et garde leurs sources.

[Installer AIR](docs/installation.md) Â· [DÃ©couvrir trois dossiers](fixtures/enterprise/asteria/README.md) Â· [Utiliser le plugin](plugins/air-local/README.md) Â· [Voir ce qui est livrÃ©](docs/etat-implementation.md)

## Ce que vous gagnez

| Votre besoin | Ce quâ€™AIR apporte |
| --- | --- |
| Expliquer la solution au management | Un Management Summary, les choix, leurs consÃ©quences et les questions encore ouvertes |
| Concevoir avec les Ã©quipes mÃ©tier | Des parcours par persona, touchpoints, usages et Customer Journey Maps interactives |
| Transmettre aux Ã©quipes de rÃ©alisation | Processus, contrats, modÃ¨les de donnÃ©es, responsabilitÃ©s, lots et critÃ¨res de rÃ©ception |
| VÃ©rifier la cohÃ©rence | ContrÃ´les dÃ©terministes, traÃ§abilitÃ© et simulations sur le design dÃ©clarÃ© |
| Piloter plusieurs dossiers | Programmes, projets, tÃ¢ches et dÃ©pendances aux versions explicitement sÃ©lectionnÃ©es |
| Partager un dossier lisible | Un site Â« Projet dâ€™architecture Â», responsive, personnalisable et conservable hors ligne |

Les plans servent Ã  construire les futurs systÃ¨mes. AIR nâ€™exÃ©cute pas Ã  leur place les activitÃ©s mÃ©tier dÃ©crites.

## Votre premier parcours

**1. Installez le moteur sur votre poste.** Python 3.11+ suffit. SQLite et une identitÃ© locale sont configurÃ©s par dÃ©faut ; Docker, Node, cloud et fournisseur dâ€™identitÃ© ne sont pas requis.

```text
python scripts/install.py --start
```

**2. DÃ©couvrez les exemples.** Les [trois dossiers Asteria](fixtures/enterprise/asteria/README.md) montrent SAV, maintenance et identitÃ©s dans une mÃªme entreprise fictive.

**3. Connectez votre assistant.** Le [plugin AIR](plugins/air-local/README.md) apporte les skills dâ€™installation et de conception. CLI et MCP utilisent les mÃªmes services. Codex et Claude Code peuvent utiliser une connexion locale ; ChatGPT exige une connexion distante autorisÃ©e Ã  votre installation.

> Â« Utilise AIR pour mâ€™aider Ã  construire ce dossier. Montre les informations manquantes, pose les questions une par une et vÃ©rifie le modÃ¨le avant de produire les livrables. Â»

**4. Progressez jusquâ€™Ã  un dossier complet.** Lâ€™assistant lit la version exacte, prÃ©pare les modifications, conserve les dÃ©cisions et rÃ©gÃ©nÃ¨re les vues. La barre de progression ouvre chaque partie du dossier, ses manques et le travail déclaré. Checklist, kanban, News et questions ouvertes complètent cette lecture. Les vidÃ©os courtes sont un atelier optionnel.

## Choisir la bonne version

| Distribution | Pour qui ? | Ã‰tat |
| --- | --- | --- |
| [Release rc9](https://github.com/yannickhuchard/air-engine/releases/tag/v0.34.0rc9) | Installer la distribution de rÃ©fÃ©rence | 0.34.0rc9 ; pÃ©rimÃ¨tre et validations propres Ã  cette release |
| Branche principale de ce dÃ©pÃ´t public | Explorer et contribuer aux capacitÃ©s courantes | 0.35.0.dev1, version de dÃ©veloppement ; PWA, parcours interactifs, News, finances, transformation et vidÃ©os |
| [Plugin public air-plugin](https://github.com/yannickhuchard/air-plugin) | Guider lâ€™installation et le travail avec un agent | Distribution de skills sÃ©parÃ©e du moteur ; disponibilitÃ© dans un annuaire Ã  vÃ©rifier sÃ©parÃ©ment |

**Les sources rÃ©centes sont publiques. La branche principale est une version de dÃ©veloppement, sans qualification globale de production.** Pour installer rc9, tÃ©lÃ©charger sa release ou sÃ©lectionner son tag ; ses archives restent inchangÃ©es. Une installation locale ne signifie pas synchronisation entre entreprises. PostgreSQL et OIDC sont des options indÃ©pendantes.

## Guides selon votre objectif

- **Architecte :** [travailler avec un agent](docs/guide-architecte-agent.md), [dossier et parcours](docs/parcours-personas-et-usages.md).
- **Ã‰quipe projet :** [lire le site](docs/site-architecture-statique.md), [processus et cartes dâ€™expÃ©rience](docs/diagrammes-processus-et-experience.md).
- **Management :** [synthÃ¨se et transformation](docs/synthese-et-pilotage-transformation.md), [finances et traÃ§abilitÃ©](docs/etat-implementation.md).
- **Communication :** [branding](docs/branding-dossiers.md), [rÃ©cit et vidÃ©os](docs/architecture-story.md), [actualiser les News et vidÃ©os](docs/actualiser-news-videos.md).
- **Installation et exploitation :** [installation](docs/installation.md), [production sur poste architecte](docs/production-poste-architecte.md).

## Contribuer et utiliser librement

AIR est sous [Apache-2.0](LICENSE), avec [avis et licences tierces](NOTICE). Voir le [guide de contribution](CONTRIBUTING.md) pour proposer une amÃ©lioration. La licence du logiciel ne publie pas les donnÃ©es dâ€™architecture de ses utilisateurs. ProtÃ©gez les identifiants et choisissez les donnÃ©es autorisÃ©es avant leur transmission Ã  un modÃ¨le cloud.

Pour dÃ©velopper : `python scripts/install.py --extras dev,proofs,backup`, puis `.venv/Scripts/python.exe -m pytest -q` (Unix : `.venv/bin/python`). Les tests locaux accompagnent les changements ; aucune CI push/PR nâ€™est activÃ©e.

[Ã‰tat de rÃ©alisation](docs/etat-implementation.md) et [validation publique](docs/validation.md) sÃ©parent capacitÃ©s livrÃ©es, critÃ¨res ouverts et validations non exÃ©cutÃ©es. AIR ne revendique ni conformitÃ© normative totale ni compatibilitÃ© reÃ§ue avec tous les clients mentionnÃ©s.
