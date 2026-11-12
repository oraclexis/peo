"""Compose files read line by line, without a YAML library (spec 12, sections 1 and 2.3).

Only `services.<name>.build` (scalar or `context:`) and short-form volumes are read;
everything else, `environment` included, is skipped (decision S-10, NF14).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

MAX_BYTES = 1024 * 1024


class Service(NamedTuple):
    file: str
    name: str
    build_context: str | None
    volumes: list[str]
    image: str | None = None


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def norm(path: str) -> str:
    """'./backend/' -> 'backend', './' or '.' -> '.'."""
    path = path.strip().rstrip("/")
    while path.startswith("./"):
        path = path[2:]
    return path or "."


def _services(file: str, text: str) -> list[Service]:
    services: list[Service] = []
    in_services = False
    name: str | None = None
    svc_indent = key_indent = None
    key = None
    build = None
    image = None
    volumes: list[str] = []

    def close():
        if name is not None:
            services.append(Service(file, name, build, volumes, image))

    for raw in text.splitlines():
        if raw.lstrip().startswith("#"):
            continue
        line = re.sub(r"\s+#.*$", "", raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        item = line.strip()
        if indent == 0:
            close()
            name, in_services = None, item == "services:"
            svc_indent = None
            continue
        if not in_services:
            continue
        if svc_indent is None:
            svc_indent = indent
        if indent == svc_indent:
            close()
            name = unquote(item[:-1]) if item.endswith(":") else None
            key_indent, key, build, image, volumes = None, None, None, None, []
            continue
        if name is None or indent < svc_indent:
            continue
        if key_indent is None:
            key_indent = indent
        if indent == key_indent:
            key, _, value = item.partition(":")
            key, value = key.strip(), value.strip()
            if key == "build" and value:
                build = unquote(value)
            elif key == "image" and value:
                image = unquote(value)
            continue
        if key == "build" and item.startswith("context:"):
            build = unquote(item.partition(":")[2])
        elif key == "volumes" and item.startswith("- "):
            volume = unquote(item[2:])
            if volume.startswith(".") and ":" in volume:   # short form ./<host>:<target>
                volumes.append(volume)
    close()
    return services


def read_services(root: Path, files: list[str]) -> list[Service]:
    services: list[Service] = []
    for file in files:
        path = root / file
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = path.read_text(errors="replace")
        except OSError:
            continue
        services.extend(_services(file, text))
    return services
