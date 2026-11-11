# Dogfooding log

PEO is developed with the workflow it will install (Spec Kit + EGM + Matt Pocock skills), installed by hand.
Write down every friction here: date, step, what happened, what PEO should do about it. This feeds the catalog and the spec.

| Date | Step | Friction | Consequence for PEO |
|---|---|---|---|
| 2026-11-11 | P1.1 `/speckit-plan` | `setup-plan.sh` names the branch after the feature directory (`001-schema-validator`), not the real branch (`feat/p1-1-validate`). | Do not rely on the branch name to locate the feature; read `.specify/feature.json`. |
| 2026-11-11 | P1.1 merge | `main` requires a review; the author cannot approve their own PR. | `peo` must not assume it can merge; the P1 flow ends at "PR ready". |

## Technical debt

Debt noted on P1.1 (`src/peo/validate.py`), to settle before or with the first change that touches the module:

- **`_check` is a long keyword chain.** Adding a keyword means editing `_SUPPORTED`, `_verify` and `_check`. Replace it with a keyword-to-handler table.
- **`Schema` immutability is shallow.** `Schema` is frozen but `root` is a mutable dict, so mutating it after construction bypasses the subset check. Deep-freeze or copy `root`.
- **`$ref` pointers do not decode `~0` / `~1`.** `#/$defs/a~1b` is rejected as unresolved. Decode the escapes if a schema needs a `/` in a definition name.
- **`additionalProperties` errors use the child path.** The error is reported at `/obj/key`, not at `/obj` as `jsonschema` does. Harmless for verdicts (A2.6); decide before `catalog validate` prints paths.
