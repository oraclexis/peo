# 08 — Risques, décisions et recommandations finales

## 1. Les cinq principaux risques

| # | Risque | Probabilité | Impact | Atténuation |
|---|---|---|---|---|
| R1 | **Le catalogue devient obsolète.** Les outils évoluent chaque semaine (Spec Kit a publié deux versions en deux jours ; Matt Pocock a renommé `CONTEXT.md` en `GLOSSARY.md` ; TDD Guard a été remplacé par Probity). Une fiche fausse produit une mauvaise recommandation, plus dangereuse qu'aucune recommandation | **Élevée** | **Élevé** | Catalogue court. Date d'expiration par fiche. CI qui recalcule la surface réelle (hooks, MCP) et ouvre une issue en cas d'écart. Versions **testées** et épinglées |
| R2 | **Claude Code absorbe la valeur de PEO.** Dépendances de plugins, workflows, règles par chemin sont arrivés en quelques mois. Une sélection de plugins native est plausible | Moyenne | Élevé | Se placer sur ce qu'Anthropic ne fera probablement pas : neutralité entre méthodologies tierces, jugement sur les outils tiers, portes de processus. Cœur indépendant de Claude (CLI) |
| R3 | **PEO devient un installeur de code tiers avec les droits de l'utilisateur.** Un plugin compromis ou une version flottante exécutée par hook est exécutée parce que PEO l'a recommandée | Moyenne | **Très élevé** | Fiches relues, versions épinglées, surface affichée avant installation, accord explicite, aucune installation système, contrôle d'Unicode caché, pas d'auto-mise à jour au MVP |
| R4 | **Dérive vers la complexité** : PEO devient un nouvel ECC (gestionnaire de paquets, agents, mémoire, méthodologie) | **Élevée** | Élevé | Règles de non-périmètre écrites (section 3). Toute nouvelle fonction doit montrer qu'aucun outil existant ne la fait. Revue d'architecture à chaque phase |
| R5 | **Adoption** : le gain ne compense pas l'effort d'apprentissage, ou l'utilisateur garde l'habitude d'installer à la main | Moyenne | Moyen | Jalon MVP mesuré (document 07, section 6). Une seule commande pour démarrer. Doc générée par projet. Abandon assumé si les seuils ne sont pas atteints |
| R6 | **Sur-promesse de sécurité** (ajout du 2026-11-12) : l'utilisateur croit ses données protégées alors que la mesure est heuristique ou contournable | Moyenne | **Très élevé** | Garantie affichée pour chaque surface (document 17, section 4) ; jamais le mot « protégé » ; contrôle canari ; aucun masquage dans PEO |

Risques secondaires : jeunesse des outils du socle par défaut (EGM 0.1) ; ~~disponibilité de l'API de détection des plugins installés (H19)~~ levé : `claude plugin list --json` est documenté (spec 10, section 5) ; latence des hooks si plusieurs plugins en posent ; conflits de fusion du journal entre branches (atténué par `merge=union`).

## 2. Les cinq décisions architecturales les plus importantes

| # | Décision | Alternative écartée | Raison |
|---|---|---|---|
| D1 | **PEO délègue l'installation** à des adaptateurs vers les installeurs natifs (Claude plugin CLI, `claude mcp`, `uv`, npm, Spec Kit), avec interface prête pour APM | Écrire un gestionnaire de paquets | APM, Claude Code et les gestionnaires de langages le font déjà et mieux. C'est la principale source de complexité évitée |
| D2 | **Un seul socle méthodologique actif par projet**, choisi par le Selector | Combiner librement les méthodologies | Vérifié : chaque méthodologie couvre tout le cycle et plusieurs injectent leur processus à chaque session. Les cumuler crée plusieurs sources de vérité |
| D3 | **`.peo/` = configuration + profil + lock + journal + doc générée**. La connaissance reste aux emplacements natifs, PEO l'indexe | `.peo/context/`, `.peo/architecture/`, `.peo/knowledge/`, `.peo/agents/` | Éviter une seconde documentation et des mémoires concurrentes. Cinq fichiers au lieu de trente |
| D4 | **Cœur déterministe** (CLI Python, bibliothèque standard) ; le LLM ne sert qu'au dialogue et à la rédaction de la mission | Logique dans des skills et des prompts | Reproductibilité, tests classiques, usage en CI, portabilité vers d'autres agents, faible coût en tokens |
| D5 | **Sélection par capacités** (vocabulaire fermé, contraintes, coût), et non par profils statiques | Profils prédéfinis à la ECC | La redondance et le conflit deviennent calculables. Les profils restent possibles comme **raccourcis** de réponses |

## 3. À ne surtout pas développer au départ

1. Un gestionnaire de paquets, un résolveur semver, un cache de téléchargement.
2. Un registre en ligne, un service, une base de données, un serveur MCP.
3. Des skills de discipline d'ingénierie propres à PEO (spec, TDD, revue) : c'est le travail des socles.
4. Des personas d'agents (`architect`, `developer`, `reviewer`, `security`).
5. Un moteur d'exécution de workflows : Claude Code workflows et Spec Kit workflows existent ; PEO compose des recettes et pose des portes.
6. Un système de mémoire ou de recherche sémantique.
7. Les mises à jour automatiques et le rollback multi-commandes.
8. Le support de plusieurs agents et de plusieurs socles.
9. Un tableau de bord ou une interface graphique.
10. Un mécanisme de masquage, de pseudonymisation ou de détection de PII dans un flux (ajout du 2026-11-12, document 17).
11. Une couche d'exécution multi-agents : worktrees, fusion, budgets (ajout du 2026-11-12, document 18).

## 4. Choix techniques recommandés

| Domaine | Choix | Justification |
|---|---|---|
| Langage du cœur | Python ≥ 3.11, bibliothèque standard | `tomllib` natif, même prérequis que Spec Kit, multiplateforme |
| Distribution | Paquet PyPI (`uv tool install peo`) + plugin Claude Code (skills fins + hooks) dans une marketplace Git | Le CLI sert aussi en CI ; le plugin sert d'interface |
| Configuration éditée | TOML | Stdlib, typage explicite |
| Données générées | JSON (+ JSON Schema), NDJSON pour le journal | Diffable, validable |
| Catalogue | Dépôt Git curé, fiches TOML, versionné par tags | Revue par merge request, historique |
| Hooks | Script du CLI (`peo gate`, `peo context`) appelé par les hooks du plugin | Déterministe, testable, sans LLM |
| Licence de PEO | Apache-2.0 ou MIT | Compatible avec tout le catalogue examiné ; Apache-2.0 apporte une clause de brevets [DÉCISION] |
| Tests | pytest, fixtures de dépôts, conteneurs pour l'intégration | Section 5 du document 07 |

## 5. Alternatives à considérer

| Alternative | Quand la préférer |
|---|---|
| **PEO comme surcouche d'APM** : PEO choisit, écrit `apm.yml`, APM installe | Si la portabilité multi-agents devient prioritaire et qu'APM passe en 1.0. PEO perd l'activation native des plugins Claude (APM copie les fichiers) |
| **PEO comme extension ou bundle Spec Kit** | Si tu acceptes de lier PEO à Spec Kit. Gain : catalogues, 43 intégrations, workflows YAML. Perte : neutralité méthodologique |
| **Rester sur `forge`** (dossier précédent) | Si le besoin reste personnel et mono-socle. Beaucoup plus simple ; PEO ne vaut l'effort que si le catalogue et la sélection servent à d'autres personnes |
| **Contribuer aux projets existants** (ex. sélection par capacités dans ECC, inventaire de hooks dans APM) | Si l'objectif est l'impact plutôt que la maîtrise d'un outil propre |

## 6. Décisions humaines nécessaires

| # | Décision | Ma recommandation |
|---|---|---|
| H1 | Développer PEO comme **couche fine** (catalogue évalué + sélection + composition + portes), en déléguant installation, portabilité et exécution | **Oui** |
| H2 | Fusionner `forge` dans PEO (forge = MVP de PEO) | **Oui** |
| H3 | Socle par défaut du MVP | Spec Kit + EGM + Matt Pocock |
| H4 | Backend d'installation : natifs (MVP) avec interface pour APM plus tard | **Oui** (option C du document 02) |
| H5 | Format de configuration : TOML ou YAML | TOML |
| H6 | Structure `.peo/` réduite à 5 éléments | **Oui** |
| H7 | Nomenclature : `/peo:init`, `/peo:status`, `/peo:tools`, `/peo:flow` | **Oui** |
| H8 | Licence du projet | Apache-2.0 |
| H9 | Gouvernance du catalogue : qui relit une fiche, à quel rythme | Toi seul au MVP, revue mensuelle ; ouverture aux contributions en P7 |
| H10 | Langue du projet (code, doc, catalogue) | Code et fiches en anglais pour l'open source ; doc utilisateur bilingue plus tard |
| H11 | Projets pilotes pour le jalon MVP | Trois dépôts réels de stacks différentes, à désigner |
| H12 | Niveau d'autonomie maximal autorisé au MVP | Guidé et semi-autonome seulement |

## 6 bis. Décisions prises le 2026-11-11

| # | Décision | Choix |
|---|---|---|
| H1 | Positionnement | **Couche fine** : catalogue évalué, sélection, composition et portes. Installation déléguée |
| H2 | `forge` | **Fusionné** : `forge` devient le MVP de PEO |
| H3 | Socle par défaut du MVP | **Spec Kit + EGM + Matt Pocock** |
| H4 | Backend d'installation | **Installeurs natifs**, avec une interface d'adaptateur prête pour APM |
| H5 | Format de configuration | **TOML** |
| H6 | Structure `.peo/` | **5 éléments** (+ `backups/` hors git) |
| H7 | Commandes | **4** : `/peo:init`, `/peo:status`, `/peo:tools`, `/peo:flow` |
| H8 | Licence | **Apache-2.0** |
| H9 | Gouvernance du catalogue | **Toi seul, revue mensuelle** au MVP ; contributions externes en P7 |
| H10 | Langue | **Code et fiches en anglais**, documentation française plus tard |
| H11 | Projets pilotes | **Un nouveau projet** + **pilote n°1** (existant, Nuxt 4 + Laravel/Filament, document 09). Reste à désigner : un dépôt existant sans front lourd. Jeu de test de référence : fixture synthétique `fx-split-stack` (spec 16, section 2 ; décision du 2026-11-12, qui remplace la copie anonymisée acceptée le 2026-11-11) |
| H12 | Autonomie maximale au MVP | **Guidé et semi-autonome** |

**Point ouvert sur H11.** L'hypothèse de valeur du MVP porte sur les **projets existants** (document 07, section 1), là où la découverte automatique et la détection de conflits apportent le plus. Un nouveau projet seul ne permet pas de la valider. Il faut au moins un, idéalement deux dépôts existants de stacks différentes pour le jalon MVP.

## 6 ter. Décisions de spécification à valider

La spécification détaillée (dossier [spec/](spec/10-spec-overview.md)) ajoute sept décisions S-1 à S-7, réversibles, listées dans la spec 10, section 6. Les deux qui changent le plus la conception :

- **S-2** : la porte vit dans les réglages du projet, pas dans le plugin PEO ;
- **S-3** : un `CLAUDE.md` existant est conservé par défaut ; la migration règle par règle devient une option.

## 6 quater. Décisions du 2026-11-12 (révision stratégique)

Analyse : documents 17 et 18, section 9 des documents 01, 02 et 04, section 7 du document 07. Numérotation à partir de H20 : H19 désigne déjà un point technique (section 1).

| # | Décision | Choix | Conséquence |
|---|---|---|---|
| H20 | Ordre de la feuille de route | **L'audit d'abord** : Discovery, Inventory et `peo status --exposure` avant le Selector | Document 07, section 7 (R0 à R6) |
| H21 | Périmètre sécurité et confidentialité | **Détecter, configurer, vérifier.** Aucun masquage ni détection de PII dans PEO ; application à l'exécution déléguée | Document 17, section 1 ; section 3, point 10 |
| H22 | Cloakroom | **Proposé seulement sur signal** (`secret_files` ou `data_stores`), jamais par défaut ; réglages natifs toujours proposés avant ; fiche écrite après le spike S5 | Document 05, section 8.2 |
| H23 | Inventaire des autres agents | **Claude Code seul au jalon A′** ; Codex en lecture seule dès qu'un pilote l'utilise ; Gemini CLI plus tard | Document 04, E7 ; document 05, section 8.3 |
| H24 | Lecture des fichiers sensibles par Discovery | `.env*` : **noms de variables seulement**. Dumps et logs : chemin, taille, extension. Aucune valeur dans une sortie de PEO, test par fixture leurre | Document 17, section 6.1 ; nouvelle exigence non fonctionnelle |
| H25 | Capacités exclusives | `privacy.masking` maintenant ; `orchestration.harness` avec la première fiche de harnais | Document 05, section 5 ; document 04, E8 |
| H26 | Livrables | Documents 17 et 18, amendements datés de 01, 02, 04, 05, 07, 08 ; **spec modifiée dans une PR séparée** | Ce dossier |

Conséquences sur la spécification (PR séparée, R0) :

- **S-5** : un signal peut aussi exister parce qu'un contrôle d'exposition le consomme.
- **NF5** : `--canary` exécute des outils tiers ; option explicite, jamais par défaut, sans réseau.
- Nouvelle exigence non fonctionnelle « aucune valeur » (H24).
- Spike **S5** (Cloakroom) et points ouverts O1 à O3 : document 17, section 8.

Revue recommandée avant la spec : relecture EGM du document 17.

## 6 quinquies. Décisions du 2026-11-13

Analyse : conception de R2 (Inventory), brainstorm EGM et deux relectures ; spec 14, section 3.

| # | Décision | Choix | Conséquence |
|---|---|---|---|
| H27 | État de la machine et sélection | **L'état de la machine bloque, il n'oriente jamais.** La sélection ne lit que les déclarations suivies du projet (`declared()` de l'Inventory : entrées de `.claude/settings.json` et `.mcp.json` suivis par git). Le Planner lit la vue observée et arrête le plan (`E_BACKBONE_CONFLICT`, code 6, portée citée) pour un socle alternatif ou un fournisseur de `privacy.masking` actif hors des déclarations suivies. Les autres capacités exclusives dans ce cas ne bloquent pas : constat `info` de `peo status` | Spec 13, sections 7.2, 8.1 et 8.5 ; spec 14, sections 2.4 et 3.4. La sélection, `[answers]` et la doc générée sont reproductibles entre machines. Code en R4 (Selector) et R5 (veto du Planner) ; R2 livre `declared()` |

## 7. Synthèse

PEO est **utile et différenciant** à condition de ne faire que ce que personne ne fait : **savoir** quels outils valent la peine pour un projet donné, **refuser** les combinaisons qui se marchent dessus, et **tenir** le processus. Il devient une mauvaise idée dès qu'il se met à installer, stocker, exécuter ou réinventer ce que Claude Code, APM, Spec Kit et les méthodologies existantes font déjà.

Le principal risque n'est pas technique : c'est la **maintenance du catalogue**. Le projet doit être conçu dès le départ pour que cette maintenance soit outillée, datée et partageable.
