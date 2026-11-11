# 14 — Planner, Inventory, adaptateurs et fichiers gérés (F3, F6 à F9, F12, F13)

## 1. Principe

Le Planner **compare** l'état voulu (sélection + configuration) à l'état réel (Inventory) et produit une liste d'actions. Il n'écrit rien. `apply` exécute les actions dans un ordre fixe, après accord, et enregistre chaque résultat. Les adaptateurs **délèguent** aux installeurs natifs (décision D1) ; aucun ne télécharge ni ne copie lui-même du code tiers au MVP.

## 2. Modèle d'action

Schéma : [schemas/plan.schema.json](schemas/plan.schema.json).

| Champ | Valeurs |
|---|---|
| `op` | `add` (+), `change` (~), `remove` (-), `keep` (=), `manual` (?) |
| `target.type` | `plugin`, `marketplace`, `mcp`, `cli`, `framework`, `file`, `block`, `json-keys`, `ci` |
| `group` | `prerequisites`, `cli`, `framework`, `plugins`, `mcp`, `files`, `ci`, `peo` |
| `risk` | voir 2.1 |
| `tool` | référence de la fiche concernée, ou `peo:core` |
| `command` | pour les actions déléguées : liste d'arguments exacte, affichée telle quelle |
| `preconditions` | empreintes `sha256` des fichiers lus ou modifiés ; absence attendue notée `absent` |
| `reason` | phrase courte, reprise de la sélection |

### 2.1 Classes de risque

| Classe | Définition | Exemples | Accord en `guided` | Accord en `semi` |
|---|---|---|---|---|
| **R0** | Lecture, ou rien à faire | `keep` | aucun | aucun |
| **R1** | Fichier du projet, réversible par la sauvegarde | `AGENTS.md`, `.peo/*`, bloc dans `.gitignore` | par groupe | accord du plan suffit |
| **R2** | Configuration qui change le comportement de l'agent dans ce projet | `.claude/settings.json` (hooks, `enabledPlugins`), `.mcp.json`, `specify init` | par groupe | accord du plan suffit |
| **R3** | Environnement de l'utilisateur ou réseau | `uv tool install`, `npm install -g`, `claude plugin install`, `claude plugin marketplace add` | par action | **par action** |
| **R4** | Destruction ou écrasement de ce que PEO ne possède pas | retirer un plugin installé à la main, écraser un fichier modifié | **interdit au MVP** : transformé en `manual` | idem |

`[policy].require_consent` de `peo.toml` peut durcir ces règles (exiger l'accord pour R1), jamais les assouplir sous le seuil du tableau.

### 2.2 Empreinte du plan

`plan_id = sha256(JSON canonique de { schema, catalog.commit, actions })`, où le JSON canonique trie les clés, n'a pas d'espace et exclut tout horodatage. `apply --expect-plan` recalcule le plan ; si l'empreinte diffère, code 4 et différence affichée. Les `preconditions` garantissent qu'un fichier modifié entre le plan et l'application change l'empreinte.

### 2.3 Ordre d'application

```text
1. sauvegarde  : copie de chaque fichier que le plan modifie → .peo/backups/<horodatage>/<chemin>
2. prerequisites (actions avec fix, ex. intelephense)
3. cli          (uv tool install, npm install -g)
4. framework    (specify init, puis configuration de Spec Kit)
5. plugins      (marketplace add, puis install --scope project)
6. mcp          (.mcp.json)
7. files        (AGENTS.md, CLAUDE.md, .claude/settings.json, .claude/rules/, .gitignore, .gitattributes)
8. ci           (bloc géré dans le fichier de CI)
9. peo          (peo.toml, profile.json, peo.lock.json, history.ndjson, README.md)
```

À chaque action : événement dans le journal (résultat `ok`, `failed`, `skipped`, `manual`). Sur échec : arrêt, **restauration des fichiers déjà écrits pendant cette exécution** depuis la sauvegarde, lock mis à jour seulement pour les actions réussies des groupes 2 à 6 (elles ont modifié l'environnement et doivent rester traçables), message donnant la commande de reprise. Une installation R3 réussie n'est jamais défaite automatiquement : `peo status` la signale comme « installé, non configuré ».

Rétention des sauvegardes : 10 dernières exécutions. `.peo/backups/` est ignoré par git (bloc géré dans `.gitignore`).

## 3. Inventory (F3)

| Portée | Source | Confiance |
|---|---|---|
| Plugins Claude | `claude plugin list --json` (≥ 2.1.285), filtré : `scope` `user` ou `managed`, ou `projectPath` égal à la racine du projet **[FAIT]** | `fact` |
| Plugins Claude (repli) | `.claude/settings.json`, `.claude/settings.local.json`, `~/.claude/settings.json` : `enabledPlugins`, `extraKnownMarketplaces` | `likely` (activation sans preuve d'installation) |
| Hooks actifs | Union des hooks des fichiers de réglages et des plugins activés (`hooks/hooks.json` sous `installPath`) ; propriétaire = fichier ou plugin | `fact` |
| Serveurs MCP | `.mcp.json` ; portée utilisateur selon le spike S3 | `fact` / non inspecté |
| Outils CLI | `uv tool list` ; `npm ls -g --depth=0 --json` ; `shutil.which` pour les binaires de `[detect].bin` | `fact` |
| Dépendances de dev (E6) | `package.json`, `composer.json`, `pyproject.toml` de chaque composant, comparés aux `[detect]` des fiches | `fact` |
| Spec Kit | `.specify/` présent, version dans `.specify/init-options.json` si présente, extensions dans `.specify/extensions/` | `fact` |

Sortie : `data.inventory` de `peo status --json`, et entrée du Selector (outils présents).

## 4. Adaptateurs

### 4.1 Contrat

```python
class Adapter(Protocol):
    kind: str                                   # "claude-plugin", "mcp", "cli-uv", "cli-npm", "framework", "files", "ci"
    def detect(self, entry, ctx) -> Detected | None          # état réel de cet outil
    def plan(self, entry, desired, detected, ctx) -> list[Action]
    def apply(self, action, ctx) -> Result                   # exécute UNE action ; jamais d'autre effet
    def verify(self, entry, ctx) -> Check                    # vérification après coup
    def owned(self, entry, lock_entry, ctx) -> list[Owned]   # possessions encore intactes
    def remove(self, entry, lock_entry, ctx) -> list[Action] # retrait limité à owned()
```

`ctx` donne la racine du projet, le profil, la configuration, un exécuteur de commandes **injectable** (faux exécuteur en test) et le journal. Un adaptateur n'appelle jamais `subprocess` directement.

### 4.2 Par type

| Type | `detect` | `apply` | Possède | Vérifie |
|---|---|---|---|---|
| `claude-plugin` | Inventory (3) | `claude plugin marketplace add <source> --json` si la marketplace manque, puis `claude plugin install <name>@<mkt> --scope project --json`. Dernière ligne de stdout analysée ; `outcome = ok` ou `failureCode = already_in_goal_state` = succès | `json-keys` : `enabledPlugins["<name>@<mkt>"]`, `extraKnownMarketplaces.<mkt>` dans `.claude/settings.json` | `claude plugin list --json` : présent, `enabled`, `errors` vide, `version` comparée à `versions.tested` (spike S2) |
| `mcp` | `.mcp.json` | Fusion de `mcpServers.<nom>` (section 6.1) | `json-keys` : `mcpServers.<nom>` | La commande du serveur existe (`shutil.which`) |
| `cli-uv` | `uv tool list` | `uv tool install <paquet>==<version>` (Python épinglé si la fiche le demande : `-p 3.13`) | aucune possession de fichier ; installation notée dans le lock | `verify` de la fiche (ex. `serena --version`) |
| `cli-npm` | `npm ls -g --depth=0 --json` | `npm install -g <paquet>@<version>` **seulement** si le préfixe global est inscriptible sans élévation (`npm prefix -g` puis test d'écriture) ; sinon action transformée en `manual` | idem | idem |
| `framework` (Spec Kit) | `.specify/` | `specify init --here --force --integration claude --integration-options="--no-model-invocation"` après sauvegarde de `.specify/` et `.claude/skills/speckit-*` ; puis configuration (5.3) | `files` : fichiers créés par `init` (liste relevée par différence avant/après, avec empreintes) | `specify check` ; présence de `.specify/memory/constitution.md` |
| `files` | lecture | Composer (section 6) | `block`, `json-keys`, `file` (empreinte) | empreinte relue |
| `ci` | fichier de CI | Bloc géré (6.7) | `block` | empreinte relue |

**Jamais** : `claude plugin install --scope user` (portée projet partageable et réversible) ; installation par la marketplace d'un outil que sa documentation déconseille ainsi (Serena) ; commande qui exige `sudo`.

## 5. Spec Kit

### 5.1 Installation

Prérequis : `uv` sur le poste (jamais installé par PEO ; absent → action `manual` avec la commande officielle d'installation). `cli:specify-cli` est installé par `uv tool install specify-cli==<version testée>` depuis la source indiquée par la fiche.

### 5.2 Préréglage `peo`

Un préréglage Spec Kit (`presets/peo`) n'est **pas** livré au MVP : les portes sont tenues par `peo gate` et la configuration ci-dessous suffit. Il reste l'option pour P6 si des gabarits doivent changer.

### 5.3 Conventions de branches (E3)

L'extension git de Spec Kit impose que le dernier segment commence par `{number}-` **[FAIT]**. Décision du Planner selon le profil :

| `conventions.branches` | Action | Question |
|---|---|---|
| `null` (moins de 5 branches) ou motif compatible avec `{number}-{slug}` sans préfixe | rien | aucune |
| Préfixes détectés, et `<prefix>/{number}-{slug}` respecte le motif détecté | Écrire `branch_prefix: "<préfixe de feat>"` dans `.specify/extensions/git/git-config.yml` (fichier possédé) | aucune ; hypothèse au tour 1 |
| `id_style = "alnum-id"` (identifiants de feuille de route dominants) | Selon `q.branch_convention` | `q.branch_convention` |

Options de `q.branch_convention` :

1. **Garder les préfixes, numéroter à la Spec Kit** (`feat/001-slug`) — recommandé : aucune interruption de l'outil.
2. **Garder les identifiants du projet** : désactiver l'extension git de Spec Kit (`specify extension disable git`) ; `peo flow start feature <slug> --id A7` crée la branche `feat/A7-<slug>` ; Spec Kit crée seulement le dossier `specs/NNN-<slug>`, relié par `.specify/feature.json`. Coût : l'identifiant du dossier et celui de la branche diffèrent.

Pour ÉPURE, le motif mesuré est `^(feat|fix)/[A-Za-z0-9-]+$` avec `id_style = "mixed"` (document 12, section 4.1) : deuxième ligne du tableau, `branch_prefix: "feat"`, **aucune question**.

Branches de correction : la recette `bugfix` en piste S ne passe pas par `specify` ; `peo flow start bugfix <slug>` crée `fix/<slug>` (premier préfixe détecté contenant « fix », sinon `fix`).

## 6. Fichiers gérés (Composer)

### 6.1 JSON (`.claude/settings.json`, `.mcp.json`)

- Analyse stricte. Fichier invalide → arrêt avec action `manual` (jamais de réécriture d'un fichier qu'on ne comprend pas).
- Fusion profonde par clé ; ordre des clés existantes conservé ; nouvelles clés ajoutées à la fin ; indentation détectée (2 espaces par défaut) ; saut de ligne final conservé.
- Tableaux de hooks : les entrées de PEO sont reconnues par leur commande (`peo gate`, `peo context`) ; elles sont remplacées en place, jamais dupliquées ; les autres entrées sont intactes.
- `permissions` : une seule modification, possédée : ajout de `Bash(peo flow approve:*)` et `Bash(peo flow override:*)` à `permissions.ask` (document 15, section 4.1 bis). Rien d'autre.
- Possession : chemins JSON (`hooks.PreToolUse[command=peo gate]`) avec l'empreinte de la valeur écrite.

### 6.2 Blocs gérés

```markdown
<!-- peo:begin id=agents-md v=1 sha=<empreinte du contenu> -->
…contenu généré…
<!-- peo:end id=agents-md -->
```

Variantes de commentaire : `#` pour YAML et `.gitignore`. Règles :

- PEO n'écrit qu'entre ses marqueurs. Contenu extérieur intact, octet pour octet (test).
- Bloc modifié à la main (empreinte différente) : régénération refusée sans `--force-block <id>` ; `status` le signale.
- Bloc absent : ajouté à la fin du fichier, précédé d'une ligne vide.

### 6.3 `AGENTS.md`

Créé s'il n'existe pas, sinon bloc géré ajouté. Contenu du bloc (au plus 60 lignes) :

1. Mission (réponse `q.mission`).
2. Composants : chemin, stacks, `runtime`, commandes `test`, `lint`, `verify` (préfixées par le runtime).
3. Processus : socle, recettes, portes actives, commande `/peo:flow`.
4. Emplacements de connaissance (`[knowledge]` du socle, surchargés par `peo.toml`).
5. Pointeur vers `.peo/README.md`.

Aucune règle du projet n'est réécrite dans ce bloc.

### 6.4 `CLAUDE.md` (E4, décision S-3)

| Situation | Action par défaut |
|---|---|
| Absent | Créer : `@AGENTS.md` + bloc géré `claude-md` (2 à 5 lignes : commandes `/peo:*` utiles) |
| `pointer` ou `thin` | Ajouter `@AGENTS.md` en première ligne s'il manque + bloc géré |
| `rich` | **Conserver** le contenu. Ajouter `@AGENTS.md` en première ligne s'il manque + bloc géré. Proposer la migration seulement si `q.claude_md = migrate` |

Migration (option) :

1. Découper `CLAUDE.md` en unités : sections de titre, éléments de liste de premier niveau, paragraphes, blocs de code.
2. Classer chaque unité, de façon déterministe : `path-scoped` (cite un chemin, une extension, un nom de fichier ou de composant présent dans le profil) → `.claude/rules/<composant ou thème>.md` avec `paths:` en tête ; `command` (bloc de code ou ligne de commande) → section Commandes d'`AGENTS.md`, hors bloc géré ; `context` (le reste) → `AGENTS.md`, hors bloc géré.
3. Présenter le **tableau de correspondance** dans le plan : unité (30 premiers caractères), classe, destination. L'humain peut corriger une ligne (la skill transmet la correction dans `answers['q.claude_md.mapping']`).
4. **Invariant vérifié avant écriture** : le multiensemble des unités normalisées (espaces réduits) en sortie est égal à celui en entrée. Sinon arrêt. Aucune règle ne disparaît, aucune n'est dupliquée.
5. Nouveau `CLAUDE.md` : `@AGENTS.md`, le bloc géré, et une ligne qui renvoie vers `.claude/rules/`. L'ancien est dans la sauvegarde.

Les principes qui relèvent de la constitution de Spec Kit **ne sont pas copiés** dans `.specify/memory/constitution.md` : PEO les liste dans `.peo/README.md` (« à considérer lors de `/speckit-constitution` ») avec un lien vers leur emplacement. Une règle n'a qu'un emplacement.

### 6.5 `.gitignore`, `.gitattributes`

Bloc géré `.gitignore` : `.peo/backups/`. Bloc géré `.gitattributes` : `.peo/history.ndjson merge=union`.

### 6.6 Cible `verify` (réponse `q.verify_cmd = make-verify`)

Bloc géré `verify` dans le `Makefile` racine (créé s'il n'existe pas) : une cible `verify` qui enchaîne, par composant, `typecheck`, `lint` et `test` connus, préfixés par le runtime. Une commande `test` d'un composant marqué `no-tests:<composant>` est omise et signalée. Pour ÉPURE : `npm run typecheck`, `npm test`, `docker compose exec -T api vendor/bin/pint --test` ; `php artisan test` est ajouté quand le premier test backend existera (`peo status` le rappelle). Les tests de bout en bout (`test:e2e`) n'en font pas partie : trop lents pour une porte locale.

### 6.7 CI (`ci-check`, décision S-4)

| Cible | Fichier | Contenu du bloc |
|---|---|---|
| GitLab | `.gitlab-ci.yml` (créé si `q.ci = gitlab` et absent) | jobs `peo-status` (`peo status --ci`) et, par fiche `ci-check` retenue, le job de la fiche (ex. `semgrep scan --config auto --error`) |
| GitHub | `.github/workflows/peo.yml` (fichier entier possédé) | idem en GitHub Actions |

Les versions des images ou actions utilisées sont **épinglées** dans les fiches.

## 7. Lock et journal (F8)

Schémas : [schemas/lock.schema.json](schemas/lock.schema.json), [schemas/history-event.schema.json](schemas/history-event.schema.json).

- Le lock est **réécrit entièrement** à la fin de chaque `apply` réussi ou partiel, trié par référence.
- `owns` est obligatoire pour chaque outil dont PEO a écrit quelque chose ; vide pour un outil seulement réutilisé (`reused: true`).
- Le journal est en ajout seul ; une ligne par action et par commande humaine (`flow approve`, `tools disable`) ; `actor` = `peo-cli` ou l'auteur git ; `plan` = empreinte.
- `merge=union` évite les conflits entre branches ; un événement en double après fusion est toléré (le lecteur déduplique par `(ts, action, tool, file)`).

## 8. Retrait et mise à jour

### 8.1 `tools remove` (F12)

1. `owned()` : possessions encore intactes (empreinte égale à celle du lock).
2. Possessions modifiées depuis : action `manual` (« clé modifiée à la main, à retirer par toi »).
3. Outil installé hors PEO (absent du lock) : retrait **refusé** au MVP (R4) ; la commande native est affichée.
4. Recettes impactées : étapes dont la capacité ne serait plus couverte, affichées avant l'accord.
5. Fichiers que l'outil écrit dans le dépôt (`surface.writes`, ex. `.serena/`) : jamais supprimés.

### 8.2 `tools update --plan` (F13)

Pour chaque outil du lock dont `versions.tested` du catalogue diffère : version actuelle → version testée, et **différence de surface** (hooks ajoutés ou retirés, nombre d'outils MCP, `network`, `write_tools` ajoutés — qui changeraient le `matcher` de la porte). Rien n'est appliqué au MVP.

## 9. Doc générée `.peo/README.md` (F9)

Sections : Projet (mission, composants), Outils retenus (raison de chaque, tirée de `selection`), Outils écartés (raison), Processus (recettes, portes, commandes), Commandes du projet, Ce qui reste à faire à la main, Notes. La section **Notes** est délimitée et préservée à la régénération. Langue : `project.languages.artifacts`.

## 10. Plan attendu pour ÉPURE

Exemple complet : [schemas/examples/plan.epure.json](schemas/examples/plan.epure.json). Rendu par la skill :

```text
Prérequis           + intelephense 1.x (npm -g)                                    R3  php-lsp a besoin du serveur
                    ? backend/vendor absent : docker compose exec api composer install   (manuel, non bloquant)
Outils du poste     + specify-cli <version testée> (uv tool)                       R3
Spec Kit            + specify init --here --integration claude (no model invocation)    R2
                    + .specify/extensions/git/git-config.yml  branch_prefix: feat  R1  convention feat/ conservée
Plugins (projet)    + egm@egm   + mattpocock-skills   + typescript-lsp   + php-lsp       R3
Fichiers            + AGENTS.md (bloc géré)                                       R1
                    ~ CLAUDE.md  @AGENTS.md en tête + bloc géré ; contenu conservé  R1
                    ~ .claude/settings.json  hooks peo gate / peo context        R2
                    ~ README.md   « backend à venir » corrigé (réponse q.docs_drift)    R1
                    ~ HANDOFF.md  → docs/archive/HANDOFF.md                       R1
                    ~ .gitignore  ~ .gitattributes                                R1
                    ~ Makefile    cible verify en bloc géré (réponse q.verify_cmd)  R1
CI                  + .gitlab-ci.yml  peo-status + semgrep (réponse q.ci)         R1
PEO                 + .peo/peo.toml  profile.json  peo.lock.json  history.ndjson  README.md
Réutilisé           = Playwright (@playwright/test) pour browser.e2e
À faire par toi     /reload-plugins · /setup-matt-pocock-skills · /speckit-constitution · docker compose exec api composer install
```

Différence avec le document 09 : `CLAUDE.md` n'est plus migré d'office (S-3) ; les 9 règles du front restent où elles sont.
