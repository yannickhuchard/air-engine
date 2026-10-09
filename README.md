# AIR · Architecture Workspace

**Du besoin métier aux plans que vos équipes peuvent comprendre, vérifier et réaliser.**

AIR (*Architecture Intermediate Representation*) relie besoins, composants, données, décisions et preuves dans un modèle versionné. Votre assistant agentique aide à construire le dossier ; le moteur garde les sources et effectue les contrôles. Créé par **Yannick Huchard**, logiciel libre sous [Apache-2.0](LICENSE).

[Installer](docs/installation.md) · [Découvrir trois exemples](fixtures/enterprise/asteria/README.md) · [Connecter un assistant](docs/agents.md) · [Utiliser le plugin](https://github.com/yannickhuchard/air-plugin)

## Pourquoi utiliser AIR ?

| Vous voulez… | AIR vous aide à… |
| --- | --- |
| Concevoir une solution avec les équipes métier | Relier besoins, exigences et fonctions aux plans de réalisation |
| Expliquer les choix au management | Présenter les décisions, conséquences et informations manquantes |
| Transmettre aux ingénieurs et opérations | Livrer un dossier sourcé, des contrats et des critères de réception |
| Éviter les affirmations sans preuve | Distinguer faits, hypothèses, contradictions et validations non exécutées |
| Travailler avec un IDE agentique | Utiliser les mêmes services depuis la CLI et le MCP |

AIR conçoit, vérifie et simule des **plans pour la réalisation ultérieure**. Il n’exécute pas les activités métier des systèmes décrits.

## Installer en quelques minutes

Python 3.11+ avec pip/venv et un répertoire inscriptible. Cloner ce dépôt ou télécharger une [release](https://github.com/yannickhuchard/air-engine/releases), puis :

```text
python scripts/install.py --start
```

L’installateur crée `.venv`, initialise SQLite, protège l’identité locale et vérifie le service. Arrêter avec `python scripts/install.py --stop`.

**Pas de Docker, Node, cloud ou fournisseur d’identité obligatoire.** PostgreSQL et OIDC sont des options indépendantes. Garder les jetons dans leurs fichiers protégés ; ne pas les coller dans un chat. [Installation détaillée et reprise](docs/installation.md).

## Comprendre avant de créer votre projet

[Asteria Industrie](fixtures/enterprise/asteria/README.md) est une entreprise fictive avec trois dossiers partageant un socle :

| Dossier | Besoin | Ce qui reste visible |
| --- | --- | --- |
| SAV | Orchestrer une intervention depuis un portail | Confirmation ERP absente : UNKNOWN |
| Atelier | Contrôler la qualité avec des mesures | Mesure périmée : VIOLATED |
| Identités | Gérer arrivées, mobilités et départs | Sources contradictoires : CONFLICTING |

```text
.venv/Scripts/python.exe scripts/demo_metier.py --output tmp/demo-public
```

Unix : `.venv/bin/python`. Le parcours produit des vues HTML et un rapport isolés. Ces cas illustrent des contrôles de conception ; les neuf scénarios des futurs systèmes métier restent non exécutés. Les portes bloquées montrent les décisions à prendre.

## Votre travail avec l’assistant

Installer le [plugin AIR](https://github.com/yannickhuchard/air-plugin), puis configurer une connexion MCP autorisée à ce moteur. Codex et Claude Code peuvent utiliser une connexion locale ; ChatGPT exige une connexion distante adaptée au client. Le plugin seul ne connecte pas le poste.

> « Utilise AIR pour construire ce dossier. Pose les questions une par une, explique les écarts, puis vérifie les plans et prépare les livrables. »

Le dossier et ses versions restent le référentiel, même si vous changez d’assistant. [Connexion des agents](docs/agents.md).

## Quelle version est incluse ?

Cette distribution contient **0.34.0rc9**, reçue sur Windows/Python 3.12/SQLite dans son périmètre documenté. Les archives et [preuves de validation](docs/validation.md) portent leurs propres empreintes. Les autres OS, nouvelles connexions natives et conformité AIR totale ne sont pas déduits de ce reçu.

Les nouveautés 0.35 de développement, dont le site PWA récent, Customer Journey Maps interactives, News et actualisation vidéo, **ne sont pas incluses ici**. Une mise à jour de ce README n’est pas une nouvelle release moteur.

Certaines vues rc9 chargent Mermaid et des polices depuis des services externes ; ne pas les présenter comme entièrement hors ligne. Le moteur et ses calculs n’exigent pas ces services. Les contenus transmis à un modèle cloud suivent les règles de votre entreprise et de ce fournisseur.

## Contribuer et recevoir la distribution

```text
python scripts/install.py --extras dev,proofs,backup
.venv/Scripts/python.exe -m pytest -q
```

[Kit de recette sur un autre poste](docs/reception-second-poste.md) · [Provenance et licences](docs/publication.md) · [Issues](https://github.com/yannickhuchard/air-engine/issues).

Aucune CI push/PR n’est activée. La licence du logiciel ne publie pas les dossiers d’entreprise. Nous séparons les contrôles réalisés, les hypothèses et les validations qui restent à faire.
