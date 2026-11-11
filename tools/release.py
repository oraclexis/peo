#!/usr/bin/env python3
"""Release helpers used by .github/workflows/{ci,release}.yml.

    release.py check-version [--tag vX.Y.Z]   pyproject, peo.__version__, tag and CHANGELOG agree
    release.py notes --tag vX.Y.Z             print the CHANGELOG section of that version

CHANGELOG.md format: "## Unreleased" on top, then one "## X.Y.Z — YYYY-MM-DD" section per release.
Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

VERSION_RE = re.compile(r'^__version__\s*=\s*"([^"]+)"', re.M)


def pyproject_version(root: Path) -> str:
    return tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]


def package_version(root: Path) -> str | None:
    match = VERSION_RE.search((root / "src" / "peo" / "__init__.py").read_text())
    return match.group(1) if match else None


def changelog_sections(root: Path) -> dict[str, str]:
    """Map heading key ("Unreleased" or "X.Y.Z") to the section body."""
    sections: dict[str, str] = {}
    key = None
    lines: list[str] = []
    for line in (root / "CHANGELOG.md").read_text().splitlines():
        heading = re.match(r"^## +(Unreleased|[0-9][^ ]*)", line)
        if heading:
            if key is not None:
                sections[key] = "\n".join(lines).strip() + "\n"
            key, lines = heading.group(1), []
        elif key is not None:
            lines.append(line)
    if key is not None:
        sections[key] = "\n".join(lines).strip() + "\n"
    return sections


def check_version(root: Path, tag: str | None) -> list[str]:
    errors = []
    version = pyproject_version(root)
    if package_version(root) != version:
        errors.append(f"src/peo/__init__.py __version__ is {package_version(root)!r}, "
                      f"pyproject.toml says {version!r}")
    sections = changelog_sections(root)
    if tag is None:
        if "Unreleased" not in sections and version not in sections:
            errors.append("CHANGELOG.md needs an '## Unreleased' section")
    else:
        if tag != f"v{version}":
            errors.append(f"tag {tag!r} does not match pyproject.toml version 'v{version}'")
        if version not in sections:
            errors.append(f"CHANGELOG.md has no '## {version}' section")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check-version")
    check.add_argument("--tag")
    notes = sub.add_parser("notes")
    notes.add_argument("--tag", required=True)
    args = parser.parse_args(argv)

    if args.cmd == "check-version":
        errors = check_version(args.root, args.tag)
        for error in errors:
            print(f"release: {error}", file=sys.stderr)
        if not errors:
            print(f"release: version {pyproject_version(args.root)} is consistent")
        return 1 if errors else 0

    section = changelog_sections(args.root).get(args.tag.removeprefix("v"))
    if section is None:
        print(f"release: CHANGELOG.md has no section for {args.tag}", file=sys.stderr)
        return 1
    sys.stdout.write(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
