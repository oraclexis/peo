# Dogfooding: milestone A′ report

Aggregated results only (document 07, section 7.1; spec 16, section 2.3). No file, excerpt or raw output of an audited repository is committed here. The raw notes stay in the local journal `docs/dogfooding.local.md`, excluded from git.

- Open source repositories: named, with the commit SHA audited.
- Pilot 1: pseudonymized, aggregated counts only.
- `X-SECRET-TRACKED` and `X-LITERAL-IN-AGENT-CONFIG` on an open source repository: counts per code only, no path or source, published after the maintainer was told privately and 30 days passed (document 07, section 7.1).

## Thresholds (document 07, section 7.1)

| Measure | Threshold | Result |
|---|---|---|
| (a) Actionable `X-*` findings | ≥ 1 on each of the 3 repositories (`X-MCP-UNEVALUATED`, `X-DATA-STORE`, `X-NO-SECRET-SCAN` and a `data_stores`-only `X-SANDBOX-OFF` excluded) | — |
| (a) False positives, severity `error` | 0 in total (`test-fixture` verdicts and `likely` findings excluded) | — |
| (a) `error` findings with confidence `likely` | counted separately, with their reason (table below) | — |
| (a) False positives, `warning`/`info` | ≤ 1/3 of the non-systematic `X-*` `warning`/`info` findings, 3 repositories together | — |
| (a) and (b) Gaps with the expected findings | each one recorded below | — |
| "Protected" or equivalent shown wrongly | 0 | — |
| Sensitive value in a PEO output | 0 | — |
| Duration of `peo status --exposure` | < 5 s per repository, `claude` subprocess time excluded (noted separately) | — |
| Network access by the PEO process | 0 (limit: `claude` subprocesses not covered, S20) | — |

## Repositories

| Repository | Stack | Commit | Config | Size (tracked lines) | Duration (PEO) | Duration (`claude`) |
|---|---|---|---|---|---|---|
| Pilot 1 (pseudonymized) | Nuxt + Laravel | — | real workstation config | — | — | — |
| [brocoders/nestjs-boilerplate](https://github.com/brocoders/nestjs-boilerplate) (MIT) | NestJS | `9620f159eefe38f47747d02ab162852367c5472c` | empty `CLAUDE_CONFIG_DIR` | 35 724 | 1.74 s (a), 1.41 s (b A), 1.32 s (b B) | included, not measured apart |
| [odense-rpa/automation-server](https://github.com/odense-rpa/automation-server) (MIT) | FastAPI + Vue | `522d6038378e35ee4b67071db2f672f6a0a38da2` | empty `CLAUDE_CONFIG_DIR` | 52 407 | 1.04 s (a), 1.19 s (b A), 1.17 s (b B) | included, not measured apart |

Durations: wall time of `peo status --exposure --json`, `claude` subprocesses included; below the 5 s threshold even with them.

Size: lines of the text files tracked by git (`grep -Ic ''` on `git ls-files`), binaries excluded.

Claude Code version, pinned and identical for the 3 audits: `2.1.325` (the only entry of `versions_tested` in `conformance/claude-rules.json`).

Known selection gaps, recorded before the run: brocoders names its env examples `env-example-relational` and `env-example-document`, which are not in Discovery's `ENV_EXAMPLES` and not matched by `secret_files` either (no leading `.env`); for automation-server, expectations on `X-SECRET-TRACKED` and on the file it concerns are kept in the local journal until the disclosure delay ends (document 07, section 7.1).

## `error` findings with confidence `likely`

| Repository | Code | Path or source | Reason |
|---|---|---|---|

## Expected findings (written before the run)

| Repository | Measure | State | Code | Path or source | Expected |
|---|---|---|---|---|---|
| brocoders | (a) | clone | `X-SECRET-*`, `X-DATA-READABLE`, `X-COVERAGE-NOT-SHARED` | — | none: `secret_files`, `data_dumps` and `log_dirs` are empty |
| brocoders | (a) | clone | `X-LITERAL-IN-AGENT-CONFIG`, `X-MCP-UNEVALUATED` | — | none: no `.claude/settings*.json`, no `.mcp.json`, empty config dir |
| brocoders | (a) | clone | `X-NO-SECRET-SCAN` | `.github/workflows/*.yml` | warning, 1 (no `gitleaks` token; `.husky/pre-commit` is not read) |
| brocoders | (a) | clone | `X-SANDBOX-OFF` | — | warning, 1, triggered by `data_stores` only (component runtime `host`): excluded from the threshold |
| brocoders | (a) | clone | `X-DATA-STORE` | compose files | info, 8 (one per `data_stores` entry; the `mongo-express` service is an admin UI classified `mongodb`, a possible Discovery false positive) |
| brocoders | (a) | clone | actionable total | — | **0**: threshold "≥ 1 actionable" expected to fail on this repository |
| brocoders | (b) | A | `X-SECRET-READABLE` | `.env` | error, `fact`, `suggested_rule = "Read(./.env)"`; `audited`: `.env` `not_covered` |
| brocoders | (b) | A | `X-SANDBOX-OFF` | — | warning, now with `secret_files` non-empty |
| brocoders | (b) | B | `X-SECRET-READABLE`, `X-COVERAGE-NOT-SHARED` | `.env` | gone; `audited`: `.env` `covered`, source `settings:project` |
| brocoders | (b) | B | `X-SANDBOX-OFF` → `X-SANDBOX-FALLBACK` | — | `X-SANDBOX-OFF` gone; `X-SANDBOX-FALLBACK` warning (`failIfUnavailable` absent), listing `.env` as covered |
| automation-server | (a) | clone | `X-SANDBOX-OFF` | — | warning, 1, component `backend` runtime `docker:api`; severity per S-9 |
| automation-server | (a) | clone | `X-NO-SECRET-SCAN` | `.github/workflows/*.yml` | warning, 1 (Trivy is used, not a recognized token) |
| automation-server | (a) | clone | `X-DATA-STORE` | `docker-compose.yml` | info, 1 (`db`, postgres) |
| automation-server | (a) | clone | `X-LITERAL-IN-AGENT-CONFIG`, `X-MCP-UNEVALUATED`, `X-DATA-READABLE`, `X-COVERAGE-NOT-SHARED` | — | none |
| automation-server | (b) | B | `X-SANDBOX-OFF` → `X-SANDBOX-FALLBACK` | — | `X-SANDBOX-OFF` gone; `X-SANDBOX-FALLBACK` warning, listing `.env` as covered |
| both | (a), (b) | all | `S-PLUGIN-ERROR`, `S-HOOK-FOREIGN`, `S-DEGRADED-INVENTORY` | — | none (empty config dir, `claude` 2.1.325 present) |
| both | (a), (b) | all | any | output | no fake value from the generated `.env` in any output (grep on the values) |

Mesure (b), setup: state A = clone + `.env` copied from the repository's example (`env-example-relational` for brocoders, `.env.example` for automation-server), every value replaced by a generated fake; state B = A + a tracked, committed `.claude/settings.json` with `permissions.deny = ["Read(./.env)"]` and `sandbox.enabled = true`, without `failIfUnavailable`.

The automation-server rows of (b) state A and B that name the withheld file were moved to the local journal with the other withheld expectations before the run.

Pilot 1: expected findings to be written before its run (real workstation config).

## Verdicts

| Repository | Code | Path or source | Verdict (`actionable`, `false-positive`, `already-known`, `test-fixture`) | Gap with the expected findings |
|---|---|---|---|---|
| brocoders | `X-NO-SECRET-SCAN` | `.github/workflows/*.yml` | `actionable` (excluded from the threshold) | none |
| brocoders | `X-SANDBOX-OFF` | — | `already-known` (`data_stores` only, excluded) | none |
| brocoders | `X-DATA-STORE` ×7 | compose files | `already-known` (systematic) | none |
| brocoders | `X-DATA-STORE` ×1 | `docker-compose.document.yaml`, service `mongo-express` | `false-positive`: an admin UI, not a database | as expected; Discovery backlog: do not classify `mongo-express`, `adminer`, `pgadmin` images as data stores |
| brocoders | actionable total | — | **0**: threshold (a) fails on this repository | as expected |
| brocoders | (b) A → B | `.env` | `not_covered` → `covered` (`settings:project`, `Read(./.env)`); `X-SECRET-READABLE` and `X-SANDBOX-OFF` gone, `X-SANDBOX-FALLBACK` appears | none |
| automation-server | `X-SANDBOX-OFF` | — | `actionable` (counts) | none |
| automation-server | `X-NO-SECRET-SCAN` | `.github/workflows/*.yml` | `false-positive`: `image-scan.yml` runs Trivy, whose default scanners include secrets (on the image, not the repository) | as expected; R4 backlog: a Trivy fiche with a `ci` token |
| automation-server | `X-DATA-STORE` | `docker-compose.yml`, service `db` | `already-known` (systematic) | none |
| automation-server | `X-SECRET-*` | withheld | in the local journal | none |
| automation-server | (b) A → B | `.env` | `not_covered` → `covered` (`settings:project`, `Read(./.env)`); `X-SANDBOX-OFF` gone, `X-SANDBOX-FALLBACK` appears | none |
| both | `S-*` | — | none emitted | none |
| both | NF14 | outputs of (a), (b) A, (b) B | 0 of the 120 generated fake values found in the 6 JSON outputs | none |

## Withheld findings (open source repositories)

| Repository | Code | Count | Maintainer told (date) | Published after |
|---|---|---|---|---|
