# Implementation Plan: Validateur de schémas sans dépendance

**Branch**: `feat/p1-1-validate` | **Date**: 2026-11-11 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-schema-validator/spec.md`

## Summary

Un module unique, `src/peo/validate.py`, en bibliothèque standard. Il expose `Schema` (seul type de schéma
accepté), `Schema.from_dict`, `load_schema(name)`, `validate(doc, schema)`, `ValidationError(path, code, message)`
et `UnsupportedSchema`. Tout contrôle du sous-ensemble NF2 passe par `Schema.from_dict`, donc à la
construction, avant toute validation d'instance. Le code existant (PR #3) est adapté : ajout du type `Schema`,
du champ `code` et du contrôle préalable ; la logique de validation est conservée.

## Technical Context

**Language/Version**: Python ≥ 3.11

**Primary Dependencies**: aucune à l'exécution (`re`, `json`, `importlib.resources`, `typing`). Dev : pytest, jsonschema (oracle de A2.6), ruff

**Storage**: les 7 schémas livrés dans `src/peo/schemas/*.schema.json` (lecture seule)

**Testing**: pytest, `tests/test_validate.py`, tests nommés `test_a2_6_*`

**Target Platform**: Linux et macOS (NF10)

**Project Type**: bibliothèque interne du paquet `peo`

**Performance Goals**: aucun objectif propre ; hors chemin chaud de `gate`/`context`

**Constraints**: stdlib seule (NF1) ; sorties déterministes (NF8) ; `validate.py` n'est pas importé par `gate.py` ni `context.py`

**Scale/Scope**: 7 schémas, 13 motifs, un module d'environ 150 lignes

## Constitution Check

| Principe | Verdict |
|---|---|
| I. Spécification d'abord | OK. Le contrat est corrigé dans la spec 10 (commit `docs(spec)`) avant le code. |
| II. Tests d'abord | OK. Les tests `test_a2_6_*` évoluent d'abord (rouge), puis le code. |
| III. Stdlib seule | OK. `importlib.resources`, `re`. |
| IV. Déterminisme | OK. Erreurs triées par `(path, code, message)`. |
| V. Sécurité | OK. Pas de sous-processus, pas de réseau ; seule lecture : fichiers de schémas du paquet. |
| VI. Couche mince | OK. Remplace `jsonschema` à l'exécution (NF2) ; aucun outil stdlib équivalent. |
| VII. Langues | OK. Code et messages en anglais, docs en français. |

Re-vérifié après la conception : aucune violation.

## Project Structure

### Documentation (this feature)

```text
specs/001-schema-validator/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/validate-api.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/peo/validate.py      # modifié : Schema, from_dict, load_schema, code d'erreur
tests/test_validate.py   # modifié : test_a2_6_*, Schema.from_dict, load_schema, codes
```

**Structure Decision**: aucun nouveau fichier de code. Les schémas restent copiés dans
`src/peo/schemas/` (test existant `test_package_schemas_are_the_spec_schemas`).

## Complexity Tracking

Aucune violation.
