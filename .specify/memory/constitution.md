# PEO Constitution

## Core Principles

### I. Specification First (NON-NEGOTIABLE)
`docs/design/spec/` is the source of truth. Any behaviour change MUST update the spec in the
same pull request, before the code. If code and spec disagree, work MUST stop and the user MUST
be asked.

### II. Tests First (NON-NEGOTIABLE)
Every feature starts with failing acceptance tests named after
`docs/design/spec/16-test-plan.md` (A1.x, A2.x…). A pull request MUST NOT be merged with a red
test or an unexplained `xfail`.

### III. Standard Library Only at Runtime
Runtime code targets Python ≥ 3.11 and MUST NOT have any runtime dependency. Dev-only
dependencies are limited to pytest, hypothesis, jsonschema and ruff.

### IV. Determinism
The same inputs MUST produce byte-identical outputs: sorted keys, stable ordering, and no
timestamps in plans.

### V. Safety
- `shell=True` is forbidden; every subprocess MUST go through the injectable command runner.
- The network MUST NOT be used outside adapters, and only after user consent.
- PEO MUST NEVER call `sudo` or a system package manager.
- PEO MUST NEVER write outside managed blocks or owned keys.

### VI. Thin Layer
PEO selects, composes and gates; it delegates installation. It MUST NOT become a package
manager, a methodology or an agent framework. A new feature MUST show that no existing tool
already does it.

### VII. Languages
Code, identifiers, messages and catalog entries are in English. Design docs stay in French.

## Governance

This constitution supersedes other practices. An amendment is a pull request that also updates
the spec. The constitution is versioned semantically: MAJOR for removed or redefined
principles, MINOR for new principles or materially expanded guidance, PATCH for wording. Every
pull request MUST tick its conformance in `.github/pull_request_template.md`.

## Development Workflow

One step of phase P1 is one Spec Kit feature and one pull request.

**Version**: 1.0.0 | **Ratified**: 2026-11-11 | **Last Amended**: 2026-11-11
