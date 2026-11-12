# 17 — Sécurité et confidentialité des données exposées aux agents

> Révision stratégique du **2026-11-12**. Décisions H20 à H26 (document 08, section 6 quater).
> Sources lues le 2026-11-12 : README, documentation et arborescence des dépôts cités, documentation officielle de Claude Code. **Aucun outil n'a été exécuté** : un **[FAIT]** signifie « documenté par le projet ou par la doc officielle », pas « testé ».
> Ce document complète le modèle de menace du document 04 (section 7.1), qui couvre les risques que PEO fait courir. Ici : les données **du projet** que l'agent peut voir ou envoyer.

## 1. Périmètre retenu (H21)

PEO **détecte, configure et vérifie**. Il ne se place **jamais** sur le chemin des données.

| PEO fait | PEO ne fait pas |
|---|---|
| Détecter les surfaces sensibles du projet (chemins, noms de variables, types de services) | Lire, stocker ou afficher une valeur sensible |
| Lire les contrôles en place (permissions, sandbox, hooks, outils de masquage, scan de secrets) | Masquer, pseudonymiser, détecter des PII dans un flux |
| Recommander et appliquer, avec accord, des **réglages natifs** et des **outils délégués** | Intercepter un prompt ou une sortie d'outil |
| Vérifier techniquement que les contrôles répondent (contrôle canari, section 6.4) | Restaurer une valeur pseudonymisée, approuver une action retenue |
| Signaler chaque mesure avec sa **garantie réelle** | Écrire « protégé » |

Raisons : la règle « bibliothèque standard seule » (NF1), la latence des hooks (NF4), la responsabilité, et l'existence d'outils spécialisés plus avancés (section 3).

## 2. Mécanismes : ne pas les confondre

| Mécanisme | Réversible | Ce que voit le modèle | Garantie | Statut RGPD [HYPOTHÈSE : lecture usuelle de l'art. 4(5) et du considérant 26] | Exemple |
|---|---|---|---|---|---|
| Détection + blocage | — | Rien | Forte sur ce qui est détecté, nulle sur le reste | Pas de traitement si bloqué | Gitleaks en pre-commit, `deny Read(./.env)` |
| Masquage temporaire | Oui, par l'humain | Valeur cachée à l'affichage | Faible : cosmétique | Donnée inchangée | Affichage `****` |
| Redaction irréversible | Non | `[REDACTED]` | Forte sur l'élément retiré | Peut rester personnelle par le contexte | Agent Privacy (sortie de Bash), barres noires de BlackBar |
| Pseudonymisation réversible | Oui, par le coffre | `PII_PERSON_1_xY3…` | Partielle : structure et quasi-identifiants restent | **Reste une donnée personnelle** | Cloakroom |
| Anonymisation | Non | Données synthétiques ou généralisées | Forte **si** la ré-identification est impossible, difficile à prouver | Hors RGPD si réelle | Greenmask, `presidio-structured` |
| Chiffrement | Oui, avec la clé | Rien d'exploitable | Forte au repos et en transit | Donnée personnelle protégée | Coffre de Cloakroom, trousseau du système |

**Règle de vocabulaire** : PEO n'emploie jamais « anonymisation » pour un outil de masquage par hooks. Envoyer « `PII_PERSON_1` habite à Lyon, client depuis 2019 » à un fournisseur reste un traitement de données personnelles.

## 3. Outils étudiés

### 3.1 Cloakroom — référence

[FAIT] `shanjeevrajendran/cloakroom`, Apache-2.0 (CLA pour les contributions), v1.4.0 du 2026-11-08, créé le 2026-10-11, un mainteneur. Sources : `README.md`, `docs-HOW-IT-WORKS.md`, `docs-LIMITS.md`.

| Sujet | Fonctionnement documenté |
|---|---|
| Détection | Règles pour les secrets de forme connue (AWS, GitHub, Stripe, Slack, OpenAI, Google, JWT, clés privées), PII avec somme de contrôle (cartes, IBAN, SSN), règles de contexte, modèle local PII-Tracer (révision épinglée, téléchargé une fois depuis Hugging Face). Mode `CLOAKROOM_MODE=rules` sans modèle |
| Pseudonymisation | Valeur remplacée par `PII_<KIND>_<n>_<tag>`, stable dans la session. Tag de 30 bits : HMAC sur l'identifiant du coffre, la session et le placeholder. Un placeholder deviné, d'une autre session ou mal signé **n'est pas restauré** |
| Formes dérivées | Base64, URL, JSON, hex, MD5/SHA-1/SHA-256, inversion : recherchées **à partir des valeurs déjà connues**, sans deviner |
| Correspondances | Coffre chiffré **par session** (AES-GCM), clé dans le trousseau du système. Journal des fichiers écrits (`~/.cloakroom/filelog.bin`) chiffré, **sans valeurs** (chemin, SHA-256, positions) : une valeur restaurée dans un fichier est re-masquée par correspondance exacte à la relecture |
| Restauration | Juste avant une écriture ou une commande locale. Jamais vers le modèle |
| Blocages | *Egress hold* : commande réseau (curl, ssh, `git push`, clients cloud et base, one-liners `python -c`…) qui porte un secret connu → refusée. *Money hold* : endpoints de paiement. Déblocage par l'humain seul (`cr: allow`, une fois, 10 min) |
| Auto-protection | L'agent ne peut ni approuver son propre blocage, ni désinstaller Cloakroom. Un hook ou un serveur MCP ajouté à une config d'agent est retenu |
| Erreurs | Programme absent → **échec fermé**. Service muet → appels d'outils retenus, prompts vérifiés par règles seules. Démarrage à froid : jusqu'à 40 s |
| Journal | Une ligne par événement, chaînée par hash, sans valeurs. `cloakroom report --verify` |
| Agents | Claude Code, Codex, Gemini CLI, Cursor (couverture différente pour chacun, tableau du README) |

**Limites documentées par le projet** :

| Cas | Effet |
|---|---|
| Commande en échec (`PostToolUseFailure`) | Sortie **non masquable** : peut atteindre le modèle. Comptée « non vérifiée » |
| Transcript local `~/.claude/projects/…` | Contient en clair les **entrées réécrites** (valeurs restaurées) et les prompts bloqués |
| `Edit` avec placeholder dans `old_string` | Échec : Claude Code compare `old_string` au fichier avant le hook |
| Prompt | Bloqué, jamais réécrit (limite de `UserPromptSubmit`) |
| Codex | Sortie des commandes longues en arrière-plan **non couverte** |
| Gemini CLI | Un hook qui dépasse son délai **laisse passer** l'appel |
| Cursor | Complétion Tab non vue ; écriture avec placeholder refusée |
| Recherche web côté serveur de l'éditeur | Non vue |
| `cloakroom proxy` | Magasin de placeholders **commun à la machine pendant 24 h** |
| Encodages arbitraires, valeur reconstruite par morceaux, secret jamais vu | Hors périmètre : « stops accidental leaks, not a model determined to leak » |
| Faux positifs | Plus nombreux que les scanners de secrets seuls (prénom isolé, par exemple) |

**Intégration dans PEO (H22)** : fiche `claude-plugin:cloakroom`, capacité `privacy.masking` (exclusive), **proposée seulement sur signal** (`secret_files` ou `data_stores`, section 6.1), jamais par défaut. Les réglages natifs (section 3.5) sont toujours proposés avant. La fiche n'est écrite qu'après le **spike S5** (section 8).

**Abstraction commune ?** Non. Un seul candidat sérieux : une interface « masqueur » serait prématurée.

### 3.2 BlackBar — périmètre précis

[FAIT] `zatuomfawas/BlackBar`, extension Chrome MV3, v0.1.10, 9 commits du 2026-07-27 au 2026-08-09. Licence **GPL-3.0 annoncée** (README, `package.json`) **sans fichier LICENSE** dans le dépôt. Version payante (licence signée hors ligne), marque déposée.

| Sujet | Constat |
|---|---|
| Détection | Lecture du **DOM avant capture** : `Range.getClientRects()` donne la géométrie exacte de chaque correspondance. 24 règles : identifiants (AWS, GitHub, Stripe, Slack, Google, SendGrid, GitLab, npm), JWT, jetons bearer, clés privées, secrets en URL, chaînes de connexion, cartes (Luhn), IBAN (mod-97), SSN, e-mails, téléphones, IP publiques, adresses, entropie ≥ 3,7. **Pas de noms, de visages ni de texte libre**, par choix |
| Contenus non analysables | `<img>`, `<canvas>`, `<video>`, iframes cross-origin : signalés comme **zones illisibles**, jamais supposés sûrs |
| Irréversibilité | Seules les barres noires comptent comme sûres (flou et pixellisation refusés par l'indicateur). Export re-rastérisé depuis le bitmap original, métadonnées supprimées |
| Réseau | `connect-src 'none'` imposé par Chrome, aucune permission d'hôte, test qui fait échouer le build si `fetch`, `XMLHttpRequest`, `WebSocket`, `sendBeacon` ou `eval` apparaissent |
| Absent | OCR (prévu en v1.1, payant), règles personnalisées, QR codes. `STRATEGY.md` cité mais absent |

**Place dans PEO : aucune intégration.** BlackBar protège les captures **qu'un humain partage depuis Chrome**. Il ne couvre ni les captures prises par un agent (Playwright MCP, computer use), ni les autres applications, et n'offre aucune API. À retenir comme **modèle de preuve** : une garantie de confidentialité vérifiable par un test de build et une politique appliquée par la plateforme.

### 3.3 Agent Privacy

[FAIT] `JackDDavis/agent-privacy`, MIT, « Experimental research project », 30 commits, dernier le 2026-06-22.

| Sujet | Constat |
|---|---|
| Architecture | Bibliothèque `pii_guard` (source unique) + adaptateurs fins par agent. Niveau 1 local : regex et `detect-secrets`. Niveau 2 optionnel : service de filtrage NLP HTTP (FastAPI + Ollama), **local ou sur le LAN** |
| Actions | allow, redact, block, *handoff* (résumé par un modèle local) |
| Couverture | Claude Code : prompt, avant outil, après outil pour Bash et Read, **pas pour Edit/Write**. Codex : la sortie est **bloquée** faute de remplacement. Copilot CLI : complète |
| Échec | Secrets : fermé. Injection : **ouvert** (`degraded=True`) |
| Journal | JSONL, empreinte SHA-256 de 16 caractères, **jamais le contenu** |
| Installation | Liens symboliques dans `~/.claude`, `~/.codex`, `~/.copilot` : portée utilisateur globale |
| Restauration | Aucune : redaction, pas pseudonymisation |

**Place dans PEO** : pas de fiche. Deux idées à garder : le journal de décisions par empreinte, et le routage d'une tâche sensible vers un modèle local. Point de vigilance : en mode LAN, le texte **quitte la machine**.

### 3.4 Autres outils

| Outil | Rôle | Licence · état | Décision |
|---|---|---|---|
| **Gitleaks** | Secrets dans le dépôt, l'historique, un dossier. Binaire unique | MIT · actif | **Fiche `ci-check:gitleaks`** au premier lot (H23 : capacité `secrets.scan.ci`). Pre-commit ensuite (`secrets.scan.commit`) |
| **Semgrep** | SAST | LGPL-2.1 · actif | Déjà prévu (`ci-check:semgrep`) |
| detect-secrets | Scan par baseline | Apache-2.0 · dernier push 2026-04 | Alternative à Gitleaks, non retenue |
| TruffleHog | Secrets + **vérification en ligne des clés** | AGPL-3.0 · actif | Optionnel. La vérification envoie les clés sur le réseau : champ `network = "runtime"` obligatoire |
| **Presidio** (`data-privacy-stack/presidio`, ex-Microsoft) | SDK de détection et d'anonymisation de PII (texte, images, données structurées). Opérateurs `replace`, `redact`, `mask`, `hash`, `encrypt` (réversible), `custom` | MIT · 2.2.366 du 2026-10-27 | **Jamais dans PEO** (lourd, contraire à NF1). Candidat de catalogue pour **préparer des données de test** |
| Greenmask | Anonymisation de bases (PostgreSQL) | Apache-2.0 · actif | Candidat de catalogue (scénario section 5) |
| varlock, dotenvx | `.env` à schéma, injection des secrets à la commande | MIT, BSD-3 · actifs | Candidats optionnels (« secrets hors du contexte ») |
| Snyk agent-scan | Scan de serveurs MCP et de skills | Apache-2.0 · actif | À évaluer comme complément de l'Inventory |
| LLM Guard, Neosync | — | **Archivés** | Écartés |

### 3.5 Contrôles natifs de Claude Code

[FAIT] Documentation officielle ([hooks](https://code.claude.com/docs/en/hooks.md), [sandboxing](https://code.claude.com/docs/en/sandboxing.md)), lue le 2026-11-12.

| Contrôle | Ce qu'il couvre | Ce qu'il ne couvre pas |
|---|---|---|
| `permissions.deny` (`Read(./.env)`…) | Outils natifs (Read, Edit…) sur les chemins listés | Les copies, `cat` via Bash si le sandbox ne l'interdit pas |
| Sandbox (désactivé par défaut) | Bash, PowerShell, Monitor et leurs processus : écriture limitée, réseau par liste de domaines | Read, Edit, Write, WebFetch, **serveurs MCP, hooks**, LSP. Lecture de tout le poste par défaut, **aucune liste de credentials interdits**, variables d'environnement **héritées**. Repli silencieux si indisponible (sauf `failIfUnavailable`), échappatoire `dangerouslyDisableSandbox` (sauf `allowUnsandboxedCommands: false`). Proxy sans inspection TLS |
| Hooks | `PreToolUse` (bloquer, réécrire l'entrée), `PostToolUse`, `UserPromptSubmit` (bloquer, pas réécrire). S'exécutent aussi dans les sous-agents | **Échec ouvert par défaut** (sauf `onFailure: "block"`, Claude Code ≥ 2.1.295). Un `PostToolUse` avec matcher `Bash` **ne s'exécute pas pour Monitor** |

## 4. Modèle de menace : surfaces d'exposition

Niveaux de garantie : **Forte** = contrôle technique en amont, échec fermé. **Partielle** = filtre heuristique. **Faible** = mesure d'hygiène. **Aucune** = rien d'automatique n'est possible.

| Surface | Risque | Détection | Protection disponible | Limite vérifiée | Garantie max |
|---|---|---|---|---|---|
| Prompt utilisateur | Collage d'une clé, d'un extrait client | `UserPromptSubmit` | Blocage (Cloakroom, Agent Privacy) | Pas de réécriture. Le prompt bloqué reste dans le transcript local | Partielle |
| Fichiers lus | `.env`, dumps, documents | Discovery (chemins) | `deny Read(...)` + masquage en sortie | Le deny vaut par chemin | Forte sur les chemins listés, partielle ailleurs |
| Commandes (entrée) | Exfiltration | `PreToolUse` | Sandbox réseau, *egress hold* | Sandbox absent de MCP et des hooks ; proxy sans TLS | Forte (réseau Bash, sandbox actif) |
| Sorties d'outils | Secret affiché | `PostToolUse` | Remplacement de la sortie | **`PostToolUseFailure` non modifiable** | Partielle |
| MCP | Lignes de base, tickets, e-mails | Inventory (`.mcp.json`) | Masquage des résultats `mcp__*` ; serveur en lecture seule sur base anonymisée | Le serveur tourne **hors sandbox** et peut exfiltrer lui-même | Aucune sur le serveur, partielle sur ce que voit le modèle |
| Logs applicatifs | PII en clair | Discovery (`log_dirs`) | `deny` + masquage | Format libre : plus de ratés | Partielle |
| Transcripts, historique | Valeurs sur le disque | — | Nettoyage (`cloakroom clean-history`), rétention courte | Les valeurs restaurées y sont **par construction** ; sauvegardes du poste | Faible |
| Captures et images | Données visibles | — | OCR local des images lues par les outils (Cloakroom) | Ratés de l'OCR. Image collée dans le prompt : [HYPOTHÈSE] non couverte | Partielle |
| PDF | Documents internes | Discovery (extensions) | Couche texte extraite et masquée, OCR | Mise en page perdue, plafond de pages | Partielle |
| Navigateur (MCP) | Session de prod, cookies | Inventory | Profil dédié, environnement de test | Rien d'automatique | Aucune |
| Arrière-plan, Monitor | Sortie non filtrée | Inventory (matchers) | Matcher incluant `Monitor` | Matcher `Bash` seul : pas de `PostToolUse`. Codex : trou ouvert | Partielle si bien configuré |
| Fichiers temporaires | Valeurs restaurées écrites | — | Journal des fichiers (Cloakroom), contrôle à l'écriture | Hors du dossier de session : non suivi | Partielle |
| Git diff, commits | Secret commité | Gitleaks | Pre-commit, CI, blocage commit/push | Formats inconnus, secrets découpés | Forte (formats connus) |
| Presse-papiers | Copier-coller humain | — | — | Aucun hook | Aucune |
| Variables d'environnement | `printenv`, erreurs | Discovery (noms) | Injection à la commande (varlock, dotenvx), masquage | Le sandbox **hérite** de l'environnement de `claude` | Partielle |
| Recherche web côté serveur | Requête porteuse d'une donnée | — | — | Invisible des hooks | Aucune |

### 4.1 Fuites causées par la restauration

1. Valeur restaurée dans une commande qui **échoue** et affiche la chaîne de connexion : sortie non masquable (`PostToolUseFailure`).
2. Valeur restaurée dans un fichier hors du dossier de session, relu plus tard : plus de correspondance exacte, retour à la détection heuristique.
3. Mode proxy : placeholders restaurables par toute session de la machine pendant 24 h.
4. Transcript local : l'entrée restaurée y est écrite en clair.

### 4.2 Opérations qu'aucun hook ne voit

Recherche web exécutée côté serveur, complétion Tab de Cursor, presse-papiers, hook qui dépasse son délai sans `onFailure: "block"`, sortie de commande en échec. [HYPOTHÈSE] Commandes tapées par l'humain avec `!` (hors sandbox selon la doc ; passage par les hooks non vérifié).

## 5. Scénario : PostgreSQL, `.env`, logs, documents, clés

Un développeur fait corriger son application par Claude Code. Dispositif recommandé, par couches :

| Couche | Mesure | Qui | Garantie |
|---|---|---|---|
| 0. Structurelle (la plus forte) | L'agent n'a **jamais** de données réelles : base de dev anonymisée (Greenmask) ou seeds synthétiques ; MCP base pointé dessus, rôle en lecture seule ; aucune URL de prod dans `.env` | Humain + outil spécialisé. **PEO détecte et recommande** | Forte |
| 1. Native | `permissions.deny` sur `.env*`, `*.pem`, dumps, logs. Sandbox avec `denyRead`, liste de domaines, `failIfUnavailable`, `allowUnsandboxedCommands: false`. Secrets injectés à la commande plutôt que présents dans l'environnement de `claude` | **PEO configure** (bloc possédé de `.claude/settings.json`) | Forte pour les chemins listés et le réseau Bash, nulle pour les copies |
| 2. Filtre | Cloakroom | Délégué | Partielle (accidentel) |
| 3. A posteriori | Gitleaks pre-commit et CI ; `cloakroom exposure` (clés à renouveler) ; nettoyage des transcripts | Délégué. **PEO vérifie la présence** | Forte au commit pour les formats connus |
| Trace | Journal PEO : décisions de configuration seulement. Journal des données : celui de l'outil délégué | PEO + délégué | — |

Le déroulé « détecter → évaluer → sélectionner → intercepter → remplacer → restaurer → bloquer → tracer » est conservé, mais **les étapes intercepter, remplacer et restaurer sont déléguées**, et l'étape bloquer se fait à l'exécution par Claude Code et l'outil délégué. PEO garde détecter, évaluer, sélectionner, configurer, vérifier et tracer ses propres décisions.

## 6. Ce que PEO ajoute

### 6.1 Signaux de Discovery (H24)

| Signal | Contenu | Lecture autorisée |
|---|---|---|
| `secret_files` | Chemins de `.env*`, `*.pem`, `*.key`, `*.p12`, `credentials*` ; pour `.env*`, **noms de variables** | Noms de variables : texte avant `=`. **Jamais la valeur** |
| `data_stores` | Services de base dans `docker-compose*.yml` (image postgres, mysql, mongo, redis…), variables du type `DATABASE_URL` | Clés et noms d'images |
| `data_dumps` | `*.sql`, `*.dump`, `*.bak`, `*.sqlite` | Chemin, taille, extension |
| `log_dirs` | `logs/`, `*.log` | Chemin, taille |
| `agent_configs` | `.mcp.json`, `.claude/settings*.json`, `.codex/` | Lu par l'Inventory |

**Règle « aucune valeur »** (nouvelle exigence non fonctionnelle, à écrire dans la spec) : aucune valeur lue dans un fichier sensible n'entre dans `profile.json`, le journal, le lock ou une sortie de commande. Test : une fixture contient une fausse clé et une fausse PII générées ; aucune n'apparaît dans aucune sortie.

Conséquence sur **S-5** (spec 10, section 6) : un signal peut aussi exister parce qu'un **contrôle d'exposition** le consomme.

### 6.2 Contrôles d'exposition (`peo status --exposure`)

Liste indicative, contractualisée dans la spec :

| Constat | Gravité |
|---|---|
| Fichier de `secret_files` lisible par Read sans règle `deny` | Haute |
| Fichier de `secret_files` suivi par git | Haute |
| Valeur littérale (et non référence `${VAR}`) dans une config d'agent versionnée. Seule la **forme** est testée, la valeur n'est jamais affichée | Haute |
| Deux outils actifs qui réécrivent entrées ou sorties d'outils | Haute |
| Sandbox désactivé alors que `secret_files` ou `data_stores` sont présents | Moyenne |
| Sandbox actif avec repli silencieux possible (`failIfUnavailable` absent, `allowUnsandboxedCommands` non fermé) | Moyenne |
| Aucun scan de secrets en CI ni au commit | Moyenne |
| Dump ou dossier de logs dans le dépôt sans règle `deny` | Moyenne |
| Serveur MCP d'accès base ou navigateur | Information + recommandation (lecture seule, données de test) |
| Hook d'un outil de sécurité sans `onFailure: "block"` | Information |

`--ci` échoue sur les constats de gravité `error`, comme les autres constats ; pas de seuil configurable au MVP (spec 10, décision S-8). Liste contractuelle : spec 15, section 7.

### 6.3 Capacités et fiches

| Capacité | Exclusive | Fournie par | Exigence |
|---|---|---|---|
| `exposure.native` | non | PEO lui-même (réglages natifs), comme `process.gates` | Souple ; dure si `secret_files` présent |
| `secrets.scan.ci` | non | `ci-check:gitleaks` | Souple, toujours |
| `secrets.scan.commit` | non | Gitleaks en pre-commit (ultérieur) | Souple |
| `privacy.masking` | **oui** | `claude-plugin:cloakroom` (après spike S5) | Souple, proposée sur signal `secret_files` ou `data_stores` |

`orchestration.harness` (exclusive) n'est ajoutée qu'avec la première fiche de harnais d'exécution (H25).

### 6.4 Contrôle canari (`--canary`)

Un contrôle déclaratif ne suffit pas : `peo status --exposure --canary` crée **hors du dépôt**, dans un dossier temporaire, un fichier leurre (fausse clé à un format connu, fausse PII), lance les détecteurs installés (`gitleaks dir`, `cloakroom check` en mode règles), vérifie qu'ils détectent le leurre, puis supprime le dossier.

- **Jamais lancé par défaut** : il exécute des outils tiers.
- Aucun accès réseau : à vérifier pour Cloakroom (le mode avec modèle peut déclencher un téléchargement), spike S5.
- Résultat : « détecté », « non détecté » ou « non vérifiable », jamais « protégé ».

## 7. Gouvernance et contrôle humain

Niveaux : **Information** (affiché par `peo status`), **Recommandation** (dans le plan, non appliquée sans accord), **Confirmation obligatoire**, **Blocage automatique**.

| Décision | Niveau | Contrôle technique qui le rend vérifiable |
|---|---|---|
| Installer un outil | Confirmation obligatoire | Plan identifié par empreinte (`--expect-plan`, S-1), journal |
| Activer un hook | Confirmation obligatoire, hooks affichés par événement | Inventory : hooks réels comparés à la fiche (`peo status`) |
| Modifier une configuration | Confirmation (sauf `.peo/`, classé sûr) | Bloc possédé avec empreinte |
| Transmettre des données à un service externe | PEO lui-même : **blocage automatique** (NF5). Outils : information (champ `network`) et recommandation. Exécution : délégué (sandbox, *egress hold*) | Test sans réseau de NF5 ; champ `network` de la fiche |
| Autoriser l'accès à un fichier sensible | Recommandation d'une règle `deny` ; à l'exécution, **blocage automatique par Claude Code** | `peo status --exposure` signale tout fichier sensible sans `deny` |
| Restaurer une donnée pseudonymisée | **Hors PEO.** Humain seul pour les actions retenues | Les adaptateurs refusent toute commande d'approbation d'un outil délégué (`cloakroom allow`…) ; test |
| Modifier les règles de sécurité | Confirmation obligatoire ; tout **affaiblissement** est marqué comme tel dans le plan | `peo status --ci` signale un contrôle présent dans le lock et disparu |
| Supprimer un outil | Confirmation ; retrait limité aux artefacts possédés et non modifiés ; retrait d'un outil `privacy.*` marqué « affaiblissement » | Empreintes du lock |
| Approuver une porte | Humain seul (spec 15, section 4.1 bis) | Existant |

## 8. Points ouverts

| # | Point | Phase |
|---|---|---|
| **S5** (spike) | Cloakroom : (a) la version installée par le plugin au premier démarrage est-elle épinglée ? (b) cohabitation avec `peo gate` (deux `PreToolUse`, ordre, `updatedInput` concurrents) ; (c) restauration dans les écritures par MCP (Serena) ; (d) `cloakroom check` sans réseau | Avant la fiche |
| O1 | Section « PostToolUse decision control » de la doc des hooks non lue en entier (page tronquée) : confirmer le champ de remplacement de sortie et son périmètre | Spec |
| O2 | Réglage de rétention des transcripts de Claude Code : nom et effet à vérifier avant d'en faire un contrôle | Spec |
| O3 | Fiche Cloakroom : `review_by` court (30 jours) pour les outils placés sur le chemin des données | Catalogue |

## Sources

- [shanjeevrajendran/cloakroom](https://github.com/shanjeevrajendran/cloakroom) (`README.md`, `docs-HOW-IT-WORKS.md`, `docs-LIMITS.md`) · [zatuomfawas/BlackBar](https://github.com/zatuomfawas/BlackBar) (`README.md`, `extension/manifest.json`, `package.json`) · [JackDDavis/agent-privacy](https://github.com/JackDDavis/agent-privacy)
- [data-privacy-stack/presidio](https://github.com/data-privacy-stack/presidio) · [gitleaks/gitleaks](https://github.com/gitleaks/gitleaks) · [semgrep/semgrep](https://github.com/semgrep/semgrep) · [Yelp/detect-secrets](https://github.com/Yelp/detect-secrets) · [trufflesecurity/trufflehog](https://github.com/trufflesecurity/trufflehog) · [GreenmaskIO/greenmask](https://github.com/GreenmaskIO/greenmask) · [dmno-dev/varlock](https://github.com/dmno-dev/varlock) · [dotenvx/dotenvx](https://github.com/dotenvx/dotenvx) · [snyk/agent-scan](https://github.com/snyk/agent-scan)
- Claude Code : [hooks](https://code.claude.com/docs/en/hooks.md), [sandboxing](https://code.claude.com/docs/en/sandboxing.md)
