# AIR — Architecture Workspace

**Architecture Intermediate Representation**, développé par **Yannick Huchard**.
Logiciel libre sous [Apache-2.0](LICENSE). Concevoir, vérifier, simuler et livrer
des dossiers d’architecture destinés aux ingénieurs, chefs de projet et opérations.

Cette distribution publique utilise le moteur **0.34.0rc9**. Le noyau est celui de
la candidate reçue sur poste Windows ; les archives publiques sont reconstruites et
leurs validations sont documentées dans [docs/validation.md](docs/validation.md).
Elle ne prétend pas à la conformité AIR complète ni à l’exécution des systèmes métier.
Les développements expérimentaux 0.35 ne sont pas inclus.

## Installer sur son poste

Python 3.11+ avec pip/venv, répertoire inscriptible et accès au registre pip ou à un
miroir. Windows/Python 3.12 est la plateforme de réception de cette distribution.
Le code est portable ; les autres plateformes nécessitent leur propre recette.
SQLite et identité locale sont les valeurs par défaut. Aucun Docker, Node,
hébergement cloud ou fournisseur d’identité n’est obligatoire.

Télécharger la source depuis [Releases](https://github.com/yannickhuchard/air-engine/releases)
ou cloner ce dépôt, puis :

```text
python scripts/install.py --start
```

Le script installe dans `.venv`, protège `.air`, initialise SQLite et l’identité,
puis vérifie le service. Arrêter : `python scripts/install.py --stop`.
Les jetons restent dans des fichiers protégés ; ne pas les coller dans un chat.
L’[installation détaillée](docs/installation.md) couvre les roues, le mode hors ligne,
les options indépendantes PostgreSQL/OIDC et la sauvegarde.
Un IDE peut suivre [.agents/skills/air-install/SKILL.md](.agents/skills/air-install/SKILL.md).

## Comprendre l’utilité avec trois dossiers

Pour recevoir la distribution sur un autre poste, utiliser le
[kit de recette publique](docs/reception-second-poste.md). Il vérifie les artefacts,
l’installation et les trois dossiers, avec une attestation humaine séparée.

[Asteria Industrie](fixtures/enterprise/asteria/README.md) est une entreprise fictive
avec trois dossiers partageant identité et intégration :

| Dossier | Besoin | Ce que le moteur doit rendre visible |
| --- | --- | --- |
| SAV | Portail et orchestration des interventions | Confirmation ERP manquante : UNKNOWN |
| Atelier | Collecte de mesures et contrôle qualité | Mesure périmée : VIOLATED |
| Identités | Arrivées, mobilités et départs | Sources contradictoires : CONFLICTING |

```text
.venv/Scripts/python.exe scripts/demo_metier.py --output tmp/demo-public
```

Sur Unix, utiliser `.venv/bin/python`. Le parcours produit trois vues HTML et un
rapport dans le dossier de sortie, avec données isolées, contrôles HTTP/MCP,
reprise de contexte et restauration. Il arrête son serveur de démonstration.
Les portes bloquées montrent les décisions à prendre ; elles ne sont pas un échec
du logiciel. Les neuf scénarios sur les futurs systèmes métier restent non exécutés.

## Travailler avec un agent

Le [plugin AIR — Architecture Workspace](https://github.com/yannickhuchard/air-plugin)
fournit les skills d’installation et de conception. [Connexion des agents](docs/agents.md).
Un IDE local peut utiliser CLI/MCP stdio. ChatGPT nécessite une connexion supportée
à cette installation ; le plugin n’est pas encore publié dans l’annuaire OpenAI.
Installer les skills ne connecte pas automatiquement le poste.

Les dossiers restent dans l’installation de leur propriétaire. Les extraits utilisés
avec un modèle cloud quittent le poste. Certaines présentations HTML chargent Mermaid
depuis jsDelivr et des polices Google : ne pas les présenter comme entièrement hors ligne.
L’installation locale et les calculs du moteur n’exigent pas ces services.

## Développer et contribuer

```text
python scripts/install.py --extras dev,proofs,backup
.venv/Scripts/python.exe -m pytest -q
```

Les tests inclus portent sur le moteur et ses exemples. Les reçus privés et les
scripts de sessions natives du développeur ne sont pas distribués. Aucun workflow CI
automatique n’est activé. [Provenance et licences tierces](docs/publication.md).
Les dossiers d’entreprise ne sont pas couverts par la licence du logiciel.

Support communautaire : [issues](https://github.com/yannickhuchard/air-engine/issues),
sans engagement de délai. N’y déposer ni secret ni dossier confidentiel ; demander
d’abord un canal privé pour un incident sensible.

English: AIR is a local architecture design, validation and simulation engine.
Run `python scripts/install.py --start`, then follow the synthetic Asteria examples.
It does not execute your future business system. ChatGPT directory availability
is pending; local storage does not prevent authorized data being sent to a model provider.
