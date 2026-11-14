# 14 — Planner, Inventory, adaptateurs et fichiers gérés (F3, F6 à F9, F12, F13)

## 1. Principe

Le Planner **compare** l'état voulu (sélection + configuration) à l'état réel (Inventory) et produit une liste d'actions. Il n'écrit rien. `apply` exécute les actions dans un ordre fixe, après accord, et enregistre chaque résultat. Les adaptateurs **délèguent** aux installeurs natifs (décision D1) ; aucun ne télécharge ni ne copie lui-même du code tiers au MVP.

## 2. Modèle d'action

Schéma : [schemas/plan.schema.json](schemas/plan.schema.json).

| Champ | Valeurs |
|---|---|
| `op` | `add` (+), `change` (~), `remove` (-), `keep` (=), `manual` (?) |
| `target.type` | `plugin`, `marketplace`, `mcp`, `cli`, `framework`, `file`, `block`, `json-keys`, `ci` |
| `group` | `prerequisites`, `cli`, `framework`, `plugins`, `mcp`, `files`, `ci`, `peo` |
| `risk` | voir 2.1 |
| `tool` | référence de la fiche concernée, ou `peo:core` |
| `command` | pour les actions déléguées : liste d'arguments exacte, affichée telle quelle |
| `preconditions` | empreintes `sha256` des fichiers lus ou modifiés ; absence attendue notée `absent` |
| `reason` | phrase courte, reprise de la sélection |
| `weakens` | `true` quand l'action **retire ou relâche un contrôle** : règle `permissions.deny` possédée retirée, outil fournissant `exposure.native`, `secrets.scan.*` ou `privacy.masking` retiré ou désactivé. Le rendu du plan l'affiche en tête. Absent sinon (ajout du 2026-11-12) |

### 2.1 Classes de risque

| Classe | Définition | Exemples | Accord en `guided` | Accord en `semi` |
|---|---|---|---|---|
| **R0** | Lecture, ou rien à faire | `keep` | aucun | aucun |
| **R1** | Fichier du projet, réversible par la sauvegarde | `AGENTS.md`, `.peo/*`, bloc dans `.gitignore` | par groupe | accord du plan suffit |
| **R2** | Configuration qui change le comportement de l'agent dans ce projet | `.claude/settings.json` (hooks, `enabledPlugins`), `.mcp.json`, `specify init` | par groupe | accord du plan suffit |
| **R3** | Environnement de l'utilisateur ou réseau | `uv tool install`, `npm install -g`, `claude plugin install`, `claude plugin marketplace add` | par action | **par action** |
| **R4** | Destruction ou écrasement de ce que PEO ne possède pas | retirer un plugin installé à la main, écraser un fichier modifié | **interdit au MVP** : transformé en `manual` | idem |

`[policy].require_consent` de `peo.toml` peut durcir ces règles (exiger l'accord pour R1), jamais les assouplir sous le seuil du tableau.

### 2.2 Empreinte du plan

`plan_id = sha256(JSON canonique de { schema, catalog.commit, actions })`, où le JSON canonique trie les clés, n'a pas d'espace et exclut tout horodatage. `apply --expect-plan` recalcule le plan ; si l'empreinte diffère, code 4 et différence affichée. Les `preconditions` garantissent qu'un fichier modifié entre le plan et l'application change l'empreinte.

### 2.3 Ordre d'application

```text
1. sauvegarde  : copie de chaque fichier que le plan modifie → .peo/backups/<horodatage>/<chemin>
2. prerequisites (actions avec fix, ex. intelephense)
3. cli          (uv tool install, npm install -g)
4. framework    (specify init, puis configuration de Spec Kit)
5. plugins      (marketplace add, puis install --scope project)
6. mcp          (.mcp.json)
7. files        (AGENTS.md, CLAUDE.md, .claude/settings.json, .claude/rules/, .gitignore, .gitattributes)
8. ci           (bloc géré dans le fichier de CI)
9. peo          (peo.toml, profile.json, peo.lock.json, history.ndjson, README.md)
```

À chaque action : événement dans le journal (résultat `ok`, `failed`, `skipped`, `manual`). Sur échec : arrêt, **restauration des fichiers déjà écrits pendant cette exécution** depuis la sauvegarde, lock mis à jour seulement pour les actions réussies des groupes 2 à 6 (elles ont modifié l'environnement et doivent rester traçables), message donnant la commande de reprise. Une installation R3 réussie n'est jamais défaite automatiquement : `peo status` la signale comme « installé, non configuré ».

Rétention des sauvegardes : 10 dernières exécutions. `.peo/backups/` est ignoré par git (bloc géré dans `.gitignore`).

### 2.4 Veto de la vue observée (H27, ajout du 2026-11-14)

Avant le calcul de `plan_id`, le Planner lit la vue observée de l'Inventory (section 3.4). Un **socle alternatif** ou un fournisseur de **`privacy.masking`** (fiche dont `surface.data_path = "rewrites-io"`) **actif** dans la vue observée mais absent des déclarations suivies du projet (`declared()`, section 3.2) arrête le plan : `E_BACKBONE_CONFLICT`, code 6, avec un message qui cite la portée de l'entrée en cause. L'outil est reconnu par l'`id` de plugin ou par le `tool_ref`, rapprochés des fiches. Les autres capacités exclusives actives hors des déclarations suivies ne bloquent pas : `peo status` (R3) les signale par un constat `info`. La sélection (spec 13 §8.1) ne lit que les déclarations suivies : l'état de la machine bloque, il n'oriente jamais.

## 3. Inventory (F3)

Révisé le 2026-11-14 (R2). L'Inventory décrit la configuration Claude Code réellement en place pour un projet sur la machine courante : hooks, permissions, sandbox, serveurs MCP et plugins, dans toutes les portées que PEO peut lire. Il n'écrit rien, ne persiste rien (ni `.peo/inventory.json`, ni `profile.json`), ne calcule ni constat ni valeur effective (R3 fusionne : scalaire = portée la plus forte ; listes = union, selon la précédence de la spec 10 §5, « Réglages Claude Code »). Ne sont pas lus : les outils CLI installés (`Adapter.detect`, R5, section 4.2), les dépendances de dev (E6, `present_tools` de Discovery), Spec Kit (`discovery/detect.toml`), les chemins `sandbox.filesystem.denyRead` et le compte des règles de permission par outil (reportés en R3, avec le premier constat qui les lit), le repli par `extraKnownMarketplaces` (retiré), les réglages d'approbation des serveurs MCP de projet (`enabledMcpjsonServers`, `disabledMcpjsonServers`, `enableAllProjectMcpServers`), l'inventaire Codex (E7, H23), les images Docker d'un serveur MCP lancé par `docker run`.

### 3.1 Sources, portées, états

Chaque source envisagée a une entrée dans `sources`, même quand elle n'est pas lue. Le **rang** d'une source est sa position dans ce tableau ; il sert aux tris (section 3.2). Le tableau suit la précédence de Claude Code à l'intérieur de chaque famille (réglages, puis MCP), la plus forte d'abord.

| `id` | Portée | Chemin affiché (`path`) | Contenu utilisé |
|---|---|---|---|
| `settings:managed` | managed | `<managed>/managed-settings.json` (absolu) | réglages |
| `settings:managed.d/#<n>` | managed | `<managed>/managed-settings.d/#<n>` : un par fichier `.json`, `<n>` = position dans l'ordre des noms ; le nom lu ne sort jamais ; dossier absent → une entrée `settings:managed.d`, `absent`, `path: null` ; `managed=None` → une entrée `settings:managed.d`, `not_inspected`, `not-provided` ; dossier sans fichier `.json` → une entrée `settings:managed.d`, `read`, `path` = le dossier, aucun réglage | réglages |
| `settings:managed-other` | managed | `null` | toujours `not_inspected`, `out-of-scope` (profil macOS, registre, MDM, console) |
| `settings:cli` | cli | `null` | toujours `not_inspected`, `out-of-scope` (`--settings`, `--bare`, `--safe-mode`) |
| `settings:local` | local | `.claude/settings.local.json` | réglages |
| `settings:project` | project | `.claude/settings.json` | réglages |
| `settings:user` | user | `<user-config>/settings.json` (lu dans `user_config`) | réglages |
| `mcp:managed` | managed | `<managed>/managed-mcp.json` | serveurs MCP |
| `mcp:local` | local | `null` | toujours `not_inspected`, `out-of-scope` (serveurs de `claude mcp add` sans portée, dans `~/.claude.json` ; spike S3) |
| `mcp:project` | project | `.mcp.json` | serveurs MCP |
| `mcp:user` | user | `null` | toujours `not_inspected`, `out-of-scope` (spike S3) |
| `claude` | `null` | `null` | `claude --version` et `claude plugin list --json` ; porte aussi les serveurs MCP des plugins |
| `plugin:#<n>` | portée du plugin (`other` si inconnue) | `plugin:#<n>/hooks/hooks.json` ; `null` si le plugin est désactivé | hooks du plugin d'index `<n>` dans `claude plugin list` (mode complet) |
| `plugin:*` | `null` | `null` | mode dégradé seulement : hooks des plugins inconnus, `not_inspected`, `degraded` |

Les sources de plugin sont **positionnelles** (`plugin:#<n>`), jamais nommées par l'id : un id rejeté par sa grammaire ne fait disparaître ni la source ni ses hooks. Un plugin désactivé a sa source, `not_inspected`, raison `disabled`. `user_config=None` marque `settings:user` `not_inspected`, `not-provided` ; `managed=None` fait de même pour `settings:managed`, `settings:managed.d` (une entrée) et `mcp:managed`.

**États.** `reason` est `null` pour `read` et `absent`.

| État | Sens | Raisons | Effet sur les constats de R3 |
|---|---|---|---|
| `read` | lu et analysé | — | applicable |
| `absent` | fichier inexistant ; code 127 sur `claude --version` | — | applicable pour un fichier : l'absence de réglage est un fait (aucun hook, aucune règle). Pour la source `claude` : mode dégradé |
| `invalid` | présent mais inexploitable | `too-large`, `binary`, `json`, `not-object`, `not-regular` | `skipped` pour les constats qui lisent cette source |
| `unavailable` | impossible à lire ici | `permission-denied`, `read-error` (autre erreur de lecture), `claude-too-old`, `version-unparsed`, `timeout-or-missing` (127 sur `plugin list` après un `--version` réussi), `command-failed`, `output-unparsed` | `skipped` |
| `not_inspected` | non lu, volontairement | `out-of-scope`, `not-provided`, `degraded`, `disabled` | `skipped` ; sauf `disabled` : les hooks d'un plugin désactivé ne s'exécutent pas, les constats sur ses hooks ne s'appliquent pas |

Une **famille invalide** (section 3.2) a le même effet que `invalid`, limité aux constats qui lisent cette famille pour cette source. Le Runner rend 127 pour une commande introuvable comme pour un délai dépassé : l'Inventory classe selon la commande. Limite : un `claude --version` qui dépasse le délai donne `absent`.

**Lecture d'un fichier.** Le chemin est résolu ; un fichier qui n'est pas un fichier ordinaire (périphérique, tube, dossier, par exemple un lien vers `/dev/zero`) donne `invalid`, `not-regular`, sans lecture. Une source du projet dont le chemin résolu sort de la racine résolue (`.mcp.json` lien vers `~/…`) n'est pas lue : `invalid`, `not-regular`. Sinon, au plus 1 048 577 octets sont lus : au-delà de 1 048 576 octets (1 Mio), `too-large`. Un octet nul ou un UTF-8 invalide donne `binary` ; un JSON invalide `json`, y compris un JSON trop imbriqué pour l'analyseur (`RecursionError` attrapée comme `JSONDecodeError`) ; une racine qui n'est pas un objet `not-object` ; une erreur de permission `unavailable`, `permission-denied` ; un fichier disparu pendant la lecture `absent` ; toute autre erreur de lecture `unavailable`, `read-error`. Le texte d'une erreur et le contenu du fichier ne sortent jamais.

**Chemins affichés** : relatifs à la racine pour le projet, préfixés par `<user-config>/` pour l'utilisateur (le dossier réel n'apparaît jamais), absolus pour managed (chemin système fixe, pouvant contenir des espaces), `plugin:#<n>/hooks/hooks.json` pour un plugin (`installPath` n'est jamais émis).

**`tracked`** : un seul appel `git ls-files -z -- <fichiers>` sur les sources du projet présentes (`settings:local`, `settings:project`, `mcp:project` à l'état `read` ou `invalid`, dans l'ordre des rangs), par le Runner, à la racine ; aucun appel si aucune n'est présente. Vrai ou faux pour ces fichiers ; `null` hors git, si `git ls-files` échoue (code non nul ou `OSError`), pour une source du projet absente, et pour toutes les autres sources.

**Claude Code, mode complet.** `claude --version` (code 0) donne une version lue par `^([0-9]+)\.([0-9]+)\.([0-9]+)\b` (chiffres ASCII) sur la première ligne de sa sortie, après `strip()` (exemple : `2.1.325 (Claude Code)`) ; une version ≥ 2.1.285 (NF9, comparée en tuple d'entiers) ouvre le mode complet ; sinon `unavailable`, `claude-too-old` ou `version-unparsed` ; 127 → `absent` ; un autre code non nul → `unavailable`, `command-failed`. Puis `claude plugin list --json` : 127 → `unavailable`, `timeout-or-missing` ; autre code non nul → `unavailable`, `command-failed` ; dans les deux cas, mode dégradé. La sortie doit être un tableau d'objets ayant chacun `id` (chaîne), `scope` (chaîne) et `enabled` (booléen) ; sinon toute la sortie est `output-unparsed` (mode dégradé : une entrée mal formée ne laisse pas un inventaire partiel). Un `OSError` levé par `run` donne `unavailable`, `command-failed`. On garde les plugins de portée `user` ou `managed`, ceux de portée `project` ou `local` dont `projectPath` résolu égale la racine résolue, et ceux d'une autre portée (`synced` gardée telle quelle, toute portée inconnue de PEO écrite `other`, pour ne rien omettre). Chaque plugin gardé donne une entrée de `plugins` de source `claude` (`confidence: "fact"`) et une source `plugin:#<index>`. `enabled` reprend le champ `enabled` de la liste : état effectif pour ce projet, fusion des portées comprise ; `projectEnabled` n'est pas lu. Les deux commandes sont lancées à la racine (la sortie dépend du dossier courant). `error_count` = taille de `errors`, 0 si `errors` est absent. Pour un plugin activé, `<installPath>/hooks/hooks.json` est lu comme sa source (sans contrôle de racine), et ses `mcpServers` deviennent des entrées de `mcp_servers` de source `claude`, avec `plugin_index`.

**Mode dégradé** : `claude` absent, trop ancien, version illisible, ou liste en échec ou illisible. La source `claude` porte l'état et la raison ; aucune source `plugin:#<n>`, mais une source `plugin:*` (`not_inspected`, `degraded`).

**Dans les deux modes**, `enabledPlugins` de chaque fichier de réglages lu donne une entrée de `plugins` par clé, de la source du fichier, `confidence: "likely"`, `error_count: null`, `scope: null`. En mode complet, un même plugin a donc une entrée `claude` et une entrée par fichier qui le déclare. **`claude_version`** (racine) : la version, émise dès que `claude --version` a été analysée, même si `plugin list` échoue ensuite ; `null` sinon.

### 3.2 Sortie, contrat d'appel, familles, tris

Schéma : [schemas/inventory.schema.json](schemas/inventory.schema.json) ; exemple : [schemas/examples/inventory.example.json](schemas/examples/inventory.example.json). Le schéma fait foi pour les champs, énumérations et motifs. Sortie : `data.inventory` de `peo status --json` (R3), jamais écrite sur le disque.

```text
inventory(root: Path, *, run: Runner | None = None,
          user_config: Path | None, managed: Path | None,
          identify: Callable[[dict], str | None] | None = None) -> dict
default_managed() -> Path | None
declared(inv: dict) -> dict          # {"plugins": [...], "mcp_servers": [...]}
```

- `user_config` est obligatoire : dossier de configuration utilisateur de Claude Code, qui contient `settings.json`. L'appelant le résout (`CLAUDE_CONFIG_DIR` s'il est défini, sinon `~/.claude`) ; le module n'appelle jamais `Path.home()`, ni `os.path.expanduser`, ni ne lit l'environnement. `None` ne couvre pas les plugins de portée user, que `claude plugin list` rapporte quand même.
- `managed` est obligatoire : `default_managed()` rend `/Library/Application Support/ClaudeCode` sous macOS, `/etc/claude-code` sous Linux, `None` ailleurs.
- `identify` reçoit la projection d'un serveur MCP (section 3.3), pour chaque serveur, y compris ceux des plugins, et rend une référence de fiche ou `None` ; l'appelant la construit depuis `[detect].mcp` des fiches. Une réponse non conforme au motif `tool_ref` devient `null`.
- `run` vaut `None`, remplacé **à l'appel** par `peo.runner.run`. Trois commandes au plus : `claude --version`, `claude plugin list --json`, `git ls-files -z -- …`, toutes à la racine. L'appelant règle le délai en passant un Runner adapté.
- Une donnée d'entrée ne fait jamais lever `inventory()`. Remontent seulement une exception d'`identify`, une exception de `run` autre qu'`OSError` (erreurs de l'appelant) et `TypeError` si `user_config` ou `managed` manque.
- `declared(inv)` : fonction pure, seule définition de H27 côté données. Elle rend les entrées de `plugins` et de `mcp_servers` dont la source est `settings:project` ou `mcp:project` et porte `tracked: true`, mêmes formes et même ordre, **y compris** les entrées `enabled: false`. Les entrées de source `claude`, `settings:local`, `settings:user` et managed n'en font jamais partie.

**Règle unique des familles invalides.** Chaque liste de sortie correspond à une famille (`permissions`, `flags`, `hooks`, `plugins`, `mcp`, `values`) ; la famille `hooks` comprend aussi les entrées de `values` dont `location` commence par `hook:`, et la famille `mcp` celles dont `location` commence par `mcp#` (précisé le 2026-11-14 : un serveur retiré ne laisse pas de valeur orpheline). Si une partie d'une famille est mal formée dans une source (type inattendu à n'importe quel niveau, événement hors grammaire, règle de permission classée `invalid`), **toutes** les entrées de cette famille pour cette source sont retirées et la famille est nommée dans `invalid_families` de la source. Aucun autre retrait n'existe. Exceptions : un nom de serveur, une clé, un `matcher` ou un id hors grammaire prennent la valeur de repli ci-dessous ; une sortie de `claude plugin list` mal formée relève de l'état de la source `claude` (`output-unparsed`).

| Liste de sortie (famille) | Clés d'entrée lues | Règle |
|---|---|---|
| `permission_rules` (`permissions`) | `permissions.allow`, `ask`, `deny` | `classify_permission(rule)` (section 3.3) : `keep` → émise en entier ; `ignore` (`Bash(…)`, `mcp__…`) → lue, jamais émise ni comptée ; `invalid` → famille invalide |
| `flags` (`flags`) | `sandbox.enabled`, `sandbox.failIfUnavailable`, `sandbox.allowUnsandboxedCommands`, `disableAllHooks`, `allowManagedHooksOnly` | booléens présents seulement ; `allowManagedHooksOnly` n'est lu que dans les sources managed et ignoré ailleurs, comme le fait Claude Code |
| `hooks` (`hooks`) | `hooks.<événement>[g].hooks[h]` | une entrée par gestionnaire ; événement hors grammaire → famille invalide ; `matcher` absent → `null`, hors grammaire → `other` ; `type` inconnu → `other` ; `onFailure` absent → `null`, autre que `block`/`continue` (y compris `null` écrit) → `other`. Ni `command`, ni `args`, ni `prompt`, ni `input`, ni `url`, ni `headers` |
| `plugins` (`plugins`) | `enabledPlugins` ; liste de `claude plugin list` (section 3.1) | id hors grammaire → `null` ; `enabledPlugins` qui n'est pas un objet, ou une valeur non booléenne, rend la famille invalide pour ce fichier |
| `mcp_servers` (`mcp`) | `mcpServers` de `.mcp.json` et `managed-mcp.json` ; `mcpServers` des plugins (source `claude`) | `index` = position dans `mcpServers` de son fichier ou de son plugin ; `plugin_index` = `index` du plugin, `null` pour un serveur de fichier ; `name` hors grammaire → `null` ; `transport`, `args_hint`, `tool_ref` (section 3.3) ; `mcpServers` d'un plugin mal formé rend la famille `mcp` invalide sur la source `claude` (tous les serveurs de plugins retirés ; sources et hooks des plugins intacts) |
| `values` (`values`) | `env` des réglages ; `env`, `headers` et `url` des serveurs MCP ; `url` et `headers` des hooks `http` | `env` des réglages ou `env`/`headers` d'un serveur qui ne sont pas des objets rendent la famille invalide (`headers` d'un hook : famille `hooks`) ; une entrée par clé, `key` hors grammaire → `null`, `key: "url"` pour une URL ; `form`, `sensitive_name`, `value_hint` (section 3.3) |

`group_index` et `hook_index` sont les positions du groupe de `matcher` dans la liste de l'événement et du gestionnaire dans ce groupe. `location` vaut `env`, `mcp#<index>.env|headers|url` pour un serveur de fichier, `mcp#<plugin_index>/<index>.env|headers|url` pour un serveur de plugin, `hook:<événement>#<group_index>.<hook_index>.url` ou `…headers` ; il ne contient que des index et des noms fixes, jamais un nom lu.

**Validation.** `inventory()` ne valide pas sa sortie à l'exécution : chaque chaîne passe par une énumération, `identifier` ou un champ chemin ; chaque test A3.x la valide avec `peo.validate`. `peo.validate`, comme `jsonschema`, applique `pattern` avec `re.search`, où `$` accepte un saut de ligne final : c'est `identifier` (`re.fullmatch`) qui l'exclut.

**Tris** (sortie déterministe octet pour octet avec `json.dumps(sort_keys=True)`) :

- `sources` : rang ; `managed.d` par nom puis `#<n>` ; `plugin:#<n>` par `n` ;
- `permission_rules` : (rang de la source, `allow` < `ask` < `deny`, index d'origine) ;
- `flags` : (rang, clé) ;
- `hooks` : (`event`, rang, `group_index`, `hook_index`) ;
- `plugins` : (rang de la source, `index`), la source `claude` classée avant toutes les sources de réglages ;
- `mcp_servers` : (rang, `plugin_index`, `index`) ; `values` : (rang, `location`, `key`) ;
- une clé de tri qui vaut `null` se classe avant toute valeur ; à égalité, l'index d'origine départage.

Seules les déclarations suivies du projet sont reproductibles entre machines.

### 3.3 Règles sur les valeurs (`peo.inventory.values`)

Fonctions pures, sans entrée-sortie ; aucune ne lève avec une valeur dans son message.

**Forme d'une valeur** (première ligne qui s'applique ; `NOM` respecte `^[A-Za-z_][A-Za-z0-9_]*$`) :

| Valeur | Forme |
|---|---|
| `""` | `empty` |
| exactement `${NOM}` ou `${NOM:-}` | `reference` |
| contient `${NOM:-x}` avec `x` non vide, n'importe où | `literal` |
| contient `${NOM}` ou `${NOM:-}` et autre chose (`Bearer ${TOKEN}`) | `interpolated` |
| tout le reste, y compris une valeur qui n'est pas une chaîne | `literal` |

Limite : `interpolated` n'est pas une garantie (`sk-abc${SUFFIXE}`) ; ce cas relève de Gitleaks (R3).

**Nom sensible** : le nom est découpé en jetons sur `_`, `-`, `.` et au passage minuscule → majuscule, puis mis en minuscules ; il est sensible si un jeton appartient à `token`, `secret`, `key`, `apikey`, `password`, `passwd`, `pwd`, `auth`, `authorization`, `cookie`, `credential`, `credentials`. `GITHUB_TOKEN`, `apiKey`, `X-Auth-Token`, `Authorization`, `Proxy-Authorization`, `Cookie` sont sensibles ; `AUTHOR`, `KEYCLOAK_REALM`, `KEYBOARD` ne le sont pas. Pour une `url` (`key: "url"`), `sensitive_name` est vrai si un nom de paramètre de la requête est sensible (`?access_token=…`).

**Indice sur la valeur** : `value_hint` (et `args_hint` pour les arguments d'un serveur MCP) vaut `url-userinfo` si la valeur contient une URL de la forme `scheme://user:pass@`, sinon `null`. Calculé en mémoire ; la valeur est ensuite jetée.

**Condition de `X-LITERAL-IN-AGENT-CONFIG`** (seule définition, reprise dans la spec 15 §7.1) : sur une source du projet (`settings:project`, `settings:local`, `mcp:project`) avec `tracked: true`, une entrée de `values` avec `form = literal` et (`sensitive_name` ou `value_hint` non nul), ou une entrée de `mcp_servers` avec `args_hint` non nul. `tracked: null` sur une source du projet donne `skipped`. Les sources user et managed ne sont jamais commitées et ne sont pas visées.

**Classement d'une règle de permission** (`classify_permission`) : une règle de l'outil `Read`, `Edit`, `Write` ou `WebFetch` (nue, ou suivie de parenthèses) est `keep` si elle respecte en entier (`re.fullmatch`) le motif `rule` du schéma, sinon `invalid` (saut de ligne, `WebFetch(x)` sans `domain:`) ; une règle d'un autre outil est `ignore` ; une valeur qui n'est pas une chaîne est `invalid`.

**Projection d'un serveur MCP, en mémoire seulement** (`mcp_identity`, jamais émise ; passée à `identify`, seul `tool_ref` sort) :

- `transport` (`mcp_transport`, émis) : si `type` est présent, sa valeur quand elle vaut `stdio`, `http`, `sse`, `ws` ou `streamable-http`, sinon `other` ; si `type` est absent, `stdio` sans `url`, `other` avec une `url`.
- Serveur local : `launcher` ∈ `npx`, `uvx`, `bunx`, `pnpm-dlx`, `docker`, `other`, d'après le nom de base de `command` (`pnpm` suivi de l'argument `dlx` → `pnpm-dlx`). Lanceur de paquets : `package` = la valeur de `--package`/`-p` (`npx`) ou de `--from` (`uvx`) si présente, sinon le premier argument qui ne commence pas par `-` (pour `pnpm-dlx`, après `dlx`) ; version retirée (`@…` après le nom, le `@` initial d'une portée npm étant gardé ; ou à partir du premier `==`, `>=`, `<=`, `~=`, `!=`, `<`, `>`, `[`), puis gardé s'il respecte la grammaire npm `^(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$` ou PEP 503 `^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$` (214 caractères au plus), sinon `null`. `docker` : `package` et `command_name` à `null`. `other` : `command_name` = nom de base de `command` s'il respecte `^[a-z0-9][a-z0-9._-]*$` et ne contient pas `${`, sinon `null`.
- Serveur distant : `url_host` = hôte en minuscules, sans port, chemin ni requête, gardé s'il respecte `^[a-z0-9.-]{1,214}$` ; `null` si l'URL a des identifiants, contient `${`, ne s'analyse pas ou ne respecte pas ce motif.
- `identify` reçoit exactement le dict `{transport, launcher, package, command_name, url_host}` (valeurs conformes ou `None`) ; `launcher`, `package`, `command_name` et `url_host` ne sortent jamais.

**`identifier(kind, s)`** applique avec `re.fullmatch` la grammaire du champ du schéma et rend `s` s'il est conforme, sinon la valeur de repli : `event` → `None` (l'appelant rend la famille `hooks` invalide) ; `name` (nom de serveur) et `key` → `None` (motif `name`) ; `matcher` → `"other"` ; `plugin_id` → `None` ; `tool_ref` → `None`. Limite écrite : un nom est émis comme un nom ; ces grammaires arrêtent les chaînes qui contiennent des séparateurs (`:`, `/`, `@`, `=`, espaces), elles laissent passer une suite alphanumérique (`sk_live_abc123` comme nom de clé). NF14 autorise les noms : c'est un choix, pas une garantie.

### 3.4 Consommateurs, « actif », vues, limites

**Consommateurs** : `peo status` et l'audit d'exposition (R3, spec 15 §6 et §7) lisent la vue observée ; le Selector (R4, spec 13 §8.1) ne lit que `declared()` ; le Planner (R5) lit la vue observée pour le veto de la section 2.4 ; `Adapter.detect` de `claude-plugin` (section 4.2) lit la section 3.1.

**Actif** (définition unique, utilisée par H27, les capacités exclusives et les constats) : un plugin est actif quand son entrée de source `claude` porte `enabled: true` (valeur déjà fusionnée par Claude Code). En mode dégradé, l'activation se déduit des entrées `enabledPlugins` par la même précédence (calcul fait en R3/R5 ; un `false` local l'emporte sur un `true` user, spec 10 §5). Un serveur MCP est actif quand il figure dans une source lue : c'est une borne haute, puisque les réglages d'approbation ne sont pas lus (R5 devra les lire avant d'appliquer le veto à un serveur MCP).

**Deux vues (H27).** La **vue observée** est toute la sortie ; elle dépend de la machine. Les **déclarations suivies du projet** sont celles que rend `declared()` (section 3.2). Exemple : `.claude/settings.json` suivi déclare `"superpowers@x": false` et la portée user l'active ; le projet l'emporte, l'entrée `claude` porte `enabled: false`, le plugin n'est pas actif, pas de veto.

**Risques acceptés** : S7, un secret alphanumérique placé dans un nom passe la grammaire (NF14 autorise les noms) ; S16b, le contenu de `permission_rules[].rule` recopie ce que l'utilisateur a écrit comme chemin ou domaine (aucun motif ne sépare un chemin d'un secret) ; S23, `interpolated` peut cacher une partie de secret (Gitleaks, R3) ; S24, un `claude --version` lent passe pour une absence. **Hypothèses sans test en R2** : S20, `claude plugin list` n'accède pas au réseau (probable, spec 10 §5 ; l'appelant peut passer un Runner à délai court) ; S28, `git ls-files` lancé dans un dépôt non fiable n'exécute pas de code (`core.fsmonitor`) ; même exposition que Discovery, à traiter pour les deux.

## 4. Adaptateurs

### 4.1 Contrat

```python
class Adapter(Protocol):
    kind: str                                   # "claude-plugin", "mcp", "cli-uv", "cli-npm", "framework", "files", "ci"
    def detect(self, entry, ctx) -> Detected | None          # état réel de cet outil
    def plan(self, entry, desired, detected, ctx) -> list[Action]
    def apply(self, action, ctx) -> Result                   # exécute UNE action ; jamais d'autre effet
    def verify(self, entry, ctx) -> Check                    # vérification après coup
    def owned(self, entry, lock_entry, ctx) -> list[Owned]   # possessions encore intactes
    def remove(self, entry, lock_entry, ctx) -> list[Action] # retrait limité à owned()
```

`ctx` donne la racine du projet, le profil, la configuration, un exécuteur de commandes **injectable** (faux exécuteur en test) et le journal. Un adaptateur n'appelle jamais `subprocess` directement.

Contrat de l'exécuteur (`peo.runner`, précisé le 2026-11-12 pour P1.3) :

```python
class Result(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes

Runner = Callable[[Sequence[str], Path], Result]
def run(args: Sequence[str], cwd: Path, timeout: float = 30) -> Result
```

Arguments en liste, jamais de shell. Commande absente ou délai dépassé : `Result(127, b"", <raison>)`, sans exception. `peo.runner` est le seul module de `src/peo/` qui importe `subprocess` ; Discovery, Inventory et les adaptateurs reçoivent un `Runner`.

### 4.2 Par type

| Type | `detect` | `apply` | Possède | Vérifie |
|---|---|---|---|---|
| `claude-plugin` | Inventory (3.1) | `claude plugin marketplace add <source> --json` si la marketplace manque, puis `claude plugin install <name>@<mkt> --scope project --json`. Dernière ligne de stdout analysée ; `outcome = ok` ou `failureCode = already_in_goal_state` = succès | `json-keys` : `enabledPlugins["<name>@<mkt>"]`, `extraKnownMarketplaces.<mkt>` dans `.claude/settings.json` | `claude plugin list --json` : présent, `enabled`, `errors` vide, `version` comparée à `versions.tested` (spike S2) |
| `mcp` | `.mcp.json` | Fusion de `mcpServers.<nom>` (section 6.1) | `json-keys` : `mcpServers.<nom>` | La commande du serveur existe (`shutil.which`) |
| `cli-uv` | `uv tool list` | `uv tool install <paquet>==<version>` (Python épinglé si la fiche le demande : `-p 3.13`) | aucune possession de fichier ; installation notée dans le lock | `verify` de la fiche (ex. `serena --version`) |
| `cli-npm` | `npm ls -g --depth=0 --json` | `npm install -g <paquet>@<version>` **seulement** si le préfixe global est inscriptible sans élévation (`npm prefix -g` puis test d'écriture) ; sinon action transformée en `manual` | idem | idem |
| `framework` (Spec Kit) | `.specify/` | `specify init --here --force --integration claude --integration-options="--no-model-invocation"` après sauvegarde de `.specify/` et `.claude/skills/speckit-*` ; puis configuration (5.3) | `files` : fichiers créés par `init` (liste relevée par différence avant/après, avec empreintes) | `specify check` ; présence de `.specify/memory/constitution.md` |
| `files` | lecture | Composer (section 6) | `block`, `json-keys`, `file` (empreinte) | empreinte relue |
| `ci` | fichier de CI | Bloc géré (6.7) | `block` | empreinte relue |

La détection des CLI installés (`cli-uv`, `cli-npm`, binaires de `[detect].bin`) est faite par `Adapter.detect`, pas par l'Inventory (révisé le 2026-11-14).

**Jamais** : `claude plugin install --scope user` (portée projet partageable et réversible) ; installation par la marketplace d'un outil que sa documentation déconseille ainsi (Serena) ; commande qui exige `sudo`.

## 5. Spec Kit

### 5.1 Installation

Prérequis : `uv` sur le poste (jamais installé par PEO ; absent → action `manual` avec la commande officielle d'installation). `cli:specify-cli` est installé par `uv tool install specify-cli==<version testée>` depuis la source indiquée par la fiche.

### 5.2 Préréglage `peo`

Un préréglage Spec Kit (`presets/peo`) n'est **pas** livré au MVP : les portes sont tenues par `peo gate` et la configuration ci-dessous suffit. Il reste l'option pour P6 si des gabarits doivent changer.

### 5.3 Conventions de branches (E3)

L'extension git de Spec Kit impose que le dernier segment commence par `{number}-` **[FAIT]**. Décision du Planner selon le profil :

| `conventions.branches` | Action | Question |
|---|---|---|
| `null` (moins de 5 branches) ou motif compatible avec `{number}-{slug}` sans préfixe | rien | aucune |
| Préfixes détectés, et `<prefix>/{number}-{slug}` respecte le motif détecté | Écrire `branch_prefix: "<préfixe de feat>"` dans `.specify/extensions/git/git-config.yml` (fichier possédé) | aucune ; hypothèse au tour 1 |
| `id_style = "alnum-id"` (identifiants de feuille de route dominants) | Selon `q.branch_convention` | `q.branch_convention` |

Options de `q.branch_convention` :

1. **Garder les préfixes, numéroter à la Spec Kit** (`feat/001-slug`) — recommandé : aucune interruption de l'outil.
2. **Garder les identifiants du projet** : désactiver l'extension git de Spec Kit (`specify extension disable git`) ; `peo flow start feature <slug> --id A7` crée la branche `feat/A7-<slug>` ; Spec Kit crée seulement le dossier `specs/NNN-<slug>`, relié par `.specify/feature.json`. Coût : l'identifiant du dossier et celui de la branche diffèrent.

Pour `fx-split-stack`, le motif mesuré est `^(feat|fix)/[A-Za-z0-9-]+$` avec `id_style = "mixed"` (document 12, section 4.1) : deuxième ligne du tableau, `branch_prefix: "feat"`, **aucune question**.

Branches de correction : la recette `bugfix` en piste S ne passe pas par `specify` ; `peo flow start bugfix <slug>` crée `fix/<slug>` (premier préfixe détecté contenant « fix », sinon `fix`).

## 6. Fichiers gérés (Composer)

### 6.1 JSON (`.claude/settings.json`, `.mcp.json`)

- Analyse stricte. Fichier invalide → arrêt avec action `manual` (jamais de réécriture d'un fichier qu'on ne comprend pas).
- Fusion profonde par clé ; ordre des clés existantes conservé ; nouvelles clés ajoutées à la fin ; indentation détectée (2 espaces par défaut) ; saut de ligne final conservé.
- Tableaux de hooks : les entrées de PEO sont reconnues par leur commande (`peo gate`, `peo context`) ; elles sont remplacées en place, jamais dupliquées ; les autres entrées sont intactes.
- `permissions` : deux modifications possédées, rien d'autre :
  - ajout de `Bash(peo flow approve:*)` et `Bash(peo flow override:*)` à `permissions.ask` (document 15, section 4.1 bis) ;
  - quand `peo:native-controls` est retenu (ajout du 2026-11-12) : ajout à `permissions.deny` de `Read(./<path>)` pour chaque entrée de `sensitive.secret_files` et `sensitive.data_dumps`, et `Read(./<path>/**)` pour chaque `sensitive.log_dirs` (spec 12, section 7 bis). Risque R2. Une règle équivalente déjà présente (même chaîne) n'est pas dupliquée et n'est pas possédée.
- `sandbox` : **jamais écrit** au MVP (décision S-9). `peo:native-controls` produit une action `manual` qui décrit les réglages recommandés (`enabled`, `filesystem.denyRead` des mêmes chemins, `failIfUnavailable: true`, `allowUnsandboxedCommands: false`), ou, si un composant a `runtime = docker:<service>`, une action `manual` qui explique pourquoi le sandbox casserait ses commandes.
- Possession : chemins JSON (`hooks.PreToolUse[command=peo gate]`) avec l'empreinte de la valeur écrite.

### 6.2 Blocs gérés

```markdown
<!-- peo:begin id=agents-md v=1 sha=<empreinte du contenu> -->
…contenu généré…
<!-- peo:end id=agents-md -->
```

Variantes de commentaire : `#` pour YAML et `.gitignore`. Règles :

- PEO n'écrit qu'entre ses marqueurs. Contenu extérieur intact, octet pour octet (test).
- Bloc modifié à la main (empreinte différente) : régénération refusée sans `--force-block <id>` ; `status` le signale.
- Bloc absent : ajouté à la fin du fichier, précédé d'une ligne vide.

### 6.3 `AGENTS.md`

Créé s'il n'existe pas, sinon bloc géré ajouté. Contenu du bloc (au plus 60 lignes) :

1. Mission (réponse `q.mission`).
2. Composants : chemin, stacks, `runtime`, commandes `test`, `lint`, `verify` (préfixées par le runtime).
3. Processus : socle, recettes, portes actives, commande `/peo:flow`.
4. Emplacements de connaissance (`[knowledge]` du socle, surchargés par `peo.toml`).
5. Pointeur vers `.peo/README.md`.

Aucune règle du projet n'est réécrite dans ce bloc.

### 6.4 `CLAUDE.md` (E4, décision S-3)

| Situation | Action par défaut |
|---|---|
| Absent | Créer : `@AGENTS.md` + bloc géré `claude-md` (2 à 5 lignes : commandes `/peo:*` utiles) |
| `pointer` ou `thin` | Ajouter `@AGENTS.md` en première ligne s'il manque + bloc géré |
| `rich` | **Conserver** le contenu. Ajouter `@AGENTS.md` en première ligne s'il manque + bloc géré. Proposer la migration seulement si `q.claude_md = migrate` |

Migration (option) :

1. Découper `CLAUDE.md` en unités : sections de titre, éléments de liste de premier niveau, paragraphes, blocs de code.
2. Classer chaque unité, de façon déterministe : `path-scoped` (cite un chemin, une extension, un nom de fichier ou de composant présent dans le profil) → `.claude/rules/<composant ou thème>.md` avec `paths:` en tête ; `command` (bloc de code ou ligne de commande) → section Commandes d'`AGENTS.md`, hors bloc géré ; `context` (le reste) → `AGENTS.md`, hors bloc géré.
3. Présenter le **tableau de correspondance** dans le plan : unité (30 premiers caractères), classe, destination. L'humain peut corriger une ligne (la skill transmet la correction dans `answers['q.claude_md.mapping']`).
4. **Invariant vérifié avant écriture** : le multiensemble des unités normalisées (espaces réduits) en sortie est égal à celui en entrée. Sinon arrêt. Aucune règle ne disparaît, aucune n'est dupliquée.
5. Nouveau `CLAUDE.md` : `@AGENTS.md`, le bloc géré, et une ligne qui renvoie vers `.claude/rules/`. L'ancien est dans la sauvegarde.

Les principes qui relèvent de la constitution de Spec Kit **ne sont pas copiés** dans `.specify/memory/constitution.md` : PEO les liste dans `.peo/README.md` (« à considérer lors de `/speckit-constitution` ») avec un lien vers leur emplacement. Une règle n'a qu'un emplacement.

### 6.5 `.gitignore`, `.gitattributes`

Bloc géré `.gitignore` : `.peo/backups/`. Bloc géré `.gitattributes` : `.peo/history.ndjson merge=union`.

### 6.6 Cible `verify` (réponse `q.verify_cmd = make-verify`)

Bloc géré `verify` dans le `Makefile` racine (créé s'il n'existe pas) : une cible `verify` qui enchaîne, par composant, `typecheck`, `lint` et `test` connus, préfixés par le runtime. Une commande `test` d'un composant marqué `no-tests:<composant>` est omise et signalée. Pour `fx-split-stack` : `npm run typecheck`, `npm test`, `docker compose exec -T api vendor/bin/pint --test` ; `php artisan test` est ajouté quand le premier test backend existera (`peo status` le rappelle). Les tests de bout en bout (`test:e2e`) n'en font pas partie : trop lents pour une porte locale.

### 6.7 CI (`ci-check`, décision S-4)

| Cible | Fichier | Contenu du bloc |
|---|---|---|
| GitLab | `.gitlab-ci.yml` (créé si `q.ci = gitlab` et absent) | jobs `peo-status` (`peo status --ci`) et, par fiche `ci-check` retenue, le job de la fiche (ex. `semgrep scan --config auto --error`) |
| GitHub | `.github/workflows/peo.yml` (fichier entier possédé) | idem en GitHub Actions |

Les versions des images ou actions utilisées sont **épinglées** dans les fiches.

Un job de scan de secrets (`ci-check:gitleaks`, ajout du 2026-11-12) masque les valeurs trouvées dans les journaux de CI (`--redact`) : sans cela, la CI publierait le secret qu'elle signale.

## 7. Lock et journal (F8)

Schémas : [schemas/lock.schema.json](schemas/lock.schema.json), [schemas/history-event.schema.json](schemas/history-event.schema.json).

- Le lock est **réécrit entièrement** à la fin de chaque `apply` réussi ou partiel, trié par référence.
- `owns` est obligatoire pour chaque outil dont PEO a écrit quelque chose ; vide pour un outil seulement réutilisé (`reused: true`).
- Le journal est en ajout seul ; une ligne par action et par commande humaine (`flow approve`, `tools disable`) ; `actor` = `peo-cli` ou l'auteur git ; `plan` = empreinte.
- `merge=union` évite les conflits entre branches ; un événement en double après fusion est toléré (le lecteur déduplique par `(ts, action, tool, file)`).

## 8. Retrait et mise à jour

### 8.1 `tools remove` (F12)

1. `owned()` : possessions encore intactes (empreinte égale à celle du lock).
2. Possessions modifiées depuis : action `manual` (« clé modifiée à la main, à retirer par toi »).
3. Outil installé hors PEO (absent du lock) : retrait **refusé** au MVP (R4) ; la commande native est affichée.
4. Recettes impactées : étapes dont la capacité ne serait plus couverte, affichées avant l'accord.
5. Fichiers que l'outil écrit dans le dépôt (`surface.writes`, ex. `.serena/`) : jamais supprimés.

### 8.2 `tools update --plan` (F13)

Pour chaque outil du lock dont `versions.tested` du catalogue diffère : version actuelle → version testée, et **différence de surface** (hooks ajoutés ou retirés, nombre d'outils MCP, `network`, `write_tools` ajoutés — qui changeraient le `matcher` de la porte). Rien n'est appliqué au MVP.

## 9. Doc générée `.peo/README.md` (F9)

Sections : Projet (mission, composants), Outils retenus (raison de chaque, tirée de `selection`), Outils écartés (raison), Processus (recettes, portes, commandes), Commandes du projet, Ce qui reste à faire à la main, Notes. La section **Notes** est délimitée et préservée à la régénération. Langue : `project.languages.artifacts`.

## 10. Plan attendu pour `fx-split-stack`

Exemple complet : [schemas/examples/plan.split-stack.json](schemas/examples/plan.split-stack.json). Rendu par la skill :

```text
Prérequis           + intelephense 1.x (npm -g)                                    R3  php-lsp a besoin du serveur
                    ? backend/vendor absent : docker compose exec api composer install   (manuel, non bloquant)
Outils du poste     + specify-cli <version testée> (uv tool)                       R3
Spec Kit            + specify init --here --integration claude (no model invocation)    R2
                    + .specify/extensions/git/git-config.yml  branch_prefix: feat  R1  convention feat/ conservée
Plugins (projet)    + egm@egm   + mattpocock-skills   + typescript-lsp   + php-lsp       R3
Fichiers            + AGENTS.md (bloc géré)                                       R1
                    ~ CLAUDE.md  @AGENTS.md en tête + bloc géré ; contenu conservé  R1
                    ~ .claude/settings.json  hooks peo gate / peo context        R2
                    ~ README.md   « backend à venir » corrigé (réponse q.docs_drift)    R1
                    ~ HANDOFF.md  → docs/archive/HANDOFF.md                       R1
                    ~ .gitignore  ~ .gitattributes                                R1
                    ~ Makefile    cible verify en bloc géré (réponse q.verify_cmd)  R1
CI                  + .gitlab-ci.yml  peo-status + semgrep (réponse q.ci)         R1
PEO                 + .peo/peo.toml  profile.json  peo.lock.json  history.ndjson  README.md
Réutilisé           = Playwright (@playwright/test) pour browser.e2e
À faire par toi     /reload-plugins · /setup-matt-pocock-skills · /speckit-constitution · docker compose exec api composer install
```

Différence avec le document 09 : `CLAUDE.md` n'est plus migré d'office (S-3) ; les 9 règles du front restent où elles sont.
