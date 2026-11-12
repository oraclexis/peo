# 12 — Discovery (F1)

Discovery lit le dépôt **sans LLM, sans réseau, sans rien écrire** (sauf `--write`) et produit `profile.json` ([schéma](schemas/profile.schema.json)). Chaque information porte une **confiance** et une **preuve**. C'est ce qui permet au questionnaire de ne jamais demander ce qui se lit.

## 1. Sources lues

| Source | Comment | Limites |
|---|---|---|
| Fichiers suivis | `git ls-files -z` ; hors git : parcours avec exclusions | Exclusions fixes : `.git`, `node_modules`, `vendor`, `dist`, `build`, `.nuxt`, `.output`, `.venv`, `target`, `coverage` |
| Historique | `git rev-list --count HEAD`, `git for-each-ref refs/heads refs/remotes`, `git log -200 --format=%s` | Pas de lecture du contenu des commits |
| Manifestes | Table 2.1 | JSON et TOML analysés ; YAML lu par motifs ligne à ligne (pas de bibliothèque YAML, NF1) |
| Docker | `docker-compose*.yml`, `compose*.yaml` | Seuls `services.<nom>.build.context` et `volumes` (forme courte) sont lus |
| Documentation | `README*`, `CLAUDE.md`, `AGENTS.md`, `HANDOFF*`, `docs/**/*.md` (200 fichiers au plus, 1 Mo au plus chacun) | |
| Inventaire | Résultat de l'Inventory (document 14, section 3) | Lu, pas recalculé |
| Surfaces sensibles (ajout du 2026-11-12) | Parcours de l'arbre de travail jusqu'à la profondeur 3, hors exclusions fixes, **fichiers suivis ou non** (un `.env` est presque toujours ignoré par git) ; motifs de la section 7 bis | Noms de fichiers ; contenu lu seulement pour les noms de variables des `.env*` (NF14) |

Taille des fichiers lus : 1 Mo au plus ; au-delà, fichier compté mais non analysé. Fichiers binaires (octet nul dans les 8 premiers ko) ignorés.

## 2. Composants (E1)

### 2.1 Manifestes reconnus

| Manifeste | Écosystème | Stacks déduites (exemples, liste complète dans `discovery/stacks.toml`) |
|---|---|---|
| `package.json` | node | `nuxt`, `next`, `vue`, `react`, `nestjs`, `express`, `vite`, `tailwind`, `threejs`, `vitest`, `jest`, `playwright`, `eslint`, `typescript` |
| `composer.json` | php | `php-laravel`, `filament`, `symfony`, `phpunit`, `pest`, `pint`, `phpstan`, `larastan` |
| `pyproject.toml`, `requirements*.txt` | python | `django`, `fastapi`, `flask`, `pytest`, `ruff`, `mypy` |
| `go.mod` | go | `go` |
| `Cargo.toml` | rust | `rust` |
| `pom.xml`, `build.gradle*` | jvm | `java`, `kotlin`, `spring` |
| `Gemfile` | ruby | `rails` |

Une stack vient d'une ou plusieurs dépendances déclarées (dépendances et dépendances de dev confondues) : confiance `fact`, preuve `"<manifeste>: <paquet>[, <paquet>…]"`, avec tous les paquets qui déclenchent la stack, triés, sans contrainte ni section (ex. `package.json: typescript, vue-tsc`, `backend/composer.json: laravel/framework`). Le chemin du manifeste est relatif à la racine du dépôt.

Version (révisée le 2026-11-12, P1.3) : seules les stacks de framework, marquées `versioned = true` dans `discovery/stacks.toml` (`nuxt`, `next`, `vue`, `react`, `nestjs`, `php-laravel`, `filament`, `symfony`, `django`, `fastapi`, `rails`, `spring`), reçoivent une version, tirée de la contrainte **de leur propre paquet** quand elle est univoque (`^11.0` → 11, `~3.5` → 3) ; sinon, stack sans version. Les outils (tests, linters, `typescript`) n'ont pas de version : aucune fiche ne la lit.

Les stacks d'un composant viennent **seulement** de ses manifestes. Une base de données d'un fichier compose n'est pas une stack : elle est décrite par `sensitive.data_stores` (section 7 bis).

Ordre des stacks : celui de `discovery/stacks.toml`, qui suit l'ordre de la table ci-dessus.

Stacks de manifeste (`go`, `rust`, `java`) : présentes dès que le manifeste existe, sans version ; preuve = chemin du manifeste (ex. `go.mod`). Les noms de dépendances sont comparés en minuscules ; pour Python, `_` et `.` valent `-`. Dans `composer.json`, `php` et `ext-*` ne sont pas des dépendances.

### 2.2 Algorithme

1. Collecter les manifestes jusqu'à une profondeur de 3, hors exclusions. Profondeur = nombre de dossiers dans le chemin du manifeste : `package.json` 0, `backend/composer.json` 1, `apps/web/package.json` 2.
2. Ajouter les espaces de travail déclarés (`workspaces` de `package.json`, `packages:` de `pnpm-workspace.yaml`, `[tool.uv.workspace]`) : chaque membre qui contient un manifeste de la table 2.1 est un composant. Le manifeste qui **déclare** les espaces de travail (ou qui est à côté de `pnpm-workspace.yaml`) n'ouvre pas de composant à lui seul.
3. Un dossier qui contient au moins un manifeste de la table 2.1 est un **composant**. Plusieurs manifestes dans le même dossier : un seul composant multi-écosystème.
4. Un `package.json`, un `composer.json` ou un `pyproject.toml` sans dépendance ni script (ex. `package.json` réduit à un nom) n'ouvre pas de composant. Pour `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle*`, `Gemfile` et `requirements*.txt`, la présence du manifeste suffit.
5. Identifiant : `root` pour `.`, sinon le chemin avec `/` remplacé par `-` (`backend`, `apps-web`).
6. `paths.code` du composant : un motif par extension de code **présente** dans ses fichiers (hors composants imbriqués), dans l'ordre de la table des langages (règle 7) : `**/*.<ext>` pour `root`, `<chemin>/**/*.<ext>` sinon ; puis, triés, les motifs négatifs `!<dossier>/**` des composants imbriqués (ex. racine de `fx-split-stack` : `**/*.vue`, `**/*.ts`, `**/*.css`, `!backend/**`).
7. `languages` : langages dont le composant a au moins 50 lignes non vides, dans l'ordre de la table des langages : `typescript` (`.vue`, `.ts`, `.tsx`), `javascript` (`.js`, `.jsx`, `.mjs`, `.cjs`), `css` (`.css`, `.scss`), `php` (`.php`), `python` (`.py`), `go` (`.go`), `rust` (`.rs`), `java` (`.java`), `kotlin` (`.kt`, `.kts`), `ruby` (`.rb`). Les `ecosystems` suivent l'ordre de la table 2.1.
8. `kind` : `frontend` si une stack de rendu (`nuxt`, `next`, `vue`, `react`, `vite`) sans stack serveur ; `backend` si une stack serveur (`php-laravel`, `symfony`, `nestjs`, `express`, `django`, `fastapi`, `spring`, `rails`) ; `fullstack` si les deux ; sinon `library`.
9. `multi_component = true` dès deux composants ; `monorepo = true` si, en plus, un outil d'espace de travail est présent (`workspaces`, pnpm, turbo, nx, lerna, uv workspace). Un seul composant : les deux valent `false`.
10. Ordre de sortie : `root` en premier, puis composants triés par identifiant.
11. Aucun composant trouvé (dépôt neuf, manifestes illisibles ou vides) : un seul composant `root` (`.`), sans écosystème ni stack, `kind = library` ; ses `languages` et `paths.code` suivent les règles 6 et 7 ; `runtime = host`, confiance `unknown`, preuve `"no manifest"`. Un dépôt a toujours au moins un composant (spec 10, glossaire).

### 2.3 Environnement d'exécution (E5)

Pour chaque composant :

| Condition | `runtime` | Confiance |
|---|---|---|
| Un service compose a `build.context` ou un volume `./<chemin>:` égal au dossier du composant, **et** le binaire principal de l'écosystème (`php`, `python3`, `go`, `cargo`, `java`, `ruby`) est absent du `PATH` | `docker:<service>` | `fact` |
| Même service compose, binaire présent sur le poste | `docker:<service>` | `likely` (question si une fiche en dépend) |
| Pas de service compose correspondant | `host` | `fact` si le binaire est présent, sinon `unknown` |
| Écosystème node **seul** : un service compose construit le dossier et `node` est absent | `docker:<service>` | `fact` |
| Écosystème node seul : sinon | `host` | `fact` si `node` est présent, sinon `unknown` |

Le binaire est cherché sans l'exécuter (`shutil.which`, injectable pour les tests). Pour un composant multi-écosystème, le binaire principal est celui du premier écosystème dans l'ordre de la table 2.1, et c'est la règle générale (construction **ou** montage) qui s'applique, pas la ligne node. Plusieurs services correspondants : le premier dans l'ordre du fichier. Fichiers lus : `docker-compose*.yml`, `docker-compose*.yaml`, `compose*.yml`, `compose*.yaml` à la racine, triés.

Format des preuves :

- service correspondant : `"<fichier>: <service> build.context <ctx>, volume <hôte>:<cible>; <bin> on PATH"` (les parties `build.context` et `volume` n'apparaissent que si elles correspondent ; plusieurs volumes séparés par `, `) ; `not on PATH` si le binaire est absent ;
- aucun service, node seul : `"no compose service builds '<chemin>'; node [not ]on PATH"` ;
- aucun service, autres cas : `"no compose service builds or mounts '<chemin>'; <bin> [not ]on PATH"`.

Le `runtime` préfixe les commandes : `docker compose exec -T <service> <commande>` (`-T` : sans pseudo-terminal, pour que la commande marche depuis un hook ou en CI ; précisé le 2026-11-12, P1.4). Un environnement `host` ou `unknown` ne préfixe rien.

## 3. Commandes

Sources, par priorité, pour chaque composant :

| Rôle | Sources | Confiance |
|---|---|---|
| `typecheck`, `test`, `lint`, `build`, `e2e`, `format` | Scripts de `package.json` (`test`, `test:e2e`, `typecheck`, `lint`…) ; scripts de `composer.json` ; `[tool.*.scripts]` ou `Makefile` | `fact` si le script existe |
| `test` sans script | `php artisan test` si `artisan` et PHPUnit ou Pest ; `pytest` si pytest déclaré | `likely`, preuve « framework déclaré, pas de script » |
| `lint` sans script (ajout du 2026-11-12) | Linter déclaré, dans l'ordre : `pint` → `vendor/bin/pint --test` ; `phpstan` → `vendor/bin/phpstan analyse` ; `eslint` → `npx eslint .` ; `ruff` → `ruff check .` | `likely`, preuve `"<stack> declared"` |
| `verify` (agrégée) | Cible `verify` ou `check` d'un `Makefile` racine ; script `verify` racine | `fact` ; sinon `unknown` |

Précisions du 2026-11-12 (P1.4) :

- **Ordre des sources** : script du manifeste, puis cible du `Makefile` du composant (`make <cible>` ; cibles = lignes `^([A-Za-z0-9_.-]+)\s*:` non suivies de `=`, hors `.PHONY` et cibles commençant par `.`), puis repli (`test` ou `lint` sans script).
- **Noms reconnus** : `typecheck` (scripts `typecheck`, `type-check`), `test` (`test`), `e2e` (`test:e2e`, `e2e`), `lint` (`lint`), `build` (`build`), `format` (`format`). Un script `test` vide ou égal au gabarit de npm (`echo "Error: no test specified" && exit 1`) est ignoré.
- **Forme des commandes** : node selon le fichier de verrouillage du dépôt (`pnpm-lock.yaml` → `pnpm`, `yarn.lock` → `yarn`, sinon `npm`) : `<pm> test` pour `test`, `<pm> run <script>` pour les autres ; `composer.json` : `composer <script>` ; `Makefile` : `make <cible>`. Préfixe de l'environnement d'exécution (section 2.3), jamais pour `verify` ni pour les commandes du `Makefile` racine.
- **Rôles sans source** : `test` et `lint` sont **toujours** présents (`value: null`, `unknown`) ; les autres rôles n'apparaissent que s'ils ont une source.
- **Preuves** : script → `"<manifeste> scripts.<nom>"` ; cible → `"<Makefile> target <cible>"` ; `test` de repli → `"<stack> declared, artisan present, no test script"` ou `"pytest declared, no test script"` ; `lint` de repli → `"<stack> declared"` ; `test` absent → `"no test script, no test framework declared"` ; `lint` absent → `"no <linters de l'écosystème, séparés par '/'>, no lint script"` (ex. `no eslint, no lint script` ; écosystème sans linter connu ou composant sans écosystème : `no lint script`) ; `verify` absent → `"no verify/check target in Makefile"` si un `Makefile` racine existe, sinon `"no Makefile, no verify script"`.

La lacune `no-tests:<composant>` est ajoutée quand le composant n'a **aucun fichier de test** (`*.spec.*`, `*.test.*`, `test_*.py`, `*_test.py`, `*_test.go`, `*Test.php`, ou tout fichier sous un dossier `tests/`, `test/`, `__tests__/`, `spec/`), sans changer la commande. La lacune `no-lint:<composant>` est ajoutée quand `lint` vaut `null`.

## 4. Conventions (E3)

### 4.1 Branches

1. Noms courts des branches locales et distantes, hors `main`, `master`, `develop`, `HEAD`. Pour une branche distante, le nom du dépôt distant est retiré (`origin/feat/x` → `feat/x`) ; `origin/HEAD` et le nom seul du dépôt distant sont ignorés ; les noms sont dédoublonnés.
2. Si moins de 5 branches : `conventions.branches = null` (valeur inconnue).
3. Préfixes = segment avant le premier `/`. Si au moins 80 % des branches ont un préfixe, et que les préfixes distincts sont au plus 5 : `prefixes` triés, motif `^(<p1>|<p2>…)/<alphabet>$` ; sinon `prefixes = []` et motif `^<alphabet>$`.
4. Style d'identifiant du dernier segment, testé dans cet ordre : `timestamp` (`^[0-9]{8}-[0-9]{6}-`), `numeric` (`^[0-9]{3,}-`), `alnum-id` (`^[A-Za-z]+[0-9]+-`), `free` (le reste). `id_style` = le style dont la part atteint 80 %, sinon `mixed` ; `id_shares` (seulement pour `mixed`) donne la part de chaque style présent, arrondie à 2 décimales.
5. Le motif généré n'impose que ce qui est respecté à 80 % : préfixes et alphabet du dernier segment. Alphabet = la plus petite classe de l'échelle `[a-z0-9-]+`, `[A-Za-z0-9-]+`, `[A-Za-z0-9._-]+`, `.+` respectée par au moins 80 % des derniers segments. `share` = part des noms qui respectent le motif (2 décimales) ; preuve `"<n> of <m> branches outside main"`.
6. Sortie (valeurs mesurées sur le pilote n°1 le 2026-11-11, reprises par `fx-split-stack`) :

```json
"branches": { "prefixes": ["feat", "fix"], "id_style": "mixed",
              "id_shares": { "alnum-id": 0.52, "free": 0.48 },
              "pattern": "^(feat|fix)/[A-Za-z0-9-]+$",
              "share": 1.0, "confidence": "fact", "evidence": "46 of 46 branches outside main" }
```

**Enseignement du pilote** : le document 09 décrivait la convention comme `feat/<id>-<slug>`. La mesure montre que seule la moitié des branches porte un identifiant de feuille de route (`A1`, `E3`…) ; l'autre moitié est `feat/<slug>`. Le motif réellement respecté est `^(feat|fix)/[A-Za-z0-9-]+$`, que le format de Spec Kit `feat/001-<slug>` **respecte**. Il n'y a donc pas de conflit à arbitrer pour le pilote n°1 (document 14, section 5.3).

### 4.2 Commits

Sujets des 200 derniers commits, **hors commits de fusion** (sujets commençant par `merge`, `Merge`, ou commits à plusieurs parents). `style = "conventional"` si au moins 80 % des sujets restants respectent `^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?!?: `. Langue : comptage de mots outils (`le, la, les, des, du, pour, avec, ajout` contre `the, for, with, add, update`) sur la partie après les deux-points ; écart d'au moins 2 contre 1, sinon `unknown`.

Précisions du 2026-11-12 (P1.4) : `style = free` sous 80 %, `unknown` sans aucun sujet ; pour un sujet conventionnel, seuls les mots après `: ` comptent pour la langue ; une langue est retenue si elle a **au moins 2** mots-outils **et** au moins le double de l'autre, sinon `unknown` ; `share` = part des sujets conventionnels (2 décimales) ; `excluded_merges` = fusions exclues ; preuve `"<n> of <m> non-merge subjects"`. Hors git : `style`, `language` et `confidence` valent `unknown`.

**Enseignement du pilote** : le pilote n°1 fusionne avec des sujets `merge: …` (46 sur 93). Sans l'exclusion des fusions, la part conventionnelle tombe à 51 % et le style serait mal détecté ; avec, elle est de 47 sur 47.

### 4.3 Dépôt (`kind`, `git`, `ci` ; ajout du 2026-11-12, P1.4)

| Champ | Règle | Confiance, preuve |
|---|---|---|
| `kind` | `new` si le dépôt a au plus 1 commit (`git rev-list --count HEAD`), sinon `existing` ; dépôt git sans commit (`rev-list` en échec) : `new` ; hors git : `new` | `fact`, `"<n> commits"` (`"0 commits"` sans commit) ; hors git : `likely`, `"not a git repository"` |
| `git.remote` | Au moins un dépôt distant (`git remote`) | — |
| `git.default_branch` | Cible de `refs/remotes/origin/HEAD` si elle existe (sans le nom du dépôt distant), sinon branche courante (`git symbolic-ref --short HEAD`) ; hors git : **absent** (le schéma n'accepte pas `null`) | — |
| `ci.kind`, `ci.file` | `.gitlab-ci.yml` → `gitlab` ; sinon premier fichier trié de `.github/workflows/*.yml` ou `*.yaml` → `github` ; sinon `none` et `null` | — |

## 5. Documentation et agents

| Champ | Règle |
|---|---|
| `docs.readme` | `true` si un `README*` existe à la racine (ajout du 2026-11-12) |
| `docs.claude_md` | `absent` si le fichier n'existe pas ; sinon `rich` dès que `rules_count` ≥ 5, quelle que soit la longueur ; sinon `pointer` (au plus 20 lignes non vides **et** au moins un import `@`), `thin` (au plus 20 lignes non vides), `rich` (au-delà). Tous les seuils se comptent en lignes non vides. Plus `lines` (lignes non vides) et `rules_count` (éléments de liste de premier niveau) |
| `docs.agents_md` | booléen |
| `docs.handoff` | chemin d'un `HANDOFF*.md` s'il existe |
| `docs.adr` | premier de `docs/adr/`, `docs/decisions/`, `adr/` qui contient un fichier suivi ; valeur = chemin sans `/` final (`docs/adr`), sinon `null` |
| `intent_from_docs` | Outils dont un nom de `discovery/intents.toml` est cité dans `README*` ou `docs/**/*.md` (comparaison sans casse, mot entier) : `tool` = identifiant de fiche, confiance `likely`, preuve `"<fichier>:<ligne> mentions <nom>"` à la première citation ; un outil une seule fois ; liste triée par `tool`. La table est limitée aux outils du catalogue initial (spec 13 §5) et sera remplacée par les noms des fiches en R3 (précisé le 2026-11-12, P1.5) |

## 6. Dérive documentaire (E2)

Détection **déterministe, présentée comme hypothèse** (confiance `likely`), jamais corrigée automatiquement. Chaque constat devient au plus une question « je le traite comment ? » (document 13, banque de questions).

| Règle | Détecte | Méthode |
|---|---|---|
| **D1 — Annonce périmée** | Ligne qui porte un marqueur (« à venir », « TODO », « pas encore », « coming soon », « not yet », « WIP »), **ou** case non cochée `- [ ]`, **ou** ligne d'une section dont le titre porte un marqueur, **et** qui cite un chemin ou un nom de fichier **qui existe** (nom seul résolu sur les fichiers suivis) | Marqueurs dans `drift_markers` (fr, en) ; jetons de chemin `[\w./-]+\.(vue\|ts\|php\|py\|…)` ou noms de dossiers de composants ; résolution par `git ls-files` |
| **D2 — Commande fantôme** | `npm run X`, `make X`, `composer X` documentés alors que `X` n'existe pas dans le manifeste ou le `Makefile` (`php artisan X` n'est **pas** vérifié : il faudrait exécuter du code du projet) | Extraction dans les blocs de code et le texte inline |
| **D3 — Chemin fantôme** | Chemin cité dans la doc qui n'existe pas | Jetons de chemin relatifs contenant au moins un `/` |
| **D4 — Document de passation daté** | `HANDOFF*.md` dont la dernière modification git précède de plus de 20 commits le dernier commit touchant un fichier qu'il cite | `git log -1 --format=%H -- <fichier>` et comptage |

Faux positifs attendus : un « TODO » qui parle d'une amélioration future d'un fichier existant. C'est pour cela que la dérive est une hypothèse posée à l'humain et non un fait.

Précisions du 2026-11-12 (P1.5) :

- **Marqueurs D1**, dans cet ordre (le premier trouvé sur la ligne, ou dans le titre de sa section, est cité) : `- [ ]`, `TODO`, `WIP`, `à venir`, `pas encore`, `coming soon`, `not yet` ; comparaison sans casse. Une ligne donne au plus un constat D1.
- **Résolution d'un nom seul** (`ContentBlock.vue`) : premier fichier suivi, par ordre trié, dont le nom est égal.
- **Messages** (gabarits fixes) : D1 `"Line marked '<marqueur>' cites <jeton>, which exists (<chemin>)"` ; D2 `"Command '<commande>' is documented but not defined in <manifeste>"` ; D3 `"Path <jeton> does not exist"` ; D4 `"Last changed <n> commits before HEAD while files it cites changed since"`, où `<n>` est le nombre de commits depuis la dernière modification du document. Aucun indice supplémentaire.
- **D2** : commandes `npm run X`, `pnpm run X`, `yarn X`, `make X`, `composer X` ; `X` cherché dans les scripts du manifeste racine ou les cibles du `Makefile` racine.
- **Jetons** : nom de fichier `[\w.-]+\.(<ext>)`, extensions de la table des langages (§2.2 règle 7) plus `md`, `json`, `toml`, `yml`, `yaml` ; chemin `[\w.-]+(?:/[\w.-]+)+/?` non précédé de `/`, `:` ou d'un caractère de mot, les URL (`…://…`) étant retirées de la ligne avant l'analyse ; dossier de composant (hors `root`) en mot entier. Un chemin existe s'il est un fichier suivi ou le préfixe d'un fichier suivi (dossier).
- **D2** : sous-commandes intégrées ignorées : `yarn install|add|remove|upgrade|init|dlx|why|info`, `composer install|require|update|remove|show|outdated|dump-autoload|create-project`.
- **D3** : jetons de chemin relatifs contenant un `/`, hors URL et hors chemins absolus.
- **Ordre** : constats triés par règle, puis fichier, puis ligne (D4 sans ligne).
- **Hors git** : pas de D4.

## 7. Signaux

Décision S-5 : un signal n'est calculé que si une fiche, une recette ou une question le référence. Signaux du MVP :

| Signal | Règle | Référencé par |
|---|---|---|
| `auth` | Dépendance parmi `keycloak*`, `laravel/socialite`, `laravel/passport`, `laravel/sanctum`, `next-auth`, `@nestjs/passport`, `passport`, `openid-client`, `authlib`, `django-allauth` ; ou mention « Keycloak », « OIDC », « SSO » dans la doc (`likely`) | `claude-plugin:security-guidance`, `ci-check:semgrep` |
| `public_surface` | Routes ou pages de formulaires (`<form`, `FormRequest`, `@Post(`) dans le code, ou mention « formulaire », « contact », « API publique » dans la doc (`likely`) | `ci-check:semgrep` |
| `frontend_heavy` | Au moins une bibliothèque de rendu riche (`three`, `gsap`, `pixi.js`, `@react-three/fiber`) ou plus de 40 % des lignes en `.vue`, `.tsx`, `.jsx` | `vendored-skill:ui-ux-pro-max` |
| `design_rules_in_instructions` | `CLAUDE.md` ou `AGENTS.md` contient au moins 3 règles citant `border-radius`, `couleur`, `color`, `token`, `font`, `typographie`, `spacing` | `vendored-skill:ui-ux-pro-max` (`when.not`) |

Précisions du 2026-11-12 (P1.6) :

- **Sources des mentions** : `README*` puis `docs/**/*.md` (mêmes fichiers et limites que `intent_from_docs`), lus dans l'ordre ; la première ligne qui contient un terme du signal (sans casse, mot entier) est citée, avec le terme tel qu'il est écrit dans la ligne. Termes : `auth` → `Keycloak`, `OIDC`, `SSO` ; `public_surface` → `formulaire`, `contact`, `API publique`, `public API`, `contact form`.
- **Indice dans le code de `public_surface`** : `<form`, `FormRequest`, `@Post(` dans un fichier de code suivi → `fact`, preuve `"<fichier>:<ligne> contains <motif>"` (premier fichier trié).
- **Confiance et preuves** : dépendance → `fact`, `"<manifeste>: <paquet>[, <paquet>…]"` (comme les stacks) ; mention dans la doc → `likely`, `"<fichier>:<ligne> mentions <terme>"` ; part des lignes de rendu → `fact`, `"<n>% of code lines in .vue/.tsx/.jsx"` (entier arrondi) ; règles de design → `fact`, `"<fichier>: <n> design rules"` (éléments de liste de premier niveau, comme `rules_count`). Ordre de priorité : dépendance ou code, puis mention.
- **Aucun indice** : `value = false`, `fact`, preuve `"no <signal> indicator"` (ex. `no auth indicator`).

Mesures (`metrics`, toujours calculées, coût négligeable) : `commits` (`git rev-list --count HEAD`), `tracked_files`, `loc` **par extension** (clé = extension sans point, lignes non vides des fichiers de code suivis dont l'extension est dans la table des langages ; précisé le 2026-11-12 : le fichier attendu et A0.1 comptent par extension) et `loc_total`, `contributors` (adresses d'auteur distinctes, `git log --format=%ae`). Hors git : `commits` et `contributors` valent 0. `loc_total` est lu par `mcp:serena` et `cli:graphify`.

## 7 ter. Outils présents (`present_tools`, ajout du 2026-11-12)

Outils du catalogue déjà présents dans le projet sous une autre forme (E6). Jusqu'à R3, les règles de détection viennent de la table provisoire `discovery/detect.toml` (règles `[detect]` des fiches du catalogue initial, spec 13 §5) ; elle sera remplacée par les fiches. Discovery ne détecte que ce qui se lit dans le dépôt : dépendances déclarées (`npm`, `composer`, `pip`) → `via = "dev-dependency"`, preuve `"<manifeste> <section>: <paquet>"` (ex. `package.json devDependencies: @playwright/test`), et fichiers (`files`) → `via = "file"`, preuve = chemin. Les binaires, plugins et serveurs MCP relèvent de l'Inventory (R2). Une entrée par outil et par composant, triée par `ref` puis `component`.

## 7 bis. Surfaces sensibles (`sensitive`, ajout du 2026-11-12)

Section toujours calculée : `peo status --exposure` (F14) la consomme (S-5 élargie). Elle décrit **où** sont les données à protéger, jamais **ce qu'elles contiennent** (NF14, H24). `data_stores` est trié par `source` puis `service`, les autres listes par `path`. Motifs et correspondances d'images dans `discovery/sensitive.toml`.

| Champ | Motifs | Ce qui est lu | Champs produits |
|---|---|---|---|
| `secret_files` | `.env`, `.env.*` **sauf** `.env.example`, `.env.sample`, `.env.template`, `.env.dist` ; `*.pem`, `*.key`, `*.p12`, `*.pfx`, `credentials*.json`, `id_rsa*`, `id_ed25519*` | `.env*` : pour chaque ligne `[export ]NOM=…`, le seul `NOM` s'il respecte `^[A-Za-z_][A-Za-z0-9_]*$` ; le reste de la ligne est ignoré dès la lecture. Autres motifs : rien (nom de fichier seulement) ; au plus 200 noms par fichier | `path`, `tracked` (`git ls-files --error-unmatch`), `variables` (triés, uniques ; liste vide hors `.env*`) |
| `data_stores` | Services de `docker-compose*.yml`, `compose*.yaml` dont `image` commence par `postgres`, `postgis/postgis` (→ `postgres`), `mysql`, `mariadb`, `mongo` (→ `mongodb`), `redis`, `valkey/valkey` (→ `redis`), `mcr.microsoft.com/mssql/server` (→ `sqlserver`), `elasticsearch`, `docker.elastic.co/elasticsearch` (→ `elasticsearch`) | La clé `image` seulement. **`environment` n'est jamais lu** (décision S-10) | `kind`, `source` (fichier compose), `service` |
| `data_dumps` | `*.sql`, `*.dump`, `*.bak`, `*.sqlite`, `*.sqlite3`, `*.db` hors dossiers de migrations (`migrations/`, `database/migrations/`) | Taille seulement | `path`, `tracked`, `bytes` |
| `log_dirs` | Dossiers nommés `logs` ou `log`, et `storage/logs` (un fichier `*.log` isolé n'est pas un dossier de logs : un chemin `.` donnerait une règle `deny` sur tout le dépôt ; précisé le 2026-11-12) | Existence seulement | `path`, `tracked` (au moins un fichier suivi dedans) |

Confiance : ces informations sont des `fact` (existence d'un fichier, clé d'un compose) ; elles ne portent pas de champ `confidence` ni d'`evidence` : le chemin est la preuve.

Valeur attendue pour `fx-split-stack` :

```json
"sensitive": {
  "secret_files": [ { "path": "backend/.env", "tracked": false,
                      "variables": ["APP_KEY", "DB_DATABASE", "DB_HOST", "DB_PASSWORD", "DB_USERNAME"] } ],
  "data_stores": [ { "kind": "postgres", "source": "docker-compose.yml", "service": "db" } ],
  "data_dumps": [],
  "log_dirs": []
}
```

## 8. Confiance

| Niveau | Quand | Effet sur le questionnaire |
|---|---|---|
| `fact` | Lu dans un manifeste, un fichier de configuration ou l'état git | Jamais demandé ; affiché dans l'hypothèse groupée du tour 1 seulement s'il influence la sélection |
| `likely` | Déduit d'un indice (doc, convention de nommage, absence de binaire) | Présenté comme hypothèse au tour 1 |
| `unknown` | Aucun indice | Question dédiée, seulement si un champ consommateur existe |

## 9. Lacunes (`gaps`)

Codes stables, utilisés par la doc générée et `status` : `no-ci`, `no-verify`, `no-tests:<composant>`, `no-lint:<composant>`, `no-remote`, `no-agents-md`, `no-adr`.

Ordre de sortie (précisé le 2026-11-12) : `no-ci`, `no-verify`, `no-remote`, `no-agents-md`, `no-adr`, puis les `no-tests:<composant>`, puis les `no-lint:<composant>`, chacun dans l'ordre des composants. Conditions : `no-ci` si `ci.kind = none` ; `no-verify` si `commands.verify` vaut `null` ; `no-remote` si `git.remote` est faux ; `no-tests` et `no-lint` : section 3 ; `no-agents-md` et `no-adr` : section 5.

## 10. Fichier attendu pour `fx-split-stack`

Le profil complet attendu est [schemas/examples/profile.split-stack.json](schemas/examples/profile.split-stack.json). Il remplace le profil simulé du document 09 (section 2) et le rend conforme au schéma. Écarts avec la simulation : `components[]` a maintenant ses commandes et ses chemins de code, `conventions.branches.id_style = "mixed"` (section 4.1), et la dérive est structurée par règle (D1, D4). Ajout du 2026-11-12 : section `sensitive` (7 bis).
