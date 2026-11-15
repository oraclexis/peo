# fx-ci-github

Hand-written cases of A14.9 (spec 16, section 1), one file per case, no `build.sh`: each test
copies **one** case to its real path in a temporary git repository and tracks it
(`.github/workflows/<case>`, or `.pre-commit-config.yaml` for `precommit.yaml`).

| Case | Content | `X-NO-SECRET-SCAN` |
|---|---|---|
| `run.yml` | `run: gitleaks detect --redact` | no |
| `uses.yml` | `uses: gitleaks/gitleaks-action@v2` | no |
| `precommit.yaml` | `id: gitleaks` | no |
| `name-only.yml` | `gitleaks` only as a job key and in `name: gitleaks` | yes |
| `comment.yml` | `gitleaks` only in a comment | yes |
