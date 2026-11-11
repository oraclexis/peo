# Contributing to PEO

The specification in [`docs/design/spec/`](docs/design/spec/10-spec-overview.md) (in French) is the source of truth. Read it before changing behaviour.

## Principles

Every pull request is checked against these seven principles. The pull request template has one box per principle.

### I. Specification first (non-negotiable)

`docs/design/spec/` is the source of truth. Any behaviour change updates the spec in the same pull request, before the code. If code and spec disagree, stop and ask.

### II. Tests first (non-negotiable)

Every feature starts with failing acceptance tests named after [`docs/design/spec/16-test-plan.md`](docs/design/spec/16-test-plan.md) (A1.x, A2.x…). No merge with a red test or an unexplained `xfail`.

### III. Standard library only at runtime

Python ≥ 3.11, no runtime dependency. Dev only: pytest, hypothesis, jsonschema, ruff.

### IV. Determinism

The same inputs give byte-identical outputs: sorted keys, stable order, no timestamps in plans.

### V. Safety

- No `shell=True`; every subprocess goes through the injectable command runner (spec 14, section 4.1).
- No network outside adapters, and only after user consent.
- Never `sudo` or a system package manager.
- Never write outside managed blocks or owned keys.

### VI. Thin layer

PEO selects, composes and gates; it delegates installation. It never becomes a package manager, a methodology or an agent framework. A new feature shows that no existing tool already does it.

### VII. Languages

Code, identifiers, messages and catalog entries in English. Design docs in French.

## Workflow

- One step of a roadmap phase is one pull request.
- Inside a pull request: spec change first, then failing tests, then code.
- Test fixtures are hand-written (spec 16, section 2). Never commit files from a real project.
- Amending these principles is a pull request that also updates the spec.

## Commands

```bash
uv sync --group dev                                                          # install
uv run pytest                                                                # tests
uv run ruff check .                                                          # lint
uv run python docs/design/spec/schemas/check_examples.py docs/design/spec/schemas   # schema examples
```
