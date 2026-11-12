# Changelog

## Unreleased

- Repository skeleton: package, CLI envelope and exit codes, JSON Schemas, CI, design dossier and MVP specification.
- Discovery, components and runtime (P1.3): `peo.discovery.discover()` finds components, stacks, languages, code paths, `monorepo`, `multi_component` and where each component's commands run (`host` or `docker:<service>`); `peo.runner`, the injectable command runner. Acceptance test A1.3 passes.
- CI/CD: `ci`, `release` (GitHub release, PyPI trusted publishing behind a switch), `codeql`, Dependabot; `tools/release.py` for version consistency and release notes.
