"""Discovery: the project profile, without an LLM, network or writes (spec 12).

P1.3 builds the components part: components, monorepo, multi_component (sections 1, 2.1 to 2.3).
Later steps add commands, conventions, docs, drift, signals, sensitive and metrics.
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import shutil
import tomllib
from collections.abc import Callable
from importlib import resources
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from peo import SCHEMA_VERSION, runner
from peo.discovery.commands import component_commands, is_test_file, package_manager, verify_command
from peo.discovery.compose import read_services
from peo.discovery.history import read_history
from peo.discovery.runtime import component_runtime

EXCLUDED = {".git", "node_modules", "vendor", "dist", "build", ".nuxt", ".output", ".venv",
            "target", "coverage"}
MAX_BYTES = 1024 * 1024
MAX_DEPTH = 3
MIN_LINES = 50
COMPOSE_FILES = ("docker-compose*.yml", "docker-compose*.yaml", "compose*.yml", "compose*.yaml")
WORKSPACE_FILES = ("pnpm-workspace.yaml", "turbo.json", "nx.json", "lerna.json")
NEEDS_DEPENDENCY = {"package.json", "composer.json", "pyproject.toml"}   # spec 12 §2.2 rule 4
GLOBAL_GAPS = ("no-ci", "no-verify", "no-remote", "no-agents-md", "no-adr")   # spec 12 §9 order

TABLES = tomllib.loads(resources.files("peo.discovery").joinpath("stacks.toml").read_text())
ECOSYSTEMS = TABLES["ecosystem"]
LANGUAGES = TABLES["language"]
STACKS = TABLES["stack"]
BINARIES = {e["id"]: e["binary"] for e in ECOSYSTEMS}


class Manifest(NamedTuple):
    path: str
    ecosystem: str
    deps: dict[str, str]          # normalized package name -> constraint ("" when none)
    scripts: dict[str, str]       # script name -> command (spec 12 §3)
    workspaces: list[str] | None  # globs, when this manifest declares workspaces


# --- files -----------------------------------------------------------------------------------

def _inside(root: Path, rel: str) -> bool:
    return (root / rel).resolve().is_relative_to(root.resolve())


def _excluded(rel: str) -> bool:
    return any(part in EXCLUDED for part in PurePosixPath(rel).parts[:-1])


def list_files(root: Path, run: runner.Runner) -> tuple[list[str], bool]:
    """Tracked files (or a walk outside git) and whether root is a git repository."""
    result = run(["git", "ls-files", "-z"], root)
    is_git = result.returncode == 0
    if is_git:
        rels = [p for p in result.stdout.decode("utf-8", "surrogateescape").split("\0") if p]
    else:
        rels = []
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED]
            base = Path(dirpath).relative_to(root)
            rels += [(base / f).as_posix() for f in filenames]
    return sorted(r for r in rels if not _excluded(r) and _inside(root, r)), is_git


def read_text(root: Path, rel: str) -> str | None:
    """Text of a file; None when absent, larger than 1 MB or binary (spec 12, section 1)."""
    try:
        path = root / rel
        if path.stat().st_size > MAX_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", "replace")


# --- manifests -------------------------------------------------------------------------------

REQUIREMENT = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*([^;#]*)")
POM_ARTIFACT = re.compile(r"<artifactId>\s*([^<\s]+)\s*</artifactId>")
GRADLE_COORDINATE = re.compile(r"""['"]([\w.-]+):([\w.-]+)(?::([\w.+-]+))?['"]""")
GRADLE_PLUGIN = re.compile(r"""\bid\s*\(?\s*['"]([\w.-]+)['"]""")
GEM = re.compile(r"""^\s*gem\s+['"]([\w-]+)['"](?:\s*,\s*['"]([^'"]+)['"])?""", re.MULTILINE)


def _strings(value) -> list[str] | None:
    return [v for v in value if isinstance(v, str)] if isinstance(value, list) else None


def _py_name(name: str) -> str:
    return re.sub(r"[._]", "-", name.lower())


def _requirements(lines) -> dict[str, str]:
    deps = {}
    for line in lines:
        if not isinstance(line, str):
            continue
        m = REQUIREMENT.match(line)
        if m and not line.lstrip().startswith(("#", "-")):
            deps[_py_name(m.group(1))] = m.group(2).strip()
    return deps


def _dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _scripts(value) -> dict[str, str]:
    out = {}
    for name, body in _dict(value).items():
        if isinstance(body, list):
            body = " && ".join(b for b in body if isinstance(b, str))
        if isinstance(body, str):
            out[name] = body
    return out


def _constraint(value) -> str:
    if isinstance(value, dict):
        value = value.get("version", "")
    return value if isinstance(value, str) else ""


def parse_manifest(rel: str, ecosystem: str, text: str) -> Manifest:
    """Raise ValueError when the manifest cannot be read."""
    name = PurePosixPath(rel).name
    deps: dict[str, str] = {}
    scripts: dict[str, str] = {}
    workspaces = None
    try:
        if name == "package.json":
            data = _dict(json.loads(text))
            for key in ("dependencies", "devDependencies"):
                deps.update({k.lower(): _constraint(v) for k, v in _dict(data.get(key)).items()})
            scripts = _scripts(data.get("scripts"))
            ws = data.get("workspaces")
            workspaces = _strings(ws.get("packages") if isinstance(ws, dict) else ws)
        elif name == "composer.json":
            data = _dict(json.loads(text))
            for key in ("require", "require-dev"):
                deps.update({k.lower(): _constraint(v) for k, v in _dict(data.get(key)).items()
                             if k != "php" and not k.startswith("ext-")})
            scripts = _scripts(data.get("scripts"))
        elif name == "pyproject.toml":
            data = tomllib.loads(text)
            project = _dict(data.get("project"))
            deps.update(_requirements(project.get("dependencies") or []))
            for group in _dict(project.get("optional-dependencies")).values():
                deps.update(_requirements(group if isinstance(group, list) else []))
            for group in _dict(data.get("dependency-groups")).values():
                deps.update(_requirements(group if isinstance(group, list) else []))
            poetry = _dict(_dict(data.get("tool")).get("poetry"))
            tables = [poetry.get("dependencies"), poetry.get("dev-dependencies")]
            tables += [_dict(g).get("dependencies") for g in _dict(poetry.get("group")).values()]
            for table in tables:
                deps.update({_py_name(k): _constraint(v) for k, v in _dict(table).items()
                             if k.lower() != "python"})
            scripts = _scripts(project.get("scripts"))
            uv = _dict(_dict(_dict(data.get("tool")).get("uv")).get("workspace"))
            workspaces = _strings(uv.get("members"))
        elif fnmatch.fnmatch(name, "requirements*.txt"):
            deps = _requirements(text.splitlines())
        elif name == "go.mod":
            block = False
            for line in text.splitlines():
                line = line.split("//")[0].strip()
                if line.startswith("require ("):
                    block = True
                elif block and line == ")":
                    block = False
                elif block or line.startswith("require "):
                    parts = line.removeprefix("require ").split()
                    if len(parts) >= 2:
                        deps[parts[0].lower()] = parts[1]
        elif name == "Cargo.toml":
            data = tomllib.loads(text)
            for key in ("dependencies", "dev-dependencies"):
                deps.update({k.lower(): _constraint(v) for k, v in _dict(data.get(key)).items()})
        elif name == "pom.xml":
            deps = {a.lower(): "" for a in POM_ARTIFACT.findall(text)}
        elif name.startswith("build.gradle"):
            for _, artifact, version in GRADLE_COORDINATE.findall(text):
                deps[artifact.lower()] = version
            deps.update({p.lower(): "" for p in GRADLE_PLUGIN.findall(text)})
        elif name == "Gemfile":
            for gem, version in GEM.findall(text):
                deps[gem.lower()] = version
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(str(exc)) from exc
    return Manifest(rel, ecosystem, deps, scripts, workspaces)


def _ecosystem_of(rel: str) -> str | None:
    name = PurePosixPath(rel).name
    for eco in ECOSYSTEMS:
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in eco["manifests"]):
            return eco["id"]
    return None


# --- stacks ----------------------------------------------------------------------------------

UNIVOCAL = re.compile(r"(\d+)(?:\.(?:\d+|x|\*))*")


def major(constraint: str) -> str | None:
    """'^11.9' -> '11', '~3.5' -> '3', '==5.0' -> '5'; ranges and wildcards -> None."""
    value = constraint.strip()
    for prefix in ("~=", "==", "^", "~", "=", "v"):
        if value.startswith(prefix):
            value = value[len(prefix):]
            break
    m = UNIVOCAL.fullmatch(value)
    return m.group(1) if m else None


def _matches(name: str, pattern: str) -> bool:
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


def stacks_of(manifests: list[Manifest]) -> list[dict]:
    found = []
    for stack in STACKS:
        for manifest in (m for m in manifests if m.ecosystem == stack["ecosystem"]):
            if stack.get("manifest_only"):
                found.append({"id": stack["id"], "confidence": "fact", "evidence": manifest.path})
                break
            packages = stack["packages"]
            names = sorted(n for n in manifest.deps if any(_matches(n, p) for p in packages))
            if not names:
                continue
            entry = {"id": stack["id"]}
            if stack.get("versioned"):
                own = next(n for p in packages for n in names if _matches(n, p))
                version = major(manifest.deps[own])
                if version:
                    entry["version"] = version
            entry |= {"confidence": "fact", "evidence": f"{manifest.path}: {', '.join(names)}"}
            found.append(entry)
            break
    return found


def kind_of(stacks: list[dict]) -> str:
    roles = {s.get("role") for s in STACKS if s["id"] in {x["id"] for x in stacks}}
    if "render" in roles and "server" in roles:
        return "fullstack"
    return "frontend" if "render" in roles else "backend" if "server" in roles else "library"


# --- components ------------------------------------------------------------------------------

def _dir(rel: str) -> str:
    parent = PurePosixPath(rel).parent.as_posix()
    return parent if parent else "."


def _under(rel: str, directory: str) -> bool:
    return directory == "." or rel == directory or rel.startswith(directory + "/")


def _pnpm_packages(text: str) -> list[str]:
    globs, inside = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if not line.startswith((" ", "-")):
            inside = stripped == "packages:"
        elif inside and stripped.startswith("- "):
            globs.append(stripped[2:].strip().strip("'\""))
    return globs


def _component(directory: str, manifests: list[Manifest], files: list[str], nested: list[str],
               loc: Callable[[str], int], services, which, read, pm: str) -> tuple[dict, bool]:
    """One component, and whether it has at least one test file (gap no-tests)."""
    own = [f for f in files if _under(f, directory) and not any(_under(f, n) for n in nested)]
    by_ext: dict[str, list[str]] = {}
    for f in own:
        by_ext.setdefault(PurePosixPath(f).suffix.lstrip("."), []).append(f)
    prefix = "" if directory == "." else directory + "/"
    languages, patterns = [], []
    for lang in LANGUAGES:
        present = [e for e in lang["extensions"] if e in by_ext]
        patterns += [f"{prefix}**/*.{e}" for e in present]
        if sum(loc(f) for e in present for f in by_ext[e]) >= MIN_LINES:
            languages.append(lang["id"])
    top_nested = [n for n in nested if not any(n != m and _under(n, m) for m in nested)]
    patterns += [f"!{n}/**" for n in sorted(top_nested)]
    present_ecos = {m.ecosystem for m in manifests}
    ecosystems = [e["id"] for e in ECOSYSTEMS if e["id"] in present_ecos]
    stacks = stacks_of(sorted(manifests, key=lambda m: m.path))
    runtime = component_runtime(directory, ecosystems, services, which, BINARIES)
    commands = component_commands(directory, manifests, own, read, pm, runtime["value"],
                                  [s["id"] for s in stacks], ecosystems)
    return {
        "id": "root" if directory == "." else directory.replace("/", "-"),
        "path": directory,
        "kind": kind_of(stacks),
        "ecosystems": ecosystems,
        "languages": languages,
        "stacks": stacks,
        "runtime": runtime,
        "commands": commands,
        "paths": {"code": patterns},
    }, any(map(is_test_file, own))


def discover(root: Path, *, run: runner.Runner = runner.run,
             which: Callable[[str], str | None] = shutil.which,
             warnings: list[dict] | None = None) -> dict:
    """Components part of the profile (spec 12, sections 1 and 2). Reads only."""
    root = Path(root)
    warnings = [] if warnings is None else warnings
    files, is_git = list_files(root, run)

    manifests: list[Manifest] = []
    for rel in files:
        ecosystem = _ecosystem_of(rel)
        if ecosystem is None or len(PurePosixPath(rel).parts) - 1 > MAX_DEPTH:
            continue
        text = read_text(root, rel)
        if text is None:
            continue
        try:
            manifests.append(parse_manifest(rel, ecosystem, text))
        except ValueError as exc:
            warnings.append({"code": "W_MANIFEST_UNREADABLE", "path": rel,
                             "message": f"manifest not readable, ignored: {exc}"})

    # Workspaces (spec 12 §2.2 rule 2): their declaring manifest opens no component.
    member_globs: list[str] = []
    declaring: set[str] = set()
    for m in manifests:
        if m.workspaces is not None:
            declaring.add(m.path)
            member_globs += [str(PurePosixPath(_dir(m.path)) / g) for g in m.workspaces]
    for rel in files:
        if PurePosixPath(rel).name == "pnpm-workspace.yaml":
            base = PurePosixPath(_dir(rel))
            declaring.add((base / "package.json").as_posix())
            globs = _pnpm_packages(read_text(root, rel) or "")
            member_globs += [(base / g).as_posix() for g in globs]
    workspace_tool = bool(declaring) or any(r in WORKSPACE_FILES for r in files)

    def member(directory: str) -> bool:
        return any(fnmatch.fnmatchcase(directory, g.removeprefix("./")) for g in member_globs)

    by_dir: dict[str, list[Manifest]] = {}
    for m in manifests:
        if m.path not in declaring:
            by_dir.setdefault(_dir(m.path), []).append(m)
    def opens(m: Manifest) -> bool:   # spec 12 §2.2 rule 4
        return PurePosixPath(m.path).name not in NEEDS_DEPENDENCY or bool(m.deps) or bool(m.scripts)

    component_dirs = sorted(d for d, ms in by_dir.items() if member(d) or any(map(opens, ms)))

    line_counts: dict[str, int] = {}

    def loc(rel: str) -> int:
        if rel not in line_counts:
            text = read_text(root, rel) or ""
            line_counts[rel] = sum(1 for line in text.splitlines() if line.strip())
        return line_counts[rel]

    compose = sorted(r for r in files if "/" not in r
                     and any(fnmatch.fnmatchcase(r, p) for p in COMPOSE_FILES))
    services = read_services(root, compose)
    pm = package_manager(files)

    def read(rel: str) -> str | None:
        return read_text(root, rel)

    if not component_dirs:
        built = [_component(".", [], files, [], loc, services, which, read, pm)]
    else:
        built = []
        for d in component_dirs:
            nested = [n for n in component_dirs if n != d and _under(n, d)]
            built.append(_component(d, by_dir[d], files, nested, loc, services, which, read, pm))
    built.sort(key=lambda item: (item[0]["id"] != "root", item[0]["id"]))
    components = [c for c, _ in built]
    history = read_history(root, run, is_git)
    root_manifests = [m for m in manifests if _dir(m.path) == "."]
    commands = {"verify": verify_command(files, root_manifests, read, pm)}
    ci = _ci(files)
    gaps = [g for g, missing in (("no-ci", ci["kind"] == "none"),
                                 ("no-verify", commands["verify"]["value"] is None),
                                 ("no-remote", not history["git"]["remote"])) if missing]
    gaps += [f"no-tests:{c['id']}" for c, has_tests in built if not has_tests]
    gaps += [f"no-lint:{c['id']}" for c in components if c["commands"]["lint"]["value"] is None]
    multi = len(components) >= 2
    return {"schema": SCHEMA_VERSION, "kind": history["kind"], "components": components,
            "monorepo": multi and workspace_tool, "multi_component": multi, "commands": commands,
            "conventions": history["conventions"], "git": history["git"], "ci": ci,
            "gaps": sorted(gaps, key=_gap_rank)}


def _ci(files: list[str]) -> dict:
    """spec 12 §4.3."""
    if ".gitlab-ci.yml" in files:
        return {"kind": "gitlab", "file": ".gitlab-ci.yml"}
    workflows = sorted(f for f in files if PurePosixPath(f).parent.as_posix() == ".github/workflows"
                       and f.endswith((".yml", ".yaml")))
    return {"kind": "github", "file": workflows[0]} if workflows else {"kind": "none", "file": None}


def _gap_rank(gap: str) -> tuple:
    """spec 12 §9: global gaps in fixed order, then no-tests:*, then no-lint:* (stable sort)."""
    if gap in GLOBAL_GAPS:
        return (GLOBAL_GAPS.index(gap),)
    return (len(GLOBAL_GAPS) + (gap.startswith("no-lint:")),)
