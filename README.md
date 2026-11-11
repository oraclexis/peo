# PEO — Project Engineering Orchestrator

[![ci](https://github.com/oraclexis/peo/actions/workflows/ci.yml/badge.svg)](https://github.com/oraclexis/peo/actions/workflows/ci.yml)
[![codeql](https://github.com/oraclexis/peo/actions/workflows/codeql.yml/badge.svg)](https://github.com/oraclexis/peo/actions/workflows/codeql.yml)

> **Status: pre-alpha, phase P1.** Nothing is usable yet. The design and the MVP specification are complete and live in [`docs/design/`](docs/design/README.md) (in French).

PEO sets up a solid, minimal and justified AI-assisted engineering environment for a software project, starting with Claude Code:

- it **discovers** the project (components, stacks, commands, conventions, documentation drift) without an LLM;
- it **selects** the smallest set of tools that covers what the project needs, from an **evaluated catalog**, refusing combinations that overlap or conflict, and explains every choice;
- it **delegates** installation to native installers (Claude Code plugins, `uv`, `npm`, Spec Kit) after showing an exact plan;
- it **enforces process gates** (no code before an approved spec, plan and tasks) through a Claude Code hook.

PEO is deliberately thin: it is not a package manager, not a methodology and not an agent framework. See [`docs/design/01-vision-et-analyse-strategique.md`](docs/design/01-vision-et-analyse-strategique.md).

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
