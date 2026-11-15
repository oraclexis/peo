# fx-ci-gitlab

Hand-written `.gitlab-ci.yml` cases of A14.9 (spec 16, section 1), one file per case, no
`build.sh`: each test copies **one** case to `.gitlab-ci.yml` in a temporary git repository.

| Case | Content | `X-NO-SECRET-SCAN` |
|---|---|---|
| `script.yml` | list item `- gitleaks dir .` | no |
| `image.yml` | `image: zricethezav/gitleaks:latest` | no |
| `image-name.yml` | `image:` block with `name: ghcr.io/gitleaks/gitleaks:v8` | no |
| `template.yml` | `include:` with `- template: Jobs/Secret-Detection.gitlab-ci.yml` | no |
| `comment.yml` | `gitleaks` only in a comment | yes |
