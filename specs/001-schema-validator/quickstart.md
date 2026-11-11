# Quickstart

```bash
uv run pytest tests/test_validate.py -k a2_6      # A2.6 : parité avec jsonschema
uv run pytest && uv run ruff check .
```

Vérification manuelle :

```python
from peo.validate import load_schema, validate
errors = validate({"schema": "x"}, load_schema("profile"))   # liste d'erreurs avec path et code
```

Attendu : liste non vide pour un document invalide, `[]` pour un fichier de `docs/design/spec/schemas/examples`,
`UnsupportedSchema` pour `Schema.from_dict({"format": "date"})`.
