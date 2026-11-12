"""Sensitive surfaces: where data to protect lives, never its content (spec 12, section 7 bis).

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
IMAGES = (("postgis/postgis", "postgres"), ("postgres", "postgres"), ("mysql", "mysql"),
          ("mariadb", "mariadb"), ("mongo", "mongodb"), ("valkey/valkey", "redis"),
          ("redis", "redis"),
          ("mcr.microsoft.com/mssql/server", "sqlserver"),
          ("docker.elastic.co/elasticsearch/elasticsearch", "elasticsearch"),
          ("elasticsearch", "elasticsearch"))


def walk(root: Path) -> tuple[list[str], list[str]]:
    """Files and directories down to depth 3, tracked or not, fixed exclusions, no outbound link."""
    files, dirs = [], []
    real_root = root.resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        base = Path(dirpath).relative_to(root)
        depth = 0 if base == Path(".") else len(base.parts)
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDED and depth < MAX_DEPTH)
        dirs += [(base / d).as_posix() for d in dirnames]
        for name in filenames:
            try:
                inside = (Path(dirpath) / name).resolve().is_relative_to(real_root)
            except (OSError, RuntimeError):   # symlink loop: RuntimeError before Python 3.13
                inside = False
            if inside:
                files.append((base / name).as_posix())
    return sorted(files), sorted(dirs)


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


def sensitive(root: Path, tracked: list[str], services: list[Service]) -> dict:
    """spec 12, section 7 bis."""
    tracked_set = set(tracked)
    files, dirs = walk(root)
    secret_files = []
    for f in files:
        if is_secret_file(f):
            is_env = PurePosixPath(f).name.startswith(".env")
            secret_files.append({"path": f, "tracked": f in tracked_set,
                                 "variables": env_names(root / f) if is_env else []})
    dumps = []
    for f in files:
        path = PurePosixPath(f)
        is_dump = any(fnmatch.fnmatchcase(path.name, p) for p in DUMP_PATTERNS)
        if is_dump and "migrations" not in path.parts[:-1]:
            size = (root / f).stat().st_size
            dumps.append({"path": f, "tracked": f in tracked_set, "bytes": size})
    log_dirs = [{"path": d, "tracked": any(t.startswith(d + "/") for t in tracked)}
                for d in dirs if PurePosixPath(d).name in LOG_DIRS]   # storage/logs included
    stores = []
    for service in services:
        kind = store_kind(service.image) if service.image else None
        if kind:
            stores.append({"kind": kind, "source": service.file, "service": service.name})
    return {"secret_files": secret_files,
            "data_stores": sorted(stores, key=lambda s: (s["source"], s["service"])),
            "data_dumps": dumps, "log_dirs": sorted(log_dirs, key=lambda d: d["path"])}
