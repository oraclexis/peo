# Fixtures

Spec: `docs/design/spec/16-test-plan.md`, section 1. Each fixture is `tree/` + `build.sh TARGET`
(deterministic git history). No real history is ever copied.

| Fixture | Built by | Status |
|---|---|---|
| `fx-epure` | `tools/anonymize_epure.py`, run once on the machine that holds the real project | to build |
| `fx-laravel`, `fx-vue`, `fx-nestjs`, `fx-python`, `fx-monorepo`, `fx-new`, `fx-conflict`, `fx-rich-claude-md`, `fx-hostile`, `fx-large` | hand-written `tree/` + `build.sh` | phase P1 |
