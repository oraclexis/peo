# Dogfooding: milestone A′ report

Aggregated results only (document 07, section 7.1; spec 16, section 2.3). No file, excerpt or raw output of an audited repository is committed here. The raw notes stay in the local journal `docs/dogfooding.local.md`, excluded from git.

- Open source repositories: named, with the commit SHA audited.
- Pilot 1: pseudonymized, aggregated counts only.
- `X-SECRET-TRACKED` and `X-LITERAL-IN-AGENT-CONFIG` on an open source repository: counts per code only, no path or source, published only once the finding is `disclosed`: 30 days after the details were sent privately, or the maintainer's answer (document 07, sections 7.1 and 7.1 bis). Any other state, or no state, publishes nothing.

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
| — | NestJS | — | empty `CLAUDE_CONFIG_DIR` | — | — | — |
| — | Python | — | empty `CLAUDE_CONFIG_DIR` | — | — | — |

Claude Code version, pinned and identical for the 3 audits: —

## `error` findings with confidence `likely`

| Repository | Code | Path or source | Reason |
|---|---|---|---|

## Expected findings (written before the run)

| Repository | Measure | State | Code | Path or source | Expected |
|---|---|---|---|---|---|

## Verdicts

| Repository | Code | Path or source | Verdict (`actionable`, `false-positive`, `already-known`, `test-fixture`) | Gap with the expected findings |
|---|---|---|---|---|

## Withheld findings (open source repositories)

Only `disclosed` findings appear in this table (document 07, section 7.1 bis).

| Repository | Code | Count | Details sent privately (date) | Disclosed (date) |
|---|---|---|---|---|

Withheld findings not disclosed for lack of a private channel (`no_private_channel`): 0.
