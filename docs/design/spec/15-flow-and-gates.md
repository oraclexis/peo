# 15 — Recettes, portes, hooks et santé (F10, F11)

## 1. Ce que PEO tient, et ce qu'il ne fait pas

PEO **ne lance pas** les commandes du socle à la place de l'humain : les skills d'EGM et de Spec Kit sont déclenchées par l'utilisateur, et un workflow natif de Claude Code ne peut pas demander une décision en cours de route **[FAIT, analyse précédente]**. PEO **sait** où en est un travail, **dit** quelle commande vient ensuite et **bloque** l'écriture de code tant que les portes requises ne sont pas passées.

## 2. Recettes du MVP

### 2.1 Correspondance capacité → commande

Elle est déclarée par le socle (`[commands]` du fichier de socle), puis **vérifiée** après installation contre les skills réellement présentes (spike S4).

| Capacité | Commande (socle par défaut) |
|---|---|
| `clarify.interview` | `/mattpocock-skills:grill-with-docs` |
| `spec.authoring` | `/speckit-specify` puis `/speckit-clarify` |
| `plan.tasks` | `/speckit-plan`, puis `/speckit-tasks` |
| `spec.review.independent` | `/egm:egm-review-loop` |
| `tdd.discipline` | `/mattpocock-skills:tdd` (pendant `/speckit-implement`) |
| `debug.diagnosis` | `/mattpocock-skills:diagnosing-bugs` |
| `review.code` | `/mattpocock-skills:code-review` |
| `drift.docs` | `/egm:egm-drift-report` |

### 2.2 Pistes

| Piste | Usage | Choisie |
|---|---|---|
| S | Changement localisé, sans nouveau comportement observable (texte, style, correctif d'une ligne) | `--track S`, ou recommandée par `flow start` si la recette est `bugfix` et qu'aucun composant `backend` n'est concerné |
| M | Fonctionnalité dans un composant | défaut (`[tracks].default`) |
| L | Plusieurs composants, ou authentification, données personnelles, schéma de base de données | `--track L` ; recommandée si la description cite un de ces thèmes |

### 2.3 `feature`

| Étape | Capacité | Pistes | Porte après | Artefact |
|---|---|---|---|---|
| clarify | `clarify.interview` | M, L | — | notes dans `GLOSSARY.md` / ADR |
| specify | `spec.authoring` | M, L | **G1** | `specs/<dir>/spec.md` |
| plan | `plan.tasks` | M, L | — | `plan.md` |
| review-plan | `spec.review.independent` | L (option en M) | **G3** | rapport de revue EGM |
| tasks | `plan.tasks` | M, L | **G4** | `tasks.md` |
| implement | `tdd.discipline` | S, M, L | — | code et tests |
| verify | commande `verify` | S, M, L | **G5** | événement `verify` réussi |
| review | `review.code` | S, M, L | **G7** | événement `gate-approve G7` |

### 2.4 `bugfix`

| Étape | Capacité | Pistes | Porte après |
|---|---|---|---|
| diagnose | `debug.diagnosis` | S, M, L | **G2** (cause identifiée et approuvée ; en S : approbation sur la description du diagnostic) |
| specify | `spec.authoring` | L | G1 |
| implement | `tdd.discipline` (test qui reproduit d'abord) | S, M, L | — |
| verify | `verify` | S, M, L | G5 |
| review | `review.code` | M, L | G7 |

## 3. Portes

| Porte | Condition vérifiable | Approuvée par |
|---|---|---|
| **G1** | `spec.md` existe, ne contient plus `[NEEDS CLARIFICATION`, et un événement `gate-approve G1` porte l'empreinte actuelle de `spec.md` | humain (`peo flow approve G1`) |
| **G2** | événement `gate-approve G2` avec une note de diagnostic non vide | humain |
| **G3** | piste L : un rapport de revue existe dans le dossier de la fonctionnalité et `gate-approve G3` porte l'empreinte de `plan.md` | humain |
| **G4** | `tasks.md` existe, `checklists/` sans case non cochée **[FAIT, Spec Kit bloque `implement` sur les checklists]**, `gate-approve G4` porte l'empreinte de `tasks.md` | humain |
| **G5** | dernier événement `verify` du travail en `ok`, postérieur à la dernière modification de code connue du journal | `peo flow verify` |
| **G7** | `gate-approve G7` | humain |

`[gates.before_code]` est défini **par recette** (défaut `feature = ["G1", "G3", "G4"]`, `bugfix = ["G2", "G1"]`), puis filtré par la piste : une porte qui suit une étape absente de la piste ne s'applique pas (en S, `feature` n'a aucune porte avant le code ; `bugfix` garde G2). Il conditionne l'écriture de code. `[gates].before_merge` (défaut `G5, G7`) conditionne `flow done` et `status --ci` sur une branche de travail.

**Caducité (S-7)** : une approbation référence l'empreinte de son artefact. Si l'artefact change, la porte redevient ouverte ; `peo context` et `peo gate` le disent.

## 4. `peo gate`

### 4.1 Algorithme

```text
lire stdin (JSON) ; en cas d'erreur → on_error
cfg  = .peo/peo.toml ; absent → sortir 0 sans rien (projet non géré)
mode = cfg.gates.mode ; "off" → sortir 0
chemin = tool_input[file_path | notebook_path | <path_arg de l'outil, depuis le lock>]
        absent → sortir 0 (outil qui n'écrit pas de fichier identifiable)
chemin = normaliser(relatif à la racine) ; hors racine → décision mode, raison "outside project"
si chemin ∈ fichiers protégés (.peo/**) → "deny" quel que soit le mode, raison "PEO state is written by the peo CLI only"
si chemin ∉ ∪ components[*].paths.code  ou  chemin ∈ cfg.gates.allow → sortir 0
travail = travail courant (4.2)
          aucun et cfg.gates.require_work_item = false (défaut) → sortir 0
          aucun et require_work_item = true → décision mode, raison "no active work item: start one with /peo:flow"
          feature.json pointe vers un dossier absent → sortir 0, avertissement sur stderr
manquantes = portes de before_code applicables à la piste et non satisfaites (section 3)
si manquantes vide → sortir 0
sinon → décision mode, raison "PEO: <travail> needs <portes> before code (<étape suivante>)"
```

`decision mode` : `ask` → `permissionDecision: "ask"` ; `deny` → `"deny"`. Toujours avec la raison, en une ligne, qui nomme la commande suivante.

Les fichiers de spécification (`specs/**`, `.specify/**`) et la documentation ne sont jamais des chemins de code : la porte ne gêne pas la rédaction.

### 4.1 bis Qui peut approuver une porte

Une approbation est un événement du journal. Trois protections empêchent l'agent de s'approuver lui-même :

1. **Écriture directe** : `.peo/**` est refusé à tout outil d'écriture de l'agent (règle ci-dessus).
2. **Commande** : l'adaptateur Claude ajoute deux règles possédées dans `permissions.ask` de `.claude/settings.json` : `Bash(peo flow approve:*)` et `Bash(peo flow override:*)`. Claude Code demande alors l'accord de l'humain à chaque tentative, même en mode d'autorisation large. C'est **la seule** modification de `permissions` faite par PEO (elle amende la règle du document 14, section 6.1).
3. **Skill** : `/peo:flow` pose la question d'approbation par `AskUserQuestion` avant de lancer la commande.

Reste possible : l'humain qui accepte sans lire. C'est un choix humain, journalisé avec l'auteur git.

### 4.1 ter Écarts avec les tests T1 à T11 du dossier `ai-eng-workflow`

| Test | Avant (`forge`) | PEO | Raison |
|---|---|---|---|
| T6 | Écrire `checklists/gates.md` : refusé | Écrire `.peo/**` : refusé ; les cases de `checklists/` restent modifiables (elles appartiennent à Spec Kit, et G4 exige en plus une approbation journalisée) | Les approbations ont quitté les cases à cocher pour le journal (S-7) |
| T7 | Variable `GATE_MODE=off` | `[gates].mode = "off"` dans `peo.toml` | Une variable d'environnement n'est pas visible ni journalisée |

Les autres tests (T1 à T5, T8 à T11) gardent le même attendu.

Sous-agents : même règle. `agent_type` est seulement repris dans la raison (« subagent <type> »).

### 4.2 Travail courant

1. `.specify/feature.json` → `feature_directory` (Spec Kit) ;
2. sinon le dernier événement `flow-start` non suivi de `flow-done` **pour la branche courante** (lue dans `.git/HEAD`, sans lancer git) ;
3. sinon aucun.

### 4.3 Performance

Lectures : `peo.toml`, `peo.lock.json` (chemins et `path_arg`), `feature.json`, et le journal **lu depuis la fin** jusqu'au `flow-start` du travail (lecture par blocs de 64 ko). Aucun appel de processus. Objectif NF4 : < 100 ms.

### 4.4 Limites connues (affichées dans `.peo/README.md`)

- Une écriture par l'outil Bash (`sed -i`, redirection) n'est pas interceptée. PEO ne prétend pas le contraire ; `status --ci` détecte après coup des fichiers de code modifiés sur une branche sans portes passées (6, constat `S-GATE-BYPASS`).
- Un outil d'écriture d'un serveur MCP **absent du catalogue** n'est pas dans le `matcher`.
- `mode = "ask"` laisse l'humain accepter : c'est voulu en mode guidé.

### 4.5 Exemples (fichiers de test)

Entrée :

```json
{"session_id":"s1","transcript_path":"/tmp/t.jsonl","cwd":"/repo","permission_mode":"default",
 "hook_event_name":"PreToolUse","tool_name":"Edit","tool_use_id":"tu1",
 "tool_input":{"file_path":"/repo/app/components/ContactForm.vue","old_string":"a","new_string":"b"}}
```

Sortie attendue (travail `004-contact-form`, G1 approuvée, G4 non) :

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask",
 "permissionDecisionReason":"PEO: 004-contact-form needs G4 (tasks approved) before code. Next: /speckit-tasks, then peo flow approve G4."}}
```

Même entrée avec `tool_input.file_path = "/repo/specs/004-contact-form/spec.md"` : aucune sortie, code 0.

## 5. `peo context`

Voir document 11, section 4.3. Contenu : identifiant du travail, piste, étape, portes passées et caduques, commande suivante. Rien d'autre.

## 6. `peo status` (F11)

| Code | Sévérité | Constat |
|---|---|---|
| `S-LOCK-MISSING` | error | Outil du lock absent de l'inventaire |
| `S-VERSION-DRIFT` | warning | Version installée différente de la version du lock |
| `S-PLUGIN-ERROR` | error | `errors` non vide dans `claude plugin list --json` |
| `S-HOOK-UNDECLARED` | warning | Hook actif dont le propriétaire est un outil dont la fiche ne le déclare pas dans `surface.hooks` |
| `S-HOOK-FOREIGN` | info | Hook actif d'un outil hors catalogue |
| `S-MANAGED-MODIFIED` | warning | Bloc ou clé possédé modifié à la main |
| `S-CATALOG-EXPIRED` | warning | Fiche d'un outil actif dont `review_by` est dépassé |
| `S-BACKBONE-CONFLICT` | error | Socle alternatif activé à côté du socle du projet |
| `S-GATE-MATCHER-STALE` | error | `matcher` du hook différent de celui que calculerait le lock (ex. Serena ajouté à la main) |
| `S-GATE-BYPASS` | error (`--ci`) | Fichiers de code modifiés sur la branche par rapport à la base, sans les portes `before_code` du travail |
| `S-GATE-OVERRIDE` | warning | `flow override` utilisé sur le travail |
| `S-DOCS-DRIFT` | info | Nouveaux constats D1 à D4 |
| `S-DEGRADED-INVENTORY` | warning | Mode dégradé de l'Inventory (spec 14 §3.1) : `claude` absent, trop ancien, version illisible, ou `claude plugin list` en échec ou illisible ; inventaire par les fichiers seulement. Le message cite l'état et la raison de la source `claude` (`absent`, `claude-too-old`, `version-unparsed`, `command-failed`, `timeout-or-missing`, `output-unparsed`) |
| `S-INSTALLED-UNCONFIGURED` | warning | Installation R3 réussie sans configuration (apply interrompu) |
| `S-PREREQ` | warning | Prérequis non bloquant toujours non satisfait (ex. `backend/vendor` absent) |

**Effet des états de l'Inventory sur les constats** (spec 14 §3.1 ; ajout du 2026-11-14, R2). Chaque constat qui lit une source de l'Inventory dépend de son état :

| État de la source | Effet sur les constats de R3 |
|---|---|
| `read` | applicable |
| `absent` | applicable pour un fichier : l'absence de réglage est un fait (aucun hook, aucune règle). Pour la source `claude` : mode dégradé (`S-DEGRADED-INVENTORY`) |
| `invalid` | `skipped` pour les constats qui lisent cette source |
| `unavailable` | `skipped` |
| `not_inspected` | `skipped` ; sauf raison `disabled` : les hooks d'un plugin désactivé ne s'exécutent pas, les constats sur ses hooks ne s'appliquent pas |
| famille nommée dans `invalid_families` | même effet que `invalid`, limité aux constats qui lisent cette famille pour cette source |

**Drapeaux de hooks.** Pour les constats de hooks (`S-HOOK-*`, `S-GATE-*`, `X-HOOK-FAIL-OPEN`) : si `disableAllHooks` (selon sa portée, spec 10 §5) ou `allowManagedHooksOnly` (lu en managed seulement) rend un hook inerte, le constat le dit. PEO ne dit jamais qu'un hook « s'exécutera » : la source `settings:cli` (`--settings`, `--bare`, `--safe-mode`) est toujours `not_inspected`.

`--ci` : code 3 si au moins un `error`. En CI, l'inventaire des plugins est sauté (pas de Claude Code) : seuls les constats sur fichiers, lock, catalogue et portes s'appliquent ; les autres sont `skipped`.

Base de comparaison pour `S-GATE-BYPASS` : variable `PEO_BASE_REF`, sinon `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` (GitLab) ou `GITHUB_BASE_REF` (GitHub), sinon `main`.

## 7. Audit d'exposition (F14, ajout du 2026-11-12)

`peo status --exposure` ajoute aux constats de la section 6 les constats `X-*` ci-dessous. Entrées : section `sensitive` du profil (spec 12, section 7 bis), Inventory (spec 14, section 3 ; vue observée), lock et catalogue. L'effet des états de source et des familles invalides est celui de la section 6. Lecture seule, sans réseau (NF5), sans valeur dans la sortie (NF14). Gravités fixes (S-8) ; `--ci` : code 3 si au moins un `error`.

**Règle de formulation** : un constat décrit un contrôle présent ou absent et sa limite. Aucun message ne dit qu'une donnée est « protégée » (document 17, section 4).

### 7.1 Constats

| Code | Sévérité | Constat |
|---|---|---|
| `X-SECRET-TRACKED` | error | Fichier de `secret_files` suivi par git |
| `X-SECRET-READABLE` | error | Fichier de `secret_files` sans règle `permissions.deny` `Read(...)` qui le couvre, dans aucune portée |
| `X-LITERAL-IN-AGENT-CONFIG` | error | Sur une source du projet (`settings:project`, `settings:local`, `mcp:project`) avec `tracked: true`, une entrée de `values` avec `form = literal` et (`sensitive_name` ou `value_hint` non nul), ou une entrée de `mcp_servers` avec `args_hint` non nul (spec 14 §3.3, seule définition). `tracked: null` sur une source du projet donne `skipped` ; les sources user et managed ne sont pas visées. Le message cite le fichier et la clé (ou le serveur), jamais la valeur |
| `X-MASKING-DUPLICATE` | error | Deux outils actifs dont la fiche a `surface.data_path = "rewrites-io"` |
| `X-DATA-READABLE` | warning | Entrée de `data_dumps` ou de `log_dirs` sans règle `deny` qui la couvre |
| `X-NO-SECRET-SCAN` | warning | Aucun fournisseur de `secrets.scan.ci` dans le lock, et aucun job de CI ne mentionne un scanner connu du catalogue (`[detect].files` de ses fiches) |
| `X-SANDBOX-OFF` | warning | `secret_files` ou `data_stores` non vide et `sandbox.enabled` absent ou faux. **`info`** si un composant a `runtime = docker:<service>` (le sandbox casserait ses commandes, S-9) |
| `X-SANDBOX-FALLBACK` | warning | Sandbox actif avec `failIfUnavailable` différent de `true` ou `allowUnsandboxedCommands` différent de `false` : repli possible hors sandbox |
| `X-DATA-STORE` | info | Entrée de `data_stores` : rappel que l'agent ne doit travailler que sur des données de test (base anonymisée, rôle en lecture seule) |
| `X-MCP-UNEVALUATED` | info | Serveur MCP dont `tool_ref` est `null` (hors catalogue), ou dont la fiche a `data_path = "reads-sensitive"` ; cité par (`source`, `plugin_index`, `index`) et par `name` s'il n'est pas `null` |
| `X-HOOK-FAIL-OPEN` | info | Hook d'un outil `data_path = "rewrites-io"` sans `onFailure: "block"` |
| `X-CANARY-MISSED` | error | `--canary` : un détecteur installé n'a pas détecté le canari |
| `X-CANARY-UNVERIFIABLE` | warning | `--canary` : commande absente, en échec pour une autre raison, ou fiche avec `surface.network = "runtime"` (non lancée) |

Un « couvre » se calcule par correspondance de motifs : `Read(./backend/.env)`, `Read(./backend/**)` et `Read(**/.env)` couvrent `backend/.env`. Une règle `deny` de portée utilisateur compte, mais le constat le précise : elle ne voyage pas avec le dépôt.

En CI (pas de Claude Code, pas de `.env`), seuls les constats calculables sur les fichiers suivis s'appliquent ; les autres sont `skipped`.

### 7.2 Canari (`--canary`)

Option explicite, jamais implicite (NF5).

1. Pour chaque outil testable (définition à fixer en R3 ; le mot « actif » est réservé à la spec 14 §3.4) dont la fiche a `[canary]` et `surface.network` ≠ `runtime` :
2. créer un dossier temporaire **hors du dépôt** (`tempfile.mkdtemp`) ;
3. y écrire un fichier leurre : une fausse clé de format connu (préfixe `AKIA` + 16 caractères `[A-Z2-7]`, et `ghp_` + 36 caractères alphanumériques), générée par `secrets` à chaque exécution, jamais écrite ailleurs ni affichée ;
4. lancer `canary.command` par l'exécuteur injectable (`{dir}` remplacé), avec un délai de 30 s ;
5. code de sortie égal à `detected_exit` → détecté ; autre code → `X-CANARY-MISSED` ; commande absente ou délai dépassé → `X-CANARY-UNVERIFIABLE` ;
6. supprimer le dossier dans tous les cas (`finally`).

Résultat par outil : `detected`, `missed` ou `unverifiable`. La sortie standard et d'erreur de l'outil ne sont **pas** reprises dans la sortie de PEO (elles peuvent contenir le leurre).

### 7.3 Sortie

`data.exposure` de `peo status --exposure --json` : `findings` (même forme que les constats de la section 6) et, avec `--canary`, `canary` : liste `{ "tool": "<ref>", "result": "detected|missed|unverifiable" }` triée par `tool`.
