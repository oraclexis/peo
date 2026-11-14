# 07 — MVP et feuille de route

> **[RECO]** dans tout le document.
>
> **Mise à jour du 2026-11-11** : les critères d'acceptation détaillés sont dans [spec/16-test-plan.md](spec/16-test-plan.md). Changements : F1 couvre aussi la dérive documentaire (E2), les conventions git (E3) et l'environnement d'exécution par composant (E5) ; F3 lit les dépendances de dev (E6 ; révisé le 2026-11-14 : F3 ne lit plus ni CLI ni dépendances de dev, qui relèvent de `Adapter.detect` et de `present_tools`) ; un cinquième type d'installeur, `ci-check`, entre au MVP (S-4) ; la question « équipe » est retirée faute de consommateur (spec 13, section 7.2).
>
> **Révision du 2026-11-12** : la feuille de route est réordonnée, l'audit d'abord (section 7, décision H20). Les sections 1 à 6 restent la référence pour le contenu des fonctionnalités F1 à F13.

## 1. Ce que le MVP doit prouver

Une seule hypothèse de valeur : **sur un projet existant, `/peo:init` produit en moins de 15 minutes un environnement que tu aurais mis une journée à assembler, sans doublon, sans conflit, et dont tu comprends chaque choix.**

Si ce n'est pas vrai sur trois projets réels, le reste de la feuille de route n'a pas d'objet.

Périmètre du MVP :

- **un agent** : Claude Code ;
- **un socle** : Spec Kit + EGM + Matt Pocock ;
- **un catalogue** de 15 à 20 fiches ;
- **deux recettes** : `feature`, `bugfix` ;
- **cinq types d'installeurs** : `claude-plugin`, `mcp`, `cli` (uv et npm), `framework` (Spec Kit), `ci-check` (GitLab, GitHub) ;
- **des données portables** dès le départ (`AGENTS.md`, `.peo/` en TOML, JSON, Markdown).

## 2. Fonctionnalités du MVP

Complexité : S (≤ 2 jours), M (≤ 1 semaine), L (> 1 semaine), pour une personne.

| # | Fonctionnalité | Objectif | Priorité | Complexité | Dépend de | Critères d'acceptation |
|---|---|---|---|---|---|---|
| F1 | **Discovery** | Profil du projet sans LLM | P0 | M | — | Sur 5 dépôts de test (Laravel, NestJS, Vue, Python, monorepo), stacks et commandes détectées conformes à un fichier attendu. Chaque information a une provenance et une confiance. < 5 s sur 100 000 lignes |
| F2 | **Catalogue + validation** | Fiches TOML validées par schéma | P0 | S | — | `peo catalog validate` rejette une fiche sans `surface` ou sans `review_by`. 15 fiches valides |
| F3 | **Inventory** | État réel des portées Claude (managed, local, project, user), MCP, plugins | P0 | M | — | Détecte un plugin activé à la main, un MCP, un outil `uv`. Liste les hooks actifs par événement avec leur propriétaire |
| F4 | **Questionnaire adaptatif** | Ne demander que l'incertain | P0 | M | F1 | Aucune question sur une information `fact`. Au plus 4 tours. Mode reconfiguration pré-rempli. Fonctionne sans interface de questions (texte) |
| F5 | **Selector** | Ensemble minimal justifié | P0 | M | F2, F3, F4 | Déterministe (mêmes entrées, même sortie, testé). Aucune paire en conflit. Chaque outil retenu et chaque candidat écarté a une raison. Détecte un socle concurrent déjà installé |
| F6 | **Planner + Installers** | Plan exact puis application | P0 | L | F5 | Plan affiché avant toute écriture. Idempotent (deuxième `apply` = tout `=`). Sauvegarde avant écriture. Aucune installation système exécutée |
| F7 | **Adaptateur Claude** | Settings, hooks, `AGENTS.md`, `CLAUDE.md` | P0 | M | F6 | Fusion sans écrasement de `.claude/settings.json`. Bloc géré entre marqueurs dans `AGENTS.md`. `CLAUDE.md` existant sauvegardé |
| F8 | **Lock + journal** | Reproductibilité, traçabilité | P0 | S | F6 | Toute action journalisée. `owns` renseigné pour chaque outil installé par PEO |
| F9 | **Doc générée** | `.peo/README.md` pour ce projet | P1 | S | F7 | Commandes réelles du projet, raisons de chaque outil. Section « Notes » préservée à la régénération |
| F10 | **Porte (`peo gate`) + recette `feature`** | Pas de code avant validation | P0 | M | F7 | Tests T1 à T11 du dossier `ai-eng-workflow` passent. Couvre les outils d'écriture déclarés par les fiches (Serena) |
| F11 | **`peo status`** | Santé, conflits, dérive des fichiers générés | P0 | M | F3, F8 | Signale : outil du lock absent, version différente, hook non déclaré par sa fiche, fichier géré modifié, fiche expirée. Mode `--ci` avec code de sortie |
| F12 | **`peo tools add/remove/enable/disable`** | Cycle de vie de base | P1 | M | F6, F8 | Retrait limité aux artefacts possédés et non modifiés. Recettes impactées affichées |
| F13 | **`peo tools update --plan`** | Préparer une mise à jour | P2 | M | F12 | Différence de surface (hooks, MCP, réseau) affichée. Aucune application automatique |

### Questionnaire adaptatif (F4) : règles

1. **Ordre** : hypothèses à confirmer d'abord (une question groupée « voici ce que j'ai compris, est-ce juste ? »), puis questions sans réponse possible par le dépôt.
2. **Une question n'existe que si sa réponse change la sélection ou la configuration.** Chaque question du catalogue déclare les champs qu'elle alimente. Une question dont aucun champ n'influence le résultat n'est pas posée.
3. **Banque de questions dans le catalogue**, pas dans le prompt : versionnée, testable.
4. **Réponse recommandée en premier**, avec sa raison tirée du profil.
5. **Questions du MVP** : mission, catégorie (SaaS, interne, API, bibliothèque, outil), sensibilité (auth, données personnelles), équipe, langue des artefacts, mode de porte, cibles de déploiement (seulement si une fiche en dépend). Les questions sur la performance, la scalabilité ou la stratégie d'évolution ne sont posées **que** si une fiche du catalogue en dépend. Au MVP, aucune n'en dépend : elles ne sont pas posées.

## 3. Hors MVP, volontairement

| Fonctionnalité | Pourquoi pas maintenant |
|---|---|
| Mises à jour automatiques | Risque élevé, valeur faible tant que l'usage de `prepare` n'est pas éprouvé |
| Rollback d'outil au-delà de la commande en cours | Dépend des tags des installeurs. `git revert` suffit pour la configuration |
| Plusieurs socles | Chaque socle demande son intégration, ses recettes, ses tests |
| Autres agents (Codex, Cursor, Copilot) | Délégable à rulesync ou APM le moment venu. Données portables dès le MVP |
| Serveur MCP PEO | Aucun besoin identifié |
| Découverte profonde (AST, graphe) | Les manifestes suffisent pour sélectionner les outils |
| Gestion de la connaissance (stockage, recherche sémantique) | Les outils du socle s'en chargent. PEO indexe |
| Personas d'agents propres à PEO | Contraire au principe « pas d'accumulation d'agents » |
| Interface graphique, tableau de bord | Aucune valeur pour la cible du MVP |
| Catalogue d'organisation | Une équipe d'abord |

## 4. Feuille de route révisée

La feuille de route proposée a deux défauts : le questionnaire (P1) arrive **avant** la découverte (P2) alors qu'il en dépend, et la génération de `.peo/` (P6) arrive **après** l'initialisation qui doit l'écrire. Révision :

| Phase | Contenu | Sortie vérifiable | Durée indicative |
|---|---|---|---|
| **P0** | Analyse et conception (ce dossier) | Décisions du document 08 prises | fait |
| **P1** | Discovery (F1) + Inventory (F3) + catalogue initial (F2) | `peo discover` et `peo status` lisent 5 dépôts de test correctement | 2 semaines |
| **P2** | Selector (F5) + questionnaire (F4) | Sélection justifiée et déterministe, sans rien installer (`peo select --dry-run`) | 2 semaines |
| **P3** | Planner, installeurs, adaptateur Claude, lock, journal, doc (F6 à F9) | `/peo:init` complet sur un projet pilote réel | 3 semaines |
| **P4** | Porte + recette `feature` + `bugfix` (F10), `peo status --ci` (F11) | Une fonctionnalité réelle menée de bout en bout | 2 semaines |
| **— Jalon MVP —** | Trois projets réels initialisés, mesures (section 6) | Décision de continuer ou non | |
| **P5** | `peo tools` complet (F12, F13) | Ajout, retrait, mise à jour préparée sur le pilote | 2 semaines |
| **P6** | Recettes `refactor`, `review`, `release`. Fiches conditionnelles (Serena, Graphify, Semgrep, Playwright CLI) | Profils conditionnels utilisés sur un projet réel | 3 semaines |
| **P7** | Catalogue partagé : dépôt public, CI de vérification des fiches (surface recalculée) | Une fiche obsolète est détectée automatiquement | 2 semaines |
| **P8** | Portabilité : adaptateur Codex ou Copilot via rulesync ou APM | Même projet utilisable par un second agent | à évaluer |
| **P9** | Socles alternatifs (Superpowers, BMAD) | Un projet sur un autre socle | à évaluer |
| **P10** | Politique `auto` des mises à jour, catalogue d'organisation | Selon la demande | à évaluer |

Durées pour une personne à temps partiel significatif ; elles servent à ordonner, pas à promettre.

## 5. Stratégie de tests

| Niveau | Quoi | Comment |
|---|---|---|
| **Unitaires** | Discovery, Selector, Planner, parsing du catalogue | `pytest`. **Dépôts de test** (fixtures) : petits dépôts synthétiques par stack, avec fichier de profil attendu (« golden files ») |
| **Propriétés** | Selector | Tests de propriétés : déterminisme, aucune paire en conflit, toutes les capacités requises couvertes ou signalées, minimalité (retirer un outil casse la couverture) |
| **Idempotence** | Planner + installeurs | `apply` deux fois : la seconde produit un plan entièrement `=` |
| **Adaptateurs** | Installeurs | Faux installeurs (enregistrent les appels) en unitaire. **Intégration en conteneur** Docker avec Claude Code, `uv`, Node réels, sur un dépôt jetable |
| **Hooks** | `peo gate`, `peo context` | Entrées JSON de hook enregistrées (stdin), sorties attendues. Mesure de latence (< 100 ms) |
| **Catalogue** | Fiches | `peo catalog validate` en CI du dépôt du catalogue. Vérification hebdomadaire des sources et de la surface réelle |
| **Bout en bout** | `/peo:init` dans Claude Code | Scénarios manuels documentés sur 3 projets pilotes, puis automatisation partielle par `claude -p` sur les étapes sans questions [HYPOTHÈSE : faisabilité à vérifier] |
| **Non-régression d'écosystème** | Nouvelles versions des outils du socle | Job programmé : installe les dernières versions dans un conteneur, rejoue un scénario, ouvre une issue si échec |

## 6. Mesures du jalon MVP

| Mesure | Seuil de succès |
|---|---|
| Temps de `/peo:init` sur un projet existant, questions comprises | < 15 min |
| Questions posées dont la réponse était déductible du dépôt | 0 |
| Outils retenus que tu aurais retirés après coup | ≤ 1 sur 3 projets |
| Conflits non détectés découverts à l'usage | 0 |
| Contexte permanent ajouté par PEO lui-même | < 500 tokens |
| Fonctionnalité menée avec les portes sans contournement involontaire | 3 sur 3 |

## 7. Feuille de route révisée du 2026-11-12 : l'audit d'abord

Raison (document 01, section 9) : Discovery et Inventory sont à construire de toute façon ; en faire un premier livrable en lecture seule donne une valeur mesurable vers 3 à 4 semaines au lieu d'environ 7, sans travail perdu.

| Étape | Contenu | Fonctionnalités | Dépend de | Critère de validation |
|---|---|---|---|---|
| **R0** | Décisions H20 à H26 consignées ; spec modifiée (spec 10, 12, 13, 15, schémas) dans une PR séparée | — | — | Spec relue et acceptée |
| **R1** | Discovery (P1 en cours) + signaux de surfaces sensibles **sans valeurs** | F1 | R0 | Fichier attendu de `fx-split-stack` enrichi ; test « aucune valeur » au vert |
| **R2** | Inventory Claude Code : hooks par événement avec propriétaire et `onFailure`, permissions, sandbox, MCP | F3 | R1 | Chaque hook lu est listé avec sa source et `on_failure` ; une valeur littérale d'une clé sensible de `.mcp.json` est classée `literal` sans être émise ; une source illisible a un état explicite (la comparaison aux fiches passe en R3) |
| **R3** | `peo status --exposure [--ci] [--canary]` + catalogue initial réduit aux fiches qu'il consomme (Gitleaks, Semgrep, réglages natifs) | F2 (partiel), F11 | R2 | **Jalon A′** (mesures ci-dessous) |
| **R4** | Selector + questionnaire, avec les capacités `privacy.*`, `secrets.*`, `exposure.native` | F4, F5 | R3 | Déterministe ; refuse deux outils `privacy.masking` |
| **R5** | Planner, installeurs, adaptateur Claude (dont le bloc `permissions` et sandbox), lock, journal, doc générée | F6 à F9 | R4 | Idempotent ; tout affaiblissement d'un contrôle marqué dans le plan |
| **R6** | Porte + recette `feature`, `peo status --ci` complet | F10, F11 | R5 | Ancien jalon MVP (section 6) |
| Ensuite | `peo tools` complet, fiche Cloakroom (après spike S5), Inventory Codex (E7), recettes supplémentaires, catalogue partagé, portabilité, socles alternatifs | F12, F13, ex-P6 à P10 | R6 | Selon la demande |

Correspondance avec l'ancienne feuille de route (section 4) : R1 à R3 = P1 élargi ; R4 = P2 ; R5 = P3 ; R6 = P4.

### 7.1 Mesures du jalon A′

| Mesure | Seuil de succès |
|---|---|
| Dépôts réels audités | 3, de stacks différentes |
| Constats actionnables par dépôt | ≥ 1 |
| Constat « protégé » ou équivalent affiché à tort | 0 |
| Valeur sensible présente dans une sortie de PEO | 0 (test par fixture leurre) |
| Durée de `peo status --exposure` sans `--canary` | < 5 s |
| Accès réseau sans `--canary` | 0 (test NF5) |

### 7.2 Hors périmètre ajouté

| Fonctionnalité | Pourquoi jamais dans PEO |
|---|---|
| Masquage, pseudonymisation, détection de PII dans un flux | Chemin des données : latence, NF1, responsabilité. Délégué (document 17) |
| Approbation d'une action retenue par un outil de sécurité | Décision humaine seulement (document 17, section 7) |
| Orchestration d'exécution multi-agents | Six projets l'occupent (document 18, section 3) |
