# Fixtures

Spec: `docs/design/spec/16-test-plan.md`, section 1. Each fixture is `tree/` + `build.sh TARGET`
(deterministic git history). No real history is ever copied.

| Fixture | Built by | Status |
|---|---|---|
| `fx-split-stack` | hand-written `tree/` + `history.tsv` (one line per branch: name, subject, files added) + `build.sh TARGET` | built (spec 16, section 2.1; checked by A0.1 and A0.2) |
| `fx-laravel`, `fx-vue`, `fx-nestjs`, `fx-python`, `fx-monorepo`, `fx-new`, `fx-conflict`, `fx-rich-claude-md`, `fx-hostile`, `fx-large` | hand-written `tree/` + `build.sh` | phase P1 |
