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
| `S-DEGRADED-INVENTORY` | warning | Claude Code < 2.1.285 ou `claude` absent : inventaire par les fichiers seulement |
| `S-INSTALLED-UNCONFIGURED` | warning | Installation R3 réussie sans configuration (apply interrompu) |
| `S-PREREQ` | warning | Prérequis non bloquant toujours non satisfait (ex. `backend/vendor` absent) |

`--ci` : code 3 si au moins un `error`. En CI, l'inventaire des plugins est sauté (pas de Claude Code) : seuls les constats sur fichiers, lock, catalogue et portes s'appliquent ; les autres sont `skipped`.

Base de comparaison pour `S-GATE-BYPASS` : variable `PEO_BASE_REF`, sinon `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` (GitLab) ou `GITHUB_BASE_REF` (GitHub), sinon `main`.
