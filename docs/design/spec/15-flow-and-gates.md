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

La colonne **Livraison** (R3) fait foi pour le jeu de règles. La livraison est une propriété de la **version de PEO** (jeu de règles embarqué), pas un état du projet : la version qui livre R3 évalue les codes marqués R3, et ainsi de suite (document 07, section 7). Un code d'une livraison à venir **n'est pas évalué** : il n'apparaît ni dans les constats ni dans `rules_evaluated`. `skipped` reste réservé à un code évalué que l'état d'une source empêche de calculer (principe ci-dessous).

| Code | Sévérité | Livraison | Constat |
|---|---|---|---|
| `S-LOCK-MISSING` | error | R5 | Outil du lock absent de l'inventaire |
| `S-VERSION-DRIFT` | warning | R5 | Version installée différente de la version du lock |
| `S-PLUGIN-ERROR` | error | R3 | `errors` non vide dans `claude plugin list --json` |
| `S-HOOK-UNDECLARED` | warning | R4 | Hook actif dont le propriétaire est un outil dont la fiche ne le déclare pas dans `surface.hooks` (il lit les fiches, chargées à partir de R4) |
| `S-HOOK-FOREIGN` | info | R3 | Hook actif d'un propriétaire hors catalogue. Propriétaire (précisé le 2026-11-14) : le plugin pour un hook de plugin ; **la source** (`settings:project`, `settings:local`…) pour un hook écrit dans un fichier de réglages. En R3, sans catalogue chargé, tout hook actif est concerné |
| `S-MANAGED-MODIFIED` | warning | R5 | Bloc ou clé possédé modifié à la main |
| `S-CATALOG-EXPIRED` | warning | R4 | Fiche d'un outil actif dont `review_by` est dépassé |
| `S-BACKBONE-CONFLICT` | error | R5 | Socle alternatif activé à côté du socle du projet (il lit les fiches de socle et le socle retenu) |
| `S-GATE-MATCHER-STALE` | error | R6 | `matcher` du hook différent de celui que calculerait le lock (ex. Serena ajouté à la main) |
| `S-GATE-BYPASS` | error (`--ci`) | R6 | Fichiers de code modifiés sur la branche par rapport à la base, sans les portes `before_code` du travail |
| `S-GATE-OVERRIDE` | warning | R6 | `flow override` utilisé sur le travail |
| `S-DOCS-DRIFT` | info | R6 | Nouveaux constats D1 à D4 (il compare à un état précédent, que `status` ne garde pas avant R6) |
| `S-DEGRADED-INVENTORY` | warning | R3 | Mode dégradé de l'Inventory (spec 14 §3.1) : `claude` absent, trop ancien, version illisible, ou `claude plugin list` en échec ou illisible ; inventaire par les fichiers seulement. Le message cite l'état et la raison de la source `claude` (`absent`, `claude-too-old`, `version-unparsed`, `command-failed`, `timeout-or-missing`, `output-unparsed`). Émis aussi quand `claude` est absent, en CI comme ailleurs (précisé le 2026-11-14) |
| `S-INSTALLED-UNCONFIGURED` | warning | R5 | Installation de classe de risque R3 (spec 14 §2.1) réussie sans configuration (apply interrompu) |
| `S-PREREQ` | warning | R5 | Prérequis non bloquant toujours non satisfait (ex. `backend/vendor` absent) |

**Forme d'un constat** (ajout du 2026-11-14, R3) : schéma [schemas/status.schema.json](schemas/status.schema.json), exemple [schemas/examples/status.split-stack.json](schemas/examples/status.split-stack.json). Un constat porte `code`, `severity`, `status` (`applied` ou `skipped`), `confidence` (`fact` ou `likely`), `message`, `evidence` (chaînes : chemins, noms de clés, règles telles qu'écrites, jamais une valeur) et, selon le code, `path`, `source`, `rule`, `reason`, `suggested_rule`, et pour un serveur MCP `plugin_index`, `index`, `name`. Le schéma fait foi. `data.rules_evaluated` est la liste triée des codes évalués (`S-*`, et `X-*` avec `--exposure`) ; avec la version de PEO, elle suffit à rejouer un résultat (pas de numéro de jeu de règles).

**Entrées par code** (codes de la livraison R3). Un code ne dépend que des sources qu'il lit :

| Code | Nature | Lit (sujet en gras : une famille, ou la source `claude` pour `S-PLUGIN-ERROR` ; les autres entrées sont des modificateurs) |
|---|---|---|
| `S-PLUGIN-ERROR` | risque présent | source **`claude`** |
| `S-HOOK-FOREIGN` | risque présent | famille **`hooks`** de chaque source ; `flags` (`disableAllHooks`, `allowManagedHooksOnly`) |
| `S-DEGRADED-INVENTORY` | — | source `claude` |
| `X-SECRET-TRACKED` | risque présent | `sensitive.secret_files` (Discovery) |
| `X-SECRET-READABLE`, `X-DATA-READABLE` | contrôle absent | `sensitive` ; famille `permissions` des sources de réglages ; `allowManagedPermissionRulesOnly` (valeur effective des sources managed, spec 14 §3.6) ; tableau de conformité de la plateforme |
| `X-COVERAGE-NOT-SHARED` | contrôle absent | mêmes entrées que `X-SECRET-READABLE` ; `tracked` des sources |
| `X-LITERAL-IN-AGENT-CONFIG` | risque présent | familles **`values`** et **`mcp`** de `settings:project`, `settings:local`, `mcp:project` |
| `X-NO-SECRET-SCAN` | contrôle absent | fichiers de CI et `.pre-commit-config.yaml` du dépôt ; lock ; `discovery/detect.toml` |
| `X-SANDBOX-OFF`, `X-SANDBOX-FALLBACK` | contrôle absent | famille `flags` des sources de réglages (valeur effective, spec 14 §3.6) ; `sensitive` ; composants |
| `X-DATA-STORE` | risque présent | `sensitive.data_stores` |
| `X-MCP-UNEVALUATED` | risque présent | famille **`mcp`** de chaque source |

**Principe unique pour les sources illisibles** (R3). L'effet dépend de la nature du code (colonne « Nature » ci-dessus) :

- **Code de contrôle absent** (`X-SECRET-READABLE`, `X-DATA-READABLE`, `X-COVERAGE-NOT-SHARED`, `X-NO-SECRET-SCAN`, `X-SANDBOX-OFF`, `X-SANDBOX-FALLBACK`) : **jamais `skipped`** à cause d'une source. Le code est calculé sur les sources lisibles. Si une source illisible peut porter le contrôle (une règle `deny`, un réglage du sandbox), et qu'aucune source lisible ne le porte, le constat est émis en confiance `likely`, `reason = "source-unreadable"`, et cite la source illisible dans `evidence`. Une valeur scalaire `unknown` (spec 14 §3.6) compte comme contrôle absent.
- **Code de risque présent** (`S-PLUGIN-ERROR`, `S-HOOK-FOREIGN`, `X-SECRET-TRACKED`, `X-LITERAL-IN-AGENT-CONFIG`, `X-DATA-STORE`, `X-MCP-UNEVALUATED` ; `X-SECRET-TRACKED` et `X-DATA-STORE` ne lisent que Discovery, aucune source ne les rend `skipped`) : les sources lisibles donnent leurs constats ; une source donne **une** entrée `skipped` (avec `source`, sans `path`) **seulement si la famille sujet** du code y est illisible (source `invalid`, `unavailable`, `not_inspected` hors `out-of-scope` et `disabled`, ou famille sujet dans `invalid_families`). Une famille **modificatrice** illisible ne donne pas de `skipped` : le constat est émis, et `evidence` dit ce qui reste inconnu (par exemple : `flags` invalide, l'état inerte du hook n'est pas connu ; spec 14 §3.6).

État d'une source et effet (spec 14 §3.1) :

| État de la source | Effet sur les constats |
|---|---|
| `read` | applicable |
| `absent` | applicable pour un fichier : l'absence de réglage est un fait (aucun hook, aucune règle). Pour la source `claude` : mode dégradé (`S-DEGRADED-INVENTORY`) ; `S-PLUGIN-ERROR` et `X-MCP-UNEVALUATED` (serveurs des plugins) donnent chacun **une** entrée `skipped`, `source = "claude"` (A14.20) |
| `invalid`, `unavailable` | source illisible : principe ci-dessus |
| `not_inspected`, raison `out-of-scope` (toute source ayant cette raison : `settings:cli`, `settings:managed-other`, `mcp:local`, `mcp:user`) | hors de portée de PEO sur toute machine : la source est sautée, sans `skipped` ni `likely`, et la limite figure dans `data.limits` (section 7.4) |
| `not_inspected`, raison `disabled` | les hooks d'un plugin désactivé ne s'exécutent pas : les constats sur ses hooks ne s'appliquent pas |
| `not_inspected`, autres raisons (dont `not-provided`, `degraded`) | source illisible : principe ci-dessus |
| famille nommée dans `invalid_families` | source illisible pour cette famille seulement ; pour un code de risque présent, seulement si c'est sa famille sujet |

**Drapeaux de hooks.** Pour les constats de hooks (`S-HOOK-*`, `S-GATE-*`, `X-HOOK-FAIL-OPEN`) : si `disableAllHooks` (selon sa portée, spec 10 §5) ou `allowManagedHooksOnly` (lu en managed seulement) rend un hook inerte, le constat le dit. PEO ne dit jamais qu'un hook « s'exécutera » : la source `settings:cli` (`--settings`, `--bare`, `--safe-mode`) est toujours `not_inspected`.

`--ci` : code 3 si au moins un `error`. Le mode CI n'est pas détecté (S-13) : sans Claude Code, la source `claude` est `absent`, le tableau ci-dessus s'applique et `S-DEGRADED-INVENTORY` est émis.

Base de comparaison pour `S-GATE-BYPASS` : variable `PEO_BASE_REF`, sinon `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` (GitLab) ou `GITHUB_BASE_REF` (GitHub), sinon `main`.

## 7. Audit d'exposition (F14, ajout du 2026-11-12)

`peo status --exposure` ajoute aux constats de la section 6 les constats `X-*` ci-dessous. Entrées (précisé le 2026-11-14, R3) : section `sensitive` d'un profil calculé **en mémoire** par Discovery à chaque appel avec `--exposure` (spec 12, section 7 bis ; `.peo/profile.json` n'est jamais lu, S-12), Inventory (spec 14, section 3 ; vue observée), tableau de conformité de la plateforme, embarqué dans le paquet (spec 14 §3.5), lock (vide jusqu'en R5) et `discovery/detect.toml` (le catalogue n'est pas chargé avant R4, S-14). L'effet des états de source est celui de la section 6. Lecture seule, sans réseau dans le processus de PEO (NF5), sans valeur dans la sortie (NF14), sans cache. Durée : NF3 ; chaque commande `claude` (`--version`, `plugin list`) est lancée avec un délai de 10 s, au-delà duquel la source `claude` est `unavailable`, `timeout-or-missing`, et l'Inventory passe en mode dégradé. Sévérités fixes (S-8) ; `--ci` : code 3 si au moins un `error`.

**Règle de formulation** : un constat décrit un contrôle présent ou absent et sa limite. Aucun message ne dit qu'une donnée est « protégée » (document 17, section 4). Une absence de constat n'est pas une garantie : `data.limits` (section 7.4) dit ce que l'audit n'a pas pu voir.

### 7.1 Constats

| Code | Sévérité | Livraison | Constat |
|---|---|---|---|
| `X-SECRET-TRACKED` | error | R3 | Fichier de `secret_files` suivi par git, à toute profondeur (spec 12 §7 bis). Un lien symbolique suivi dont la cible est hors du projet (`link_target = null`) donne **`warning`**, message distinct : le lien est partagé, pas forcément le secret |
| `X-SECRET-READABLE` | error | R3 | Fichier de `secret_files` sans règle `permissions.deny` `Read(...)` qui le couvre, dans aucune portée lue. Verdict du comparateur de règles (spec 14, section 3.5) : `not_covered` → constat, confiance `fact`, sauf si un fichier de `nested_claude_settings` (spec 12 §7 bis) est dans un dossier parent du chemin : confiance `likely`, `reason = "nested-settings"`, fichier cité dans `evidence` ; `undecidable` → constat, confiance `likely`, `reason`, `rule` et `source` de la règle en cause, **jamais `skipped`** ; `covered` → pas de constat (voir `X-COVERAGE-NOT-SHARED`). Le constat propose `suggested_rule = "Read(./<chemin exact>)"` ; pour un lien symbolique dont la cible est dans le projet, le chemin exact est la cible (`link_target`), seule comparée par la spec 14 §3.5, passe 2 (précisé le 2026-11-15) ; sauf si un segment du chemin sort de l'ensemble littéral de la spec 14 §3.5 (`[A-Za-z0-9._@+-]`, pas de `#` initial) : pas de suggestion, le message dit d'écrire la règle à la main |
| `X-COVERAGE-NOT-SHARED` | warning | R3 | Chemin de `secret_files`, `data_dumps` ou `log_dirs` dont le verdict est `covered`, mais dont la règle décisive (spec 14 §3.5, passe 6) ne vient pas d'une source `settings:project` avec `tracked: true` et `modified: false` : la couverture n'est pas partagée par le dépôt (règle locale, utilisateur ou managed, fichier projet non suivi, ou fichier suivi modifié et pas commité ; `modified: null` compte comme modifié). Cite le chemin, la règle, la portée décisive et, le cas échéant, `modified` dans `evidence` |
| `X-LITERAL-IN-AGENT-CONFIG` | error | R3 | Sur une source du projet (`settings:project`, `settings:local`, `mcp:project`) avec `tracked: true`, une entrée de `values` avec `form = literal` et (`sensitive_name` ou `value_hint` non nul), ou une entrée de `mcp_servers` avec `args_hint` non nul (spec 14 §3.3, seule définition). Un constat par entrée en cause. `tracked: null` sur une source du projet donne `skipped` ; les sources user et managed ne sont pas visées. Le message cite le fichier et la clé (ou le serveur), jamais la valeur |
| `X-MASKING-DUPLICATE` | error | R4 | Deux outils actifs dont la fiche a `surface.data_path = "rewrites-io"` (il lit les fiches ; reporté de R3 le 2026-11-14 : aucun outil réel ne le déclenche sans catalogue) |
| `X-DATA-READABLE` | warning | R3 | Entrée de `data_dumps` ou de `log_dirs` sans règle `deny` qui la couvre, même comparateur et mêmes verdicts que `X-SECRET-READABLE` ; `log_dirs` est passé avec `is_dir` ; pour un dossier, `suggested_rule = "Read(./<dossier>/**)"`, mêmes exclusions |
| `X-NO-SECRET-SCAN` | warning | R3 | Aucun fournisseur de `secrets.scan.ci` dans le lock, et aucun scanner connu trouvé dans les fichiers de CI ni dans `.pre-commit-config.yaml`. Jusqu'en R5, les fournisseurs du lock sont l'ensemble vide : seule la seconde branche compte. Mécanisme : section 7.1 bis. Le message dit quels scanners sont reconnus (R3 : jetons `gitleaks` et `Secret-Detection`) |
| `X-SANDBOX-OFF` | warning | R3 | `secret_files` ou `data_stores` non vide et `sandbox.enabled` absent, faux ou `unknown` (valeur effective, spec 14 §3.6). Si un composant a `runtime = docker:<service>` (le sandbox casserait ses commandes, S-9) : **`warning`** si `secret_files` est non vide, **`info`** sinon (révisé le 2026-11-14). Le message liste les fichiers de `secret_files` couverts par une règle `deny Read`, et dit sa limite : le spike a montré que le sandbox applique ces règles aux commandes Bash ; sans sandbox, leur effet sur Bash n'est pas vérifié (spec 10 §5) |
| `X-SANDBOX-FALLBACK` | warning | R3 | Sandbox actif avec `failIfUnavailable` différent de `true` ou `allowUnsandboxedCommands` différent de `false` (valeurs effectives ; `unknown` compte comme différent) : repli possible hors sandbox. Même liste de fichiers couverts par `deny Read` et même limite que `X-SANDBOX-OFF` |
| `X-DATA-STORE` | info | R3 | Entrée de `data_stores` : rappel que l'agent ne doit travailler que sur des données de test (base anonymisée, rôle en lecture seule) |
| `X-MCP-UNEVALUATED` | info | R3 | Serveur MCP dont `tool_ref` est `null` (hors catalogue), ou dont la fiche a `data_path = "reads-sensitive"` ; cité par `source`, `plugin_index`, `index` et `name` s'il n'est pas `null`. En R3, sans catalogue chargé, le code se déclenche sur **tout** serveur MCP lu |
| `X-HOOK-FAIL-OPEN` | info | R4 | Hook d'un outil `data_path = "rewrites-io"` sans `onFailure: "block"` (il lit les fiches ; reporté de R3 le 2026-11-14) |
| `X-CANARY-MISSED` | error | R4.1 | `--canary` : un détecteur installé n'a pas détecté le canari |
| `X-CANARY-UNVERIFIABLE` | warning | R4.1 | `--canary` : commande absente, en échec pour une autre raison, ou fiche avec `surface.network = "runtime"` (non lancée) |

« Couvre » est défini en un seul endroit : le comparateur de règles de la spec 14, section 3.5. Une règle `deny` hors d'un `settings:project` suivi compte, mais `X-COVERAGE-NOT-SHARED` le signale. `sandbox.filesystem.denyRead` ne compte pas comme couverture : le sandbox ne couvre pas l'outil Read (document 17, section 3.5).

### 7.1 bis Mécanisme de `X-NO-SECRET-SCAN` (R3)

1. Fichiers lus, comme texte, ligne par ligne, sans analyse YAML : `.gitlab-ci.yml`, **tous** les `.github/workflows/*.yml` et `*.yaml` suivis par git (pas seulement `ci.file` de Discovery), et `.pre-commit-config.yaml`.
2. Lignes exclues : commentaires (`#` en début de ligne, après les espaces) ; lignes qui ne sont qu'une clé (`gitleaks:`) ; valeur d'une clé `name:` sans `/` (nom de job ou d'étape ; une valeur avec `/` est une référence d'image, lue, sans suivre l'indentation).
3. Jetons : champ `ci` des entrées de `discovery/detect.toml` (R3 ; il passe dans `[detect]` des fiches en R4), comparés sans casse et en mot entier (bornes : début, fin, ou caractère hors `[A-Za-z0-9_-]`). R3 : `ci = ["gitleaks", "Secret-Detection"]` pour `ci-check:gitleaks`. Reconnus, par exemple : `run: gitleaks detect --redact`, `uses: gitleaks/gitleaks-action@v2`, `image: zricethezav/gitleaks:latest`, `name: ghcr.io/gitleaks/gitleaks:v8` dans un bloc `image:` (valeur avec `/`), `- template: Jobs/Secret-Detection.gitlab-ci.yml`, `id: gitleaks` dans `.pre-commit-config.yaml`.
4. Un jeton trouvé → pas de constat ; aucun → constat, preuve = fichiers lus. Aucun fichier → constat, preuve `"no CI file"`.

Limites écrites dans le message : seuls les scanners dont une entrée porte `ci` sont reconnus ; un autre scanner, ou un appel par script intermédiaire (`make scan`), donne un faux positif. Faux négatif accepté : une ligne qui ne fait que citer le jeton (`run: echo "TODO gitleaks"`) supprime le constat.

### 7.2 Canari (`--canary`, livraison R4.1)

Option explicite, jamais implicite (NF5). Reportée le 2026-11-14 en R4.1, après le chargeur de catalogue (R4) : elle lit `[canary]` et `[detect].bin` des fiches. Le jalon A′ ne la mesure pas.

1. Pour chaque outil testable dont la fiche a `[canary]` et `surface.network` ≠ `runtime`. Définition proposée pour R4.1 : « installé » = un binaire de `[detect].bin` résolu sur le `PATH` (confiance `fact`) ; un job de CI ne suffit pas ; on exécute le **chemin absolu résolu** et on l'affiche dans le résultat. Le mot « actif » est réservé à la spec 14 §3.4. Préalable : `gitleaks dir` et `detected_exit = 1` vérifiés sur la version épinglée (spec 13, section 5) :
2. créer un dossier temporaire **hors du dépôt** (`tempfile.mkdtemp`) ;
3. y écrire un fichier leurre : une fausse clé de format connu (préfixe `AKIA` + 16 caractères `[A-Z2-7]`, et `ghp_` + 36 caractères alphanumériques), générée par `secrets` à chaque exécution, jamais écrite ailleurs ni affichée ;
4. lancer `canary.command` par l'exécuteur injectable (`{dir}` remplacé), avec un délai de 30 s ;
5. code de sortie égal à `detected_exit` → détecté ; autre code → `X-CANARY-MISSED` ; commande absente ou délai dépassé → `X-CANARY-UNVERIFIABLE` ;
6. supprimer le dossier dans tous les cas (`finally`).

Résultat par outil : `detected`, `missed` ou `unverifiable`. La sortie standard et d'erreur de l'outil ne sont **pas** reprises dans la sortie de PEO (elles peuvent contenir le leurre).

### 7.3 Sortie

`data` de `peo status [--exposure] --json` (schéma [schemas/status.schema.json](schemas/status.schema.json)) : `inventory` (spec 14, section 3.2), `findings` (constats `S-*`), `rules_evaluated`, `limits` et, avec `--exposure`, `exposure` : `{ "audited": [...], "findings": [constats X-*], "linked_dirs": [...] }`. `audited` liste **chaque** chemin de `secret_files`, `data_dumps` et `log_dirs` avec son verdict : `{ "path", "kind" (`secret_file`, `data_dump`, `log_dir`), "verdict", "reason", "rule", "source" }` (chemins et règles seulement, NF14), trié par `path` ; un chemin `covered` y figure, ce qui distingue « couvert » de « jamais vu ». `linked_dirs` reprend `sensitive.walk.linked_dirs`. À partir de R4.1, `canary` est **à côté** de `exposure` dans `data` (schéma étendu en R4.1) : liste `{ "tool": "<ref>", "path": "<binaire résolu>", "result": "detected|missed|unverifiable" }` triée par `tool`. Constats triés par `code`, `path`, `source`, `plugin_index`, `index`, puis `evidence` (ordre lexicographique de la liste) : l'ordre est total.

**Sortie humaine** (sans `--json`). Un constat `applied` par ligne : `<sévérité> <code> <path ou source>: <message>` ; un constat `likely` ajoute ` (likely: <reason>)` ; les entrées `skipped` suivent, une par ligne : `skipped <code> <source>: <message>`. Puis les limites, une par ligne, et pour `L-SYMLINK-DIR` les dossiers de `linked_dirs`, un par ligne. Tout chemin, règle ou nom issu du dépôt est **échappé** avant affichage : caractères C0 et C1 (dont retour à la ligne et ESC) et caractères bidirectionnels de NF13 écrits `\xNN` ou `\u{NNNN}` (NF13). Spec 11 renvoie ici.

### 7.4 Limites déclarées (`data.limits`, R3)

Liste triée de codes fixes : ce que l'audit n'a pas pu voir sur cette exécution. Une limite n'est pas un constat (pas de sévérité, pas d'effet sur `--ci`). Une limite n'est émise que quand elle s'applique à l'exécution.

| Limite | Émise quand | Sens |
|---|---|---|
| `L-LAUNCH-ROOT` | au moins une source `settings:project` ou `settings:local` lue | Les verdicts supposent que Claude Code est lancé depuis la racine du projet. Quand Claude Code est lancé depuis un sous-dossier, les réglages de la racine ne sont pas chargés (spike du 2026-11-14) |
| `L-NESTED-SETTINGS` | `sensitive.nested_claude_settings` non vide | Des réglages `.claude/` de sous-dossiers existent et ne sont pas lus : ils s'appliquent quand Claude Code est lancé depuis ce sous-dossier. Les constats des chemins situés dessous passent en confiance `likely` (section 7.1) |
| `L-CLAUDE-NEWER` | au moins un verdict `covered` avec une version de Claude Code postérieure à `max(versions_tested)` | Le comportement de cette version n'a pas été rejoué ; le tableau de la version la plus récente testée est appliqué (spec 14 §3.5) |
| `L-CASE-SENSITIVITY` | au moins un verdict `covered` | La sensibilité à la casse du volume du projet n'est pas mesurée ; le tableau suppose celle de `case_sensitive_fs` (spec 14 §3.5) |
| `L-GREP-GLOB` | au moins un verdict `covered` | La couverture des outils Grep et Glob par une règle `deny Read` n'est pas vérifiée (spike : outils différés en 2.1.325) |
| `L-SETTINGS-CLI` | toujours | `settings:cli` (`--settings`, `--bare`, `--safe-mode`) n'est jamais lu |
| `L-SETTINGS-MANAGED-OTHER` | toujours | Réglages managed hors des emplacements connus (MDM, registre, profil) non lus ; s'ils posent `allowManagedPermissionRulesOnly`, les règles non managed sont ignorées par Claude Code et un `covered` est faux (spec 14 §3.5) |
| `L-SERVER-MANAGED` | toujours | Réglages managed distribués par le serveur (console d'administration) : illisibles depuis le poste ; même conséquence possible sur `covered` |
| `L-MCP-LOCAL-USER` | toujours, avec `--exposure` | Serveurs MCP des portées local et user (`~/.claude.json`, écrits par défaut par `claude mcp add`) non lus : `X-MCP-UNEVALUATED` ne les voit pas |
| `L-MCP-APPROVAL` | un serveur MCP de projet est lu | Les réglages d'approbation des serveurs MCP de projet ne sont pas lus : « actif » est une borne haute (spec 14 §3.4) |
| `L-DISCOVERY-DEPTH` | le parcours de Discovery a coupé à la profondeur 3 (`sensitive.walk.depth_pruned`, spec 12, section 7 bis) | Un fichier sensible **non suivi** plus profond n'est pas audité ; les fichiers suivis le sont à toute profondeur |
| `L-SYMLINK-DIR` | le parcours a rencontré un dossier lié non suivi (`sensitive.walk.linked_dirs` non vide) | Les fichiers sous un dossier lié ne sont pas audités ; les dossiers sont cités dans la sortie humaine |
| `L-HTTP-HOOK` | un hook actif de type `http` est lu | Un hook `http` envoie des données hors du poste ; sa destination n'est pas auditée (URL jamais lue, NF14) |

