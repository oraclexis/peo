"""Claude Code Inventory (F3, R2); see spec 14 §3.

Reads Claude Code settings, MCP files and `claude plugin list --json` for one project and
returns a dict that conforms to inventory.schema.json. Writes nothing, opens no socket, and
emits no value: every emitted string goes through an enum, `values.identifier` or a path field.
"""

import json
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

from peo import SCHEMA_VERSION, runner
from peo.inventory import values

_LIMIT = 1_048_576
_MIN_CLAUDE = (2, 1, 285)
_VERSION = re.compile(r"([0-9]{1,9})\.([0-9]{1,9})\.([0-9]{1,9})\b", re.ASCII)  # int() cap
_PROJECT_IDS = ("settings:local", "settings:project", "mcp:project")
_DECLARED_IDS = ("settings:project", "mcp:project")
_PLUGIN_SCOPES = ("user", "managed", "project", "local", "synced")
_HOOK_TYPES = ("command", "http", "mcp_tool", "prompt", "agent")
_LISTS = ("allow", "ask", "deny")
_SANDBOX_FLAGS = ("enabled", "failIfUnavailable", "allowUnsandboxedCommands")


class _Invalid(Exception):
    """A family is malformed in one source: drop all its entries there and name it."""


def default_managed() -> Path | None:
    """Folder of the managed settings files on this platform."""
    if sys.platform == "darwin":
        return Path("/Library/Application Support/ClaudeCode")
    if sys.platform.startswith("linux"):
        return Path("/etc/claude-code")
    return None


def declared(inv: dict) -> dict:
    """Tracked project declarations (H27): the only part of the Inventory selection reads."""
    ids = {s["id"] for s in inv["sources"] if s["id"] in _DECLARED_IDS and s["tracked"] is True}
    return {"plugins": [p for p in inv["plugins"] if p["source"] in ids],
            "mcp_servers": [m for m in inv["mcp_servers"] if m["source"] in ids]}


def _source(sid, scope, path=None, status="read", reason=None):
    return {"id": sid, "scope": scope, "path": path, "status": status, "reason": reason,
            "tracked": None, "invalid_families": []}


def _read(path: Path, root: Path | None):
    """(status, reason, object) of one JSON file; `root` confines project files."""
    try:
        resolved = path.resolve(strict=True)
        if (root is not None and not resolved.is_relative_to(root)) or not resolved.is_file():
            return "invalid", "not-regular", None
        with resolved.open("rb") as f:
            raw = f.read(_LIMIT + 1)
    except FileNotFoundError:
        return "absent", None, None
    except PermissionError:
        return "unavailable", "permission-denied", None
    except (IsADirectoryError, RuntimeError):  # RuntimeError: symlink loop before Python 3.13
        return "invalid", "not-regular", None
    except OSError as e:
        if e.errno == 40 or e.errno == 62:  # ELOOP on Linux, macOS
            return "invalid", "not-regular", None
        return "unavailable", "read-error", None
    except ValueError:  # NUL byte or lone surrogate in a path from `claude plugin list`
        return "unavailable", "read-error", None
    if len(raw) > _LIMIT:
        return "invalid", "too-large", None
    try:
        if b"\0" in raw:
            raise UnicodeDecodeError("utf-8", raw, 0, 1, "nul byte")
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return "invalid", "binary", None
    try:
        data = json.loads(text)
    except (ValueError, RecursionError):  # ValueError covers JSONDecodeError and huge ints
        return "invalid", "json", None
    if not isinstance(data, dict):
        return "invalid", "not-object", None
    return "read", None, data


def _file(sid, scope, path, display, root=None):
    status, reason, data = _read(path, root)
    return _source(sid, scope, display, status, reason), data


def _value(sid, location, key, value):
    return {"source": sid, "location": location, "key": values.identifier("key", key),
            "form": values.value_form(value), "sensitive_name": values.is_sensitive_name(key),
            "value_hint": values.value_hint(value)}


def _url_value(sid, location, url):
    return {"source": sid, "location": location, "key": "url", "form": values.value_form(url),
            "sensitive_name": values.url_sensitive_name(url), "value_hint": values.value_hint(url)}


def _object(data, key):
    """data[key] as a dict, {} when absent; any other type makes the family invalid."""
    found = data.get(key, {})
    if not isinstance(found, dict):
        raise _Invalid
    return found


def _permissions(sid, data):
    permissions = _object(data, "permissions")
    rules = []
    for name in _LISTS:
        listed = permissions.get(name, [])
        if not isinstance(listed, list):
            raise _Invalid
        for rule in listed:
            verdict = values.classify_permission(rule)
            if verdict == "invalid":
                raise _Invalid
            if verdict == "keep":
                rules.append({"source": sid, "list": name, "rule": rule})
    return rules


def _flags(sid, data, is_managed):
    found = {f"sandbox.{k}": v for k, v in _object(data, "sandbox").items() if k in _SANDBOX_FLAGS}
    keys = ("disableAllHooks", "allowManagedHooksOnly") if is_managed else ("disableAllHooks",)
    found.update({k: data[k] for k in keys if k in data})
    if not all(isinstance(v, bool) for v in found.values()):
        raise _Invalid
    return [{"source": sid, "key": k, "value": v} for k, v in found.items()]


def _hooks(sid, data):
    hooks, hook_values = [], []
    for event, groups in _object(data, "hooks").items():
        if values.identifier("event", event) is None or not isinstance(groups, list):
            raise _Invalid
        for g, group in enumerate(groups):
            if not isinstance(group, dict):
                raise _Invalid
            matcher = group.get("matcher")
            handlers = group.get("hooks", [])
            if not isinstance(handlers, list) or not isinstance(matcher, str | None):
                raise _Invalid
            for h, handler in enumerate(handlers):
                if not isinstance(handler, dict):
                    raise _Invalid
                kind = handler.get("type")
                if kind is not None and not isinstance(kind, str):
                    raise _Invalid
                hooks.append({
                    "source": sid, "event": event, "group_index": g, "hook_index": h,
                    "matcher": None if matcher is None else values.identifier("matcher", matcher),
                    "type": kind if kind in _HOOK_TYPES else "other",
                    "on_failure": _on_failure(handler)})
                if kind == "http":
                    hook_values += _http_values(sid, f"hook:{event}#{g}.{h}", handler)
    return hooks, hook_values


def _on_failure(handler):
    if "onFailure" not in handler:
        return None
    return handler["onFailure"] if handler["onFailure"] in ("block", "continue") else "other"


def _http_values(sid, prefix, handler):
    headers = _object(handler, "headers")
    found = [_value(sid, f"{prefix}.headers", k, v) for k, v in headers.items()]
    if "url" in handler:
        if not isinstance(handler["url"], str):
            raise _Invalid
        found.append(_url_value(sid, f"{prefix}.url", handler["url"]))
    return found


def _enabled_plugins(sid, data):
    enabled = _object(data, "enabledPlugins")
    if not all(isinstance(v, bool) for v in enabled.values()):
        raise _Invalid
    return [{"source": sid, "index": i, "id": values.identifier("plugin_id", k), "scope": None,
             "enabled": v, "error_count": None, "confidence": "likely"}
            for i, (k, v) in enumerate(enabled.items())]


def _check_server(server):
    if not isinstance(server, dict):
        raise _Invalid
    for key in ("command", "type", "url"):
        if key in server and not isinstance(server[key], str):
            raise _Invalid
    args = server.get("args", [])
    if not isinstance(args, list) or not all(isinstance(a, str) for a in args):
        raise _Invalid


def _servers(sid, groups, identify):
    """MCP servers of one source; groups = [(plugin_index or None, mcpServers)]."""
    servers, server_values = [], []
    for plugin_index, table in groups:
        if not isinstance(table, dict):
            raise _Invalid
        for server in table.values():
            _check_server(server)
        for index, (name, server) in enumerate(table.items()):
            ref = identify(values.mcp_identity(server)) if identify is not None else None
            servers.append({"source": sid, "plugin_index": plugin_index, "index": index,
                            "name": values.identifier("name", name),
                            "transport": values.mcp_transport(server),
                            "args_hint": values.args_hint(server),
                            "tool_ref": values.identifier("tool_ref", ref)})
            prefix = f"mcp#{index}" if plugin_index is None else f"mcp#{plugin_index}/{index}"
            server_values.append((prefix, server))
    return servers, server_values


def _server_values(sid, server_values):
    found = []
    for prefix, server in server_values:
        for part in ("env", "headers"):
            table = _object(server, part)
            found += [_value(sid, f"{prefix}.{part}", k, v) for k, v in table.items()]
        if "url" in server:
            found.append(_url_value(sid, f"{prefix}.url", server["url"]))
    return found


class _Output:
    def __init__(self):
        self.lists = {k: [] for k in ("permission_rules", "flags", "hooks", "plugins",
                                      "mcp_servers", "values")}

    def family(self, src, name, fn, *args):
        """Run one family extractor; on _Invalid, name the family and keep nothing from it."""
        try:
            return fn(*args)
        except _Invalid:
            src["invalid_families"].append(name)
            return None

    def settings(self, src, data):
        sid = src["id"]
        add = self.lists
        add["permission_rules"] += self.family(src, "permissions", _permissions, sid, data) or []
        is_managed = src["scope"] == "managed"
        add["flags"] += self.family(src, "flags", _flags, sid, data, is_managed) or []
        self.hooks(src, data)
        add["plugins"] += self.family(src, "plugins", _enabled_plugins, sid, data) or []
        add["values"] += self.family(src, "values", lambda: [
            _value(sid, "env", k, v) for k, v in _object(data, "env").items()]) or []

    def hooks(self, src, data):
        found = self.family(src, "hooks", _hooks, src["id"], data)
        if found:
            self.lists["hooks"] += found[0]
            self.lists["values"] += found[1]

    def mcp(self, src, groups, identify):
        found = self.family(src, "mcp", _servers, src["id"], groups, identify)
        if found:
            self.lists["mcp_servers"] += found[0]
            self.lists["values"] += self.family(src, "values", _server_values, src["id"],
                                                found[1]) or []


def _same_folder(path, root):
    if not isinstance(path, str) or not os.path.isabs(path):
        return False
    try:
        return Path(path).resolve() == root
    except (OSError, RuntimeError, ValueError):
        return False


def _claude(run, root):
    """(claude source, claude_version, plugin listing or None for the degraded mode)."""
    src = _source("claude", None)
    try:
        done = run(["claude", "--version"], root)
    except OSError:
        src.update(status="unavailable", reason="command-failed")
        return src, None, None
    if done.returncode == 127:
        src.update(status="absent")
        return src, None, None
    if done.returncode != 0:
        src.update(status="unavailable", reason="command-failed")
        return src, None, None
    lines = done.stdout.decode("utf-8", "replace").strip().splitlines()
    match = _VERSION.match(lines[0]) if lines else None
    if match is None:
        src.update(status="unavailable", reason="version-unparsed")
        return src, None, None
    version = ".".join(match.groups())
    if tuple(int(n) for n in match.groups()) < _MIN_CLAUDE:
        src.update(status="unavailable", reason="claude-too-old")
        return src, version, None
    try:
        done = run(["claude", "plugin", "list", "--json"], root)
    except OSError:
        src.update(status="unavailable", reason="command-failed")
        return src, version, None
    if done.returncode != 0:
        reason = "timeout-or-missing" if done.returncode == 127 else "command-failed"
        src.update(status="unavailable", reason=reason)
        return src, version, None
    try:
        listing = json.loads(done.stdout.decode("utf-8"))
    except (ValueError, RecursionError):  # UnicodeDecodeError is a ValueError
        listing = None
    if not isinstance(listing, list) or not all(
            isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("scope"), str)
            and isinstance(p.get("enabled"), bool) for p in listing):
        src.update(status="unavailable", reason="output-unparsed")
        return src, version, None
    return src, version, listing


def _managed_d(managed):
    folder = managed / "managed-settings.d"
    one = ("settings:managed.d", "managed", str(folder))  # single entry for the whole folder
    try:
        names = sorted(p.name for p in folder.iterdir() if p.name.endswith(".json"))
    except FileNotFoundError:
        return [(_source("settings:managed.d", "managed", None, "absent"), None)]
    except NotADirectoryError:
        return [(_source(*one, "invalid", "not-regular"), None)]
    except PermissionError:
        return [(_source(*one, "unavailable", "permission-denied"), None)]
    except OSError:
        return [(_source(*one, "unavailable", "read-error"), None)]
    if not names:
        return [(_source(*one), None)]
    return [_file(f"settings:managed.d/#{n}", "managed", folder / name, str(folder / f"#{n}"))
            for n, name in enumerate(names)]


def _tracked(run, root, project_sources):
    present = [s for s in project_sources if s["status"] in ("read", "invalid")]
    if not present:
        return
    try:
        done = run(["git", "ls-files", "-z", "--", *[s["path"] for s in present]], root)
    except OSError:
        return
    if done.returncode != 0:
        return
    listed = set(done.stdout.split(b"\0"))
    for s in present:
        s["tracked"] = s["path"].encode() in listed


def _null_first(value):
    return (0, 0) if value is None else (1, value)


def inventory(root: Path, *, run: runner.Runner | None = None, user_config: Path | None,
              managed: Path | None, identify: Callable[[dict], str | None] | None = None) -> dict:
    """Observed Claude Code configuration of `root` on this machine (spec 14 §3.2)."""
    run = runner.run if run is None else run  # resolved at call time: tests can intercept it
    real_root = root.resolve()
    files = []  # (source, kind, data) in rank order; kind: settings or mcp

    def fixed(sid, scope, reason="out-of-scope"):
        files.append((_source(sid, scope, None, "not_inspected", reason), None, None))

    def add(kind, pair):
        files.append((pair[0], kind, pair[1]))

    if managed is None:
        fixed("settings:managed", "managed", "not-provided")
        fixed("settings:managed.d", "managed", "not-provided")
    else:
        add("settings", _file("settings:managed", "managed", managed / "managed-settings.json",
                              str(managed / "managed-settings.json")))
        for pair in _managed_d(managed):
            add("settings", pair)
    fixed("settings:managed-other", "managed")
    fixed("settings:cli", "cli")
    add("settings", _file("settings:local", "local", root / ".claude" / "settings.local.json",
                          ".claude/settings.local.json", real_root))
    add("settings", _file("settings:project", "project", root / ".claude" / "settings.json",
                          ".claude/settings.json", real_root))
    if user_config is None:
        fixed("settings:user", "user", "not-provided")
    else:
        add("settings", _file("settings:user", "user", user_config / "settings.json",
                              "<user-config>/settings.json"))
    if managed is None:
        fixed("mcp:managed", "managed", "not-provided")
    else:
        add("mcp", _file("mcp:managed", "managed", managed / "managed-mcp.json",
                         str(managed / "managed-mcp.json")))
    fixed("mcp:local", "local")
    add("mcp", _file("mcp:project", "project", root / ".mcp.json", ".mcp.json", real_root))
    fixed("mcp:user", "user")

    claude, version, listing = _claude(run, root)
    sources = [f[0] for f in files] + [claude]
    plugins, plugin_files, plugin_servers = [], [], []
    if listing is None:
        sources.append(_source("plugin:*", None, None, "not_inspected", "degraded"))
    for n, plugin in enumerate(listing or []):
        scope = plugin["scope"]
        if scope in ("project", "local") and not _same_folder(plugin.get("projectPath"), real_root):
            continue
        scope = scope if scope in _PLUGIN_SCOPES else "other"
        errors = plugin.get("errors")
        plugins.append({"source": "claude", "index": n, "scope": scope,
                        "id": values.identifier("plugin_id", plugin["id"]),
                        "enabled": plugin["enabled"], "confidence": "fact",
                        "error_count": len(errors) if isinstance(errors, list) else 0})
        if not plugin["enabled"]:
            sources.append(_source(f"plugin:#{n}", scope, None, "not_inspected", "disabled"))
            continue
        install = plugin.get("installPath")
        display = f"plugin:#{n}/hooks/hooks.json"
        if isinstance(install, str) and os.path.isabs(install):
            hooks_file = Path(install) / "hooks" / "hooks.json"  # outside the root, on purpose
            src, data = _file(f"plugin:#{n}", scope, hooks_file, display)
        else:
            src, data = _source(f"plugin:#{n}", scope, display, "unavailable", "read-error"), None
        sources.append(src)
        plugin_files.append((src, data))
        if "mcpServers" in plugin:
            plugin_servers.append((n, plugin["mcpServers"]))

    _tracked(run, root, [s for s in sources if s["id"] in _PROJECT_IDS])

    out = _Output()
    out.lists["plugins"] += plugins
    for src, kind, data in files:
        if data is None:
            continue
        if kind == "settings":
            out.settings(src, data)
        else:
            out.mcp(src, [(None, data.get("mcpServers", {}))], identify)
    if plugin_servers:
        out.mcp(claude, plugin_servers, identify)
    for src, data in plugin_files:
        if data is not None:
            out.hooks(src, data)

    rank = {s["id"]: i for i, s in enumerate(sources)}
    lists = out.lists
    lists["permission_rules"].sort(key=lambda r: (rank[r["source"]], _LISTS.index(r["list"])))
    lists["flags"].sort(key=lambda f: (rank[f["source"]], f["key"]))
    lists["hooks"].sort(key=lambda h: (h["event"], rank[h["source"]], h["group_index"],
                                       h["hook_index"]))
    lists["plugins"].sort(key=lambda p: (-1 if p["source"] == "claude" else rank[p["source"]],
                                         p["index"]))
    lists["mcp_servers"].sort(key=lambda m: (rank[m["source"]], _null_first(m["plugin_index"]),
                                             m["index"]))
    lists["values"].sort(key=lambda v: (rank[v["source"]], v["location"], _null_first(v["key"])))
    return {"schema": SCHEMA_VERSION, "claude_version": version, "sources": sources, **lists}
