"""Exposure audit (F14, R3): the X-* findings, `audited` and the exposure limits (spec 15 §7).

Reads the profile computed in memory (`sensitive`, `components`), the Inventory, the embedded
conformance table, `discovery/detect.toml` (field `ci`) and the CI files of spec 15 §7.1 bis as
text. Runs no command, writes nothing, and never opens a link that leaves the project.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
import tomllib
from importlib import resources
from pathlib import Path

from peo import status as st
from peo.inventory.claude_rules import covers
from peo.inventory.effective import effective

X_CODES = ("X-COVERAGE-NOT-SHARED", "X-DATA-READABLE", "X-DATA-STORE", "X-LITERAL-IN-AGENT-CONFIG",
           "X-MCP-UNEVALUATED", "X-NO-SECRET-SCAN", "X-SANDBOX-FALLBACK", "X-SANDBOX-OFF",
           "X-SECRET-READABLE", "X-SECRET-TRACKED")
TABLES = {"Darwin": "claude-rules.json", "Linux": "claude-rules.linux.json"}
_SEGMENT = re.compile(r"[A-Za-z0-9._@+-]+")   # literal set of spec 14 §3.5
_KEY = re.compile(r"^\s*(?:-\s+)?([A-Za-z0-9_.-]+)\s*:(?:\s+(.*))?$")
_PROJECT_IDS = ("settings:project", "settings:local", "mcp:project")
_KINDS = {"secret_file": "secret file", "data_dump": "data dump", "log_dir": "log folder"}
_MAX_BYTES = 1024 * 1024
_LIMIT_TEXT = ("the sandbox applies deny Read rules to Bash commands; without it, their effect on "
               "Bash is not verified")


def load_table(platform: str) -> dict | None:
    """Embedded conformance table of the platform (research R4); None when there is none."""
    name = TABLES.get(platform)
    path = resources.files("peo").joinpath("conformance", name) if name else None
    return json.loads(path.read_text()) if path is not None and path.is_file() else None


def ci_tokens() -> list[str]:
    """Tokens of the `ci` field of discovery/detect.toml, in file order."""
    data = tomllib.loads(resources.files("peo.discovery").joinpath("detect.toml").read_text())
    return list(dict.fromkeys(t for tool in data["tool"] for t in tool.get("ci", [])))


def suggested_rule(path: str, is_dir: bool) -> str | None:
    """Read(./<path>) or Read(./<dir>/**) when every segment is literal (spec 15 §7.1)."""
    parts = path.split("/")
    if not all(_SEGMENT.fullmatch(p) and p not in (".", "..") for p in parts):
        return None
    return f"Read(./{path}/**)" if is_dir else f"Read(./{path})"


def _under(path: str, folder: str) -> bool:
    return path.startswith(folder + "/")


def _readable(path, kind, is_dir, v, unreadable, nested, link):
    code = "X-SECRET-READABLE" if kind == "secret_file" else "X-DATA-READABLE"
    severity = "error" if kind == "secret_file" else "warning"
    # A link inside the project: covers() compares its target only (spec 15 §7.1).
    rule = suggested_rule(link if isinstance(link, str) else path, is_dir)
    advice = (f"suggested rule {rule}" if rule else "write the deny Read rule by hand: the path "
              "holds characters outside the rule grammar")
    what = _KINDS[kind]
    reason = v["reason"]
    if v["verdict"] == "not_covered":
        evidence = [f"{path} {kind}: no deny Read rule matches"]
        message = f"{path}: no deny Read rule covers this {what}; {advice}"
        if unreadable:
            reason = "source-unreadable"
            evidence += [f"{st.why(s, 'permissions')}: source-unreadable" for s in unreadable]
            ids = ", ".join(s["id"] for s in unreadable)
            message += f"; unreadable settings may hold one ({ids})"
        parents = [n for n in nested if _under(path, posixpath.dirname(posixpath.dirname(n)))]
        if parents:
            reason = reason or "nested-settings"
            evidence += [f"{n}: nested settings not read" for n in parents]
            message += f"; nested settings apply when Claude Code is launched below ({parents[0]})"
    elif reason == "symlink-outside":
        evidence = [f"{path}: symbolic link to a file outside the project"]
        message = (f"{path} is a symbolic link to a file outside the project: no deny Read rule "
                   f"can be checked for it; {advice}")
    else:
        evidence = [f"{v['source']} deny {v['rule']}: {reason}", *v["evidence"]]
        message = (f"{path}: deny rule {v['rule']} found, but whether Claude Code applies it here "
                   f"is not verified ({reason}); {advice}")
    return st.finding(code, severity, message, evidence,
                      confidence="fact" if reason is None else "likely", path=path, reason=reason,
                      rule=v["rule"], source=v["source"], suggested_rule=rule)


def _not_shared(path, v, by_id):
    src = by_id[v["source"]]
    if src["id"] == "settings:project" and src["tracked"] is True and src["modified"] is False:
        return []
    evidence = [path, v["rule"], f"scope {src['scope']}"]
    if src["id"] != "settings:project":
        detail = f"the rule comes from {src['id']}"
    elif src["tracked"] is not True:
        detail = ".claude/settings.json is not tracked by git" if src["tracked"] is False else (
            "whether .claude/settings.json is tracked is unknown")
        evidence.append(f"tracked {json.dumps(src['tracked'])}")
    else:
        detail = (".claude/settings.json is modified and not committed" if src["modified"] else
                  "whether .claude/settings.json differs from the last commit is unknown")
        evidence.append(f"modified {json.dumps(src['modified'])}")
    return [st.finding("X-COVERAGE-NOT-SHARED", "warning",
                       f"{path}: covered by {v['rule']}, but the repository does not share this "
                       f"rule ({detail}); commit it in .claude/settings.json", evidence,
                       path=path, rule=v["rule"], source=src["id"])]


def _tracked_secrets(secret_files):
    found = []
    for e in (e for e in secret_files if e["tracked"]):
        if "link_target" in e and e["link_target"] is None:
            found.append(st.finding(
                "X-SECRET-TRACKED", "warning",
                f"{e['path']} is a tracked symbolic link to a file outside the project: the link "
                "is shared, not necessarily the secret", [f"{e['path']} tracked symbolic link"],
                path=e["path"]))
        else:
            found.append(st.finding(
                "X-SECRET-TRACKED", "error",
                f"{e['path']} is tracked by git: the file is in the repository; remove it from "
                "the index and rotate what it holds", [f"{e['path']} tracked"], path=e["path"]))
    return found


def _literals(inv, by_id):
    found = []
    for sid in _PROJECT_IDS:
        src = by_id[sid]
        if src["status"] == "absent" or src["tracked"] is False:
            continue
        broken = [f for f in ("values", "mcp") if st.classify(src, f) == "unreadable"]
        if src["tracked"] is None or broken:
            evidence = [st.why(src, f) for f in broken] or [f"{sid} tracked null"]
            text = (st.unreadable_text(src, broken[0]) if broken
                    else "whether the file is tracked by git is unknown")
            found.append(st.finding("X-LITERAL-IN-AGENT-CONFIG", "error",
                                    f"Literal values of {sid} not evaluated: {text}", evidence,
                                    status="skipped", source=sid))
            if src["tracked"] is None:
                continue
        # A readable subject family still gives its findings (spec 15 §6).
        servers = {m["index"]: m for m in inv["mcp_servers"]
                   if m["source"] == sid and m["plugin_index"] is None}
        for val in ([] if "values" in broken else inv["values"]):
            if val["source"] != sid or val["form"] != "literal" or not (
                    val["sensitive_name"] or val["value_hint"]):
                continue
            extra = {}
            match = re.match(r"mcp#([0-9]+)\.", val["location"])
            if match and int(match.group(1)) in servers:
                server = servers[int(match.group(1))]
                extra = {"index": server["index"], "name": server["name"], "plugin_index": None}
            key = val["key"] or "<unnamed>"
            found.append(st.finding(
                "X-LITERAL-IN-AGENT-CONFIG", "error",
                f"Tracked {src['path']}: key {key} ({val['location']}) holds a literal value; "
                "value not shown", [f"{src['path']} {val['location']} {key}"], source=sid, **extra))
        for m in ([] if "mcp" in broken else servers.values()):
            if m["args_hint"] is None:
                continue
            name = m["name"] or f"#{m['index']}"
            found.append(st.finding(
                "X-LITERAL-IN-AGENT-CONFIG", "error",
                f"Tracked {src['path']}: server {name} has credentials in an argument "
                f"({m['args_hint']}); value not shown", [f"{src['path']} mcpServers.{name} args"],
                source=sid, index=m["index"], name=m["name"], plugin_index=None))
    return found


def _ci_text(root: Path, real_root: str, rel: str) -> str | None:
    """Text of a CI file inside the project; None when it leaves it or cannot be read."""
    real = os.path.realpath(root / rel)
    if not real.startswith(real_root + os.sep) or not os.path.isfile(real):
        return None
    try:
        with open(real, "rb") as f:
            data = f.read(_MAX_BYTES + 1)
    except OSError:
        return None
    if len(data) > _MAX_BYTES or b"\0" in data:
        return None
    return data.decode("utf-8", "replace")


def _scanned(line: str) -> str | None:
    """Part of a line where scanner tokens count (spec 15 §7.1 bis, step 2)."""
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    match = _KEY.match(line)
    if match is None:
        return text
    key, value = match.group(1), (match.group(2) or "").strip()
    if not value or (key == "name" and "/" not in value):
        return None   # a key alone, or a job or step name
    return value


def _no_scan(root: Path, real_root: str, tracked: list[str]) -> list[dict]:
    tokens = ci_tokens()
    patterns = [re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(t)}(?![A-Za-z0-9_-])", re.IGNORECASE)
                for t in tokens]
    workflows = sorted(t for t in tracked if posixpath.dirname(t) == ".github/workflows"
                       and t.endswith((".yml", ".yaml")))
    files = [r for r in (".gitlab-ci.yml",) if os.path.lexists(root / r)] + workflows
    files += [r for r in (".pre-commit-config.yaml",) if os.path.lexists(root / r)]
    read, unreadable = [], []
    for rel in files:
        text = _ci_text(root, real_root, rel)
        if text is None:
            unreadable.append(rel)
            continue
        read.append(rel)
        for line in text.splitlines():
            part = _scanned(line)
            if part is not None and any(p.search(part) for p in patterns):
                return []
    recognized = ", ".join(tokens)
    message = (f"No known secret scanner in CI files or .pre-commit-config.yaml (recognized: "
               f"{recognized}); another scanner, or one called through a script, is not recognized")
    if not files:
        return [st.finding("X-NO-SECRET-SCAN", "warning", message, ["no CI file"])]
    if unreadable:
        return [st.finding("X-NO-SECRET-SCAN", "warning", message,
                           read + [f"{r} unreadable" for r in unreadable], confidence="likely",
                           reason="source-unreadable")]
    return [st.finding("X-NO-SECRET-SCAN", "warning", message, read)]


def _state(value: dict) -> str:
    return {None: "absent", True: "true", False: "false"}.get(value["value"], "unknown")


def _unknown(values: list[dict], by_id: dict) -> list[str]:
    unknown = [v for v in values if v["value"] == "unknown"]
    ids = dict.fromkeys(i for v in unknown for i in v["unreadable"])
    conflicts = dict.fromkeys(i for v in unknown for i in v["conflict"])
    return ([f"{st.why(by_id[i], 'flags')}: source-unreadable" for i in ids]
            + [f"{i}: disagrees with another managed source" for i in conflicts])


def _sandbox(profile, inv, covered, by_id):
    sens = profile["sensitive"]
    if not (sens["secret_files"] or sens["data_stores"]):
        return []
    sources, flags = inv["sources"], inv["flags"]
    listing = (f"files covered by a deny Read rule: {', '.join(covered)}" if covered
               else "no secret file is covered by a deny Read rule")
    enabled = effective("sandbox.enabled", sources, flags)
    if enabled["value"] is not True:
        docker = [c["runtime"]["value"] for c in profile["components"]
                  if c["runtime"]["value"].startswith("docker:")]
        severity = "info" if docker and not sens["secret_files"] else "warning"
        where = f" ({enabled['source']})" if enabled["source"] else ""
        evidence = [f"sandbox.enabled {_state(enabled)}{where}", *covered, *docker,
                    *_unknown([enabled], by_id)]
        unknown = enabled["value"] == "unknown"
        return [st.finding("X-SANDBOX-OFF", severity,
                           f"Sandbox not enabled (sandbox.enabled {_state(enabled)}{where}); "
                           f"{listing}; {_LIMIT_TEXT}", evidence,
                           confidence="likely" if unknown else "fact",
                           reason="source-unreadable" if unknown else None,
                           source=enabled["source"])]
    fail = effective("sandbox.failIfUnavailable", sources, flags)
    unsandboxed = effective("sandbox.allowUnsandboxedCommands", sources, flags)
    gaps = []
    if fail["value"] is not True:
        gaps.append(f"failIfUnavailable is {_state(fail)}")
    if unsandboxed["value"] is not False:
        gaps.append(f"allowUnsandboxedCommands is {_state(unsandboxed)}")
    if not gaps:
        return []
    unknown = _unknown([fail, unsandboxed], by_id)
    return [st.finding("X-SANDBOX-FALLBACK", "warning",
                       f"Sandbox enabled ({enabled['source']}) but {' and '.join(gaps)}: commands "
                       f"may run outside the sandbox; {listing}; {_LIMIT_TEXT}",
                       [f"{enabled['source']} sandbox.enabled true", *covered, *unknown],
                       confidence="likely" if unknown else "fact",
                       reason="source-unreadable" if unknown else None, source=enabled["source"])]


def _data_stores(stores):
    return [st.finding("X-DATA-STORE", "info",
                       f"Compose service {s['service']} runs a database ({s['kind']}): let the "
                       "agent work on test data only (anonymized copy, read-only role)",
                       [f"{s['source']} services.{s['service']} {s['kind']}"]) for s in stores]


def _mcp(inv):
    found = []
    for src in inv["sources"]:
        sid = src["id"]
        if not (sid.startswith("mcp:") or sid == "claude"):
            continue
        state = st.classify(src, "mcp")
        if state == "out-of-scope":
            continue
        if state == "unreadable" or (sid == "claude" and src["status"] != "read"):
            text = (f"claude {st.claude_state(src)}" if sid == "claude"
                    else st.unreadable_text(src, "mcp"))
            evidence = [f"claude {st.claude_state(src)}" if sid == "claude" else st.why(src, "mcp")]
            found.append(st.finding("X-MCP-UNEVALUATED", "info",
                                    f"MCP servers of {sid} not evaluated: {text}", evidence,
                                    status="skipped", source=sid))
            continue
        for m in (m for m in inv["mcp_servers"] if m["source"] == sid):
            name = m["name"] or f"#{m['index']}"
            plugin = "" if m["plugin_index"] is None else f" of plugin {m['plugin_index']}"
            ref = (f"claude plugin {m['plugin_index']} mcp#{m['index']} {name}"
                   if m["plugin_index"] is not None else f"{sid} mcp#{m['index']} {name}")
            found.append(st.finding("X-MCP-UNEVALUATED", "info",
                                    f"MCP server {name}{plugin} is not described by the catalog: "
                                    "what it reads is not evaluated", [ref], source=sid,
                                    plugin_index=m["plugin_index"], index=m["index"],
                                    name=m["name"]))
    return found


def audit(profile: dict, inv: dict, tracked: list[str], *, root: Path, home: Path,
          platform: str, table: dict | None) -> tuple[dict, set[str]]:
    """({"audited", "findings", "linked_dirs"}, exposure limits) of spec 15 §7.3 and §7.4."""
    sens = profile["sensitive"]
    sources = inv["sources"]
    by_id = {s["id"]: s for s in sources}
    real_root = os.path.realpath(root)
    deny = [r for r in inv["permission_rules"] if r["list"] == "deny"]
    managed_only = effective("allowManagedPermissionRulesOnly", sources, inv["flags"],
                             managed_only=True)["value"]
    unreadable = [s for s in sources if s["id"].startswith("settings:")
                  and st.classify(s, "permissions") == "unreadable"]
    nested = sens.get("nested_claude_settings", [])
    entries = ([(e, "secret_file", False) for e in sens["secret_files"]]
               + [(e, "data_dump", False) for e in sens["data_dumps"]]
               + [(e, "log_dir", True) for e in sens["log_dirs"]])
    audited, findings, covered, newer = [], [], [], False
    for e, kind, is_dir in entries:
        v = covers(e["path"], is_dir, e.get("link_target", False), deny, sources, managed_only,
                   inv["claude_version"], platform, table, real_root, str(home))
        audited.append({"path": e["path"], "kind": kind, "verdict": v["verdict"],
                        "reason": v["reason"], "rule": v["rule"], "source": v["source"]})
        if v["verdict"] == "covered":
            newer = newer or v["newer"]
            findings += _not_shared(e["path"], v, by_id)
            if kind == "secret_file":
                covered.append(e["path"])
        else:
            findings += [_readable(e["path"], kind, is_dir, v, unreadable, nested,
                                   e.get("link_target", False))]
    findings += _tracked_secrets(sens["secret_files"])
    findings += _literals(inv, by_id)
    findings += _no_scan(root, real_root, tracked)
    findings += _sandbox(profile, inv, covered, by_id)
    findings += _data_stores(sens["data_stores"])
    findings += _mcp(inv)
    walk = sens.get("walk", {"depth_pruned": False, "linked_dirs": []})
    limits = {"L-MCP-LOCAL-USER"}
    if any(a["verdict"] == "covered" for a in audited):
        limits |= {"L-CASE-SENSITIVITY", "L-GREP-GLOB"}
    for code, applies in (("L-CLAUDE-NEWER", newer), ("L-NESTED-SETTINGS", bool(nested)),
                          ("L-DISCOVERY-DEPTH", walk["depth_pruned"]),
                          ("L-SYMLINK-DIR", bool(walk["linked_dirs"]))):
        if applies:
            limits.add(code)
    return ({"audited": sorted(audited, key=lambda a: (a["path"], a["kind"])),
             "findings": sorted(findings, key=st.sort_key), "linked_dirs": walk["linked_dirs"]},
            limits)
