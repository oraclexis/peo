# Dogfooding: milestone A′ report

Aggregated results only (document 07, section 7.1; spec 16, section 2.3). No file, excerpt or raw output of an audited repository is committed here. The raw notes stay in the local journal `docs/dogfooding.local.md`, excluded from git.

- Open source repositories: named, with the commit SHA audited.
- Pilot n°1: pseudonymized, aggregated counts only.

## Thresholds (document 07, section 7.1)

| Measure | Threshold | Result |
|---|---|---|
| (a) Actionable findings | ≥ 1 on each of the 3 repositories | — |
| (a) False positives, severity `error` | 0 in total | — |
| (a) False positives, non-systematic `warning`/`info` | ≤ 1/3 in total | — |
| (b) A/B fidelity | every gap with the expected findings recorded | — |
| Duration of `peo status --exposure` | < 5 s per repository | — |

## Repositories

| Repository | Stack | Commit | Size (tracked lines) | Duration |
|---|---|---|---|---|
| Pilot n°1 (pseudonymized) | Nuxt + Laravel | — | — | — |
| — | NestJS | — | — | — |
| — | Python | — | — | — |

## Expected findings (written before the run)

| Repository | Measure | State | Code | Path or source | Expected |
|---|---|---|---|---|---|

## Verdicts

| Repository | Code | Path or source | Verdict (`actionable`, `false positive`, `already known`) | Gap with the expected findings |
|---|---|---|---|---|
