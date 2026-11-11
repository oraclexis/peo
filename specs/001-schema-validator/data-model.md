# Data Model

- **Schema** — enveloppe immuable d'un schéma déjà contrôlé. Construit par `Schema.from_dict(d)` ou
  `load_schema(name)`. Contient le dict racine ; la résolution de `$ref` se fait contre lui.
- **ValidationError** — `NamedTuple(path: str, code: str, message: str)`. `path` : JSON Pointer, `""` pour la
  racine, `~` et `/` échappés en `~0` et `~1`. `code` ∈ {`type`, `required`, `enum`, `const`, `pattern`,
  `minimum`, `minItems`, `additionalProperties`, `oneOf`}. Tri : `(path, code, message)`.
- **UnsupportedSchema** — exception levée à la construction d'un `Schema` : mot-clé hors sous-ensemble, `$ref` non
  local ou non résolu, schéma qui n'est pas un objet.

Mots-clés supportés : `type`, `required`, `properties`, `additionalProperties`, `items`, `enum`, `const`,
`pattern`, `minimum`, `minItems`, `$ref`, `$defs`, `oneOf`. Annotations ignorées : `$schema`, `$id`, `title`,
`description`.
