"""Command-line entry point (spec 11).

Only the envelope, exit codes and command names exist at this stage. Each command
is implemented in its phase (P1: discover, catalog, status; P2: questions, select; ...).
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from peo import SCHEMA_VERSION, __version__

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
        p = sub.add_parser(name, help=f"(not implemented yet, phase {phase})")
        p.add_argument("rest", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    phase = COMMANDS[args.command]
    message = f"'peo {args.command}' is specified but not implemented yet (phase {phase})"
    error = {"code": "E_NOT_IMPLEMENTED", "message": message}
    if args.json:
        print(json.dumps(envelope(args.command, False, errors=[error])))
    else:
        print(f"peo: {error['message']}", file=sys.stderr)
    return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
