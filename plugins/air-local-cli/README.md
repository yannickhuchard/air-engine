# AIR Skills-only CLI plugin

**Use your local AIR engine from an AI assistant with a local executor.**

Development release **0.1.16** by **Yannick Huchard**, under [Apache-2.0](LICENSE).
The package contains two skills, a Python CLI helper and their resources. The
engine, project data and credentials stay in your separate AIR installation.
No MCP server is declared. Both manifests set `requires_local_executor: true`.

## What you need

- A desktop client/session that can install this plugin and execute local commands.
- Python 3.11+ and an authorized engine checkout with its venv at `.venv`.
- A private AIR home, known loopback port, protected credential filename and project.
- A compatible engine: **0.35.0.dev8** is the companion prerelease.
  Verify the installed capabilities; installing a plugin does not upgrade the engine.

The helper launches the engine's installed Python and its CLI. Authenticated
operations use the engine's HTTP service on `127.0.0.1`; the engine consumes the
credential file. The helper is a workflow guard, not a sandbox for untrusted code.
It does not make a remote web chat able to execute on your computer.

## Install the candidate

From an authorized AIR development checkout containing `scripts/build_plugin.py`,
build into a new output directory:

```sh
python scripts/build_plugin.py --variant cli --direct-marketplace --output-dir dist/cli-0.1.16-preview
```

The CLI ZIP contains the plugin; the marketplace ZIP adds a local catalogue.
Extract the marketplace ZIP into a dedicated directory and open its `AIR-plugins`
root as a local project in ChatGPT desktop. Restart the app, install AIR from the
**AIR CLI - Distribution directe** source in **Plugins**, and start a new local
chat with an executor. The checkout's `docs/installation-chatgpt.md` also explains
how to use a source catalogue without building an archive.

If Codex CLI is already available, `codex plugin marketplace add .` from the
marketplace root registers that source. Registration, plugin installation and
engine setup are separate steps. Follow the client UI for installation and verify
that the skills are available in the new session.

Download the CLI and marketplace archives with their SHA-256 receipts from
[release 0.1.16](https://github.com/yannickhuchard/air-plugin/releases/tag/v0.1.16).
This GitHub distribution does not establish OpenAI-directory approval or native
client acceptance. Historical approved archives, including 0.1.7, retain their bytes.

## Let an agent set up and use AIR

> Use air-local-setup to install or connect the authorized AIR engine for this
> project. Use Python, SQLite and local authentication, preserve existing data,
> verify the source version and live connection, then use air-local-design to
> build the dossier. Keep credential contents out of the conversation.

1. [air-local-setup](skills/air-local-setup/SKILL.md) identifies the engine, home,
   port, identity and project, then follows the chosen engine's installation guide.
   A user's installation request covers that target's ordinary setup steps.
2. Verify `doctor`, `workstation-check`, authenticated `whoami` and the installed
   catalogue. The helper's `capabilities` output describes the binary; check the
   running service version separately. Do not silently switch homes or roles.
3. [air-local-design](skills/air-local-design/SKILL.md) reads the exact baseline,
   prepares and validates changes, runs supported checks and generates the
   **Projet d’architecture** website and builder handoff.
4. Preserve real blockers, decisions and unexecuted tests. A local simulation
   describes the declared model; the future business application is built later.

For longer work, dev8 exposes completion runs, scoped delivery checks, context
export controls, generation traces, CI evidence import and effort comparison.
Discover the actual commands first. Portable files can preserve work when the
engine is unavailable, with engine checks left pending.

## Diagnose a failed setup

| Error or symptom | Next step |
| --- | --- |
| `AIR_ENGINE_MISSING` | Select the authorized checkout with an installed `.venv` |
| `AIR_CONFIGURATION_MISSING` | Check the explicit home and credential filename without reading secrets |
| `AIR_UNREACHABLE` | Check the identified loopback service and chosen port |
| `AIR_EXECUTION_UNAVAILABLE` | Use a session with an accessible local executor |
| Missing skill or command | Refresh the installed plugin, start a new session and verify engine compatibility |
| Access refused | Retain the error and have the configured permissions checked |

[Engine](https://github.com/yannickhuchard/air-engine) ·
[Public plugin](https://github.com/yannickhuchard/air-plugin) ·
[Support](https://github.com/yannickhuchard/air-plugin/issues)
