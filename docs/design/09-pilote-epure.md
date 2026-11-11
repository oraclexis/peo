# 09 — Pilote n°1 : projet existant « ÉPURE »

> Projet `nuxt-app` (paquet `epure-studio`) sur ton poste, examiné le **2026-11-11** en **lecture seule** (aucun fichier modifié, aucune commande d'installation).
> Ce document joue **à la main** ce que `peo discover`, le questionnaire et `peo select` feraient, pour confronter la conception (documents 04 à 07) à un cas réel.
> **[FAIT]** = lu dans le dépôt · **[SIMULÉ]** = sortie attendue de PEO · **[ÉCART]** = besoin que la conception ne couvrait pas.

## 1. Ce que le dépôt dit de lui-même

### 1.1 Faits relevés

| Domaine | Constat | Source |
|---|---|---|
| Historique | 93 commits du 2026-07-23 au 2026-07-30, 47 branches (38 `feat/`, 8 `fix/`, `main`). **Aucun dépôt distant** | `git log`, `git branch`, `git remote -v` |
| Conventions git | Branches `feat/A1-canvas-layout`, `fix/particles-hero`. Commits « Conventional Commits » en français (`feat(article): …`), fusions explicites `merge: …` | `git log` |
| Front | Nuxt 4 (`^4.2.0`), Vue 3.5, Tailwind (`@nuxtjs/tailwindcss`), three `^0.171`, Lenis, SplitType, Atropos. SSR activé. TypeScript | `package.json`, `nuxt.config.ts` |
| Back | **Sous-projet** `backend/` : Laravel 11, Filament 3, spatie/laravel-medialibrary, PHP ^8.2. PostgreSQL 16 | `backend/composer.json`, `docker-compose.yml` |
| Exécution | PHP **uniquement dans Docker** (`docker compose exec api …`). Pas de PHP sur le poste, pas de `vendor/` local. Node présent sur le poste | `Makefile`, `which` |
| Infra | Docker Compose dev et prod, nginx « edge » en prod | `docker-compose*.yml`, `docker/` |
| Tests front | Vitest (1 fichier : `test/morph.spec.ts`), Playwright (1 fichier : `e2e/home.spec.ts`, SSR et scroll-spy en `reducedMotion`) | `test/`, `e2e/` |
| Tests back | **Aucun** dossier `backend/tests/` alors que PHPUnit est déclaré | `backend/composer.json` |
| Qualité | `nuxt typecheck`. **Pas d'ESLint ni de Prettier** côté front. Pint déclaré côté back, sans configuration ni script | `package.json`, absence de fichiers |
| CI | **Aucune** | absence de `.gitlab-ci.yml`, `.github/` |
| Taille | ≈ 4 800 lignes (Vue 2 242, TS 1 197, PHP 1 234, CSS 130), 99 fichiers suivis. Deux fichiers lourds : `pages/index.vue` (985 lignes), `useExperience.ts` (624) | `git ls-files` |
| Instructions IA | `CLAUDE.md` riche (9 règles précises : SSR, imports client-only, moteur pur, bloom maison, zéro border-radius, tokens, `prefers-reduced-motion`, perf), `HANDOFF.md`, `README.md`. **Pas d'`AGENTS.md`, pas de `.claude/`** | racine |
| Sécurité | Admin Filament authentifié. Keycloak (OIDC) **prévu** mais absent. Formulaire de contact prévu avec honeypot et limitation de débit | `README.md`, `HANDOFF.md`, `backend/app` |
| Feuille de route | Le README prévoit Spec Kit (constitution, puis spécifications par module : Content, Personas, Engagement, Leads, Settings) et un monorepo GitLab `apps/nuxt`, `apps/laravel`, `infra/` | `README.md` |

### 1.2 Dérive documentation ↔ code, détectée sans LLM

| Ce que dit la doc | Ce que montre le code |
|---|---|
| README : « `apps/laravel/` ← backend + Filament (**à venir**) » | `backend/` existe : Laravel 11 + Filament 3 + médiathèque, dockerisé |
| README et HANDOFF : « TODO : `BlockRenderer.vue` » (tâche prioritaire) | `app/components/article/BlockRenderer.vue` existe (90 lignes), utilisé par `pages/articles/[slug].vue` |
| `CLAUDE.md` : « Landing one-page » | Pages `articles/index.vue`, `articles/[slug].vue`, `error.vue` : le site n'est plus une page unique |
| `CLAUDE.md` : commandes `dev`, `build`, `typecheck` | `test` et `test:e2e` existent mais ne sont pas cités |

Ces écarts sont exactement le type d'information obsolète que le document 06 du dossier `ai-eng-workflow` cherchait à éviter. Un agent qui lit `HANDOFF.md` aujourd'hui recommencerait une tâche déjà faite.

## 2. Profil que produirait `peo discover` [SIMULÉ]

```json
{
  "kind": { "value": "existing", "confidence": "fact", "evidence": "93 commits" },
  "components": [
    { "path": ".", "stacks": ["nuxt4", "vue3", "tailwind", "threejs"], "runtime": "host-node", "confidence": "fact" },
    { "path": "backend", "stacks": ["php-laravel11", "filament3", "postgres16"], "runtime": "docker:api", "confidence": "fact" }
  ],
  "commands": {
    "front.typecheck": { "value": "npm run typecheck", "confidence": "fact" },
    "front.test":      { "value": "npm test", "confidence": "fact" },
    "front.e2e":       { "value": "npm run test:e2e", "confidence": "fact" },
    "back.test":       { "value": "docker compose exec api php artisan test", "confidence": "likely", "evidence": "PHPUnit déclaré, aucun test" },
    "back.lint":       { "value": "docker compose exec api vendor/bin/pint --test", "confidence": "likely" },
    "verify":          { "value": null, "confidence": "unknown", "evidence": "aucune cible agrégée" }
  },
  "conventions": {
    "branches": { "pattern": "^(feat|fix)/[A-Za-z0-9-]+$", "confidence": "fact", "evidence": "46 branches sur 47" },
    "commits":  { "style": "conventional", "language": "fr", "confidence": "fact" }
  },
  "ai": { "claude_md": "rich", "agents_md": false, "plugins_project": [], "handoff_doc": "HANDOFF.md" },
  "docs_drift": [
    "README annonce le backend « à venir » : backend/ existe",
    "TODO BlockRenderer.vue : le fichier existe et il est utilisé"
  ],
  "gaps": ["Pas de CI", "Pas de commande verify", "Aucun test backend", "Pas de lint front", "Pas de dépôt distant"],
  "signals": { "frontend_heavy": true, "public_forms_planned": true, "admin_panel": true, "auth_planned": "keycloak-oidc" },
  "intent_from_docs": ["spec-kit", "monorepo-gitlab", "keycloak"]
}
```

## 3. Questionnaire [SIMULÉ]

Ce qui est déjà su n'est pas demandé : stacks, commandes, conventions, intention d'utiliser Spec Kit. Il reste **un tour d'hypothèses** et **trois questions**.

| Tour | Question | Réponse recommandée | Pourquoi elle est posée |
|---|---|---|---|
| 1 | « J'ai compris : site vitrine + journal en Nuxt 4 SSR, CMS Laravel/Filament dans `backend/`, Spec Kit envisagé, passage prévu en monorepo GitLab. Juste ? » | Oui | Valide en une fois les faits `likely` |
| 1 | « `README.md` et `HANDOFF.md` sont en retard sur le code (backend, BlockRenderer). Je les traite comment ? » | Archiver `HANDOFF.md`, corriger le README dans le même plan | Dérive détectée, la décision t'appartient |
| 2 | « Commande unique de vérification : je propose une cible `make verify` (typecheck + Vitest + Pint et PHPUnit dans le conteneur). D'accord ? » | Oui | `verify` inconnu, et les portes en dépendent |
| 2 | « Le formulaire de contact et l'admin seront exposés publiquement : activer une analyse de sécurité statique en CI (Semgrep) ? » | Oui, en CI seulement | Signal `public_forms_planned`, coût nul en contexte |

Questions **non posées** et pourquoi : catégorie (déduite : site + CMS), équipe (seul contributeur dans l'historique, hypothèse présentée au tour 1), langue (déduite des commits et de la doc : français), performance (aucune fiche du catalogue n'en dépend ; les contraintes de perf sont déjà dans `CLAUDE.md`).

## 4. Sélection [SIMULÉ]

### 4.1 Retenus

| Outil | Capacité | Justification |
|---|---|---|
| Socle Spec Kit + EGM + Matt Pocock | spec, plan, tâches, relecture indépendante, TDD, revue | Socle par défaut, et Spec Kit déjà prévu par le README |
| `typescript-lsp` | navigation (front) | Composant `.` en TypeScript et Vue |
| `php-lsp` | navigation (back) | Composant `backend/` en PHP. **Mais** le serveur `intelephense` doit tourner sur le poste, sans PHP local : à confirmer [ÉCART E5] |
| Playwright **déjà présent** | `browser.e2e` | Réutilisé tel quel (principe « réutiliser l'existant »). Aucun plugin ni MCP ajouté |
| Semgrep en CI | `review.security.sast` | Formulaire public et admin à venir. Coût nul en contexte |

### 4.2 Écartés, avec la raison

| Candidat | Raison |
|---|---|
| Serena, Graphify | 4 800 lignes, bien documentées : la navigation native suffit |
| UI UX Pro Max | Direction artistique **déjà fixée et stricte** dans `CLAUDE.md` (zéro border-radius, tokens, chanfrein du CTA). Un skill de design proposerait des choix contraires. Signal `frontend_heavy` vrai, mais l'outil serait nuisible ici |
| `laravel-boost` | Exige le paquet Composer dans le projet et un `php artisan` sur le poste : PHP n'est que dans Docker [ÉCART E5] |
| `security-guidance` | Coût en tokens à chaque arrêt. Semgrep en CI couvre le besoin au stade actuel. À réévaluer avec Keycloak |
| Ponytail | Simplicité déjà portée par des règles projet précises. Injection de hooks inutile |
| REA | Aucun artefact sans code source |

## 5. Plan qui serait présenté [SIMULÉ, extrait]

```text
Plugins (portée projet)    + egm@egm   + mattpocock-skills   + typescript-lsp   ? php-lsp (voir E5)
Outils du poste            + specify-cli 1.4.0   + semgrep (CI seulement : rien sur le poste)
Spec Kit                   + specify init --here --integration claude --no-model-invocation
                           + preset peo-eng  (branches : convention feat/<id>-<slug> conservée, voir E3)
Fichiers                   + AGENTS.md          contenu de CLAUDE.md réorganisé en pointeurs, règles conservées mot pour mot
                           ~ CLAUDE.md          « @AGENTS.md » + bloc Agent skills — ancien sauvegardé
                           + .claude/rules/frontend.md   paths: app/**, *.vue — les 9 règles front de CLAUDE.md
                           + .specify/memory/constitution.md   amorce depuis CLAUDE.md (SSR/SEO, reduced-motion, perf, tokens)
                           ~ Makefile           + cible verify (bloc géré # peo:begin verify)
                           ~ README.md          corrections de dérive proposées (diff affiché)
                           ~ HANDOFF.md         déplacé vers docs/archive/ (décision du tour 1)
                           + .gitlab-ci.yml     verify + semgrep + peo status --ci (sans dépôt distant : prêt pour plus tard)
                           + .peo/peo.toml, profile.json, peo.lock.json, history.ndjson, README.md
Ignoré                     ~ .gitignore         + .peo/backups/
Restera à faire par toi    /reload-plugins · /setup-matt-pocock-skills · ratifier la constitution · premier commit
```

## 6. Écarts révélés par le pilote

Le pilote valide l'essentiel de la conception : la découverte suffit à éviter presque toutes les questions, la sélection écarte cinq outils avec des raisons concrètes, et un outil populaire (UI UX Pro Max) est **nuisible** dans ce contexte précis. Il révèle aussi **six besoins non couverts**.

| # | Écart | Impact sur la conception | Où le traiter |
|---|---|---|---|
| **E1** | **Plusieurs composants dans un dépôt** (front à la racine, back dans `backend/`), et un monorepo prévu | Le profil et `peo.toml` supposaient une seule stack et un seul jeu de commandes. Il faut une notion de **composant** (chemin, stacks, commandes, environnement d'exécution) | Doc 06 : `components[]` dans `profile.json` et `[components.<id>]` dans `peo.toml`. Doc 04 : la porte utilise les chemins de code de tous les composants |
| **E2** | **Dérive documentaire dès l'initialisation** | La dérive était prévue en régime de croisière (étape 14). Elle existe **avant** PEO, et elle trompe l'agent | Doc 07 : ajouter à F1 une détection déterministe simple : TODO citant un fichier existant, composant annoncé « à venir » mais présent, commandes du `package.json` absentes de la doc. Proposition de correction dans le plan, jamais automatique |
| **E3** | **Conventions git existantes** (`feat/<id>-<slug>` supposé ; mesure : 24 branches sur 46 seulement ont un identifiant, voir spec 12, section 4.1 ; Conventional Commits en français hors fusions) | Spec Kit crée par défaut des branches `NNN-slug` et des dossiers `specs/NNN-slug`. Imposer ce format casserait une convention établie | Doc 06 : `conventions` dans le profil. Doc 05 : la fiche Spec Kit déclare ses conventions et le Planner configure ou signale le conflit. `.specify/feature.json` découple déjà dossier et branche [FAIT, analyse précédente] |
| **E4** | **`CLAUDE.md` riche et spécifique** (9 règles, toutes front) | « Réduire `CLAUDE.md` à des pointeurs » ne doit pas faire perdre une seule règle. Ces règles sont aussi des principes de constitution et des règles par chemin | Doc 04 : l'adaptateur Claude **migre**, ne réécrit pas : chaque règle conservée mot pour mot, rangée (constitution, `.claude/rules/` à portée de chemin, `AGENTS.md`), avec un **tableau de correspondance** dans le plan |
| **E5** | **Chaîne d'outils dans Docker** (PHP, Composer, Artisan seulement dans le conteneur `api`) | Commandes de vérification, LSP PHP et `laravel-boost` supposaient PHP sur le poste | Doc 06 : `runtime` par composant (`host`, `docker:<service>`). Doc 03 : chaque fiche déclare ses prérequis d'exécution ; le Selector écarte ou adapte |
| **E6** | **Outil déjà présent hors catalogue** (Playwright en dépendance de dev) | L'inventaire ne regardait que les plugins, MCP et outils `uv` | Doc 05 : l'Inventory lit aussi les dépendances de dev (`package.json`, `composer.json`) pour reconnaître les capacités déjà couvertes |

Un septième point est une **confirmation** plutôt qu'un écart : la règle « ne jamais proposer un outil parce que le signal est vrai » (ici `frontend_heavy`) doit pouvoir être contredite par une **contre-indication** de la fiche (`when.not`), par exemple : « direction artistique imposée dans les instructions du projet ». Le modèle de données le permet déjà ; le pilote montre qu'il faut l'utiliser.

## 7. Ce que le pilote ne permet pas encore de valider

- Le temps réel de `/peo:init` (rien n'est construit).
- ~~Le comportement de Spec Kit avec une convention de branche personnalisée~~ : **levé le 2026-11-11** (spec 10, section 5). `branch_prefix: "feat"` produit `feat/001-<slug>`, conforme au motif réellement mesuré dans ce dépôt ; aucune question nécessaire.
- ~~Le LSP PHP sans PHP sur le poste (E5)~~ : **levé le 2026-11-11**. Intelephense ne demande pas PHP ; il faut `backend/vendor` sur le poste, que le montage `./backend:/var/www/html` rend visible après `composer install` dans le conteneur.

**Révision par la spécification** : `CLAUDE.md` n'est plus migré d'office (décision S-3) ; le plan de la section 5 est remplacé par celui de la spec 14, section 10.

## 8. Prochaine étape proposée pour ce pilote

Quand la spécification détaillée sera validée, ce dépôt servira de **jeu de test de référence** pour F1 (Discovery) : le profil de la section 2 devient le fichier attendu (« golden file »), à partir d'une copie anonymisée de sa structure placée dans les fixtures de PEO.

**Décision prise le 2026-11-11 : acceptée.** Conditions retenues pour la copie :

- arborescence et manifestes seulement (`package.json`, `composer.json`, `Makefile`, `docker-compose*.yml`, `nuxt.config.ts`, configs de test), **aucun fichier de code source** : les fichiers `.vue`, `.ts`, `.php` sont remplacés par des fichiers vides de même nom ;
- noms anonymisés (`epure` → `sample`, domaine `epure.studio` → `example.test`) ;
- valeurs par défaut de mots de passe et identifiants retirées (`DB_PASSWORD:-secret`, compte admin du `Makefile`) ;
- `CLAUDE.md`, `README.md`, `HANDOFF.md` conservés **en texte**, car ils servent aux tests de dérive documentaire (E2) et de migration des règles (E4) ;
- historique git **non** copié : remplacé par un script qui recrée 93 commits et 47 branches factices avec les mêmes motifs de nommage (E3).

La copie sera faite au début de la phase F1, pas avant.

Pour couvrir H11, il manque encore un dépôt existant **sans** front lourd (par exemple un service NestJS ou Python) afin de vérifier que la sélection ne pousse pas les mêmes outils partout.
