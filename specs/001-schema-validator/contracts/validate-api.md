# Contract: `peo.validate`

```python
class UnsupportedSchema(Exception): ...

class ValidationError(NamedTuple):
    path: str
    code: str
    message: str

class Schema:
    @classmethod
    def from_dict(cls, d: dict) -> "Schema": ...   # raises UnsupportedSchema

def load_schema(name: str) -> Schema: ...          # src/peo/schemas/<name>.schema.json

def validate(doc: Any, schema: Schema) -> list[ValidationError]: ...  # [] = valid, sorted
```

Garanties : `validate` ne lève jamais `UnsupportedSchema` (déjà levée à la construction) ; il n'accepte que
`Schema` ; deux appels sur les mêmes entrées renvoient des listes égales ; le verdict (`== []`) égale celui de
`jsonschema` Draft 2020-12 sur le sous-ensemble.
