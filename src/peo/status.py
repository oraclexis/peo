"""peo status (F11, R3): S-* findings, source states, findings order, limits and human output.

Spec 15 §6 (codes of the R3 delivery, unreadable sources), §7.3 (output) and §7.4 (limits).
Reads the Inventory only; with exposure=True, Discovery runs in memory and peo.exposure adds the
X-* findings. Never reads .peo/profile.json, writes nothing, opens no socket.
"""

from __future__ import annotations

from pathlib import Path

from peo import runner
from peo.inventory import inventory
from peo.inventory.effective import effective

S_CODES = ("S-DEGRADED-INVENTORY", "S-HOOK-FOREIGN", "S-PLUGIN-ERROR")
ALWAYS = ("L-SERVER-MANAGED", "L-SETTINGS-CLI", "L-SETTINGS-MANAGED-OTHER")
LIMITS = {
    "L-CASE-SENSITIVITY": "case sensitivity of the project volume is not measured",
    "L-CLAUDE-NEWER": "this Claude Code version is newer than those the rule table was played on",
    "L-DISCOVERY-DEPTH": "untracked sensitive files deeper than 3 folders are not audited",
    "L-GREP-GLOB": "whether deny Read rules apply to the Grep and Glob tools is not verified",
    "L-HTTP-HOOK": "an http hook sends data off this machine; its destination is not audited",
    "L-LAUNCH-ROOT": "verdicts assume Claude Code is launched from the project root",
    "L-MCP-APPROVAL": "approval settings of project MCP servers are not read",
    "L-MCP-LOCAL-USER": "MCP servers of the local and user scopes (~/.claude.json) are not read",
    "L-NESTED-SETTINGS": "settings of .claude/ folders below the root are not read",
    "L-SERVER-MANAGED": "managed settings sent by the server are not readable from this machine",
    "L-SETTINGS-CLI": "settings passed on the command line (--settings, --bare) are never read",
    "L-SETTINGS-MANAGED-OTHER": "managed settings outside the known files (MDM) are not read",
    "L-SYMLINK-DIR": "files under these linked folders are not audited:",
}
# NF13 (spec 10): invisible and bidirectional characters, written \u{NNNN} in human output.
_BIDI = frozenset([*range(0x200B, 0x2010), *range(0x202A, 0x202F), *range(0x2066, 0x206A), 0xFEFF])
_FIELDS = ("path", "source", "rule", "reason", "suggested_rule", "index")   # omitted when None


def escape(text: str) -> str:
    """C0, DEL and C1 as \\xNN, NF13 characters as \\u{NNNN}; anything else unchanged."""
    out = []
    for ch in text:
        cp = ord(ch)
        if cp < 0x20 or 0x7F <= cp <= 0x9F:
            out.append(f"\\x{cp:02x}")
        elif cp in _BIDI:
            out.append(f"\\u{{{cp:04x}}}")
        else:
            out.append(ch)
    return "".join(out)


def finding(code: str, severity: str, message: str, evidence: list[str], *,
            status: str = "applied", confidence: str = "fact", **fields) -> dict:
    """One finding of status.schema.json; plugin_index and name stay when null."""
    out = {"code": code, "severity": severity, "status": status, "confidence": confidence,
           "message": message, "evidence": list(evidence)}
    for key, value in fields.items():
        if value is not None or key not in _FIELDS:
            out[key] = value
    return out


def _null_first(value):
    return (0, "") if value is None else (1, value)


def sort_key(f: dict) -> tuple:
    """Total order of spec 15 §7.3 and A11.5; None sorts before any value."""
    return (f["code"], _null_first(f.get("path")), _null_first(f.get("source")),
            _null_first(f.get("plugin_index")), _null_first(f.get("index")), f["evidence"])


def classify(src: dict, family: str) -> str:
    """readable, unreadable, out-of-scope or disabled for one family of one source (15 §6)."""
    if src["reason"] == "out-of-scope":
        return "out-of-scope"
    if src["reason"] == "disabled":
        return "disabled"
    if src["status"] in ("read", "absent") and family not in src["invalid_families"]:
        return "readable"
    return "unreadable"


def why(src: dict, family: str) -> str:
    """Evidence naming why a family of a source is unreadable, never its content."""
    if src["status"] in ("read", "absent"):
        return f"{src['id']} invalid_families {family}"
    return f"{src['id']} {src['status']} {src['reason']}"


def unreadable_text(src: dict, family: str) -> str:
    if src["status"] in ("read", "absent"):
        return f"family {family} invalid"
    if src["status"] == "not_inspected":
        return f"not inspected ({src['reason']})"
    return f"file {src['status']} ({src['reason']})"


def _claude(inv: dict) -> dict:
    return next(s for s in inv["sources"] if s["id"] == "claude")


def claude_state(src: dict) -> str:
    return src["status"] if src["reason"] is None else f"{src['status']} {src['reason']}"


def _plugin_errors(inv: dict) -> list[dict]:
    claude = _claude(inv)
    if claude["status"] != "read":
        return [finding("S-PLUGIN-ERROR", "error",
                        f"Plugin errors not evaluated: claude {claude_state(claude)}",
                        [f"claude {claude_state(claude)}"], status="skipped", source="claude")]
    return [finding("S-PLUGIN-ERROR", "error",
                    f"Plugin {p['index']} of claude plugin list reports errors; error text not "
                    "shown",
                    [f"claude plugin {p['index']} errors {p['error_count']}"], source="claude")
            for p in inv["plugins"] if p["source"] == "claude" and p["error_count"]]


def _degraded(inv: dict) -> list[dict]:
    claude = _claude(inv)
    if claude["status"] == "read":
        return []
    state = claude_state(claude)
    return [finding("S-DEGRADED-INVENTORY", "warning",
                    f"Claude Code inventory degraded (claude {state}): plugins and their hooks "
                    "are known from settings files only", [f"claude {state}"], source="claude")]


def _inert(hook_src: dict, sources: list[dict], flags: list[dict]) -> tuple[list[str], list[str]]:
    """(message notes, evidence) on whether disableAllHooks or allowManagedHooksOnly applies."""
    notes, evidence = [], []
    by_id = {s["id"]: s for s in sources}
    managed_file = hook_src["id"].startswith("settings:managed")
    for key, value in (("disableAllHooks", effective("disableAllHooks", sources, flags)),
                       ("allowManagedHooksOnly", effective("allowManagedHooksOnly", sources, flags,
                                                           managed_only=True))):
        if value["value"] == "unknown":
            ids = value["unreadable"]
            notes.append(f"whether {key} makes it inert is unknown ({', '.join(ids)} unreadable)")
            evidence += [f"{why(by_id[i], 'flags')}: {key} unknown, hook may be inert" for i in ids]
            continue
        if value["value"] is not True:
            continue
        # spec 10 §5: disableAllHooks spares managed hooks unless set in managed;
        # allowManagedHooksOnly keeps managed hooks and plugins forced in managed.
        if key == "disableAllHooks":
            inert = value["source"].startswith("settings:managed") or not managed_file
        else:
            inert = hook_src["scope"] != "managed"
        if inert:
            notes.append(f"inert: {key} is true in {value['source']}")
            evidence.append(f"{value['source']} {key} true")
    return notes, evidence


def _hooks(inv: dict) -> list[dict]:
    found = []
    sources, flags = inv["sources"], inv["flags"]
    plugin_ids = {p["index"]: p["id"] for p in inv["plugins"] if p["source"] == "claude"}
    for src in sources:
        sid = src["id"]
        if not sid.startswith(("settings:", "plugin:")):
            continue
        state = classify(src, "hooks")
        if state in ("out-of-scope", "disabled"):
            continue
        if state == "unreadable":
            found.append(finding("S-HOOK-FOREIGN", "info",
                                 f"Hooks of {sid} not evaluated: {unreadable_text(src, 'hooks')}",
                                 [why(src, "hooks")], status="skipped", source=sid))
            continue
        for h in (h for h in inv["hooks"] if h["source"] == sid):
            if sid.startswith("plugin:"):
                n = int(sid.removeprefix("plugin:#"))
                name = plugin_ids.get(n) or f"#{n}"
                message = (f"{h['event']} {h['type']} hook of plugin {name}: owner outside the "
                           "catalog")
            else:
                message = (f"{h['event']} {h['type']} hook written in {src['path']}: owner {sid}, "
                           "outside the catalog")
            notes, extra = _inert(src, sources, flags)
            found.append(finding("S-HOOK-FOREIGN", "info", "; ".join([message, *notes]),
                                 [f"{sid} {h['event']}#{h['group_index']}.{h['hook_index']} "
                                  f"{h['type']}", *extra], source=sid))
    return found


def common_limits(inv: dict) -> set[str]:
    """Limits of spec 15 §7.4 that do not depend on Discovery."""
    limits = set(ALWAYS)
    if any(s["id"] in ("settings:project", "settings:local") and s["status"] == "read"
           for s in inv["sources"]):
        limits.add("L-LAUNCH-ROOT")
    if any(m["source"] == "mcp:project" for m in inv["mcp_servers"]):
        limits.add("L-MCP-APPROVAL")
    if any(h["type"] == "http" for h in inv["hooks"]):
        limits.add("L-HTTP-HOOK")
    return limits


def status(root: Path, *, exposure: bool, run: runner.Runner | None = None,
           user_config: Path | None, managed: Path | None, home: Path, platform: str) -> dict:
    """`data` of status.schema.json; the caller resolves every machine fact (research R5)."""
    run = runner.run if run is None else run   # resolved at call time: tests can intercept it
    inv = inventory(root, run=run, user_config=user_config, managed=managed)
    findings = _plugin_errors(inv) + _hooks(inv) + _degraded(inv)
    limits = common_limits(inv)
    data = {"inventory": inv, "findings": sorted(findings, key=sort_key),
            "rules_evaluated": list(S_CODES)}
    if exposure:
        # Imported here: peo.exposure imports this module, and Discovery is only for --exposure.
        from peo import exposure as ex
        from peo.discovery import discover, list_files

        profile = discover(root, run=run, warnings=[])
        tracked, _ = list_files(root, run)
        data["exposure"], more = ex.audit(profile, inv, tracked, root=root, home=home,
                                          platform=platform, table=ex.load_table(platform))
        data["rules_evaluated"] = sorted(S_CODES + ex.X_CODES)
        limits |= more
    data["limits"] = sorted(limits)
    return data


def render(data: dict) -> str:
    """Human output of spec 15 §7.3; every string from the repository goes through escape()."""
    found = data["findings"] + data.get("exposure", {}).get("findings", [])
    lines = []
    for f in (f for f in found if f["status"] == "applied"):
        where = f.get("path") or f.get("source")
        head = f"{f['severity']} {f['code']}" + (f" {escape(where)}" if where else "")
        likely = f" (likely: {f['reason']})" if f["confidence"] == "likely" else ""
        message = f["message"].removeprefix(f"{where}: ") if where else f["message"]
        lines.append(f"{head}: {escape(message)}{likely}")
    lines += [f"skipped {f['code']} {escape(f.get('source') or '')}: {escape(f['message'])}"
              for f in found if f["status"] == "skipped"]
    for code in data["limits"]:
        lines.append(f"limit {code}: {LIMITS[code]}")
        if code == "L-SYMLINK-DIR":
            lines += [f"  {escape(d)}" for d in data["exposure"]["linked_dirs"]]
    return "\n".join(lines)
