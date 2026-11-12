"""Command-line entry point (spec 11).

The envelope, exit codes and command names exist for every command. Each command is
implemented in its phase (P1: discover, catalog, status; P2: questions, select; ...).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from shutil import which
from typing import Any

from peo import SCHEMA_VERSION, __version__, runner
from peo.discovery import discover

# Exit codes (spec 11, section 1.3)
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_STATUS_FINDINGS = 3
EXIT_CONSENT_OR_STALE_PLAN = 4
EXIT_PREREQUISITE = 5
EXIT_SELECTION_IMPOSSIBLE = 6

# Command name -> phase that implements it (docs/design/07-mvp-et-roadmap.md, section 4)
COMMANDS: dict[str, str] = {
    "discover": "P1",
    "catalog": "P1",
    "status": "P1",
    "questions": "P2",
    "select": "P2",
    "plan": "P3",
    "apply": "P3",
    "render-doc": "P3",
    "tools": "P3",
    "flow": "P4",
    "gate": "P4",
    "context": "P4",
}


def envelope(command: str, ok: bool, data: Any = None,
             warnings: list[dict] | None = None, errors: list[dict] | None = None) -> dict:
    """JSON envelope shared by every command (spec 11, section 1.2)."""
    return {
        "schema": SCHEMA_VERSION,
        "command": command,
        "ok": ok,
        "data": data if data is not None else {},
        "warnings": warnings or [],
        "errors": errors or [],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="peo", description="Project Engineering Orchestrator")
    parser.add_argument("--version", action="version", version=f"peo {__version__}")
    parser.add_argument("--project", metavar="DIR", help="project root (default: git root of cwd)")
    parser.add_argument("--json", action="store_true", help="print the JSON envelope on stdout")
    parser.add_argument("--catalog", metavar="SOURCE", help="local path or URL@ref of the catalog")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    for name, phase in COMMANDS.items():
        if name == "discover":
            p = sub.add_parser(name, help="detect the project profile (spec 11, section 2.1)")
            # SUPPRESS: without it the subparser default overwrites the global option.
            p.add_argument("--project", metavar="DIR", default=argparse.SUPPRESS,
                           help="project root")
            p.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                           help="print the JSON envelope on stdout")
            p.add_argument("--write", action="store_true", help="write .peo/profile.json")
            continue
        p = sub.add_parser(name, help=f"(not implemented yet, phase {phase})")
        p.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def _emit(args: argparse.Namespace, env: dict, human: str | None) -> None:
    """The envelope on stdout with --json; otherwise the human text, or the errors on stderr."""
    if args.json:
        print(json.dumps(env, sort_keys=True))
    elif env["ok"]:
        print(human)
    for error in env["errors"]:
        if not args.json:
            print(f"peo: {error['code']}: {error['message']}", file=sys.stderr)


def _project_root(project: str | None) -> Path | None:
    """--project as given if it is a directory; otherwise the git root of cwd, else cwd."""
    if project is not None:
        return Path(project) if Path(project).is_dir() else None
    done = runner.run(["git", "rev-parse", "--show-toplevel"], Path.cwd())
    return Path(os.fsdecode(done.stdout.strip())) if done.returncode == 0 else Path.cwd()


def _write_profile(root: Path, profile: dict) -> Path:
    """Write .peo/profile.json atomically, with generated in UTC (spec 11, section 2.1)."""
    peo_dir = root / ".peo"
    if not peo_dir.resolve().is_relative_to(root.resolve()):
        raise OSError(f"{peo_dir} resolves outside the project root")
    peo_dir.mkdir(exist_ok=True)
    generated = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = json.dumps(profile | {"generated": generated}, sort_keys=True, indent=2,
                      ensure_ascii=False) + "\n"
    target = peo_dir / "profile.json"
    umask = os.umask(0)
    os.umask(umask)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=peo_dir, prefix=".profile.",
                                         delete=False) as f:
            tmp = Path(f.name)
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, target)
    finally:
        # Gone after a successful replace; removed on any failure, Ctrl-C included.
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return target


def _summary(profile: dict, warnings: list[dict], written: Path | None) -> str:
    lines = [f"kind: {profile['kind']['value']}"]
    lines += [f"component {c['id']} ({c['path']}) runtime {c['runtime']['value']}"
              for c in profile["components"]]
    lines += [f"docs drift: {len(profile['docs_drift'])}", f"warnings: {len(warnings)}"]
    if written is not None:
        lines.append(f"written: {written}")
    return "\n".join(lines)


def discover_command(args: argparse.Namespace) -> int:
    root = _project_root(args.project)
    if root is None:
        error = {"code": "E_PROJECT_NOT_FOUND",
                 "message": f"project directory not found: {args.project}"}
        _emit(args, envelope("discover", False, errors=[error]), None)
        return EXIT_USAGE
    warnings: list[dict] = []
    # runner.run looked up at call time so tests can record the commands (A1.6).
    profile = discover(root, run=runner.run, which=which, warnings=warnings)
    for w in warnings:
        print(f"{w['code']} {w['path']}: {w['message']}", file=sys.stderr)
    written = None
    if args.write:
        try:
            written = _write_profile(root, profile)
        except OSError as exc:
            error = {"code": "E_WRITE_FAILED", "message": f"cannot write .peo/profile.json: {exc}"}
            _emit(args, envelope("discover", False, warnings=warnings, errors=[error]), None)
            return EXIT_ERROR
    _emit(args, envelope("discover", True, profile, warnings), _summary(profile, warnings, written))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    if args.command == "discover":
        return discover_command(args)
    phase = COMMANDS[args.command]
    message = f"'peo {args.command}' is specified but not implemented yet (phase {phase})"
    error = {"code": "E_NOT_IMPLEMENTED", "message": message}
    _emit(args, envelope(args.command, False, errors=[error]), None)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
