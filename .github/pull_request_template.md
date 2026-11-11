## What

<!-- one or two sentences -->

## Constitution

Tick each box, or write `n/a: <reason>` next to it. See `.specify/memory/constitution.md`.

- [ ] **I. Specification first**: the behaviour change is described in `docs/design/spec/` in this PR, committed before the code (or no spec change is needed: say why)
- [ ] **II. Tests first**: failing acceptance tests named after `16-test-plan.md` (A1.x, A2.x…) came first; no red test and no unexplained `xfail`
- [ ] **III. Standard library only at runtime**: no runtime dependency added; dev dependencies stay within pytest, hypothesis, jsonschema, ruff
- [ ] **IV. Determinism**: the same inputs give byte-identical outputs (sorted keys, stable order, no timestamps in plans)
- [ ] **V. Safety**: no `shell=True`, every subprocess goes through the command runner, no network outside adapters or before consent, no `sudo` or system package manager, no write outside managed blocks or owned keys
- [ ] **VI. Thin layer**: PEO only selects, composes and gates; any new feature shows that no existing tool already does it
- [ ] **VII. Languages**: code, identifiers, messages and catalog entries in English; design docs in French
