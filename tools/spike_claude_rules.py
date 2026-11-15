#!/usr/bin/env python3
"""Spike (R3, stage 0): how Claude Code matches `deny` permission rules on file paths.

    spike_claude_rules.py run --out FILE [--model haiku] [--only ID ...]
    spike_claude_rules.py dry-run          build every case and print its settings, no claude call

Each case builds a throwaway project under the home directory (so `~/` rules can be tested),
holding fake files only. The project gets `.claude/settings*.json` with `allow: ["Read", ...]`
plus the rule under test, then `claude -p` is asked to read one target with one tool. The fake
files carry a random marker; the verdict is:

    read          a result of the tool carried the marker
    denied        an entry in `permission_denials` names the tool and, for Read, the target path
    os-denied     the tool ran and the operating system or sandbox blocked it
    no-hit        the tool ran without error and returned no marker
    not-called    the tool was never called (refused by the model, or removed from its tools)
    auth-or-run-failed  claude ended in error before any tool call (often: no login)
    inconclusive  anything else

The verdict comes from `--output-format stream-json` tool results, never from the model's
reply; only a category is kept, not the result text.

Control cases carry no deny rule, one per target: they must come out `read`, or the run is not
trusted. Each case has a role (spec 14 section 3.5): `reference` (form, relation, scope),
`off-list` or `other-condition`.

The output table holds rules and paths with `<root>` and `<home>` placeholders, never the
marker, so it can be versioned (spec 14 section 3.5, schema claude-rules.schema.json). User
settings are excluded with `--setting-sources project,local`; managed settings on the machine
still apply: their top-level key names (never values) go to `managed_keys`.
Standard library only; every subprocess call takes an argument list.

User and managed scopes are not played: a temporary CLAUDE_CONFIG_DIR holds no login, and
managed settings need administrator rights. Rules from those scopes stay `undecidable`.
`sandbox-excluded-command` uses `cat` as a stand-in for `docker`; on 2.1.325 it still came out
`os-denied`.

Linux pass (case-sensitive file system), as the non-root user `node` so `bypassPermissions` is
accepted (node:22-bookworm already ships python3 and git). The container has no login: export
CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token` first. OUT is an empty folder you created:

    docker run --rm --user node -e CLAUDE_CODE_OAUTH_TOKEN -e NPM_CONFIG_PREFIX=/home/node/.npm \
      -v "$PWD:/peo:ro" -v "$OUT:/out" node:22-bookworm bash -c \
      'npm install -g @anthropic-ai/claude-code@2.1.325 >/dev/null && cd /tmp \
       && PATH=/home/node/.npm/bin:$PATH python3 /peo/tools/spike_claude_rules.py run \
          --out /out/claude-rules.linux.json'
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ENV_FILE = "backend/.env"
FAKE_FILES = (".env", ENV_FILE, "backend/sub/.env", ".claude/backend/.env", "backend/.env.local",
              "backend/key.pem")
MANAGED = {"Darwin": Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
           "Linux": Path("/etc/claude-code/managed-settings.json")}

# (id, deny rule, target, tool, extra settings, options). The rule may use {root} and {home_rel}.
# Options: "scope" = project (default) or local (settings.local.json); "cwd" runs claude from
# a subfolder; "mode" sets --permission-mode; "allow" adds allow rules; "no_allow" drops the
# default allow Read.
CASES = [
    ("control-read", None, ENV_FILE, "Read", {}, {}),
    ("control-read-root-env", None, ".env", "Read", {}, {}),
    ("control-read-sub", None, "backend/sub/.env", "Read", {}, {}),
    ("control-read-claude-dir", None, ".claude/backend/.env", "Read", {}, {}),
    ("control-read-link", None, "link.env", "Read", {}, {}),
    ("control-read-linkdir", None, "linkdir/.env", "Read", {}, {}),
    ("control-read-env-local", None, "backend/.env.local", "Read", {}, {}),
    ("control-read-pem", None, "backend/key.pem", "Read", {}, {}),
    ("control-grep", None, "backend", "Grep", {}, {}),
    ("control-glob", None, "backend", "Glob", {}, {}),
    ("control-sandbox-bash", None, ENV_FILE, "Bash",
     {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True}},
     {"allow": ["Bash(cat:*)"]}),
    ("dot-exact", "Read(./backend/.env)", ENV_FILE, "Read", {}, {}),
    ("bare-relative", "Read(backend/.env)", ENV_FILE, "Read", {}, {}),
    ("slash-anchor", "Read(/backend/.env)", ENV_FILE, "Read", {}, {}),
    ("slash-anchor-claude-dir", "Read(/backend/.env)", ".claude/backend/.env", "Read", {}, {}),
    ("double-slash-abs", "Read(/{root}/backend/.env)", ENV_FILE, "Read", {}, {}),
    ("tilde", "Read(~/{home_rel}/backend/.env)", ENV_FILE, "Read", {}, {}),
    ("bare-name-at-depth", "Read(.env)", ENV_FILE, "Read", {}, {}),
    ("bare-name-at-root", "Read(.env)", ".env", "Read", {}, {}),
    ("doublestar-name", "Read(**/.env)", ENV_FILE, "Read", {}, {}),
    ("dir-doublestar", "Read(./backend/**)", ENV_FILE, "Read", {}, {}),
    ("dir-star-nested", "Read(./backend/*)", "backend/sub/.env", "Read", {}, {}),
    ("dir-star-direct", "Read(./backend/*)", ENV_FILE, "Read", {}, {}),
    ("dir-trailing-slash", "Read(./backend/)", ENV_FILE, "Read", {}, {}),
    ("dir-no-slash", "Read(./backend)", ENV_FILE, "Read", {}, {}),
    ("bare-tool", "Read", ENV_FILE, "Read", {}, {}),
    ("bare-tool-deny-only", "Read", ENV_FILE, "Read", {}, {"no_allow": True}),
    ("case-differs", "Read(./backend/.ENV)", ENV_FILE, "Read", {}, {}),
    ("question-mark", "Read(./backend/.en?)", ENV_FILE, "Read", {}, {}),
    ("brackets", "Read(./backend/.[e]nv)", ENV_FILE, "Read", {}, {}),
    ("symlink", "Read(./backend/.env)", "link.env", "Read", {}, {}),
    ("grep", "Read(./backend/.env)", "backend", "Grep", {}, {}),
    ("glob", "Read(./backend/**)", "backend", "Glob", {}, {}),
    ("allow-specific-vs-deny", "Read(./backend/**)", ENV_FILE, "Read", {},
     {"allow": ["Read(./backend/.env)"]}),
    ("local-scope", "Read(./backend/.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-bare-relative", "Read(backend/.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-slash-anchor", "Read(/backend/.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-double-slash-abs", "Read(/{root}/backend/.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-tilde", "Read(~/{home_rel}/backend/.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-bare-name", "Read(.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-doublestar-name", "Read(**/.env)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("local-dir-doublestar", "Read(./backend/**)", ENV_FILE, "Read", {}, {"scope": "local"}),
    ("symlink-deny-link-read-link", "Read(./link.env)", "link.env", "Read", {}, {}),
    ("symlink-deny-link-read-target", "Read(./link.env)", ENV_FILE, "Read", {}, {}),
    ("symlink-dir", "Read(./backend/.env)", "linkdir/.env", "Read", {}, {}),
    ("symlink-dir-deny-linkdir", "Read(./linkdir/**)", ENV_FILE, "Read", {}, {}),
    ("sandbox-excluded-command", "Read(./backend/.env)", ENV_FILE, "Bash",
     {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True,
                  "excludedCommands": ["cat"]}},
     {"allow": ["Bash(cat:*)"]}),
    ("cwd-subfolder", "Read(./backend/.env)", ".env", "Read", {}, {"cwd": "backend"}),
    ("cwd-subfolder-abs", "Read(/{root}/backend/.env)", ".env", "Read", {}, {"cwd": "backend"}),
    ("bypass-mode", "Read(./backend/.env)", ENV_FILE, "Read", {}, {"mode": "bypassPermissions"}),
    ("sandbox-bash-deny-read", "Read(./backend/.env)", ENV_FILE, "Bash",
     {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True}},
     {"allow": ["Bash(cat:*)"]}),
    ("sandbox-bash-denyread", None, ENV_FILE, "Bash",
     {"sandbox": {"enabled": True, "autoAllowBashIfSandboxed": True,
                  "filesystem": {"denyRead": ["./backend/.env"]}}},
     {"allow": ["Bash(cat:*)"]}),
    # Played before milestone A' (spec 14 section 3.5, form star-segment): one `*` in the last segment.
    ("star-segment-dot", "Read(./backend/.env.*)", "backend/.env.local", "Read", {}, {}),
    ("star-segment-dot-local", "Read(./backend/.env.*)", "backend/.env.local", "Read", {},
     {"scope": "local"}),
    ("star-segment-any-depth", "Read(**/.env*)", "backend/.env.local", "Read", {}, {}),
    ("star-segment-any-depth-local", "Read(**/.env*)", "backend/.env.local", "Read", {},
     {"scope": "local"}),
    ("star-segment-extension", "Read(**/*.pem)", "backend/key.pem", "Read", {}, {}),
    ("star-segment-no-cross", "Read(./*.env)", "backend/.env", "Read", {}, {}),
]

# Role of each case in covers() (spec 14 section 3.5). Reference cases: (form, relation).
REFERENCE = {"dot-exact": ("dot", "exact"), "local-scope": ("dot", "exact"),
             "bare-relative": ("relative", "exact"), "local-bare-relative": ("relative", "exact"),
             "slash-anchor": ("root", "exact"), "local-slash-anchor": ("root", "exact"),
             "double-slash-abs": ("absolute", "exact"),
             "local-double-slash-abs": ("absolute", "exact"),
             "tilde": ("home", "exact"), "local-tilde": ("home", "exact"),
             "bare-name-at-depth": ("name", "exact"), "bare-name-at-root": ("name", "exact"),
             "local-bare-name": ("name", "exact"),
             "doublestar-name": ("any-depth", "exact"),
             "local-doublestar-name": ("any-depth", "exact"),
             "dir-doublestar": ("dot", "folder"), "dir-trailing-slash": ("dot", "folder"),
             "local-dir-doublestar": ("dot", "folder"), "dir-no-slash": ("dot", "under"),
             "star-segment-dot": ("star-segment", "exact"),
             "star-segment-dot-local": ("star-segment", "exact"),
             "star-segment-any-depth": ("star-segment", "exact"),
             "star-segment-any-depth-local": ("star-segment", "exact"),
             "star-segment-extension": ("star-segment", "exact")}
OTHER_CONDITION = {"control-grep", "control-glob", "control-sandbox-bash", "grep", "glob",
                   "sandbox-excluded-command", "cwd-subfolder", "cwd-subfolder-abs",
                   "sandbox-bash-deny-read", "sandbox-bash-denyread"}


def role(cid: str, opts: dict) -> dict:
    if cid in REFERENCE:
        form, relation = REFERENCE[cid]
        return {"role": "reference", "form": form, "relation": relation,
                "scope": opts.get("scope", "project")}
    if cid.startswith("control-") or cid in OTHER_CONDITION:
        return {"role": "other-condition"}
    return {"role": "off-list"}

PROMPTS = {
    "Read": "Use the Read tool, and no other tool, to read the file {path}. "
            "Reply with its first line only.",
    "Grep": "Use the Grep tool, and no other tool, to search the folder {path} for the text "
            "'spike marker', showing matching lines. Reply with the matching line only.",
    "Glob": "Use the Glob tool, and no other tool, to list the files matching {path}/** "
            "including dotfiles. Reply with the list only.",
    "Bash": "Use the Bash tool, and no other tool, to run: cat {path}. "
            "Reply with the first line of its output only.",
}
SUFFIX = " If the tool is refused or fails, reply exactly REFUSED."


def build(case, marker: str) -> tuple[Path, Path, str, dict]:
    """Create the throwaway project for one case. Returns (root, cwd, prompt, settings)."""
    cid, rule, target, tool, extra, opts = case
    home = Path.home()
    root = Path(tempfile.mkdtemp(prefix=".peo-spike-", dir=home))
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    for rel in FAKE_FILES:
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(f"spike marker {marker}\n")
    os.symlink(root / ENV_FILE, root / "link.env")
    os.symlink(root / "backend", root / "linkdir", target_is_directory=True)
    allow = ([] if opts.get("no_allow") else ["Read"]) + opts.get("allow", [])
    if tool in ("Grep", "Glob"):
        allow.append(tool)
    permissions: dict = {"allow": allow}
    if rule:
        permissions["deny"] = [rule.format(root=root, home_rel=root.relative_to(home))]
    settings = {"permissions": permissions, **extra}
    name = "settings.local.json" if opts.get("scope") == "local" else "settings.json"
    (root / ".claude" / name).write_text(json.dumps(settings, indent=2) + "\n")
    cwd = root / opts.get("cwd", "")
    path = target if tool in ("Bash", "Grep", "Glob") else str(cwd / target)
    prompt = PROMPTS[tool].format(path=path) + SUFFIX
    return root, cwd, prompt, settings


def tool_events(lines: list[str], marker: str) -> tuple[list[list[str]], dict]:
    """Tool calls and the category of each result, from stream-json; never their text."""
    names, events, final = {}, [], {}
    for line in lines:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(msg, dict):
            continue
        if msg.get("type") == "result":
            final = msg
        message = msg.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                names[block.get("id")] = block.get("name", "?")
            elif block.get("type") == "tool_result":
                text = json.dumps(block.get("content", ""))
                if marker in text:
                    category = "marker"
                elif not block.get("is_error"):
                    category = "no-marker"
                elif "sandbox" in text.lower() or "operation not permitted" in text.lower():
                    category = "os-denied"
                elif "permission" in text.lower():
                    category = "permission"
                elif any(w in text.lower() for w in ("denied", "not allowed", "blocked")):
                    category = "rule-blocked"
                else:
                    category = "error"
                events.append([names.get(block.get("tool_use_id"), "?"), category])
    return events, final


def denies(denial: dict, tool: str, target: str) -> bool:
    """A denial counts for its tool; for Read, only when it names the target path."""
    if denial.get("tool_name") != tool:
        return False
    if tool != "Read":
        return True
    path = (denial.get("tool_input") or {}).get("file_path", "")
    return isinstance(path, str) and path.endswith("/" + target)


def verdict(events: list[list[str]], final: dict, tool: str, target: str) -> str:
    """Decided from tool results and permission_denials, never from the model's reply."""
    mine = [c for name, c in events if name == tool]
    if "marker" in mine:
        return "read"
    if any(denies(d, tool, target) for d in final.get("permission_denials") or []):
        return "denied"
    if "os-denied" in mine:
        return "os-denied"
    if mine and set(mine) == {"no-marker"}:
        return "no-hit"
    if not mine:
        return "not-called"
    return "inconclusive"


def case_sensitive() -> bool:
    """Whether the file system holding the home directory distinguishes case."""
    with tempfile.TemporaryDirectory(dir=Path.home()) as d:
        (Path(d) / "a").touch()
        return not (Path(d) / "A").exists()


def placeholder(value, root: Path):
    """Replace machine paths with <root> and <home> in the stored table."""
    text = json.dumps(value).replace(str(root), "<root>").replace(str(Path.home()), "<home>")
    text = text.replace(root.name, "<root-name>")
    return json.loads(text)


def managed_keys() -> list[str]:
    """Top-level key names of this machine's managed settings file, never the values."""
    path = MANAGED.get(platform.system())
    try:
        data = json.loads(path.read_text()) if path else {}
    except (OSError, ValueError):
        return []
    return sorted(data) if isinstance(data, dict) else []


def version_number(raw: str) -> str:
    """'2.1.325 (Claude Code)' -> '2.1.325'."""
    return raw.split()[0] if raw.split() else raw


def run_case(case, model: str) -> dict:
    cid, rule, target, tool, _, opts = case
    marker = secrets.token_hex(16)
    root, cwd, prompt, settings = build(case, marker)
    sources = "project,local"
    command = ["claude", "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--model", model, "--setting-sources", sources, "--strict-mcp-config",
               "--no-session-persistence", "--permission-mode", opts.get("mode", "default")]
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                              timeout=180)
        events, final = tool_events(done.stdout.splitlines(), marker)
        result = verdict(events, final, tool, target)
        if not events and (final.get("is_error") or not final):
            result = "auth-or-run-failed"
        denied_tools = sorted({d.get("tool_name", "?")
                               for d in final.get("permission_denials") or []})
    except subprocess.TimeoutExpired:
        result, events, denied_tools = "inconclusive", [], []
    finally:
        shutil.rmtree(root, ignore_errors=True)
    row = {"id": cid, "tool": tool, "target": target, "settings": settings,
           "options": {k: v for k, v in opts.items() if k != "allow"},
           "setting_sources": sources, "observed": result, "denied_tools": denied_tools,
           "tool_results": events, **role(cid, opts)}
    return placeholder(row, root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--out", required=True, type=Path)
    run.add_argument("--model", default="haiku")
    run.add_argument("--only", nargs="*", default=None)
    sub.add_parser("dry-run")
    args = parser.parse_args(argv)
    if args.cmd == "dry-run":
        for case in CASES:
            root, cwd, prompt, settings = build(case, "0" * 32)
            try:
                assert cwd.is_dir() and (root / ".claude").is_dir(), case[0]
                print(case[0], json.dumps(placeholder(settings, root), sort_keys=True))
            finally:
                shutil.rmtree(root)
        return 0
    if shutil.which("claude") is None:
        print("claude not found on PATH", file=sys.stderr)
        return 1
    version = subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout
    cases = [c for c in CASES if args.only is None or c[0] in args.only]
    rows = []
    for case in cases:
        rows.append(run_case(case, args.model))
        print(f"{rows[-1]['id']}: {rows[-1]['observed']}", file=sys.stderr)
        # Written after each case: a crash keeps the rows already played.
        # versions_tested: append by hand when a later pass gives the same observations
        # (spec 14 section 3.5); a changed observation replaces the table.
        table = {"claude_version": version.strip(), "date": date.today().isoformat(),
                 "platform": platform.system(), "case_sensitive_fs": case_sensitive(),
                 "model": args.model, "setting_sources": "project,local",
                 "note": "managed settings of the machine that ran the spike still applied",
                 "managed_keys": managed_keys(),
                 "versions_tested": [version_number(version.strip())], "cases": rows}
        args.out.write_text(json.dumps(table, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
