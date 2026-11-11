# PEO

Python CLI + thin Claude Code plugin. Specification: `docs/design/spec/` (French). It is the source of truth.

## Rules

- Change the spec before the code. If code and spec disagree, stop and ask.
- Tests first. Acceptance test IDs (A1.x, A2.x…) come from `docs/design/spec/16-test-plan.md`; name tests after them.
- Runtime: Python ≥ 3.11 standard library only. Dev dependencies: pytest, hypothesis, jsonschema, ruff.
- Never `shell=True`. Every subprocess goes through the injectable command runner (spec 14, section 4.1).
- Outputs are deterministic: sorted keys, stable order, no timestamps in plans.
- Code, identifiers, messages and catalog entries in English. Design docs stay in French.
- `src/peo/gate.py` and `src/peo/context.py` import only json, os, pathlib, fnmatch, tomllib and flow (latency < 100 ms).
- Never commit files from a real project into `tests/fixtures/` except through `tools/anonymize_epure.py`.

## Commands

- `uv run pytest` — tests
- `uv run ruff check .` — lint
- `uv run python docs/design/spec/schemas/check_examples.py docs/design/spec/schemas` — schema examples
