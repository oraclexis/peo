"""Sensitive surfaces: where sensitive data lives, never its content (spec 12, section 7 bis).

NF14: the right-hand side of a .env line is never kept, returned or logged; compose
`environment` blocks are never read.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path, PurePosixPath

from peo.discovery.compose import Service

EXCLUDED = {".git", ".peo", "node_modules", "vendor", "dist", "build", ".nuxt", ".output", ".venv",
            "target", "coverage"}
MAX_DEPTH = 3
MAX_BYTES = 1024 * 1024
MAX_NAMES = 200
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENV_EXAMPLES = {".env.example", ".env.sample", ".env.template", ".env.dist"}
SECRET_PATTERNS = ("*.pem", "*.key", "*.p12", "*.pfx", "credentials*.json", "id_rsa*",
                   "id_ed25519*")
DUMP_PATTERNS = ("*.sql", "*.dump", "*.bak", "*.sqlite", "*.sqlite3", "*.db")
LOG_DIRS = {"logs", "log"}
NESTED_SETTINGS = {"settings.json", "settings.local.json"}
IMAGES = (("postgis/postgis", "postgres"), ("postgres", "postgres"), ("mysql", "mysql"),
          ("mariadb", "mariadb"), ("mongo", "mongodb"), ("valkey/valkey", "redis"),
          ("redis", "redis"),
          ("mcr.microsoft.com/mssql/server", "sqlserver"),
          ("docker.elastic.co/elasticsearch/elasticsearch", "elasticsearch"),
          ("elasticsearch", "elasticsearch"))


def walk(root: Path) -> tuple[list[str], list[str], bool, list[str]]:
    """(files, dirs, depth_pruned, linked_dirs) down to depth 3, fixed exclusions, no link followed.

    A file link is listed whatever its target; the caller never opens one that leaves the root.
    """
    files, dirs, linked = [], [], []
    pruned = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath).relative_to(root)
        depth = 0 if base == Path(".") else len(base.parts)
        kept = sorted(d for d in dirnames if d not in EXCLUDED)
        is_link = {d: os.path.islink(os.path.join(dirpath, d)) for d in kept}
        if depth >= MAX_DEPTH:
            pruned = pruned or not all(is_link.values())
            kept = []
        dirs += [(base / d).as_posix() for d in kept]
        linked += [(base / d).as_posix() for d in kept if is_link[d]]
        dirnames[:] = kept
        files += [(base / name).as_posix() for name in filenames]
    return sorted(files), sorted(dirs), pruned, sorted(linked)


def link_target(root: Path, real_root: str, rel: str) -> str | None | bool:
    """False for an ordinary path; else the resolved target relative to the root, None outside.

    os.path.realpath only reads links (lstat, readlink): the target is never opened.
    """
    real = os.path.realpath(root / rel)
    if real == os.path.join(real_root, rel):
        return False
    inside = real.startswith(real_root + os.sep)
    return os.path.relpath(real, real_root).replace(os.sep, "/") if inside else None


def is_secret_file(rel: str) -> bool:
    name = PurePosixPath(rel).name
    if name in ENV_EXAMPLES:
        return False
    if name == ".env" or name.startswith(".env."):
        return True
    return any(fnmatch.fnmatchcase(name, p) for p in SECRET_PATTERNS)


def env_names(path: Path) -> list[str]:
    """Variable names only: the text after '=' is dropped at once (NF14)."""
    try:
        if path.stat().st_size > MAX_BYTES:
            return []
        data = path.read_bytes()
    except OSError:
        return []
    if b"\0" in data[:8192]:
        return []
    names: list[str] = []
    for raw in data.decode("utf-8", "replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        left = line.split("=", 1)[0].strip()
        left = left.removeprefix("export ").strip()
        if NAME.match(left) and left not in names:
            names.append(left)
        if len(names) == MAX_NAMES:
            break
    return sorted(names)


def store_kind(image: str) -> str | None:
    """'docker.io/library/postgres:16' -> 'postgres'; None for an image that is not a database."""
    name = image.split("@", 1)[0]
    head, _, last = name.rpartition("/")
    name = f"{head}/{last.split(':', 1)[0]}" if head else last.split(":", 1)[0]
    for prefix in ("docker.io/library/", "docker.io/", "library/"):
        name = name.removeprefix(prefix)
    return next((kind for start, kind in IMAGES if name.startswith(start)), None)


def _with_link(entry: dict, target: str | None | bool) -> dict:
    return entry if target is False else entry | {"link_target": target}


def sensitive(root: Path, tracked: list[str], services: list[Service]) -> dict:
    """spec 12, section 7 bis: the walk united with every tracked path, at any depth."""
    tracked_set = set(tracked)
    real_root = os.path.realpath(root)
    files, dirs, depth_pruned, linked_dirs = walk(root)
    candidates = sorted(set(files) | tracked_set)
    secret_files, dumps, nested = [], [], []
    for f in candidates:
        path = PurePosixPath(f)
        is_dump = any(fnmatch.fnmatchcase(path.name, p) for p in DUMP_PATTERNS)
        if not (is_secret_file(f) or is_dump):
            if path.name in NESTED_SETTINGS and len(path.parts) > 2 and path.parts[-2] == ".claude":
                nested.append(f)
            continue
        target = link_target(root, real_root, f)
        if is_secret_file(f):
            is_env = path.name.startswith(".env") and target is not None
            secret_files.append(_with_link({"path": f, "tracked": f in tracked_set,
                                            "variables": env_names(root / f) if is_env else []},
                                           target))
        elif "migrations" not in path.parts[:-1]:
            try:
                size = 0 if target is None else (root / f).stat().st_size
            except OSError:   # broken symbolic link or file gone: nothing to audit
                continue
            entry = {"path": f, "tracked": f in tracked_set, "bytes": size}
            dumps.append(_with_link(entry, target))
    log_dirs = [_with_link({"path": d, "tracked": any(t.startswith(d + "/") for t in tracked)},
                           link_target(root, real_root, d))
                for d in dirs if PurePosixPath(d).name in LOG_DIRS]   # storage/logs included
    stores = []
    for service in services:
        kind = store_kind(service.image) if service.image else None
        if kind:
            stores.append({"kind": kind, "source": service.file, "service": service.name})
    return {"secret_files": secret_files,
            "data_stores": sorted(stores, key=lambda s: (s["source"], s["service"])),
            "data_dumps": dumps, "log_dirs": log_dirs, "nested_claude_settings": nested,
            "walk": {"depth_pruned": depth_pruned, "linked_dirs": linked_dirs}}
