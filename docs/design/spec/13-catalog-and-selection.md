# 13 — Catalogue, questionnaire et sélection (F2, F4, F5)

## 1. Dépôt du catalogue

```text
peo-catalog/
├── capabilities.toml        # vocabulaire fermé
├── requirements.toml        # règles qui dérivent les exigences du profil
├── questions.toml           # banque de questions
├── backbones/*.toml
├── recipes/*.toml
├── tools/<kind>/<id>.toml   # une fiche par outil
└── CHANGELOG.md             # une entrée par fiche ajoutée, modifiée, expirée
```

Versionné par tags `vAAAA.MM[.n]`. Une fiche modifiée par un commit doit mettre à jour `notes.evaluated`. La CI du catalogue lance `peo catalog validate`.

## 2. Vocabulaire de capacités du MVP

| Capacité | Exclusive | Origine habituelle de l'exigence |
|---|---|---|
| `clarify.interview` | oui | socle (dure) |
| `spec.authoring` | oui | socle (dure) |
| `spec.review.independent` | non | socle (dure) |
| `plan.tasks` | oui | socle (dure) |
| `tdd.discipline` | oui | socle (dure) |
| `review.code` | oui | socle (dure) |
| `debug.diagnosis` | oui | socle (dure), recette `bugfix` |
| `drift.docs` | non | socle (dure) |
| `process.gates` | oui | toujours (dure), fournie par PEO lui-même |
| `nav.lsp.typescript`, `nav.lsp.php`, `nav.lsp.python` | non | langage d'un composant (souple, S-6) |
| `nav.symbols` | non | taille du code ou refonte prévue (souple) |
| `nav.graph` | non | taille du code (souple) |
| `review.security.sast` | non | signaux `auth` ou `public_surface` (souple) |
| `review.security.guidance` | oui | sensibilité déclarée et authentification présente (souple) |
| `browser.e2e` | oui | composant front (souple) |
| `ui.design` | oui | `frontend_heavy` sans règles de design imposées (souple) |
| `docs.libraries` | non | réponse explicite seulement (souple) |
| `knowledge.lessons` | oui | fourni par les socles alternatifs seulement |
| `re.artifact` | non | réponse explicite seulement (souple) |
| `exposure.native` | non | fichier de secrets présent (dure) ; dump ou dossier de logs présent (souple). Fournie par PEO lui-même. Ajout du 2026-11-12 |
| `secrets.scan.ci` | non | toujours (souple). Ajout du 2026-11-12 |
| `privacy.masking` | **oui** | aucune règle tant qu'aucune fiche ne la fournit (spike S5, H22). Ajout du 2026-11-12 |

Ajouter une capacité est un changement du catalogue relu comme une fiche.

`orchestration.harness` (exclusive, H25) et `secrets.scan.commit` seront ajoutées avec leur première fiche.

## 3. Langage `when`

Les conditions des fiches, des exigences et des questions sont des **expressions** évaluées par `expr.py`, sans `eval`.

```text
expr    := or
or      := and ("or" and)*
and     := unary ("and" unary)*
unary   := "not" unary | cmp
cmp     := operand (op operand)?
op      := "==" | "!=" | ">" | ">=" | "<" | "<=" | "in" | "contains" | "matches"
operand := path | string | number | "true" | "false" | "null" | list | "(" expr ")"
path    := ("profile" | "answers" | "selection") ("." ident | "[" string "]")*
         | "any" "(" path "," expr ")"           # quantificateur sur une liste, élément nommé « it »
list    := "[" (operand ("," operand)*)? "]"
```

Règles :

- Un chemin absent vaut `null`. `null` comparé par `>`, `<`… est faux, jamais une erreur.
- `matches` : expression régulière Python, ancrée, compilée une fois, 200 caractères au plus.
- Les champs `confidence` sont accessibles : `profile.signals.auth.confidence == 'fact'`.
- Une expression invalide rend la **fiche invalide** au chargement (`catalog validate`), jamais à l'exécution.

Exemples :

```text
profile.metrics.loc_total > 50000 or answers['q.refactoring'] == true
any(profile.components, 'php' in it.languages)
not profile.signals.design_rules_in_instructions.value
profile.sensitive.secret_files != []
```

## 4. Fiche d'outil

Schéma : [schemas/tool-entry.schema.json](schemas/tool-entry.schema.json). Le document 06 (section 3) reste la référence de structure ; la spécification ajoute quatre sections, issues du pilote.

| Section | Champs | Rôle | Écart |
|---|---|---|---|
| `[selection]` | `when.any`, `when.all`, `when.not`, `score` | `any` : au moins une vraie ; `all` : toutes vraies ; `not` : contre-indications, aucune ne doit être vraie. Absence de `when` = toujours candidat si une capacité fournie est requise | Confirmation du pilote (UI UX Pro Max) |
| `[[prerequisites]]` | `check`, `fix`, `hint`, `blocking` | Ce qui doit être vrai pour que l'outil fonctionne : `bin:<nom>` (sur le poste), `path:<chemin>` (avec `{component:<id>}`), `runtime:host` (le composant visé tourne sur le poste). `fix` : référence d'une autre fiche du catalogue qui satisfait le prérequis (ex. `cli:intelephense`) ; `hint` : étape manuelle affichée | **E5** |
| `[detect]` | `npm`, `composer`, `pip`, `bin`, `plugin`, `mcp`, `files` | Reconnaître l'outil **déjà présent** sous une autre forme (dépendance de dev, binaire, plugin installé à la main) | **E6** |
| `[conventions]` | `branch.final_segment`, `branch.configurable`, `specs_dir` | Conventions imposées par un framework et ce qui en est configurable | **E3** |
| `[surface]` (ajout du 2026-11-12) | `data_path` (`none`, `reads-sensitive`, `rewrites-io`), `fail_mode` (`open`, `closed`), **obligatoires** | `reads-sensitive` : lit des données hors du code (base, navigateur, e-mails). `rewrites-io` : réécrit les entrées ou sorties d'outils de l'agent. `fail_mode` : comportement de la session quand l'outil est absent ou en panne (`closed` bloque, `open` laisse passer ; `open` pour un outil sans hook) | Document 05, section 8.1 |
| `[canary]` (ajout du 2026-11-12) | `command` (liste d'arguments, `{dir}` remplacé par le dossier du canari), `detected_exit` | Commande qui doit détecter le canari (spec 15, section 7.2). Optionnelle | Document 17, section 6.4 |

Exemple de prérequis (`tools/claude-plugin/php-lsp.toml`, extrait) :

```toml
[[prerequisites]]
check    = "bin:intelephense"
fix      = "cli:intelephense"              # fiche du catalogue (kind = "cli", manager npm) : action R3
blocking = true

[[prerequisites]]
check    = "path:{component:php}/vendor"   # premier composant PHP
hint     = "Install PHP dependencies so Intelephense can index the framework: {runtime_prefix}composer install"
blocking = false                           # l'outil marche, avec une navigation incomplète
```

`{runtime_prefix}` vaut `docker compose exec <service> ` quand le composant a `runtime = docker:<service>`, sinon une chaîne vide.

Exemple de détection (`tools/cli/playwright.toml`, extrait) :

```toml
[detect]
npm = ["@playwright/test", "playwright"]
bin = ["playwright"]

[selection]
reuse_only = true    # PEO reconnaît et réutilise, n'installe jamais cet outil au MVP
```

## 5. Catalogue initial (21 fiches)

| Référence | Statut | Fournit | Condition résumée | Installé par PEO au MVP |
|---|---|---|---|---|
| `framework:spec-kit` | core | `spec.authoring`, `plan.tasks` | socle par défaut | oui (`specify init`) |
| `cli:specify-cli` | core | — (prérequis de Spec Kit) | requis par `framework:spec-kit` | oui (`uv tool install`) |
| `claude-plugin:egm` | core | `spec.review.independent`, `drift.docs` | socle par défaut | oui |
| `claude-plugin:mattpocock-skills` | core | `clarify.interview`, `tdd.discipline`, `review.code`, `debug.diagnosis` | socle par défaut | oui |
| `peo:gates` | core | `process.gates` | toujours | oui (hooks du projet) |
| `peo:native-controls` | core | `exposure.native` | exigence présente (fichier de secrets, dump ou logs) | oui : règles `permissions.deny` ; sandbox recommandé seulement (S-9). Ajout du 2026-11-12 |
| `ci-check:gitleaks` | conditional | `secrets.scan.ci` | toujours candidat | oui (bloc CI, valeurs masquées dans les journaux de CI avec `--redact`). `[canary]` : `gitleaks dir {dir}`, détecté = code 1 [À VÉRIFIER sur la version épinglée à l'écriture de la fiche]. Ajout du 2026-11-12 |
| `claude-plugin:typescript-lsp` | conditional | `nav.lsp.typescript` | composant TypeScript ou Vue | oui |
| `claude-plugin:php-lsp` | conditional | `nav.lsp.php` | composant PHP | oui, avec prérequis |
| `cli:intelephense` | conditional | — (prérequis de `php-lsp`) | requis par `php-lsp` | oui (`npm install -g`, R3) |
| `claude-plugin:pyright-lsp` | conditional | `nav.lsp.python` | composant Python | oui |
| `mcp:serena` | conditional | `nav.symbols` | `loc_total > 50000` ou refonte prévue ; pas sur un projet neuf | oui |
| `cli:graphify` | conditional | `nav.graph` | `loc_total > 100000` | oui |
| `ci-check:semgrep` | conditional | `review.security.sast` | signal `auth` ou `public_surface` | oui (bloc CI) |
| `claude-plugin:security-guidance` | conditional | `review.security.guidance` | sensibilité déclarée **et** `auth` en `fact` | oui |
| `vendored-skill:ui-ux-pro-max` | conditional | `ui.design` | `frontend_heavy`, **sauf** `design_rules_in_instructions` | non au MVP (type `vendored-skill` hors MVP) : proposé en étape manuelle |
| `cli:playwright` | reuse | `browser.e2e` | détecté seulement | non (réutilisation) |
| `claude-plugin:context7` | optional | `docs.libraries` | réponse explicite | oui |
| `claude-plugin:superpowers` | backbone-alt | socle complet | détecté seulement | non : détecté pour signaler le conflit |
| `claude-plugin:compound-engineering` | backbone-alt | socle complet + `knowledge.lessons` | détecté seulement | non : idem |
| `claude-plugin:everything-claude-code` | watch | socle complet | détecté seulement | non : idem |

Les versions testées et les sources sont celles du document 03 ; chaque fiche porte `review_by` à trois mois.

## 6. Exigences dérivées (`requirements.toml`)

```toml
[[rules]]
id = "lsp-per-language"
for_each = "profile.components"
when = "'php' in it.languages"
require = { capability = "nav.lsp.php", strength = "soft" }
# règles identiques pour typescript et python

[[rules]]
id = "sast-when-exposed"
when = "profile.signals.auth.value == true or profile.signals.public_surface.value == true"
require = { capability = "review.security.sast", strength = "soft" }

[[rules]]
id = "e2e-for-frontends"
when = "any(profile.components, it.kind == 'frontend')"
require = { capability = "browser.e2e", strength = "soft" }

[[rules]]
id = "symbols-for-large-code"
when = "profile.metrics.loc_total > 50000 or answers['q.refactoring'] == true"
require = { capability = "nav.symbols", strength = "soft" }

# Ajouts du 2026-11-12 (H21)
[[rules]]
id = "native-controls-for-secrets"
when = "profile.sensitive.secret_files != []"
require = { capability = "exposure.native", strength = "hard" }

[[rules]]
id = "native-controls-for-data"
when = "profile.sensitive.data_dumps != [] or profile.sensitive.log_dirs != []"
require = { capability = "exposure.native", strength = "soft" }

[[rules]]
id = "secret-scan-ci"
require = { capability = "secrets.scan.ci", strength = "soft" }
```

Une règle sans `when` s'applique toujours. Deux règles qui exigent la même capacité donnent une seule exigence, de la force la plus élevée.

Exigences **dures** : celles du socle, `process.gates` et `exposure.native` quand un fichier de secrets existe. Toutes les autres sont souples.

## 7. Questionnaire (F4)

### 7.1 Format de la banque

```toml
[[questions]]
id      = "q.verify_cmd"
round   = 2
kind    = "choice"                       # confirm | choice | text
feeds   = ["commands.verify"]            # champs alimentés (peo.toml ou answers)
ask_if  = "profile.commands.verify.confidence == 'unknown'"
text    = "There is no single verification command. Which one should gates run?"
[[questions.options]]
value = "make-verify"
label = "Create a 'verify' target"
detail = "Aggregates: {commands_to_aggregate}"
recommend_if = "true"
[[questions.options]]
value = "none"
label = "None for now"
detail = "Gate G5 will be skipped until a command exists"
```

Règles de validation (`catalog validate`) :

1. Chaque champ de `feeds` doit être lu par au moins une expression du catalogue, une recette ou un champ de `peo.toml` consommé par le CLI (décision S-5). Sinon la question est rejetée.
2. Au plus 4 options ; la recommandée en premier à l'affichage.
3. Les textes sont en anglais dans le catalogue ; la skill les reformule dans la langue de l'utilisateur.

### 7.2 Questions du MVP

| Id | Tour | Posée si | Alimente |
|---|---|---|---|
| `q.confirm_profile` | 1 | toujours, si au moins un `likely` influence la sélection | confirmation des hypothèses |
| `q.backbone_conflict` | 1 | un socle alternatif est détecté (installé ou activé) | `backbone.id` ou abandon |
| `q.docs_drift` | 1 | au moins un constat de dérive (questions regroupées en une seule) | actions de correction dans le plan |
| `q.mission` | 2 | toujours (texte libre ; recommandation tirée du premier paragraphe du README) | `project.mission`, doc générée |
| `q.verify_cmd` | 2 | `commands.verify` inconnu | `commands.verify`, porte G5 |
| `q.ci` | 2 | une fiche `ci-check` est retenue **et** lacune `no-ci` | cible CI |
| `q.gate_mode` | 2 | toujours (recommandation `ask`) | `gates.mode` |
| `q.sensitivity` | 3 | `signals.auth` est `likely` ou `unknown` et une fiche en dépend | `answers['q.sensitivity']` |
| `q.branch_convention` | 3 | `conventions.branches.id_style == 'alnum-id'` | configuration de Spec Kit (document 14, section 5.3) |
| `q.claude_md` | 3 | `docs.claude_md == 'rich'` et plus de 200 lignes | conserver ou migrer (S-3) |
| `q.artifacts_language` | 3 | langue des commits `unknown` | `project.languages.artifacts` |
| `q.refactoring` | 3 | `loc_total` entre 20 000 et 50 000 | exigence `nav.symbols` |

**Retirée par rapport au document 07** : la question « équipe ». Aucun champ ne la consomme au MVP (règle 1). Elle reviendra avec une fonction qui en dépend.

### 7.3 Ordre et plafonds

- Tours dans l'ordre ; dans un tour, ordre de la banque ; au plus 4 questions par tour (contrainte d'`AskUserQuestion`) ; débordement reporté au tour suivant.
- Au plus 4 tours. Au-delà, les questions restantes prennent leur valeur recommandée et le plan le signale.
- Mode reconfiguration (`/peo:init` sur un projet déjà initialisé) : les réponses de `[answers]` sont pré-remplies ; seules les questions dont l'entrée a changé (profil différent) sont reposées.

## 8. Selector (F5)

### 8.1 Entrées et étapes

```text
1. socle    = backbone de peo.toml, sinon socle par défaut du catalogue
              si un socle alternatif est détecté : erreur E_BACKBONE_CONFLICT (code 6),
              sauf réponse à q.backbone_conflict
2. requis   = capacités du socle (dures) ∪ process.gates (dure) ∪ règles de requirements.toml
3. présents = outils reconnus par [detect] dans l'inventaire (E6) → capacités couvertes à coût 0
4. candidats = fiches t telles que
               t.status ∉ {rejected, watch, backbone-alt}
               t fournit au moins une capacité requise et non couverte par « présents »
               when(t) vrai
              chaque candidat écarté reçoit un code (8.3)
5. prérequis : pour chaque candidat, chaque prérequis bloquant non satisfait
               sans `fix` → écarté (PREREQ_UNMET) ; avec `fix` → action ajoutée au plan
6. recherche exhaustive (8.2) sur les candidats restants
7. justification et capacités non couvertes
```

### 8.2 Recherche

Coût d'un outil :

```text
coût(t) = 1
        + ceil(t.cost.context_static_tokens / 500)
        + 3 × len(t.surface.hooks)
        + 2 × (t.surface.network == "runtime")
        + 1 par prérequis avec `fix`
```

On cherche S ⊆ candidats qui minimise, **dans cet ordre lexicographique** :

1. le nombre d'exigences dures non couvertes ;
2. le nombre d'exigences souples non couvertes ;
3. Σ coût(t) ;
4. |S| ;
5. la liste triée des identifiants de S (pour départager de façon stable).

Sous contraintes : pas de paire en `conflicts` ; pour chaque capacité exclusive, au plus un fournisseur dans S ∪ présents ; `requires` de chaque outil inclus dans S ∪ présents.

Algorithme : séparation et évaluation, en essayant d'abord les outils qui couvrent le plus d'exigences non couvertes. Au-delà de **24 candidats**, erreur `E_TOO_MANY_CANDIDATES` : c'est un défaut de catalogue (conditions trop larges), pas un cas à optimiser.

Un outil qui fournit une capacité exclusive déjà couverte par un outil **présent** est écarté (`REDUNDANT`), même si sa condition est vraie : on réutilise l'existant.

### 8.3 Codes de justification

| Code | Sens | Exemple `fx-split-stack` |
|---|---|---|
| `SELECTED` | Retenu ; liste des capacités couvertes et de la règle qui l'a rendu candidat | `claude-plugin:php-lsp` couvre `nav.lsp.php` (règle `lsp-per-language`, composant `backend`) |
| `REUSED` | Outil présent qui couvre une capacité requise | `cli:playwright` (`@playwright/test` en dépendance de dev) couvre `browser.e2e` |
| `CONDITION_FALSE` | `when` faux ; l'expression fautive est citée | `mcp:serena` : `profile.metrics.loc_total > 50000` faux (4 717) |
| `CONTRAINDICATED` | Une expression de `when.not` est vraie | `vendored-skill:ui-ux-pro-max` : règles de design dans `CLAUDE.md` |
| `NOT_REQUIRED` | Aucune capacité fournie n'est requise | `claude-plugin:context7` |
| `REDUNDANT` | Capacité exclusive déjà fournie | — |
| `CONFLICT` | En conflit avec un outil retenu ou présent ; l'outil est cité | — |
| `COST` | Couverture identique à moindre coût par un autre ensemble | — |
| `PREREQ_UNMET` | Prérequis bloquant sans correction possible | — |
| `BACKBONE_EXCLUSIVE` | Socle alternatif | `claude-plugin:superpowers` |
| `STATUS` | Fiche `rejected` ou `watch` | `claude-plugin:everything-claude-code` |

### 8.4 Sortie

Schéma : [schemas/selection.schema.json](schemas/selection.schema.json). Exemple attendu pour `fx-split-stack` : [schemas/examples/selection.split-stack.json](schemas/examples/selection.split-stack.json).

### 8.5 Propriétés testées

| Propriété | Énoncé |
|---|---|
| Déterminisme | Même catalogue, profil, réponses et inventaire ⇒ sortie identique octet pour octet |
| Absence de conflit | Aucune paire de S en `conflicts` ; aucune capacité exclusive fournie deux fois dans S ∪ présents |
| Couverture | Toute exigence dure est couverte, ou la sortie a `ok = false` et la cite |
| Minimalité | Retirer un outil quelconque de S fait perdre une exigence couverte |
| Traçabilité | Chaque fiche applicable du catalogue apparaît exactement une fois, dans `selected`, `reused` ou `rejected` |
| Stabilité | Ajouter au catalogue une fiche dont `when` est faux ne change pas S |
