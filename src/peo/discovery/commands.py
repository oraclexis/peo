"""Commands per component and the aggregated verify (spec 12, section 3). Nothing is executed."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import PurePosixPath

ROLE_SCRIPTS = {"typecheck": ("typecheck", "type-check"), "test": ("test",),
                "e2e": ("test:e2e", "e2e"), "lint": ("lint",), "build": ("build",),
                "format": ("format",)}
NPM_PLACEHOLDER = 'echo "Error: no test specified" && exit 1'
LINT_FALLBACK = (("pint", "vendor/bin/pint --test"), ("phpstan", "vendor/bin/phpstan analyse"),
                 ("eslint", "npx eslint ."), ("ruff", "ruff check ."))
ECOSYSTEM_LINTERS = {"node": ("eslint",), "php": ("pint", "phpstan"), "python": ("ruff",)}
TARGET = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", re.MULTILINE)
TEST_NAME = re.compile(r"\.(spec|test)\.[^.]+$|^test_.*\.py$|_test\.(py|go)$|Test\.php$")
TEST_DIRS = {"tests", "test", "__tests__", "spec"}


def makefile_targets(text: str) -> list[str]:
    targets: list[str] = []
    for match in TARGET.finditer(text):
        name = match.group(1)
        if not name.startswith(".") and name not in targets:
            targets.append(name)
    return targets


def is_test_file(rel: str) -> bool:
    path = PurePosixPath(rel)
    return bool(TEST_NAME.search(path.name)) or any(part in TEST_DIRS for part in path.parts[:-1])


def package_manager(files: list[str]) -> str:
    return "pnpm" if "pnpm-lock.yaml" in files else "yarn" if "yarn.lock" in files else "npm"


def _usable(role: str, body: str) -> bool:
    return bool(body.strip()) and not (role == "test" and body.strip() == NPM_PLACEHOLDER)


def _script_command(manifest: str, script: str, pm: str) -> str | None:
    name = PurePosixPath(manifest).name
    if name == "package.json":
        return f"{pm} test" if script == "test" else f"{pm} run {script}"
    if name == "composer.json":
        return f"composer {script}"
    return None                           # pyproject [project.scripts] are entry points, not tasks


def _entry(value, confidence, evidence) -> dict:
    return {"value": value, "confidence": confidence, "evidence": evidence}


Reader = Callable[[str], str | None]


def component_commands(directory: str, manifests, own_files: list[str], read: Reader, pm: str,
                       runtime: str, stack_ids: list[str], ecosystems: list[str]) -> dict:
    service = runtime.split(":", 1)[1] if runtime.startswith("docker:") else None
    prefix = f"docker compose exec -T {service} " if service else ""
    base = "" if directory == "." else directory + "/"
    makefile = f"{base}Makefile"
    targets = makefile_targets(read(makefile) or "") if makefile in own_files else []
    commands: dict[str, dict] = {}
    for role, names in ROLE_SCRIPTS.items():
        found = None
        for manifest in sorted(manifests, key=lambda m: m.path):
            for name in names:
                body = manifest.scripts.get(name)
                command = _script_command(manifest.path, name, pm) if body is not None else None
                if command and _usable(role, body):
                    found = _entry(prefix + command, "fact", f"{manifest.path} scripts.{name}")
                    break
            if found:
                break
        if not found:
            target = next((n for n in names if n in targets), None)
            if target:
                make_prefix = "" if directory == "." else prefix     # root Makefile: never prefixed
                found = _entry(f"{make_prefix}make {target}", "fact", f"{makefile} target {target}")
        if not found and role == "test":
            framework = next((s for s in ("phpunit", "pest") if s in stack_ids), None)
            if framework and f"{base}artisan" in own_files:
                found = _entry(prefix + "php artisan test", "likely",
                               f"{framework} declared, artisan present, no test script")
            elif "pytest" in stack_ids:
                found = _entry(prefix + "pytest", "likely", "pytest declared, no test script")
            else:
                found = _entry(None, "unknown", "no test script, no test framework declared")
        if not found and role == "lint":
            linter = next(((s, c) for s, c in LINT_FALLBACK if s in stack_ids), None)
            if linter:
                found = _entry(prefix + linter[1], "likely", f"{linter[0]} declared")
            else:
                known = ECOSYSTEM_LINTERS.get(ecosystems[0]) if ecosystems else None
                evidence = f"no {'/'.join(known)}, no lint script" if known else "no lint script"
                found = _entry(None, "unknown", evidence)
        if found:
            commands[role] = found
    return commands


def verify_command(files: list[str], root_manifests, read: Reader, pm: str) -> dict:
    has_makefile = "Makefile" in files
    targets = makefile_targets(read("Makefile") or "") if has_makefile else []
    for target in ("verify", "check"):
        if target in targets:
            return _entry(f"make {target}", "fact", f"Makefile target {target}")
    for manifest in sorted(root_manifests, key=lambda m: m.path):
        command = _script_command(manifest.path, "verify", pm)
        if command and _usable("verify", manifest.scripts.get("verify", "")):
            return _entry(command, "fact", f"{manifest.path} scripts.verify")
    if has_makefile:
        return _entry(None, "unknown", "no verify/check target in Makefile")
    return _entry(None, "unknown", "no Makefile, no verify script")
