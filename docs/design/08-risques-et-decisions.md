# 08 — Risques, décisions et recommandations finales

## 1. Les cinq principaux risques

| # | Risque | Probabilité | Impact | Atténuation |
|---|---|---|---|---|
| R1 | **Le catalogue devient obsolète.** Les outils évoluent chaque semaine (Spec Kit a publié deux versions en deux jours ; Matt Pocock a renommé `CONTEXT.md` en `GLOSSARY.md` ; TDD Guard a été remplacé par Probity). Une fiche fausse produit une mauvaise recommandation, plus dangereuse qu'aucune recommandation | **Élevée** | **Élevé** | Catalogue court. Date d'expiration par fiche. CI qui recalcule la surface réelle (hooks, MCP) et ouvre une issue en cas d'écart. Versions **testées** et épinglées |
| R2 | **Claude Code absorbe la valeur de PEO.** Dépendances de plugins, workflows, règles par chemin sont arrivés en quelques mois. Une sélection de plugins native est plausible | Moyenne | Élevé | Se placer sur ce qu'Anthropic ne fera probablement pas : neutralité entre méthodologies tierces, jugement sur les outils tiers, portes de processus. Cœur indépendant de Claude (CLI) |
| R3 | **PEO devient un installeur de code tiers avec les droits de l'utilisateur.** Un plugin compromis ou une version flottante exécutée par hook est exécutée parce que PEO l'a recommandée | Moyenne | **Très élevé** | Fiches relues, versions épinglées, surface affichée avant installation, accord explicite, aucune installation système, contrôle d'Unicode caché, pas d'auto-mise à jour au MVP |
| R4 | **Dérive vers la complexité** : PEO devient un nouvel ECC (gestionnaire de paquets, agents, mémoire, méthodologie) | **Élevée** | Élevé | Règles de non-périmètre écrites (section 3). Toute nouvelle fonction doit montrer qu'aucun outil existant ne la fait. Revue d'architecture à chaque phase |
| R5 | **Adoption** : le gain ne compense pas l'effort d'apprentissage, ou l'utilisateur garde l'habitude d'installer à la main | Moyenne | Moyen | Jalon MVP mesuré (document 07, section 6). Une seule commande pour démarrer. Doc générée par projet. Abandon assumé si les seuils ne sont pas atteints |

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
| H11 | Projets pilotes | **Un nouveau projet** + **ÉPURE** (existant, Nuxt 4 + Laravel/Filament, document 09). Reste à désigner : un dépôt existant sans front lourd. Copie anonymisée d'ÉPURE acceptée comme jeu de test de référence |
| H12 | Autonomie maximale au MVP | **Guidé et semi-autonome** |

**Point ouvert sur H11.** L'hypothèse de valeur du MVP porte sur les **projets existants** (document 07, section 1), là où la découverte automatique et la détection de conflits apportent le plus. Un nouveau projet seul ne permet pas de la valider. Il faut au moins un, idéalement deux dépôts existants de stacks différentes pour le jalon MVP.

## 6 ter. Décisions de spécification à valider

La spécification détaillée (dossier [spec/](spec/10-spec-overview.md)) ajoute sept décisions S-1 à S-7, réversibles, listées dans la spec 10, section 6. Les deux qui changent le plus la conception :

- **S-2** : la porte vit dans les réglages du projet, pas dans le plugin PEO ;
- **S-3** : un `CLAUDE.md` existant est conservé par défaut ; la migration règle par règle devient une option.

## 7. Synthèse

PEO est **utile et différenciant** à condition de ne faire que ce que personne ne fait : **savoir** quels outils valent la peine pour un projet donné, **refuser** les combinaisons qui se marchent dessus, et **tenir** le processus. Il devient une mauvaise idée dès qu'il se met à installer, stocker, exécuter ou réinventer ce que Claude Code, APM, Spec Kit et les méthodologies existantes font déjà.

Le principal risque n'est pas technique : c'est la **maintenance du catalogue**. Le projet doit être conçu dès le départ pour que cette maintenance soit outillée, datée et partageable.
