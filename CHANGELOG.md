# Changelog

## Unreleased

- Repository skeleton: package, CLI envelope and exit codes, JSON Schemas, CI, design dossier and MVP specification.
- Discovery, components and runtime (P1.3): `peo.discovery.discover()` finds components, stacks, languages, code paths, `monorepo`, `multi_component` and where each component's commands run (`host` or `docker:<service>`); `peo.runner`, the injectable command runner. Acceptance test A1.3 passes.
- Discovery, commands and conventions (P1.4): commands per component (`typecheck`, `test`, `lint`, `build`, `e2e`, `format`) prefixed by the runtime, the aggregated `verify`, branch and commit conventions measured from git history (merges excluded), `kind`, `git`, `ci` and the gaps `no-ci`, `no-verify`, `no-remote`, `no-tests:*`, `no-lint:*`. Acceptance test A1.4 passes.
- CI/CD: `ci`, `release` (GitHub release, PyPI trusted publishing behind a switch), `codeql`, Dependabot; `tools/release.py` for version consistency and release notes.
