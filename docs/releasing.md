# Releasing

1. Set the same version in `pyproject.toml` and `src/peo/__init__.py`, rename `## Unreleased` in `CHANGELOG.md`
   to `## X.Y.Z — YYYY-MM-DD` (add a new empty `## Unreleased` above), merge to `main`.
   `python tools/release.py check-version --tag vX.Y.Z` must pass.
2. Tag and push: `git tag v0.1.0 && git push origin v0.1.0`.
3. The `release` workflow checks that tag, package version and CHANGELOG agree (`tools/release.py`), runs the tests, builds the wheel and sdist,
   smoke-tests the wheel, and creates the GitHub release with the files attached and the CHANGELOG section as notes (pre-release for `v0.*`, `a`, `b`, `rc`).
4. PyPI publication runs only when the repository variable `PUBLISH_PYPI` is `true`.

## One-time PyPI setup (trusted publishing, no token)

1. On PyPI, add a *pending publisher* for project `peo`: owner `oraclexis`, repository `peo`,
   workflow `release.yml`, environment `pypi`. The name `peo` was free on PyPI on 2026-11-11.
2. On GitHub: Settings → Environments → create `pypi` (optionally require your approval).
3. Settings → Secrets and variables → Actions → Variables: `PUBLISH_PYPI = true`.

## Recommended repository settings

- Branch protection on `main`: require the `ci` checks (`test (...)`, `package`) and a pull request.
- Settings → Code security: enable Dependabot alerts and secret scanning (push protection).
