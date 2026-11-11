# 03 — Audit des outils proposés

> Tous les dépôts ont été clonés et lus le **2026-11-11** (manifestes, hooks, skills, mécanismes d'installation). Commit et date entre parenthèses.
> Les fiches EGM, Spec Kit, Matt Pocock, Superpowers, Compound Engineering, Serena, Graphify et REA reprennent l'analyse détaillée du dossier `ai-eng-workflow` (documents 01 et 08), revérifiée pour les versions.

## 1. Comment lire les décisions

Les décisions sont prises **du point de vue de PEO**, c'est-à-dire : « cet outil doit-il figurer dans le catalogue, et avec quel statut ? ». Une décision « À écarter » signifie « ne pas proposer par défaut », pas « mauvais outil ».

| Décision | Sens dans le catalogue |
|---|---|
| **MVP** | Fiche complète, testée, proposée dès la première version |
| **Ultérieur** | Fiche prévue après le MVP |
| **Optionnel** | Proposé seulement sur signal précis du projet |
| **Écarter** | Pas de fiche active. Fiche « refusé » avec la raison, pour pouvoir **détecter** l'outil et prévenir |
| **Surveiller** | Pas de fiche. Réévaluation à date fixe |

Nouveau statut proposé [RECO] : **Socle alternatif**. Une méthodologie complète que PEO peut proposer **à la place** du socle par défaut, jamais en plus.

## 2. Matrice de synthèse

| Outil | Fonction réelle | Valeur pour PEO | Redondances | Limites | Décision |
|---|---|---|---|---|---|
| **Elephant-Goldfish Model** (`8c29f56`, 2026-11-10, Apache-2.0, plugin 0.1.1) | Relecture par sous-agents **sans contexte** (Goldfish), boucles de convergence, détection de dérive doc ↔ code, cartographie par README | **Seule** relecture réellement indépendante du marché examiné | Rédaction de design doc ≈ Spec Kit (spec + plan) | Jeune (0.1). Skills non chaînables. Coût élevé en sous-agents. Exige Claude Code ≥ 2.1.271 pour isoler les Goldfish | **MVP** (dans le socle par défaut, rôle : vérification) |
| **GitHub Spec Kit** (`f29319d`, 2026-11-10, MIT, 1.4.0) | CLI qui installe un processus de spécification : `spec.md`, `plan.md`, `tasks.md`, constitution, presets, extensions, workflows, 43 intégrations | Colonne vertébrale traçable (identifiants `FR`, `T`), portable, porte native sur `checklists/` | Plan et tâches ≈ EGM, Matt Pocock, Superpowers, BMAD | Publications quasi quotidiennes. Hooks d'extension appliqués par prompt, non contraints | **MVP** (socle par défaut, rôle : artefacts) |
| **Matt Pocock Skills** (`4ae2317`, 2026-10-31, MIT, 1.3.2) | Petits skills composables : `grilling`, `domain-modeling`, `tdd`, `code-review`, `diagnosing-bugs`… | Discipline d'exécution, glossaire et ADR, TDD par tranches verticales | `to-spec`, `to-tickets`, `implement` ≈ Spec Kit | Pas d'état, pas de portes. Renommages fréquents. Collisions de noms (`/code-review`) | **MVP** (socle par défaut, rôle : alignement et exécution) |
| **Superpowers** (`22f0b46`, 2026-11-03, MIT, 7.0.2) | Méthodologie complète en 14 skills, imposée par un hook `SessionStart` | Méthodologie cohérente et éprouvée | Recouvre tout le socle par défaut | Injection à chaque session (« if there is even a 1% chance… you ABSOLUTELY MUST invoke the skill »). Incompatible avec tout autre socle | **Socle alternatif**, exclusif |
| **Everything Claude Code** (`d2ef268`, 2026-11-06, MIT, 2.2.3) | « Harness OS » : 71 agents, 314 skills (313 invocables par le modèle), 27 hooks sur 8 événements, profils d'installation | Concepts : profils et modules, manifeste de propriété, niveaux de hooks | Recouvre tout, et PEO lui-même sur la partie profils | Contexte énorme. Offre commerciale associée. Impossible à combiner avec un autre socle | **Écarter** par défaut, **Surveiller** comme socle alternatif. **Reprendre les concepts** |
| **Compound Engineering** (`4ba4887`, 2026-11-11, MIT, 3.37.1) | Boucle brainstorm → plan → work → review → compound. Mode autonome `lfg` | `ce-compound` : capitalisation des leçons sous la forme la moins coûteuse | 28 skills invocables recouvrent le socle | `CONCEPTS.md` concurrence le glossaire. `lfg` contraire aux portes humaines | **Socle alternatif**, exclusif. `ce-compound` seul : **Ultérieur** (copie) |
| **Ponytail** (`96608e0`, 2026-10-29, MIT, plugin 5.3.3) | Mode « lazy senior dev » : solution la plus simple, YAGNI, bibliothèque standard d'abord | Discipline de simplicité, revendiquée mesurée | `zoom-out` d'EGM, YAGNI de la constitution, refactoring de `code-review` | 3 hooks d'injection (`SessionStart`, `SubagentStart`, `UserPromptSubmit`). Tableau de bord **activé par défaut** qui écrit dans `~/.config/ponytail/band/`, webhook optionnel. Chiffres de benchmark **auto-déclarés** | **Optionnel**, à évaluer sur le pilote. Ne pas activer avec un autre plugin qui injecte au démarrage |
| **TDD Guard** (`ffb7026`, 2026-11-03, MIT, plugin 1.3.0, npm 1.7.0) | Bloque l'écriture de code sans test en échec, par hooks | Application **réelle** du TDD | `tdd` de Matt Pocock (discipline sans contrainte) | Hooks qui lancent `npx tdd-guard@latest` : **version non épinglée exécutée à chaque écriture**. Validation par appel LLM à chaque action (coût, latence). Le README annonce son successeur | **Écarter** au profit de **Probity** |
| **Probity** (`eeac421`, 2026-11-03, MIT) | Règles déterministes ou validées par IA sur chaque écriture et commande, multi-agents (Claude Code, Codex, Copilot CLI) | Moteur de **règles d'action** portable. Pourrait porter les portes de PEO | Le hook `gate` de PEO | Configuration en TypeScript (Node requis). Jeune | **Ultérieur** : évaluer comme moteur de portes à la place d'un hook maison |
| **Semgrep** (`06d9993`, 2026-11-09, LGPL-2.1) | Analyse statique de sécurité, règles par motifs. `semgrep mcp`. Plugin Claude dans la marketplace officielle, épinglé par SHA (`b58f407`) | Sécurité déterministe, en CI et dans la boucle | `security-guidance` (Anthropic), SonarQube | Plugin = hooks d'analyse : coût de latence. Règles avancées dans l'offre payante | **Optionnel** (profil sécurité) : CLI en CI **au MVP**, plugin ultérieur |
| **REA** (`dc5527b`, 2026-11-11, MIT, 6.8.0) | Rétro-ingénierie : binaires, Electron, .NET, APK, HAR, firmwares. MCP + skill de 43 Ko | Seul outil pour un artefact sans code source | Aucune | Catalogue MCP volumineux (réductible avec `hot-cold`). Lance parfois la cible. Cadre légal à respecter | **Optionnel**, rare, jamais par défaut |
| **Serena** (`6e5c377`, 2026-11-09, GPL-3.0-or-later pour l'application, MIT pour SolidLSP) | Outils d'IDE par symbole via LSP (40+ langages) : recherche, références, édition, renommage | Grands dépôts, refactorings transverses | LSP natifs de Claude Code (lecture), Graphify (vue macro) | Le README déconseille la marketplace. Le contexte `claude-code` remplace `Edit` par ses propres outils (**contourne les portes** si non pris en compte). Mémoire concurrente à désactiver | **Optionnel** (gros dépôts) |
| **Graphify** (`35d1d20`, 2026-11-10, Apache-2.0 + MIT, 0.9.106) | Graphe de connaissances du code par tree-sitter, sans LLM. Requêtes, rayon d'impact | Découverte rapide d'un existant, comparaison aux frontières déclarées | Serena (niveau symbole), `egm-bootstrap` | `graphify install` modifie `CLAUDE.md` et intercepte `Read`/`Grep`. Offre cloud commerciale | **Optionnel** (CLI seul). **Ultérieur** comme source de la découverte profonde |
| **Tree-sitter** (`8a476cb`, 2026-11-06, MIT, 0.28.0) | **Bibliothèque** d'analyse syntaxique incrémentale | Base technique d'outils (Graphify, ast-grep), pas un outil pour l'agent | Embarqué par Graphify et ast-grep | Utiliser directement = dépendance et grammaires à gérer | **Écarter** comme entrée de catalogue. **Ultérieur** comme dépendance de la découverte profonde, de préférence via ast-grep |
| **ast-grep** (`627f854`, 2026-11-11, MIT, 0.51.2) | Recherche et réécriture structurelles par motifs d'AST, binaire unique. **Skill officiel** (`ast-grep/agent-skill`, marketplace Claude, 2026-11-03) | Règles d'architecture déterministes, codemods, recherche fiable | grep, Serena (en partie) | Écriture de règles demandant un apprentissage | **Optionnel** pour l'agent. **Ultérieur** comme moteur de règles de dérive dans PEO |
| **Playwright** (`3b43822`, 2026-11-10, Apache-2.0). MCP `0.0.85` | Automatisation navigateur. Le README du MCP **recommande la CLI + skills** pour les agents de code, plus économe en tokens | Validation de bout en bout du front | `chrome-devtools-mcp` | MCP coûteux en contexte (arbres d'accessibilité) | **Optionnel** (profil front), **CLI + skill de préférence** |

## 3. Observations transverses

### 3.1 La moitié des outils injectent quelque chose à chaque session

| Outil | Injection |
|---|---|
| Superpowers | `SessionStart` (startup, clear, compact) |
| Ponytail | `SessionStart`, `SubagentStart`, `UserPromptSubmit` |
| TDD Guard | `SessionStart`, `UserPromptSubmit`, `PreToolUse` |
| ECC | 27 gestionnaires sur 8 événements |
| Graphify (`graphify install`) | `PreToolUse` sur `Read`, `Glob`, `Bash`, `Grep` + bloc dans `CLAUDE.md` |

**Conséquence pour PEO** [RECO] : le catalogue doit décrire, pour chaque outil, **les événements de hook qu'il occupe**. Le moteur de sélection doit refuser deux outils qui injectent un processus en `SessionStart`, et `peo status` doit lister tous les hooks actifs avec leur propriétaire. Aucun outil du marché ne fait cet inventaire.

### 3.2 Versions flottantes exécutées automatiquement

TDD Guard exécute `npx tdd-guard@latest` à chaque écriture, l'entrée Serena de la marketplace officielle utilise la branche principale, Playwright MCP se lance avec `@latest` dans sa doc. **Le catalogue PEO doit réécrire ces commandes avec une version épinglée** quand l'outil le permet, ou signaler le risque.

### 3.3 Les chiffres de performance sont auto-déclarés

Ponytail (« −45 % de tokens »), Graphify (« −80 % »). Le catalogue doit distinguer **mesure indépendante**, **mesure de l'éditeur** et **non mesuré**. [RECO] Champ `evidence` dans chaque fiche.

### 3.4 Lien fourni pour Graphify

[FAIT] L'adresse `https://github.com/graphify` donnée dans la demande ne désigne pas le projet. Le dépôt est `Graphify-Labs/graphify` (anciennement `safishamsi/graphify`, qui redirige).

## 4. Outils ajoutés à l'étude

| Outil | Pourquoi | Décision |
|---|---|---|
| **Microsoft APM** | Gestionnaire de paquets d'agents complet (document 02) | **Ultérieur** comme backend d'installation optionnel |
| **skills CLI** | Installe, met à jour et verrouille (empreintes) les skills copiés | **MVP** comme installeur délégué pour les skills copiés **[À VÉRIFIER : compatibilité de `skills-lock.json` avec le lock de PEO]** |
| **Probity** | Moteur de règles d'action portable | **Ultérieur** (voir matrice) |
| **rulesync** | Portabilité vers d'autres agents | **Ultérieur** (P10) |
| **LSP natifs** (`php-lsp`, `typescript-lsp`, `pyright-lsp`) | Navigation de code native, peu coûteuse | **MVP** dans les profils de stack |
| **Context7** | Doc de bibliothèques à jour (service hébergé) | **Optionnel** |

## 5. Socles méthodologiques : une décision structurante

Le catalogue contiendra plusieurs **socles exclusifs**. [RECO] **Le MVP n'en supporte qu'un** : Spec Kit + EGM + Matt Pocock, déjà conçu et justifié. Les autres apparaissent comme fiches « socle alternatif, non supporté par le MVP », pour que PEO sache les **détecter** et **refuser de les cumuler**.

[DÉCISION] Socle par défaut du MVP : Spec Kit + EGM + Matt Pocock (recommandé), ou un autre ?

## Sources

Dépôts (commit, date) : [google/elephant-goldfish-model](https://github.com/google/elephant-goldfish-model) · [github/spec-kit](https://github.com/github/spec-kit) · [mattpocock/skills](https://github.com/mattpocock/skills) · [obra/superpowers](https://github.com/obra/superpowers) · [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) · [EveryInc/compound-engineering-plugin](https://github.com/EveryInc/compound-engineering-plugin) · [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) · [nizos/tdd-guard](https://github.com/nizos/tdd-guard) · [nizos/probity](https://github.com/nizos/probity) · [semgrep/semgrep](https://github.com/semgrep/semgrep) · [morluto/rea](https://github.com/morluto/rea) · [oraios/serena](https://github.com/oraios/serena) · [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) · [tree-sitter/tree-sitter](https://github.com/tree-sitter/tree-sitter) · [ast-grep/ast-grep](https://github.com/ast-grep/ast-grep) · [ast-grep/agent-skill](https://github.com/ast-grep/agent-skill) · [microsoft/playwright](https://github.com/microsoft/playwright) · [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) · [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) (`43fd1f9`, 2026-11-10)
