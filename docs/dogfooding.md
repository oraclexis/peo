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
| Duration of `peo status --exposure` | < 5 s per repository, `claude` subprocess time excluded (noted separately) | met on the 2 open source repositories and their 4 A/B copies: at most 0.68 s without `claude` (pilot 1 pending) |
| Network access by the PEO process | 0 (limit: `claude` subprocesses not covered, S20) | 0 on the same 6 runs (spec 16 §2.3 test, sockets refused in the PEO process; pilot 1 pending) |

## Repositories

| Repository | Stack | Commit | Config | Size (tracked lines) | Duration (PEO) | Duration (`claude`) |
|---|---|---|---|---|---|---|
| Pilot 1 (pseudonymized) | Nuxt + Laravel | withheld (pseudonymized) | real workstation config | 99 tracked files | 0.89 s (a) | 1.03 s (a) |
| [brocoders/nestjs-boilerplate](https://github.com/brocoders/nestjs-boilerplate) (MIT) | NestJS | `9620f159eefe38f47747d02ab162852367c5472c` | empty `CLAUDE_CONFIG_DIR` | 35 724 | 0.54 s (a), 0.65 s (b A), 0.68 s (b B) | 0.48 s (a), 1.78 s (b A), 0.49 s (b B) |
| [odense-rpa/automation-server](https://github.com/odense-rpa/automation-server) (MIT) | FastAPI + Vue | `522d6038378e35ee4b67071db2f672f6a0a38da2` | empty `CLAUDE_CONFIG_DIR` | 52 407 | 0.49 s (a), 0.57 s (b A), 0.58 s (b B) | 0.55 s (a), 0.84 s (b A), 0.49 s (b B) |

Durations: measured by the local test of spec 16, section 2.3 (`PEO_AUDIT_PATHS`, `PEO_CLAUDE_VERSION=2.1.325`), which times the `claude` subprocesses apart; the same test found no write in the audited trees, no "protected" wording and no `.env` value in the outputs on these 6 runs.

Size: lines of the text files tracked by git (`grep -Ic ''` on `git ls-files`), binaries excluded.

Claude Code version, pinned and identical for the 3 audits: `2.1.325` (the only entry of `versions_tested` in `conformance/claude-rules.json`).

Selection gap recorded before the run: brocoders names its env examples `env-example-relational` and `env-example-document`, which are not in Discovery's `ENV_EXAMPLES` (Discovery backlog).

Measure (a) on the open source repositories (expected findings and verdicts, both repositories together) is published in one block once the disclosure process of document 07, section 7.1 bis, has ended for every retained finding of these repositories. The block was written on 2026-11-15 and is kept in the local journal; its SHA-256 is `e02370ad7e327986d590d776ddc093567e5fa0765dec44434ba04ad1dd9ab9ac`, so the published block can be checked against it.

## `error` findings with confidence `likely`

| Repository | Code | Path or source | Reason |
|---|---|---|---|

## Expected findings (written before the run)

| Repository | Measure | State | Code | Path or source | Expected |
|---|---|---|---|---|---|
| brocoders | (b) | A | `X-SECRET-READABLE` | `.env` | error, `fact`, `suggested_rule = "Read(./.env)"`; `audited`: `.env` `not_covered` |
| brocoders | (b) | B | `X-SECRET-READABLE`, `X-COVERAGE-NOT-SHARED` | `.env` | none on `.env`; `audited`: `.env` `covered`, source `settings:project` |
| automation-server | (b) | A | `X-SECRET-READABLE` | `.env` | error, `fact`; `audited`: `.env` `not_covered` |
| automation-server | (b) | B | `X-SECRET-READABLE`, `X-COVERAGE-NOT-SHARED` | `.env` | none on `.env`; `audited`: `.env` `covered`, source `settings:project` |
| both | (b) | A → B | `X-SANDBOX-OFF` → `X-SANDBOX-FALLBACK` | — | `X-SANDBOX-OFF` gone; `X-SANDBOX-FALLBACK` warning (`failIfUnavailable` absent), listing `.env` as covered |
| both | (a), (b) | all | `S-PLUGIN-ERROR`, `S-HOOK-FOREIGN`, `S-DEGRADED-INVENTORY` | — | none (empty config dir, `claude` 2.1.325 present) |
| both | (a), (b) | all | any | output | no fake value from the generated `.env` in any output (grep on the values) |

Measure (b), setup: state A = clone + `.env` copied from the repository's example (`env-example-relational` for brocoders, `.env.example` for automation-server), every value replaced by a generated fake; state B = A + a tracked, committed `.claude/settings.json` with `permissions.deny = ["Read(./.env)"]` and `sandbox.enabled = true`, without `failIfUnavailable`. Measure (b) compares the verdicts of `.env` only.

These expected findings were first pushed on 2026-11-15, before any run; the original commits are referenced in the local journal.

Pilot 1 (aggregated counts only, spec 16, section 2.2), real workstation config, written on 2026-11-16 before its run:

| Repository | Measure | Code | Expected |
|---|---|---|---|
| Pilot 1 | (a) | `X-DATA-READABLE` | warning, 1 (a log directory without a `deny Read` rule) |
| Pilot 1 | (a) | `X-NO-SECRET-SCAN` | warning, 1 (no CI file) |
| Pilot 1 | (a) | `X-SANDBOX-OFF` | info, 1 (`data_stores` only, a component runs in docker) |
| Pilot 1 | (a) | `X-DATA-STORE` | info, 1 |
| Pilot 1 | (a) | `X-MCP-UNEVALUATED` | info, one per MCP server of the enabled plugins (about 40) |
| Pilot 1 | (a) | `S-HOOK-FOREIGN` | info, 10 from the user settings, plus any plugin hook |
| Pilot 1 | (a) | `X-SECRET-*`, `X-COVERAGE-NOT-SHARED`, `X-LITERAL-IN-AGENT-CONFIG`, `S-PLUGIN-ERROR`, `S-DEGRADED-INVENTORY` | none |
| Pilot 1 | (a) | actionable total | 1, from `X-DATA-READABLE` |

## Verdicts

| Repository | Code | Path or source | Verdict (`actionable`, `false-positive`, `already-known`, `test-fixture`) | Gap with the expected findings |
|---|---|---|---|---|
| Pilot 1 | `X-DATA-READABLE` | a log directory | `actionable` | none |
| Pilot 1 | `X-NO-SECRET-SCAN` | no CI file | `actionable` (excluded from the threshold) | none |
| Pilot 1 | `X-SANDBOX-OFF` (info) | — | `already-known` (`data_stores` only, excluded) | none |
| Pilot 1 | `X-DATA-STORE` | compose | `already-known` (systematic) | none |
| Pilot 1 | `S-HOOK-FOREIGN` ×10 | user settings | `already-known` | none |
| Pilot 1 | `X-MCP-UNEVALUATED` | plugins | **0 emitted, 43 expected**: false negative | **gap**: spec 14 §3.4 reads plugin MCP servers from the `mcpServers` field of `claude plugin list --json`, which Claude Code 2.1.325 does not emit; the servers are declared in the plugins' own files, and no limit tells the reader |
| Pilot 1 | actionable total | — | 1: threshold (a) met | none |
| brocoders | (b) A → B | `.env` | `not_covered` → `covered` (`settings:project`, `Read(./.env)`) | none |
| automation-server | (b) A → B | `.env` | `not_covered` → `covered` (`settings:project`, `Read(./.env)`) | none |
| both | (b) A → B | — | `X-SANDBOX-OFF` gone, `X-SANDBOX-FALLBACK` appears | none |
| both | `S-*` | — | none emitted | none |
| both | NF14 | outputs of (a), (b) A, (b) B | 0 of the 120 generated fake values found in the 6 JSON outputs | none |

## Withheld findings (open source repositories)

Only `disclosed` findings appear in this table (document 07, section 7.1 bis).

| Repository | Code | Count | Details sent privately (date) | Disclosed (date) |
|---|---|---|---|---|

Withheld findings not disclosed for lack of a private channel (`no_private_channel`): 0.
