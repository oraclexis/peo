# Catalog snapshot

Format: `docs/design/spec/13-catalog-and-selection.md`. Schema: `src/peo/schemas/tool-entry.schema.json`.

- `capabilities.toml`: capability vocabulary (13 section 2).
- `requirements.toml`: derived requirement rules (13 section 6).
- `tools/<kind>/<id>.toml`: the 21 initial entries (13 section 5), one file per entry.

Check it with `uv run peo catalog validate catalog/`. Fields without a source in the design documents
are written `TBD`, never guessed. Moves to its own repository (`peo-catalog`) in phase P7.
