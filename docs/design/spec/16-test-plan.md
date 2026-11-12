# 16 — Plan de tests

Principe : **les tests sont écrits avant le code de chaque phase**, à partir de cette spécification. Une fonctionnalité est terminée quand ses tests d'acceptation passent.

## 1. Fixtures (dépôts de test)

Chaque fixture est un dossier sous `tests/fixtures/<nom>/` **et** un script `build.sh` qui crée l'historique git (commits, branches) de façon déterministe (`GIT_AUTHOR_DATE` fixé). Aucun historique réel n'est copié. Les chemins listés dans `untracked.txt` de la fixture sont copiés après l'historique, **sans `git add`** : ils sont présents et non suivis dans le dépôt construit (précisé le 2026-11-12, P1.6).

| Fixture | Contenu | Sert à |
|---|---|---|
| `fx-new` | Dépôt vide, un commit | Projet neuf : `kind = new`, aucune commande, questions maximales |
| `fx-laravel` | `composer.json` Laravel 11, `artisan`, `tests/Feature/ExampleTest.php`, `Makefile` avec `verify` | Composant backend, `verify` en `fact` |
| `fx-nestjs` | `package.json` NestJS, Jest, ESLint, `.github/workflows/ci.yml` | Second pilote cible (dépôt sans front lourd, H11) |
| `fx-vue` | Vue 3 + Vite + Vitest | Front seul |
| `fx-python` | `pyproject.toml` FastAPI, pytest, ruff | Écosystème Python |
| `fx-monorepo` | pnpm workspaces : `apps/web` (Nuxt), `apps/api` (NestJS), `packages/ui` | `monorepo = true`, 3 composants |
| `fx-split-stack` | Fixture synthétique reproduisant les traits du pilote n°1 (2.1) | Référence publique : E1 à E6 |
| `fx-conflict` | `fx-vue` + `.claude/settings.json` activant `superpowers@…` | `E_BACKBONE_CONFLICT` |
| `fx-rich-claude-md` | `CLAUDE.md` de 240 lignes, règles à portée de chemin et commandes | Migration (S-3, E4) |
| `fx-hostile` | Liens symboliques sortants, chemins `..`, Unicode bidirectionnel dans une fiche, `settings.json` invalide | NF6, NF13, arrêt sur fichier illisible |
| `fx-large` | Généré : 100 000 lignes suivies | NF3 |

Fichiers attendus (« golden ») par fixture : `profile.json`, `selection.json`, `plan.json`, `plan.txt` (rendu humain), et pour `fx-rich-claude-md` le tableau de correspondance attendu. Mise à jour d'un fichier attendu : seulement par `pytest --update-golden`, relue en revue.

## 2. Fixture de référence `fx-split-stack` et test local du pilote n°1

**Décision du 2026-11-12**, qui remplace celle du 2026-11-11 (copie anonymisée du pilote n°1) : aucune copie d'un projet réel, même anonymisée, n'entre dans le dépôt de PEO.

### 2.1 `fx-split-stack` (référence publique)

Fixture écrite à la main (`tree/` + `build.sh`, section 1). Elle reproduit les traits mesurés sur le pilote n°1 (document 09) **sans aucun texte, nom, domaine, adresse ni valeur tirés du projet réel**.

| Trait | Contenu de la fixture |
|---|---|
| E1 | Front Nuxt à la racine, back Laravel dans `backend/` |
| E2 | `README.md` annonçant « à venir » un chemin `apps/api/` qui n'existe pas, le back étant dans `backend/` (D3) ; TODO citant un composant présent (D1) ; commandes `test` et `test:e2e` du `package.json` absentes de `CLAUDE.md` ; `HANDOFF.md` (dérives D1 et D4) |
| E3 | `build.sh` recrée 93 commits (dont 46 fusions `merge: …`) et 46 branches hors `main` : 24 au format `feat/<A-Z><n>-<slug>`, 22 au format `(feat\|fix)/<slug>` ; sujets conventionnels en français |
| E4 | `CLAUDE.md` de 27 lignes non vides et 9 règles front, rédigées pour la fixture (classe `rich`, spec 12, section 5) |
| E5 | `docker-compose.yml` avec un service `api` ; `Makefile` qui exécute PHP par `docker compose exec api` ; pas de `backend/vendor` |
| E6 | Playwright en dépendance de développement |
| Taille | Fichiers de code au contenu `// line n`, en nombre suffisant pour tenir les seuils de sélection (environ 4 800 lignes, deux fichiers lourds) |
| Surfaces sensibles (ajout du 2026-11-12) | `backend/.env` avec les variables `APP_KEY`, `DB_DATABASE`, `DB_HOST`, `DB_PASSWORD`, `DB_USERNAME` et des valeurs **manifestement factices** (`fixture-not-a-secret`) ; listé dans `untracked.txt`, donc présent dans l'arbre de travail construit et **non suivi** (et ignoré par le `.gitignore` de la fixture) ; ajouté au dépôt de PEO avec `git add -f`. Valeurs : `APP_KEY=fixture-not-a-secret`, `DB_DATABASE=app`, `DB_HOST=db`, `DB_PASSWORD=fixture-not-a-secret`, `DB_USERNAME=app`. Le service `db` (`postgres:16`) du `docker-compose.yml` existe déjà. Les valeurs leurres de NF14 ne sont **jamais** dans la fixture : elles sont générées par le test (A14.2) |

Fichiers attendus : `tests/golden/fx-split-stack/`. La fixture n'est produite par aucun script de copie ; sa relecture en revue vérifie qu'elle ne contient rien du projet réel.

### 2.2 Pilote n°1, test d'acceptation local

- Activé seulement quand la variable `PEO_PILOT1_PATH` désigne un clone local du projet ; sinon ignoré (`skip`). Jamais exécuté en CI.
- Lit ce dépôt en lecture seule ; n'écrit rien, ni dans ce dépôt ni dans celui de PEO.
- Vérifie les traits E1 à E6 (assertions de A1.3, A1.4 et A1.5), pas l'égalité avec un fichier attendu : le projet réel évolue.
- Aucun fichier, extrait ni sortie de ce test n'est versionné.

## 3. Tests d'acceptation par fonctionnalité

| F | Tests | Fixtures |
|---|---|---|
| **F0** Fixtures | A0.1 `build.sh` recrée les comptages attendus : commits, fusions, branches, fichiers suivis, lignes non vides par langage · A0.2 deux constructions donnent le même `HEAD` | `fx-split-stack` |
| **F1** Discovery | A1.1 profil égal au fichier attendu (6 fixtures) · A1.2 chaque champ a `confidence` et `evidence` · A1.3 `fx-split-stack` : 2 composants, `backend` en `docker:api` (E1, E5) · A1.4 `fx-split-stack` : branches `mixed`, motif `^(feat\|fix)/[A-Za-z0-9-]+$`, commits conventionnels malgré les fusions (E3) · A1.5 `fx-split-stack` : dérive D1 (README « backend à venir », TODO citant un composant présent) et D4 (`HANDOFF.md`) (E2) · A1.6 aucun accès réseau · A1.7 `fx-large` < 5 s · A1.8 `fx-split-stack` : section `sensitive` égale à la valeur attendue (spec 12, section 7 bis) ; `.env.example` n'est pas un fichier de secrets ; `environment` du compose jamais lu | toutes |
| **F2** Catalogue | A2.1 21 fiches valides · A2.2 fiche sans `surface`, sans `surface.data_path`, sans `surface.fail_mode` ou sans `review_by` rejetée · A2.3 expression `when` invalide rejetée au chargement · A2.4 question dont `feeds` n'est consommé nulle part rejetée (S-5) · A2.5 Unicode bidirectionnel rejeté · A2.6 `validate.py` et `jsonschema` donnent le même verdict sur tous les exemples et contre-exemples | catalogue de test |
| **F3** Inventory | A3.1 plugin activé à la main détecté (sortie enregistrée de `claude plugin list --json`) · A3.2 installation de portée projet d'un **autre** projet ignorée (`projectPath`) · A3.3 hooks listés par événement avec propriétaire · A3.4 Playwright reconnu par `[detect].npm` (E6) · A3.5 mode dégradé sans `claude` · A3.6 permissions, réglages du sandbox et `onFailure` lus dans les trois portées · A3.7 clé sensible de `.mcp.json` classée `literal` ou `reference`, valeur absente de la sortie | `fx-split-stack`, `fx-conflict` |
| **F4** Questionnaire | A4.1 aucune question sur un champ `fact` · A4.2 `fx-split-stack` : 2 tours, questions `q.confirm_profile`, `q.docs_drift`, `q.mission`, `q.verify_cmd`, `q.ci`, `q.gate_mode` ; **pas** `q.branch_convention` · A4.3 ≤ 4 questions par tour, ≤ 4 options · A4.4 reconfiguration : réponses pré-remplies, seules les questions dont l'entrée a changé reviennent | `fx-split-stack`, `fx-new` |
| **F5** Selector | A5.1 `fx-split-stack` : sélection égale au fichier attendu · A5.2 propriétés (13, section 8.5) par tests de propriétés sur catalogues générés · A5.3 `fx-conflict` : code 6 · A5.4 > 24 candidats : `E_TOO_MANY_CANDIDATES` · A5.5 `fx-nestjs` : ni `php-lsp`, ni `ui-ux-pro-max`, ni Serena (la sélection ne pousse pas les mêmes outils partout) | toutes |
| **F6** Planner + adaptateurs | A6.1 plan égal au fichier attendu · A6.2 `apply` deux fois : second plan entièrement `keep` · A6.3 `--expect-plan` faux : code 4, rien d'écrit · A6.4 fichier modifié entre plan et apply : code 4 · A6.5 échec simulé au groupe `files` : fichiers restaurés, lock contient les installations R3 déjà faites · A6.6 aucune commande avec `sudo` ; `npm -g` sans préfixe inscriptible → `manual` · A6.7 R4 jamais exécuté | `fx-split-stack`, `fx-laravel` |
| **F7** Adaptateur Claude | A7.1 fusion de `settings.json` : clés étrangères et ordre intacts · A7.2 contenu hors blocs gérés identique octet pour octet · A7.3 `fx-split-stack` : `CLAUDE.md` conservé, `@AGENTS.md` ajouté en tête · A7.4 `fx-rich-claude-md` migré : invariant du multiensemble, tableau égal au fichier attendu · A7.5 `settings.json` invalide : arrêt, action `manual` · A7.6 `matcher` contient les `write_tools` de Serena quand Serena est retenu · A7.7 `fx-split-stack` : `permissions.deny` reçoit `Read(./backend/.env)` (possédée) ; une règle identique déjà présente n'est ni dupliquée ni possédée ; le sandbox n'est jamais écrit, action `manual` qui cite `docker:api` (S-9) · A7.8 retrait d'une règle `deny` possédée : action `weakens = true` | `fx-split-stack`, `fx-rich-claude-md`, `fx-hostile` |
| **F8** Lock + journal | A8.1 chaque action a un événement · A8.2 `owns` présent pour tout outil configuré par PEO · A8.3 lock et événements valides contre leurs schémas · A8.4 fusion de deux journaux (`merge=union`) lisible, doublons ignorés | `fx-split-stack` |
| **F9** Doc générée | A9.1 commandes réelles du projet · A9.2 raison de chaque outil retenu et écarté · A9.3 section « Notes » préservée | `fx-split-stack` |
| **F10** Porte + recettes | A10.1 tests T1 à T11 du dossier `ai-eng-workflow` (document 07) rejoués sur entrées JSON enregistrées · A10.2 chemin de spécification jamais bloqué · A10.3 caducité : `spec.md` modifié après G1 → G1 ouverte · A10.4 outil d'écriture Serena (`relative_path`) bloqué comme `Edit` · A10.5 `on_error = closed` + `peo` absent → code 2 · A10.6 latence < 100 ms au 95e centile sur 200 appels | `fx-split-stack` |
| **F11** Status | A11.1 un test par constat de la table (document 15, section 6) · A11.2 `--ci` code 3 sur `error` · A11.3 `S-GATE-BYPASS` sur une branche avec code modifié sans portes | `fx-split-stack`, `fx-laravel` |
| **F12** `tools add/remove` | A12.1 retrait limité aux possessions intactes · A12.2 possession modifiée → `manual` · A12.3 outil hors lock : retrait refusé · A12.4 recettes impactées listées | `fx-split-stack` |
| **F13** `tools update --plan` | A13.1 différence de surface affichée (hook ajouté, `write_tools` ajouté) · A13.2 rien d'écrit | catalogue de test v1 → v2 |
| **F14** Audit d'exposition (ajout du 2026-11-12) | A14.1 un test par constat `X-*` (document 15, section 7.1) · A14.2 **aucune valeur** (NF14) : une copie de la fixture reçoit des valeurs leurres générées par le test dans `backend/.env` et dans `.mcp.json` ; aucune n'apparaît dans les sorties de `discover`, `select`, `plan`, `status --exposure --canary` (stdout, stderr, JSON, fichiers de `.peo/`) · A14.3 `fx-split-stack` sans réglages : `X-SECRET-READABLE` (`backend/.env`), `X-NO-SECRET-SCAN`, `X-SANDBOX-OFF` en `info` (composant `docker:api`), `X-DATA-STORE` (`db`) ; après `apply` : plus de `X-SECRET-READABLE` · A14.4 canari avec exécuteur factice : code attendu → `detected`, autre code → `X-CANARY-MISSED`, commande absente ou délai → `X-CANARY-UNVERIFIABLE` ; dossier temporaire hors du dépôt et supprimé, même en cas d'erreur ; sortie de l'outil non reprise · A14.5 sans `--canary`, aucune commande tierce exécutée (exécuteur factice vide) et aucun accès réseau · A14.6 deux fiches `rewrites-io` actives : `X-MASKING-DUPLICATE` · A14.7 `--ci` : code 3 sur `X-SECRET-TRACKED` · A14.8 aucun message ne contient « protected » ni « protégé » | `fx-split-stack`, catalogue de test |

## 4. Niveaux et outillage

| Niveau | Outil | Quand |
|---|---|---|
| Unitaires et propriétés | pytest, hypothesis | à chaque commit |
| Contrats d'adaptateurs | Exécuteur de commandes factice qui rejoue des sorties enregistrées (`claude plugin list --json`, `uv tool list`, `npm ls -g --json`) | à chaque commit |
| Intégration | Conteneur avec Claude Code, `uv`, Node réels, sur une copie de `fx-split-stack` ; réseau limité aux sources des fiches | chaque nuit et avant une version |
| Bout en bout | `/peo:init` joué à la main sur `fx-split-stack`, puis sur le projet réel du pilote n°1 **avec ton accord**, puis sur le second dépôt existant | jalon MVP |
| Non-régression d'écosystème | Job programmé : versions les plus récentes des outils du socle dans le conteneur, scénario rejoué, issue ouverte si échec | chaque semaine |

## 5. Ce qui ne peut pas être testé automatiquement au MVP

- La qualité des formulations des questions (relecture humaine).
- Le comportement de `claude plugin install` lancé depuis une session (spike S1 : essai manuel documenté).
- La pertinence de la sélection au-delà des fichiers attendus : c'est l'objet des mesures du jalon MVP (document 07, section 6).
