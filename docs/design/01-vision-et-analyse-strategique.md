# 01 — Vision et analyse stratégique

> Phase P0, conception uniquement. Vérifications faites le **2026-11-11**.
> Légende utilisée dans tout le dossier :
> **[FAIT]** vérifié dans le code ou la doc officielle, avec source ·
> **[HYPOTHÈSE]** plausible, non vérifié ·
> **[RECO]** recommandation de ma part ·
> **[DÉCISION]** arbitrage qui t'appartient.

## 1. Réponse courte à la question posée

> **PEO mérite-t-il d'être un projet indépendant, ou ses fonctionnalités devraient-elles être intégrées à un outil existant ?**

**Ni l'un ni l'autre tel que formulé.** [RECO]

- **Comme plateforme indépendante complète** (registry, gestionnaire de paquets, moteur de workflows, gestion de connaissances, agents), PEO arriverait sur un terrain déjà occupé, par des projets mieux dotés qui avancent chaque semaine. Microsoft APM fait déjà le gestionnaire de paquets multi-agents avec manifeste, lockfile à empreintes, désinstallation propre, politique et détection de dérive. Everything Claude Code fait déjà les profils d'installation. Claude Code fait déjà plugins, dépendances, marketplaces, hooks et workflows (document 02). Reconstruire ces briques serait la principale erreur de conception possible.
- **Comme simple extension d'un outil existant**, PEO perdrait ce qui le rend utile : il doit rester **neutre** vis-à-vis des méthodologies (Spec Kit, Superpowers, BMAD, Compound Engineering…), ce qu'aucune d'elles ne fera pour ses concurrentes.

**Ce qui justifie un projet à part, c'est une couche fine** qui fait trois choses que personne ne fait aujourd'hui :

1. **Un catalogue évalué**, pas un annuaire : pour chaque outil, ce qu'il fait réellement, avec quoi il entre en conflit, ce qu'il coûte en contexte, quels hooks et accès réseau il ajoute. C'est une **base de connaissances sur les outils**.
2. **Une sélection minimale et justifiée** à partir du profil réel du projet : choisir **une** méthodologie, les capacités complémentaires utiles, et rien d'autre.
3. **La composition et le verrouillage du processus** : des portes humaines appliquées par hooks et CI, une seule source d'état, une doc générée pour le projet.

Tout le reste (installer, mettre à jour, synchroniser des règles vers d'autres agents, exécuter des workflows) est **délégué** aux outils qui le font déjà.

## 2. Le problème réellement résolu

| Symptôme observé | Cause | Ce que PEO apporte |
|---|---|---|
| Plugins accumulés « parce qu'ils sont populaires » | Pas d'évaluation comparée, pas de vue d'ensemble | Catalogue évalué, conflits explicites |
| Deux ou trois méthodologies actives en même temps | Chaque plugin se présente comme complet. Superpowers injecte même son processus à chaque session | Un seul « socle méthodologique » par projet |
| Contexte saturé | Descriptions de skills, schémas MCP, injections au démarrage | Coût de contexte connu et budgété par outil |
| Règles du processus non appliquées | Aucun des outils du socle n'applique ses propres règles (vérifié dans ce fil pour EGM, Spec Kit, Matt Pocock) | Portes par hooks et CI |
| Configuration non reproductible | Installations manuelles, versions flottantes | Configuration et lockfile versionnés |
| Chaque nouveau projet recommence de zéro | Pas de détection, pas de modèle | Découverte automatique + questions ciblées |

Le problème est **réel** : je l'ai vécu concrètement dans la conception précédente (dossier `ai-eng-workflow`), où l'essentiel du travail a consisté à détecter des recouvrements et des conflits de fichiers entre outils.

## 3. Utilisateurs cibles

| Segment | Besoin | Priorité |
|---|---|---|
| **Développeur senior ou lead technique** qui démarre ou reprend des projets régulièrement, sur plusieurs stacks | Environnement fiable en minutes, sans veille permanente sur les plugins | **Cible principale du MVP** |
| Petite équipe (2 à 10) | Même configuration pour tous, reproductible en CI | Secondaire, dès que la config est versionnée |
| Équipe plateforme d'une organisation | Catalogue interne, politique d'outils autorisés | Plus tard. APM couvre déjà la gouvernance d'entreprise |
| Débutant en IA agentique | Être guidé | Non prioritaire : nécessite beaucoup de pédagogie |

## 4. Cas d'utilisation prioritaires

| # | Cas | Priorité | Pourquoi |
|---|---|---|---|
| U1 | Initialiser un **projet existant** | **MVP** | Cas le plus fréquent, et celui où la découverte automatique apporte le plus |
| U2 | Initialiser un **nouveau projet** | **MVP** | Même mécanique, moins de détection |
| U3 | Connaître l'état : outils, versions, conflits, dérive | **MVP** | Sans cela, la configuration se dégrade en quelques semaines |
| U4 | Ajouter ou retirer un outil proprement | **MVP réduit** | Ajout et retrait, sans mises à jour automatiques |
| U5 | Dérouler une fonctionnalité avec portes | **MVP** | C'est ce qui transforme une installation en processus |
| U6 | Mettre à jour les outils | Plus tard, en mode manuel d'abord | Risque de régression élevé, valeur moyenne au démarrage |
| U7 | Moderniser ou reconstruire un logiciel | Plus tard | Dépend de capacités d'analyse lourdes (Graphify, REA, Serena) |
| U8 | Porter la configuration vers Codex, Cursor, Copilot | Plus tard, **mais données portables dès le MVP** | Délégable à des outils existants (rulesync, APM) |

## 5. Valeur ajoutée par rapport à Claude Code seul

| Besoin | Claude Code seul (vérifié) | Ce qu'ajoute PEO |
|---|---|---|
| Générer un `CLAUDE.md` | `/init` | Un `AGENTS.md` portable, structuré en pointeurs, cohérent avec les outils choisis |
| Installer des plugins | `claude plugin install`, `--scope project`, `enabledPlugins` | **Quels** plugins, **pourquoi**, et lesquels refuser |
| Regrouper des plugins | Plugin « bundle » avec `dependencies` | Bundle **calculé** pour le projet, et non figé par rôle |
| Mettre à jour | `autoUpdate`, contraintes semver sur tags git | Vue des versions testées ensemble, avant mise à jour |
| Hooks | Mécanisme complet | Hooks de portes prêts à l'emploi, et **inventaire des hooks des autres plugins** |
| Orchestration multi-agents | Workflows dynamiques (`.claude/workflows/*.js`), sans saisie utilisateur en cours d'exécution | Processus avec validations humaines entre les étapes |
| Mémoire | `CLAUDE.md`, règles par chemin, auto memory hors dépôt | Mémoire versionnée, une source par type de connaissance |

Sources : [skills](https://code.claude.com/docs/en/skills.md), [hooks](https://code.claude.com/docs/en/hooks.md), [mémoire](https://code.claude.com/docs/en/claude-md), [manifeste de plugin](https://code.claude.com/docs/en/plugins/manifest-reference.md), [dépendances](https://code.claude.com/docs/en/plugins/dependencies.md), [workflows](https://code.claude.com/docs/en/workflows.md). Vérifiées le 2026-11-11.

**Point de vigilance** : chaque version de Claude Code absorbe une partie de ce que les outils tiers faisaient (dépendances de plugins, workflows, règles par chemin). La valeur de PEO doit donc être placée **là où Anthropic n'ira probablement pas** : la neutralité entre méthodologies tierces et le jugement sur les outils tiers. [HYPOTHÈSE]

## 6. Risques de complexité

| Risque | Signe d'alerte | Garde-fou [RECO] |
|---|---|---|
| Devenir un gestionnaire de paquets | Écrire du code de téléchargement, de résolution semver, de cache | Déléguer à chaque installeur natif |
| Devenir une méthodologie de plus | Écrire ses propres skills de spec, de TDD, de revue | PEO n'écrit **aucun** skill de discipline d'ingénierie |
| Devenir un système de documentation | Dossier `.peo/context/`, `.peo/architecture/` | `.peo/` ne contient que de la configuration, un journal et une vue générée |
| Catalogue ingérable | Plus de 30 entrées à tenir à jour | Catalogue court, chaque fiche a une date d'évaluation et expire |
| Accumulation d'agents | Personas « architecte », « développeur », « reviewer » propres à PEO | Les outils choisis apportent leurs agents. PEO n'en ajoute pas |
| Dépendance à un fournisseur | Logique dans des prompts propres à Claude | Cœur déterministe en Python, prompts limités au dialogue |

## 7. Lien avec la conception précédente

Le plugin `forge` conçu dans `ai-eng-workflow/09-init-plugin.md` est **un cas particulier de PEO** : un seul socle (Spec Kit + EGM + Matt Pocock), un catalogue figé dans le plugin, une commande d'initialisation. PEO généralise ce design :

| `forge` | PEO |
|---|---|
| Socle méthodologique imposé | Socle **choisi** parmi plusieurs, un seul actif |
| Profils figés | Sélection par **capacités** et contraintes |
| `forge.toml`, `forge.lock.json`, doc générée | Même principe, renommé et étendu (`.peo/`) |
| `/forge:init`, `/forge:flow`, `/forge:doctor` | `/peo:init`, `/peo:flow`, `/peo:status`, `/peo:tools` |

[RECO] Fusionner les deux projets : `forge` devient le MVP de PEO, avec le socle Spec Kit + EGM + Matt Pocock comme premier socle du catalogue.

## 8. Conclusion de l'étape 1

| Question | Réponse |
|---|---|
| Le concept est-il pertinent ? | Oui, **sur un périmètre réduit** : catalogue évalué, sélection, composition et portes |
| Le problème est-il réel ? | Oui, et il grandit avec le nombre de plugins publiés |
| Faut-il tout construire ? | Non. Gestion des paquets, synchronisation multi-agents et exécution de workflows sont déjà disponibles |
| Principal risque | La maintenance du catalogue, pas la technique (document 08) |
| Forme recommandée | Cœur CLI Python déterministe + plugin Claude Code comme interface + catalogue curé dans un dépôt versionné |
