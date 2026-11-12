# PEO — Project Engineering Orchestrator

[![ci](https://github.com/oraclexis/peo/actions/workflows/ci.yml/badge.svg)](https://github.com/oraclexis/peo/actions/workflows/ci.yml)
[![codeql](https://github.com/oraclexis/peo/actions/workflows/codeql.yml/badge.svg)](https://github.com/oraclexis/peo/actions/workflows/codeql.yml)

> **Status: pre-alpha, phase P1.** Nothing is usable yet. The design and the MVP specification are complete and live in [`docs/design/`](docs/design/README.md) (in French).

PEO sets up a solid, minimal and justified AI-assisted engineering environment for a software project, starting with Claude Code. It works in three steps:

1. **Audit** (read only). It **discovers** the project (components, stacks, commands, conventions, documentation drift) without an LLM, and **inventories** the agent environment: installed tools, hooks per event and their owner, conflicts, and **what the agent can read and send** (secret files, databases, dumps, logs, missing controls).
2. **Recommend**. It **selects** the smallest set of tools that covers what the project needs, from an **evaluated catalog**, refusing combinations that overlap or conflict, and explains every choice.
3. **Apply**. It **delegates** installation to native installers (Claude Code plugins, `uv`, `npm`, Spec Kit) after showing an exact plan, and **enforces process gates** (no code before an approved spec, plan and tasks) through a Claude Code hook.

For security and privacy, PEO **detects, configures and verifies** controls (Claude Code permissions, secret scanning, masking tools). It never masks data itself and never sits on the data path, and it never claims that data is protected.

PEO is deliberately thin: it is not a package manager, not a methodology, not an agent framework and not a data-masking tool. See [`docs/design/01-vision-et-analyse-strategique.md`](docs/design/01-vision-et-analyse-strategique.md) (section 9 for the 2026-11-12 review) and [`docs/design/17-securite-et-confidentialite.md`](docs/design/17-securite-et-confidentialite.md).

## Repository layout

| Path | Content |
|---|---|
| `src/peo/` | Python package (standard library only at runtime) |
| `src/peo/schemas/` | JSON Schemas, copied from `docs/design/spec/schemas/` |
| `catalog/` | Tool catalog snapshot (moves to its own repository in phase P7) |
| `plugin/` | Claude Code plugin (thin skills calling the CLI), from phase P3 |
| `tests/` | Tests, fixtures and golden files |
| `tools/` | Maintenance scripts (release) |
| `docs/design/` | Design dossier and MVP specification |

## Development

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run peo --version
```

Rules: the specification is the source of truth (change it first, then the code); tests before code; no runtime dependency.

## CI/CD

| Workflow | When | What |
|---|---|---|
| `ci` | push to `main`, pull requests | lint, version consistency, tests and spec examples on Linux and macOS (Python 3.11, 3.13); wheel built and smoke-tested |
| `release` | tag `vX.Y.Z` | consistency check, tests, build, GitHub release with CHANGELOG notes; PyPI publication once enabled |
| `codeql` | push, pull requests, weekly | static analysis of Python code and workflows |
| Dependabot | weekly | GitHub Actions and Python dev dependencies |

Release procedure: [docs/releasing.md](docs/releasing.md).

## License

Apache-2.0. See [LICENSE](LICENSE).
