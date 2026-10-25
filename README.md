# AIR · Architecture Workspace

**Turn a business idea into an architecture that people can understand, check and build.**

AIR means *Architecture Intermediate Representation*. It connects business needs,
user journeys, components, data, decisions and evidence in one versioned model.
Your AI assistant helps you design the solution. The AIR engine checks the
declared model and keeps its sources and revision history.

Created by **Yannick Huchard**. Python 3.11+, SQLite and local authentication are
the starting point. Docker, Node, a cloud account and an identity provider are
optional rather than installation requirements.

[Install AIR](#install-and-verify-the-engine) · [For AI agents](docs/agent-quickstart.md) ·
[Implementation status](docs/etat-implementation.md)

## Which repository do you need?

| Repository | Its role | Use it when |
| --- | --- | --- |
| **air-engine**, this repository | Python engine, CLI/API/MCP, deterministic checks, examples and technical guides | You want to install, operate or develop AIR |
| [air-plugin](https://github.com/yannickhuchard/air-plugin) | Agent skills, plugin manifests and client installation guidance | You want your assistant to follow the AIR workflow |
| Your own architecture repository | Business sources, design drafts, selected baselines and generated deliverables | You want to design a specific solution; keep client data under your control |

You can use the engine directly without a plugin. A plugin supplies instructions;
it does not bundle the engine or grant access to your project.

## What you can do with AIR

| You want to | AIR helps you produce |
| --- | --- |
| Explain a solution | A management summary, decisions, alternatives and open questions |
| Design with business teams | Personas, user journeys, processes and the needs behind them |
| Prepare construction | Versioned handoffs, component contracts, responsibilities and acceptance criteria |
| Check the design | Traceability, deterministic checks, declared-model simulations and reproducible counterexamples |
| Understand a change | Comparisons between exact baselines and evidence that needs to be reviewed again |
| Share the result | A readable, responsive website named **Projet d’architecture**, with source links |

The architecture describes systems to be built later. A successful model check
does not mean that the future business application has been implemented or run.

## Version and delivery status

This source branch contains **engine 0.35.0.dev4**. It is a development version.
The [dev4 release](https://github.com/yannickhuchard/air-engine/releases/tag/v0.35.0.dev4)
contains its downloadable artifacts and checksums. The
[rc9 release](https://github.com/yannickhuchard/air-engine/releases/tag/v0.34.0rc9)
retains its own historical local qualification; that qualification does not extend
automatically to later versions.

Read the [public implementation status](docs/etat-implementation.md) and
[validation record](docs/validation.md) for delivered features and limits.
Engine and plugin versions are independent. A GitHub release, an installation
test and acceptance by a client's public plugin directory are separate events.

## Install and verify the engine

You can ask an assistant with terminal access to do this for you:

> Install the official AIR engine for this architecture project in a dedicated
> local directory. Use Python, SQLite and local authentication. Read the repository
> instructions, identify the source version, inspect the installer, preserve any
> existing data, then start AIR and verify it. Keep credentials out of the chat.

For a new installation from the public source repository:

```sh
git clone https://github.com/yannickhuchard/air-engine.git
cd air-engine
python scripts/install.py --start
```

Run these commands in an empty parent directory where you want to keep AIR.
Git is needed for this checkout route. Alternatively, extract a verified source
archive from [engine releases](https://github.com/yannickhuchard/air-engine/releases),
open its root directory and run the same installer. Select the release tag or
commit before installation when you need a reproducible version; `main` changes.

If you already have an authorized engine checkout, run the installer from that
checkout instead. It creates `.venv` and the private `.air` home, installs the
constrained dependencies and starts the API at `http://127.0.0.1:8740`.
Reinstallation preserves existing identities and revisions. Back up an existing
installation before an upgrade; the [installation guide](docs/installation.md)
explains custom paths, ports, verified wheels, offline dependencies and recovery.

From the engine directory, verify with its installed Python:

**Windows PowerShell**

```powershell
.\.venv\Scripts\python.exe -m air doctor
.\.venv\Scripts\python.exe -m air workstation-check
.\.venv\Scripts\python.exe -m air whoami
.\.venv\Scripts\python.exe -m air capabilities
.\.venv\Scripts\python.exe -m air validate examples/scope.json
```

**macOS / Linux shell**

```sh
.venv/bin/python -m air doctor
.venv/bin/python -m air workstation-check
.venv/bin/python -m air whoami
.venv/bin/python -m air capabilities
.venv/bin/python -m air validate examples/scope.json
```

These commands use the default home and port. `capabilities` describes the
installed binary; `whoami` checks the authenticated live connection. `/health`
reports the running service version. The API address is not the generated
architecture website. The website is produced later from your project model.

For another location, supply `--home` before the CLI command and the documented
connection options for network commands. Stop the identified local service with
`python scripts/install.py --stop`. Do not stop an unrelated process to free a port.

## Build your first architecture with an assistant

1. Connect your authorized project using the [AIR plugin](https://github.com/yannickhuchard/air-plugin)
   or the engine's [CLI/MCP integration](docs/mcp.md). The engine, plugin and project
   are separate: installing one does not configure all three.
2. Give the assistant the business need, scope, sources and known constraints.
   For an existing dossier, provide its baseline reference and project directory.
3. Ask it to read the exact baseline, explain gaps, prepare changes and run the
   checks the installed engine actually supports.
4. Review consequential decisions and missing evidence, then generate the
   **Projet d’architecture** website and the construction handoff.

> Use AIR to design this project. Start with the intended users and outcomes,
> identify what is missing, and ask focused questions. Keep sources and decisions
> traceable, validate the model, then generate the architecture website and handoff.
> Show the remaining blockers without inventing an approval or a test result.

Start with the [three fictional Asteria dossiers](fixtures/enterprise/asteria/README.md)
to see service operations, workshop maintenance and identity management in one
company. Their blocked gates and unexecuted future business tests are intentional.

For AI platforms, the [agent quickstart](docs/agent-quickstart.md) provides the
installation inputs, verification sequence, design loop and completion report.
It works as a handoff to an agent with a shell, a project MCP connection, or a
remote client connected to an authorized AIR service. Shell access is required
for automatic local installation.

## If something does not work

| Symptom | What to check |
| --- | --- |
| `python` is unavailable | Select a Python 3.11+ interpreter with venv/pip; use its full path if needed |
| Dependencies fail to install | Check network access or the approved Python package mirror and the selected version's constraints |
| Port 8740 is occupied | Identify the existing service or choose an explicit unused port with `--port` |
| Authentication or namespace access is refused | Check the selected home, credential filename and authorized scope; retain the refusal |
| A skill or tool is missing | Check the engine version, client support, enabled plugin and filtered tool catalogue |
| A design remains blocked | Open the reported missing source, criterion, decision or evidence; a blocked result can be correct |

The [installation guide](docs/installation.md) and [implemented scope](docs/etat-implementation.md)
provide the detailed diagnosis. Each organization or client should have a separate
private home and identities. Local installations do not automatically synchronize.

## Explore the project

| Your role | Start here |
| --- | --- |
| Architect or AI agent | [Agent quickstart](docs/agent-quickstart.md), [architect's guide](docs/guide-architecte-agent.md) |
| Business or project team | [Personas and journeys](docs/parcours-personas-et-usages.md), [reading the website](docs/site-architecture-statique.md) |
| Builder | [Component contracts](docs/lot-b-profils-et-contrats.md), [team handoffs](docs/lot-c-transmission-equipes.md) |
| Reviewer | [Counterexamples and evidence impact](docs/lot-d-verification-impact.md) |
| Management | [Summary and transformation](docs/synthese-et-pilotage-transformation.md) |
| Operator | [Installation](docs/installation.md), [architect workstation profile](docs/production-poste-architecte.md) |

The detailed guides are currently written mainly in French. Source code,
structured requests and tool names remain the authoritative interfaces.

## License, data and contribution

AIR is licensed under [Apache-2.0](LICENSE), with third-party notices in [NOTICE](NOTICE).
The software license does not publish your architecture data. Keep `.air`, private
logs and credentials outside version control, and choose what may be sent to your
model provider under your organization's policy.

For local development, install the required optional tools with
`python scripts/install.py --extras dev,proofs,backup`, then run the relevant tests
with `.venv/Scripts/python.exe -m pytest -q` on Windows or
`.venv/bin/python -m pytest -q` on macOS/Linux. CI remains manually triggered.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md) before contributing.
