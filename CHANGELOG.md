# Changelog

## Unreleased

- Repository skeleton: package, CLI envelope and exit codes, JSON Schemas, CI, design dossier and MVP specification.
- Discovery, components and runtime (P1.3): `peo.discovery.discover()` finds components, stacks, languages, code paths, `monorepo`, `multi_component` and where each component's commands run (`host` or `docker:<service>`); `peo.runner`, the injectable command runner. Acceptance test A1.3 passes.
- Discovery, commands and conventions (P1.4): commands per component (`typecheck`, `test`, `lint`, `build`, `e2e`, `format`) prefixed by the runtime, the aggregated `verify`, branch and commit conventions measured from git history (merges excluded), `kind`, `git`, `ci` and the gaps `no-ci`, `no-verify`, `no-remote`, `no-tests:*`, `no-lint:*`. Acceptance test A1.4 passes.
- Discovery, documentation and drift (P1.5): `docs` (README, `CLAUDE.md` class, `AGENTS.md`, handoff, decisions folder), tools announced by the docs (`intent_from_docs`, from a table of the initial catalog), documentation drift D1 to D4 with fixed messages, and the gaps `no-agents-md` and `no-adr`. Acceptance test A1.5 passes; only A1.1 (full profile) remains.
- Discovery, signals, sensitive surfaces, present tools and metrics (P1.6): the four selection signals, `sensitive` (secret files with variable names only, databases from compose images, dumps, log directories; no secret value ever in an output, NF14), catalog tools already present (`present_tools`, provisional `detect.toml`) and `metrics`. The `fx-split-stack` fixture gains an untracked `backend/.env` with fake values. Acceptance tests A1.8 and the Discovery part of A14.2 pass, and so does A1.1: the whole profile equals the golden file (only `generated`, written by `peo discover --write`, is left for P1.7).
- Known debt: `Schema.from_dict` keeps a deep copy of the schema; unit tests for the Go, Rust, JVM, Ruby and `requirements*.txt` manifest readers.
- CI/CD: `ci`, `release` (GitHub release, PyPI trusted publishing behind a switch), `codeql`, Dependabot; `tools/release.py` for version consistency and release notes.
