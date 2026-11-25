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

**Lecture d'un catalogue** (précisé le 2026-11-18, R4a) : chaque fichier est lu en octets, 1 Mio au plus, en UTF-8 strict ; un lien symbolique est ignoré, avec l'avertissement `W_SYMLINK_IGNORED` (précisé le 2026-11-21) ; un caractère de contrôle bidirectionnel Unicode (U+061C, U+200E, U+200F, U+202A à U+202E, U+2066 à U+2069 : la propriété `Bidi_Control`) rejette le fichier. `backbones/*.toml` et `recipes/*.toml` n'ont pas de format défini avant R6 : ils sont lus comme des tables dont seule la syntaxe est vérifiée, et toute valeur chaîne (ou liste de chaînes) d'une clé nommée `when`, `ask_if`, `recommend_if` ou `for_each`, à toute profondeur, est une expression analysée comme les autres et compte parmi les consommateurs de la règle S-5 (section 7.1). Un `review_by` antérieur à la date du jour est un avertissement, jamais une erreur.

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

- `it` n'existe que dans le second argument de `any(...)` et, au niveau racine, dans le `when` d'une règle qui a `for_each` (§6), où il nomme l'élément courant (précisé le 2026-11-20, R4a). Ailleurs, c'est une erreur d'analyse.
- Un chemin absent vaut `null`. `null` comparé par `>`, `<`… est faux, jamais une erreur.
- `matches` : expression régulière Python, 200 caractères au plus, compilée une fois, appliquée par `fullmatch` (ancrée aux deux bouts) à une chaîne de 512 caractères au plus (au-delà, la comparaison est fausse). Pour éviter le retour arrière exponentiel d'un motif venu d'un catalogue (précisé le 2026-11-23, R4b), le motif est refusé à l'analyse s'il contient une rétro-référence ou une assertion (avant ou arrière), une répétition large (`*`, `+`, `{n,}` ou plus de 8 occurrences) qui contient une autre répétition de plus d'une occurrence ou une alternative `|`, ou plus de deux répétitions larges, une répétition (de plus d'une occurrence) d'une partie qui peut ne rien reconnaître (`(a?){20}`), plus de 8 répétitions ou de 4 alternatives en tout (précisé le 2026-11-24, revue de code de R4b). Un motif dont le nombre de répétitions dépasse les limites de `re` est une erreur d'analyse, pas un plantage.
- `selection` (précisé le 2026-11-23, R4b) : seuls `selection.selected` (liste des références retenues) et `selection.covered` (liste des capacités couvertes) sont définis ; tout autre chemin de cette racine vaut `null`.
- Une comparaison entre types différents est fausse (sauf `==` et `!=`, qui comparent les valeurs) ; `in` teste l'appartenance à une liste ou à une chaîne, `contains` est son inverse ; `any` sur une valeur qui n'est pas une liste est faux. L'évaluation ne lève jamais d'erreur.
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
| `[detect]` | `npm`, `composer`, `pip`, `bin`, `plugin`, `mcp`, `files` | Reconnaître l'outil **déjà présent** sous une autre forme (dépendance de dev, binaire, plugin installé à la main). En R4, un champ `ci` (jetons de la spec 15 §7.1 bis) viendra de `discovery/detect.toml`, où il vit en R3. `mcp` (révisé le 2026-11-14, R2) est un tableau d'objets `{kind = "package" \| "host" \| "command", value = "…"}`, comparés à la projection en mémoire d'un serveur MCP (paquet, hôte, nom de commande ; spec 14 §3.3) par la fonction `identify` que l'appelant (R3, R4, R5) passe à l'Inventory ; exemple : `mcp = [{ kind = "command", value = "serena" }]` | **E6** |
| `[conventions]` | `branch.final_segment`, `branch.configurable`, `specs_dir` | Conventions imposées par un framework et ce qui en est configurable | **E3** |
| `[surface]` (ajout du 2026-11-12) | `data_path` (`none`, `reads-sensitive`, `rewrites-io`), `fail_mode` (`open`, `closed`), **obligatoires** | `reads-sensitive` : lit des données hors du code (base, navigateur, e-mails). `rewrites-io` : réécrit les entrées ou sorties d'outils de l'agent. `fail_mode` : comportement de la session quand l'outil est absent ou en panne (`closed` bloque, `open` laisse passer ; `open` pour un outil sans hook) | Document 05, section 8.1 |
| `[canary]` (ajout du 2026-11-12) | `command` (liste d'arguments, `{dir}` remplacé par le dossier du canari), `detected_exit` | Commande qui doit détecter le canari (spec 15, section 7.2). Optionnelle | Document 17, section 6.4 |

Exemple de prérequis (`tools/claude-plugin/php-lsp.toml`, extrait) :

```toml
[[prerequisites]]
check    = "bin:intelephense"
fix      = "cli:intelephense"              # fiche du catalogue (kind = "cli", manager npm) : action de classe de risque R3
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

**Catalogue en R3** (R3, S-14) : R3 ne charge **aucune fiche**. Le chargeur de catalogue, `peo:native-controls` et `ci-check:semgrep` arrivent en R4, avec le Selector : aucun constat de R3 ne lit une fiche, et les codes qui en ont besoin (`S-HOOK-UNDECLARED`, `X-MASKING-DUPLICATE`, `X-HOOK-FAIL-OPEN`) passent en R4 (spec 15). Les jetons de `X-NO-SECRET-SCAN` vivent dans `discovery/detect.toml` (champ `ci`, spec 12 §7 ter), qui reste la source des détections de Discovery jusqu'en R4, comme `discovery/intents.toml` (spec 12, sections 5 et 7 ter). `tool-entry.schema.json` n'est pas modifié en R3.

| Référence | Statut | Fournit | Condition résumée | Installé par PEO au MVP |
|---|---|---|---|---|
| `framework:spec-kit` | core | `spec.authoring`, `plan.tasks` | socle par défaut | oui (`specify init`) |
| `cli:specify-cli` | core | — (prérequis de Spec Kit) | requis par `framework:spec-kit` | oui (`uv tool install`) |
| `claude-plugin:egm` | core | `spec.review.independent`, `drift.docs` | socle par défaut | oui |
| `claude-plugin:mattpocock-skills` | core | `clarify.interview`, `tdd.discipline`, `review.code`, `debug.diagnosis` | socle par défaut | oui |
| `peo:gates` | core | `process.gates` | toujours | oui (hooks du projet) |
| `peo:native-controls` | core | `exposure.native` | exigence présente (fichier de secrets, dump ou logs) | oui : règles `permissions.deny` ; sandbox recommandé seulement (S-9). Ajout du 2026-11-12 |
| `ci-check:gitleaks` | conditional | `secrets.scan.ci` | toujours candidat | oui (bloc CI, valeurs masquées dans les journaux de CI avec `--redact`). Jetons `ci = ["gitleaks", "Secret-Detection"]` dans `discovery/detect.toml` en R3 (spec 12 §7 ter). `[canary]` (R4.1) : `gitleaks dir {dir}`, détecté = code 1 [À VÉRIFIER sur la version épinglée à l'écriture de la fiche]. Ajout du 2026-11-12 |
| `claude-plugin:typescript-lsp` | conditional | `nav.lsp.typescript` | composant TypeScript ou Vue | oui |
| `claude-plugin:php-lsp` | conditional | `nav.lsp.php` | composant PHP | oui, avec prérequis |
| `cli:intelephense` | conditional | — (prérequis de `php-lsp`) | requis par `php-lsp` | oui (`npm install -g`, classe de risque R3) |
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
id = "lsp-php"                      # un identifiant par langage (précisé le 2026-11-23, R4b)
for_each = "profile.components"
when = "'php' in it.languages"
require = { capability = "nav.lsp.php", strength = "soft" }
# `lsp-typescript` et `lsp-python` : règles identiques

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

1. Chaque champ de `feeds` doit être lu par au moins une expression du catalogue, une recette ou un champ de `peo.toml` consommé par le CLI (décision S-5). Sinon la question est rejetée. Champs de `peo.toml` consommés par le CLI (précisé le 2026-11-18, R4a) : `project.mission`, `project.languages.artifacts`, `commands.verify`, `gates.mode`, `backbone.id` ; un champ de `answers` est consommé si une expression lit `answers['<id>']`. Ajouter un champ à cette liste est une modification de cette section.
2. Au plus 4 options ; la recommandée en premier à l'affichage.
3. Les textes sont en anglais dans le catalogue ; la skill les reformule dans la langue de l'utilisateur.

### 7.2 Questions du MVP

| Id | Tour | Posée si | Alimente |
|---|---|---|---|
| `q.confirm_profile` | 1 | toujours, si au moins un `likely` influence la sélection | confirmation des hypothèses |
| `q.backbone_conflict` | 1 | un socle alternatif figure dans les déclarations suivies du projet (spec 14 §3.4 ; H27, révisé le 2026-11-14). Actif ailleurs (vue observée), il n'est pas vu par le Selector : c'est le Planner qui arrête le plan (spec 14 §2.4) | `backbone.id` ou abandon |
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
              si un socle alternatif figure dans les déclarations suivies du projet
              (H27) : erreur E_BACKBONE_CONFLICT (code 6), sauf réponse à q.backbone_conflict ;
              actif seulement dans la vue observée : veto du Planner (spec 14 §2.4).
              La réponse à q.backbone_conflict porte l'identifiant du socle retenu. En R4b
              seul le socle par défaut (`speckit-egm-mattpocock` : spec-kit, egm,
              mattpocock-skills) est défini : toute autre valeur, ou un `backbone.id` inconnu,
              donne E_BACKBONE_UNKNOWN (code 2). Les socles alternatifs sont R6
2. requis   = capacités du socle (dures) ∪ process.gates (dure) ∪ règles de requirements.toml
3. présents = present_tools (Discovery) + déclarations suivies du projet (declared(),
              spec 14 §3.2 ; H27) reconnus par [detect] (E6) → capacités couvertes à coût 0.
              Un élément déclaré est reconnu quand sa valeur est égale (chaîne exacte) à un
              jeton de `detect.plugin` d'une fiche, ou son nom avant `@` ; un serveur MCP
              déclaré est reconnu quand `identify` lui a donné la référence d'une fiche
              (champ `tool_ref` de `declared()`) ;
              s'il correspond à une fiche `backbone-alt`, ce n'est pas un outil présent mais
              un socle alternatif (étape 1)
4. candidats = fiches t telles que
               t.status ∉ {rejected, watch, backbone-alt}
               t fournit au moins une capacité requise et non couverte par « présents »
               when(t) vrai
              chaque candidat écarté reçoit un code (8.3)
5. prérequis : pour chaque candidat, chaque prérequis bloquant non satisfait
               sans `fix` → écarté (PREREQ_UNMET) ; avec `fix` → action ajoutée au plan.
               Le statut se calcule sur le profil seul (le Selector ne lit jamais la machine) :
               `bin:<nom>` est `met` si un outil présent a ce binaire dans `detect.bin` ;
               `path:<chemin>` (`{component:<id>}` résolu par `profile.components`) est `met`
               si le profil le liste ; `runtime:host` est `met` si le composant visé a
               `runtime.value == "host"` ; tout autre cas est `unmet`. Action : `fix` si la
               fiche en a un, sinon `hint`, sinon `none`
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
        + 1 par prérequis non satisfait avec `fix`
```

On cherche S ⊆ candidats qui minimise, **dans cet ordre lexicographique** :

1. le nombre d'exigences dures non couvertes ;
2. le nombre d'exigences souples non couvertes ;
3. Σ coût(t) ;
4. |S| ;
5. la liste triée des identifiants de S (pour départager de façon stable).

Sous contraintes : pas de paire en `conflicts` ; pour chaque capacité exclusive, au plus un fournisseur dans S ∪ présents ; `requires` de chaque outil inclus dans S ∪ présents.

Algorithme : séparation et évaluation, en essayant d'abord les outils qui couvrent le plus d'exigences non couvertes (nombre décroissant, puis identifiant). On abandonne une branche dont le nombre minimal atteignable d'exigences dures non couvertes dépasse celui du meilleur ensemble trouvé (précisé le 2026-11-23, R4b). Au-delà de **24 candidats**, erreur `E_TOO_MANY_CANDIDATES` : c'est un défaut de catalogue (conditions trop larges), pas un cas à optimiser.

Le coût est un entier. Un outil sélectionné entraîne ses `requires` et les `fix` de ses prérequis bloquants non satisfaits ; ils entrent dans S (couverture vide, coût compté).

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

Ordre d'évaluation des codes pour une fiche (un seul code, le premier qui s'applique ; précisé le 2026-11-23, R4b) : `STATUS`, `BACKBONE_EXCLUSIVE`, outil présent (`REUSED`, ou `NOT_REQUIRED` s'il ne couvre aucune exigence), `CONDITION_FALSE`, `CONTRAINDICATED`, `NOT_REQUIRED`, `REDUNDANT`, `PREREQ_UNMET` ; après la recherche : `CONFLICT`, puis `COST`.

Textes (`reason` d'un retenu, `detail` d'un écarté) : gabarits fixes, en anglais, sans chemin absolu ni valeur d'environnement. `CONDITION_FALSE` : `<expression> is false` (la première expression fausse de `when.all`, sinon les expressions de `when.any` jointes par ` or `) ; `CONTRAINDICATED` : `<expression> is true` ; `NOT_REQUIRED` : `<capacités> not required` ; `BACKBONE_EXCLUSIVE` : `alternative backbone` ; `STATUS` : `status <statut>` ; `REDUNDANT` : `<capacité> already provided by <ref>` ; `CONFLICT` : `conflicts with <ref>` ; `COST` : `same coverage at a higher cost than <refs>` ; `PREREQ_UNMET` : `<check> unmet and no fix`, ou `requires <ref> unavailable` quand un outil requis est indisponible ; `NOT_REQUIRED` d'une fiche qui ne fournit aucune capacité : `not required by a selected tool` ; `COST` sans recouvrement avec un retenu : `not needed by the cheapest set`. `reason` d'un retenu : `covers <capacités>`, ou `required by <ref>` / `prerequisite of <ref>`. Le test A5.1 compare tout le reste de la sortie octet pour octet ; il ne compare pas `reason` ni `detail`.

### 8.4 Sortie

Schéma : [schemas/selection.schema.json](schemas/selection.schema.json). Exemple attendu pour `fx-split-stack` : [schemas/examples/selection.split-stack.json](schemas/examples/selection.split-stack.json).

Ordres (précisé le 2026-11-23, R4b) : `requirements` dans l'ordre de `capabilities.toml` ; `source` vaut `backbone`, `always` ou l'identifiant de la règle, suivi de ` (<id de l'élément>)` pour une règle `for_each` ; `selected` : les outils du socle dans l'ordre du socle, puis les autres par rang de leur première exigence couverte, chaque outil entraîné (`requires`, `fix`) juste après celui qui l'entraîne ; `reused` et `rejected` par référence. `cost_total` est la somme des `cost` de `selected`. `rule` d'un retenu : `backbone`, `always`, l'identifiant de la règle, `requires (<ref>)` ou `prerequisite (<ref>)`.

### 8.5 Propriétés testées

| Propriété | Énoncé |
|---|---|
| Déterminisme | Même catalogue, profil, réponses et déclarations suivies du projet ⇒ sortie identique octet pour octet. La vue observée (machine) n'entre jamais dans la sélection (H27) |
| Absence de conflit | Aucune paire de S en `conflicts` ; aucune capacité exclusive fournie deux fois dans S ∪ présents |
| Couverture | Toute exigence dure est couverte, ou la sortie a `ok = false` et la cite |
| Minimalité | Retirer un outil quelconque de S fait perdre une exigence couverte |
| Traçabilité | Chaque fiche applicable du catalogue apparaît exactement une fois, dans `selected`, `reused` ou `rejected` |
| Stabilité | Ajouter au catalogue une fiche dont `when` est faux ne change pas S |
