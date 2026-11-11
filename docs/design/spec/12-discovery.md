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

Taille des fichiers lus : 1 Mo au plus ; au-delà, fichier compté mais non analysé. Fichiers binaires (octet nul dans les 8 premiers ko) ignorés.

## 2. Composants (E1)

### 2.1 Manifestes reconnus

| Manifeste | Écosystème | Stacks déduites (exemples, liste complète dans `discovery/stacks.toml`) |
|---|---|---|
| `package.json` | node | `nuxt`, `next`, `vue`, `react`, `nestjs`, `express`, `vite`, `tailwind`, `threejs`, `playwright`, `vitest`, `jest`, `eslint`, `typescript` |
| `composer.json` | php | `php-laravel`, `filament`, `symfony`, `phpunit`, `pest`, `pint`, `phpstan`, `larastan` |
| `pyproject.toml`, `requirements*.txt` | python | `django`, `fastapi`, `flask`, `pytest`, `ruff`, `mypy` |
| `go.mod` | go | `go` |
| `Cargo.toml` | rust | `rust` |
| `pom.xml`, `build.gradle*` | jvm | `java`, `kotlin`, `spring` |
| `Gemfile` | ruby | `rails` |

Une stack vient d'une dépendance déclarée : confiance `fact`, preuve `"<manifeste>: <paquet> <contrainte>"`. La version majeure est extraite de la contrainte quand elle est univoque (`^11.0` → 11, `~3.5` → 3) ; sinon, stack sans version.

### 2.2 Algorithme

1. Collecter les manifestes jusqu'à une profondeur de 3, hors exclusions.
2. Ajouter les espaces de travail déclarés (`workspaces` de `package.json`, `packages:` de `pnpm-workspace.yaml`, `[tool.uv.workspace]`) : chaque membre est un composant.
3. Un dossier qui contient au moins un manifeste de la table 2.1 est un **composant**. Plusieurs manifestes dans le même dossier : un seul composant multi-écosystème.
4. Un manifeste sans dépendance ni script (ex. `package.json` réduit à un nom) n'ouvre pas de composant.
5. Identifiant : `root` pour `.`, sinon le chemin avec `/` remplacé par `-` (`backend`, `apps-web`).
6. `paths.code` du composant : motifs glob des extensions de code de son écosystème, sous son dossier ; les dossiers d'autres composants imbriqués sont exclus par un motif négatif préfixé de `!` (ex. racine de `fx-split-stack` : `**/*.vue`, `**/*.ts`, `**/*.css`, `!backend/**`).
7. `languages` : langages dont le composant a au moins 50 lignes de code (`typescript` inclut `.vue` et `.tsx`, `php`, `python`…).
8. `kind` : `frontend` si une stack de rendu (`nuxt`, `next`, `vue`, `react`, `vite`) sans stack serveur ; `backend` si une stack serveur (`php-laravel`, `symfony`, `nestjs`, `express`, `django`, `fastapi`, `spring`, `rails`) ; `fullstack` si les deux ; sinon `library`.
9. `monorepo = true` si au moins deux composants **et** un outil d'espace de travail (`workspaces`, pnpm, turbo, nx, lerna, uv workspace) ; deux composants sans outil d'espace de travail : `monorepo = false`, `multi_component = true`.

### 2.3 Environnement d'exécution (E5)

Pour chaque composant :

| Condition | `runtime` | Confiance |
|---|---|---|
| Un service compose a `build.context` ou un volume `./<chemin>:` égal au dossier du composant, **et** le binaire principal de l'écosystème (`php`, `python3`, `go`, `cargo`, `java`, `ruby`) est absent du `PATH` | `docker:<service>` | `fact` |
| Même service compose, binaire présent sur le poste | `docker:<service>` | `likely` (question si une fiche en dépend) |
| Pas de service compose correspondant | `host` | `fact` si le binaire est présent, sinon `unknown` |
| Écosystème node | `host` sauf si un service compose le construit **et** `node` est absent | |

Le binaire est cherché avec `shutil.which`, sans l'exécuter.

Le `runtime` préfixe les commandes : `docker compose exec <service> <commande>`.

## 3. Commandes

Sources, par priorité, pour chaque composant :

| Rôle | Sources | Confiance |
|---|---|---|
| `typecheck`, `test`, `lint`, `build`, `e2e`, `format` | Scripts de `package.json` (`test`, `test:e2e`, `typecheck`, `lint`…) ; scripts de `composer.json` ; `[tool.*.scripts]` ou `Makefile` | `fact` si le script existe |
| `test` sans script | `php artisan test` si `artisan` et PHPUnit ou Pest ; `pytest` si pytest déclaré | `likely`, preuve « framework déclaré, pas de script » |
| `verify` (agrégée) | Cible `verify` ou `check` d'un `Makefile` racine ; script `verify` racine | `fact` ; sinon `unknown` |

Un dossier de tests vide (aucun fichier de test) ajoute la lacune `no-tests:<composant>` sans changer la commande.

## 4. Conventions (E3)

### 4.1 Branches

1. Noms courts des branches locales et distantes, hors `main`, `master`, `develop`, `HEAD`.
2. Si moins de 5 branches : `conventions.branches = null`, confiance `unknown`.
3. Préfixes = segment avant le premier `/`. Si au moins 80 % des branches ont un préfixe, et que les préfixes distincts sont au plus 5 : motif `^(<p1>|<p2>…)/<id_part>$`.
4. Style d'identifiant du dernier segment, par part : `numeric` (`^[0-9]{3,}-`), `timestamp` (`^[0-9]{8}-[0-9]{6}-`), `alnum-id` (`^[A-Za-z]+[0-9]+-`), `free` (le reste). `id_style` = le style dont la part atteint 80 %, sinon `mixed` avec le détail des parts.
5. Le motif généré n'impose que ce qui est respecté à 80 % : préfixes et alphabet du dernier segment.
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

**Enseignement du pilote** : le pilote n°1 fusionne avec des sujets `merge: …` (46 sur 93). Sans l'exclusion des fusions, la part conventionnelle tombe à 51 % et le style serait mal détecté ; avec, elle est de 47 sur 47.

## 5. Documentation et agents

| Champ | Règle |
|---|---|
| `docs.claude_md` | `absent` si le fichier n'existe pas ; sinon `rich` dès que `rules_count` ≥ 5, quelle que soit la longueur ; sinon `pointer` (au plus 20 lignes non vides **et** au moins un import `@`), `thin` (au plus 20 lignes non vides), `rich` (au-delà). Tous les seuils se comptent en lignes non vides. Plus `lines` (lignes non vides) et `rules_count` (éléments de liste de premier niveau) |
| `docs.agents_md` | booléen |
| `docs.handoff` | chemin d'un `HANDOFF*.md` s'il existe |
| `docs.adr` | premier de `docs/adr/`, `docs/decisions/`, `adr/` qui existe |
| `intent_from_docs` | Identifiants ou noms d'outils du catalogue cités dans `README*` ou `docs/` (ex. « Spec Kit ») : confiance `likely`, preuve = fichier et ligne |

## 6. Dérive documentaire (E2)

Détection **déterministe, présentée comme hypothèse** (confiance `likely`), jamais corrigée automatiquement. Chaque constat devient au plus une question « je le traite comment ? » (document 13, banque de questions).

| Règle | Détecte | Méthode |
|---|---|---|
| **D1 — Annonce périmée** | Ligne qui porte un marqueur (« à venir », « TODO », « pas encore », « coming soon », « not yet », « WIP »), **ou** case non cochée `- [ ]`, **ou** ligne d'une section dont le titre porte un marqueur, **et** qui cite un chemin ou un nom de fichier **qui existe** (nom seul résolu sur les fichiers suivis) | Marqueurs dans `drift_markers` (fr, en) ; jetons de chemin `[\w./-]+\.(vue\|ts\|php\|py\|…)` ou noms de dossiers de composants ; résolution par `git ls-files` |
| **D2 — Commande fantôme** | `npm run X`, `make X`, `composer X`, `php artisan X` documentés alors que `X` n'existe pas dans le manifeste ou le `Makefile` | Extraction dans les blocs de code et le texte inline |
| **D3 — Chemin fantôme** | Chemin cité dans la doc qui n'existe pas | Jetons de chemin relatifs contenant au moins un `/` |
| **D4 — Document de passation daté** | `HANDOFF*.md` dont la dernière modification git précède de plus de 20 commits le dernier commit touchant un fichier qu'il cite | `git log -1 --format=%H -- <fichier>` et comptage |

Faux positifs attendus : un « TODO » qui parle d'une amélioration future d'un fichier existant. C'est pour cela que la dérive est une hypothèse posée à l'humain et non un fait.

## 7. Signaux

Décision S-5 : un signal n'est calculé que si une fiche, une recette ou une question le référence. Signaux du MVP :

| Signal | Règle | Référencé par |
|---|---|---|
| `auth` | Dépendance parmi `keycloak*`, `laravel/socialite`, `laravel/passport`, `laravel/sanctum`, `next-auth`, `@nestjs/passport`, `passport`, `openid-client`, `authlib`, `django-allauth` ; ou mention « Keycloak », « OIDC », « SSO » dans la doc (`likely`) | `claude-plugin:security-guidance`, `ci-check:semgrep` |
| `public_surface` | Routes ou pages de formulaires (`<form`, `FormRequest`, `@Post(`) dans le code, ou mention « formulaire », « contact », « API publique » dans la doc (`likely`) | `ci-check:semgrep` |
| `frontend_heavy` | Au moins une bibliothèque de rendu riche (`three`, `gsap`, `pixi.js`, `@react-three/fiber`) ou plus de 40 % des lignes en `.vue`, `.tsx`, `.jsx` | `vendored-skill:ui-ux-pro-max` |
| `design_rules_in_instructions` | `CLAUDE.md` ou `AGENTS.md` contient au moins 3 règles citant `border-radius`, `couleur`, `color`, `token`, `font`, `typographie`, `spacing` | `vendored-skill:ui-ux-pro-max` (`when.not`) |

Mesures (`metrics`, toujours calculées, coût négligeable) : `commits`, `tracked_files`, `loc` par langage et `loc_total` (lignes non vides des fichiers de code suivis), `contributors` (auteurs distincts). `loc_total` est lu par `mcp:serena` et `cli:graphify`.

## 8. Confiance

| Niveau | Quand | Effet sur le questionnaire |
|---|---|---|
| `fact` | Lu dans un manifeste, un fichier de configuration ou l'état git | Jamais demandé ; affiché dans l'hypothèse groupée du tour 1 seulement s'il influence la sélection |
| `likely` | Déduit d'un indice (doc, convention de nommage, absence de binaire) | Présenté comme hypothèse au tour 1 |
| `unknown` | Aucun indice | Question dédiée, seulement si un champ consommateur existe |

## 9. Lacunes (`gaps`)

Codes stables, utilisés par la doc générée et `status` : `no-ci`, `no-verify`, `no-tests:<composant>`, `no-lint:<composant>`, `no-remote`, `no-agents-md`, `no-adr`.

## 10. Fichier attendu pour `fx-split-stack`

Le profil complet attendu est [schemas/examples/profile.split-stack.json](schemas/examples/profile.split-stack.json). Il remplace le profil simulé du document 09 (section 2) et le rend conforme au schéma. Écarts avec la simulation : `components[]` a maintenant ses commandes et ses chemins de code, `conventions.branches.id_style = "mixed"` (section 4.1), et la dérive est structurée par règle (D1, D4).
