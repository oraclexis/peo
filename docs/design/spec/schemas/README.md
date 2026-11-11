# Schémas JSON de PEO

JSON Schema 2020-12, limité au sous-ensemble que le validateur interne de PEO implémente (document 10, NF2). Les fichiers TOML (`peo.toml`, fiches du catalogue) sont validés après lecture par `tomllib`.

| Schéma | Valide | Écrit par |
|---|---|---|
| [profile.schema.json](profile.schema.json) | `.peo/profile.json` | `peo discover` |
| [peo-config.schema.json](peo-config.schema.json) | `.peo/peo.toml` | `/peo:init`, puis l'humain |
| [tool-entry.schema.json](tool-entry.schema.json) | `tools/<kind>/<id>.toml` du catalogue | mainteneurs du catalogue |
| [selection.schema.json](selection.schema.json) | `data` de `peo select` | Selector |
| [plan.schema.json](plan.schema.json) | `data` de `peo plan` | Planner |
| [lock.schema.json](lock.schema.json) | `.peo/peo.lock.json` | `peo apply` |
| [history-event.schema.json](history-event.schema.json) | chaque ligne de `.peo/history.ndjson` | `peo` |

## Exemples

`examples/` contient les sorties attendues pour la fixture synthétique `fx-split-stack` (document 16, section 2.1), dont les traits reprennent les mesures du pilote n°1 (document 09) sans aucun texte réel. Elles servent de première version des fichiers attendus de `fx-split-stack` et seront régénérées sur la fixture puis relues.

Conventions des exemples :

- `TBD` : valeur non vérifiée à ce stade (version d'Intelephense, licence du plugin `php-lsp`, commit du catalogue). Aucune valeur n'a été inventée.
- Les empreintes `sha256` sont au bon format mais **factices** (dérivées d'un libellé), sauf `plan_id` qui est réellement calculé sur les actions de l'exemple selon la règle du document 14 (section 2.2).
- `plan.split-stack.json` est un **extrait** de 13 actions représentatives (toutes les classes de risque, tous les groupes sauf `mcp`).

`invalid/` contient des contre-exemples qui doivent être rejetés : fiche sans `surface`, fiche sans `review_by`, `runtime` invalide, possession incomplète, autonomie `autonomous` (interdite au MVP, H12).

## Vérification

```bash
python3 check_examples.py .     # nécessite jsonschema (dépendance de développement uniquement)
```

Résultat au 2026-11-11 : 8 exemples valides, 5 contre-exemples rejetés pour la raison attendue. Contrôles croisés effectués en plus : chacune des 19 fiches apparaît exactement une fois dans la sélection de `fx-split-stack` ; chaque exigence est couverte par un outil retenu ou réutilisé ; `cost_total` égale la somme des coûts.
