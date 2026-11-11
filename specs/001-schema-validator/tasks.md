# Tasks: Validateur de schémas sans dépendance

**Input**: `specs/001-schema-validator/` (plan.md, spec.md, data-model.md, contracts/validate-api.md, research.md)

**Tests**: obligatoires (constitution II) : chaque tâche de test précède son implémentation et doit échouer d'abord. Tous les tests sont dans `tests/test_validate.py`, nommés `test_a2_6_*` ; le code est dans `src/peo/validate.py`. Les tâches touchent les mêmes deux fichiers : aucune n'est parallélisable.

## Phase 1: Setup

- [X] T001 Vérifier la base verte : `uv run pytest -q`, `uv run ruff check .` et `uv run python docs/design/spec/schemas/check_examples.py docs/design/spec/schemas`

## Phase 2: Foundational (bloque toutes les histoires)

- [X] T002 Écrire dans `tests/test_validate.py` les tests rouges `test_a2_6_schema_type` : `Schema` est immuable, `Schema.from_dict({"type": "null"})` renvoie un `Schema`, `load_schema("profile")` renvoie un `Schema`, `load_schema("nope")` lève `FileNotFoundError`, et `validate("x", {"type": "string"})` (dict brut) lève `TypeError`
- [X] T003 Dans `src/peo/validate.py`, ajouter `Schema` (`dataclass(frozen=True)`, champ `root`), `Schema.from_dict` (pour l'instant : refuse un non-objet avec `UnsupportedSchema`), `load_schema(name)` via `importlib.resources.files("peo") / "schemas" / f"{name}.schema.json"` et le refus de tout type autre que `Schema` dans `validate`
- [X] T004 Dans `tests/test_validate.py`, remplacer les appels `validate(x, dict)` par `validate(x, Schema.from_dict(dict))` (tests par mot-clé) et `schema_for` par `load_schema` (fichiers de la spec)

**Checkpoint**: la suite existante est verte avec le nouveau type.

## Phase 3: User Story 1 — Valider un document PEO sans dépendance (P1) 🎯 MVP

**Goal**: même verdict que `jsonschema` sur tous les fichiers de `examples/`, `invalid/` et sur les fichiers golden.

**Independent Test**: `uv run pytest tests/test_validate.py -k a2_6_same_verdict`

- [X] T005 [US1] Dans `tests/test_validate.py`, faire pointer `test_a2_6_same_verdict_as_jsonschema_on_spec_files` sur `load_schema(...)` (schémas livrés dans `src/peo/schemas/`) en conservant la comparaison avec `Draft202012Validator` ; vérifier qu'il passe (la logique de `validate` est déjà en place)
- [X] T006 [US1] Dans `tests/test_validate.py`, garder `test_a2_6_same_verdict_as_jsonschema_per_keyword` : au moins un cas valide et un cas invalide pour chacun des 12 mots-clés (SC-004), dont `additionalProperties` en sous-schéma et `$ref` imbriqué

**Checkpoint**: US1 livrée, A2.6 vert.

## Phase 4: User Story 2 — Localiser et identifier chaque erreur (P2)

**Goal**: chaque erreur porte un chemin JSON Pointer et un code stable égal au mot-clé violé, triées par `(path, code, message)`.

**Independent Test**: `uv run pytest tests/test_validate.py -k a2_6_errors`

- [X] T007 [US2] Écrire dans `tests/test_validate.py` les tests rouges `test_a2_6_errors_have_keyword_codes` : un cas par code (`type`, `required`, `enum`, `const`, `pattern`, `minimum`, `minItems`, `additionalProperties`, `oneOf`), l'échappement `~0`/`~1` dans les chemins, et deux validations successives identiques (SC-003)
- [X] T008 [US2] Dans `src/peo/validate.py`, passer `ValidationError` à `NamedTuple(path, code, message)` ; chaque `err(...)` reçoit son code ; le tri se fait sur `(path, code, message)` ; adapter `test_a2_6_errors_are_json_pointers_sorted_and_complete`

**Checkpoint**: US1 et US2 vertes.

## Phase 5: User Story 3 — Refuser un schéma hors sous-ensemble (P3)

**Goal**: tout mot-clé hors sous-ensemble ou `$ref` non local ou non résolu lève `UnsupportedSchema` à la construction du `Schema`, y compris dans une branche jamais visitée.

**Independent Test**: `uv run pytest tests/test_validate.py -k a2_6_unsupported`

- [X] T009 [US3] Écrire dans `tests/test_validate.py` les tests rouges `test_a2_6_unsupported_at_construction` : `format`, `allOf`, `$ref` HTTP, `$ref` vers un `$defs` absent ; mot-clé interdit imbriqué dans `properties`, `items`, `oneOf`, `additionalProperties` sous-schéma et `$defs` ; schéma non objet ; annotations `$schema`, `$id`, `title`, `description` acceptées ; tous les schémas de `src/peo/schemas/` se chargent
- [X] T010 [US3] Dans `src/peo/validate.py`, faire parcourir à `Schema.from_dict` tout le schéma (`properties`, `additionalProperties`, `items`, `oneOf`, `$defs`) ; mots-clés autorisés = `type required properties additionalProperties items enum const pattern minimum minItems $ref oneOf` + annotations ; `$ref` de la forme `#/$defs/<nom>` et présent dans `$defs` du schéma racine ; retirer les contrôles paresseux de `_check` devenus inutiles

**Checkpoint**: les trois histoires sont vertes.

## Phase 6: Polish

- [X] T011 Exécuter `uv run pytest -q`, `uv run ruff check .` et `uv run python docs/design/spec/schemas/check_examples.py docs/design/spec/schemas` ; exécuter le scénario de `specs/001-schema-validator/quickstart.md`
- [X] T012 Pousser la branche `feat/p1-1-validate` et mettre à jour la description de la PR #3 (cocher la conformité de `.github/pull_request_template.md`)

## Dépendances

T001 → T002 → T003 → T004 → US1 (T005, T006) → US2 (T007 → T008) → US3 (T009 → T010) → T011 → T012. US2 et US3 sont indépendantes l'une de l'autre après la Phase 2, mais touchent les mêmes fichiers : exécution séquentielle.

## Stratégie

MVP = Phase 2 + US1 (parité A2.6 avec le nouveau type). Ensuite US2 puis US3, une tâche de test rouge avant chaque tâche de code.
