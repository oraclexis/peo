# PEO — dossier de conception et spécification (phase P0)

Analyse, challenge et conception du **Project Engineering Orchestrator**. Aucune ligne de code, aucune installation, aucun fichier de projet modifié. Vérifications faites le **2026-11-11** sur les dépôts clonés et la documentation officielle de Claude Code.

## Conclusion en cinq lignes

1. PEO vaut la peine **en couche fine** : catalogue d'outils **évalué**, **sélection minimale justifiée**, **composition du processus avec portes**. Personne ne fait cela aujourd'hui.
2. PEO ne doit **pas** être un gestionnaire de paquets : Claude Code, Microsoft APM, `uv`, npm et Spec Kit installent déjà. PEO calcule le plan et **délègue**.
3. **Un seul socle méthodologique par projet** (Spec Kit + EGM + Matt Pocock par défaut ; Superpowers, BMAD, Compound Engineering, ECC comme alternatives exclusives).
4. `.peo/` passe de **30 éléments à 5** : configuration, profil, lock, journal, doc générée. La connaissance reste à ses emplacements natifs.
5. Principal risque : la **maintenance du catalogue**, pas la technique.

## Décisions

Les décisions H1 à H12 ont été prises le 2026-11-11 (document 08, section 6 bis). Pilote existant n°1 : ÉPURE (document 09). Reste à désigner : un dépôt existant sans front lourd.

**Spécification détaillée du MVP : dossier [spec/](spec/10-spec-overview.md)** (documents 10 à 16 et schémas JSON validés). Elle attend ta validation, notamment des décisions S-1 à S-7, avant le début de la phase P1.

## Documents

| Fichier | Contenu |
|---|---|
| [01-vision-et-analyse-strategique.md](01-vision-et-analyse-strategique.md) | Pertinence, problème, cibles, cas prioritaires, valeur face à Claude Code seul, réponse franche « projet indépendant ou non » |
| [02-analyse-concurrentielle.md](02-analyse-concurrentielle.md) | APM, ECC, claude-code-templates, skills CLI, rulesync, ruler, BMAD, Probity, fonctions natives de Claude Code, concepts à reprendre |
| [03-audit-des-outils.md](03-audit-des-outils.md) | Matrice des 15 outils demandés + 6 ajoutés, avec décision justifiée |
| [04-architecture-cible.md](04-architecture-cible.md) | Challenge des 10 composants, architecture simplifiée et évolutive, flux, structure `.peo/` définitive, commandes, sécurité et autonomie |
| [05-plugin-manager.md](05-plugin-manager.md) | Types d'outils et adaptateurs, opérations, mises à jour, rollback, conflits, validation, stratégie de catalogue |
| [06-modele-de-donnees.md](06-modele-de-donnees.md) | Capacités, fiche d'outil, socle, recette, `peo.toml`, `profile.json`, lock, journal, algorithme de sélection |
| [07-mvp-et-roadmap.md](07-mvp-et-roadmap.md) | MVP (13 fonctionnalités avec critères d'acceptation), hors périmètre, feuille de route révisée, stratégie de tests, mesures |
| [09-pilote-epure.md](09-pilote-epure.md) | Découverte, questionnaire et sélection joués à la main sur un projet réel ; 6 écarts de conception révélés |
| [08-risques-et-decisions.md](08-risques-et-decisions.md) | 5 risques, 5 décisions, ce qu'il ne faut pas construire, choix techniques, alternatives, 12 décisions humaines |
| [spec/10-spec-overview.md](spec/10-spec-overview.md) | Spécification : périmètre, glossaire, architecture du code, exigences non fonctionnelles, points techniques levés, décisions S-1 à S-7 |
| [spec/11-cli-and-commands.md](spec/11-cli-and-commands.md) | CLI, sorties JSON, codes de sortie, skills, hooks |
| [spec/12-discovery.md](spec/12-discovery.md) | Détection : composants, runtime, commandes, conventions, dérive documentaire, signaux |
| [spec/13-catalog-and-selection.md](spec/13-catalog-and-selection.md) | Catalogue initial (19 fiches), langage `when`, questionnaire, Selector |
| [spec/14-planner-installers.md](spec/14-planner-installers.md) | Actions et risques, Inventory, adaptateurs, Spec Kit, fichiers gérés, `CLAUDE.md`, lock, journal |
| [spec/15-flow-and-gates.md](spec/15-flow-and-gates.md) | Recettes, portes, `peo gate`, `peo context`, `peo status` |
| [spec/16-test-plan.md](spec/16-test-plan.md) | Fixtures, référence synthétique `fx-split-stack`, test local ÉPURE, tests d'acceptation F1 à F13 |
| [spec/schemas/](spec/schemas/README.md) | 7 schémas JSON, exemples ÉPURE, contre-exemples, script de vérification |

Ordre de lecture conseillé : 01 → 08 → 04 → 03 → 02 → 06 → 05 → 07 → 09, puis la spécification 10 → 16.

## Légende

- **[FAIT]** vérifié dans le code ou la documentation officielle (source et date indiquées)
- **[HYPOTHÈSE]** plausible, non vérifié
- **[RECO]** recommandation
- **[DÉCISION]** arbitrage qui t'appartient

## Lien avec les travaux précédents

Ce dossier s'appuie sur le dossier `ai-eng-workflow` (analyse détaillée d'EGM, Spec Kit, Matt Pocock et de six plugins, conception du plugin `forge`). Il recommande de faire de `forge` le MVP de PEO.
