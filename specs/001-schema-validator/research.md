# Research: Validateur de schémas

Aucun point `NEEDS CLARIFICATION`. Décisions de conception :

- **Contrôle à la construction.** `Schema.from_dict` parcourt tout le schéma (`properties`, `additionalProperties`
  sous-schéma, `items`, `oneOf`, `$defs`) et rejette tout mot-clé hors sous-ensemble ; chaque `$ref` doit
  être de la forme `#/$defs/<nom>` et exister. Rationale : FR-003, un seul chemin de contrôle.
  Alternative écartée : contrôle paresseux pendant la traversée (laisse passer les branches non visitées).
- **`Schema` comme enveloppe immuable** d'un dict déjà contrôlé (`dataclass(frozen=True)`, un champ `root`).
  Alternative écartée : sous-classe de `dict` (n'empêche pas la mutation après contrôle).
- **Chargement via `importlib.resources`** (`files("peo") / "schemas" / f"{name}.schema.json"`). Alternative
  écartée : chemin relatif à `__file__` (fragile hors installation en place).
- **Code d'erreur = mot-clé violé** (clarification Q1). Alternative écartée : liste fermée propre à PEO.
- **`oneOf` sans contrôle de forme** (clarification Q2).
- **Oracle** : `jsonschema.Draft202012Validator` en dépendance de développement seulement.
