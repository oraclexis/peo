"""Catalog tools already present in the repository (spec 12, section 7 ter)."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import PurePosixPath

_TABLE = resources.files("peo.discovery").joinpath("detect.toml").read_text()
TOOLS = tomllib.loads(_TABLE)["tool"]


def _manager_of(manifest) -> str | None:
    name = PurePosixPath(manifest.path).name
    if name == "package.json":
        return "npm"
    if name == "composer.json":
        return "composer"
    return "pip" if manifest.ecosystem == "python" else None


def present_tools(files: list[str], manifests, component_of) -> list[dict]:
    """One entry per tool and component; dependencies first found in path order; sorted."""
    found: dict[tuple[str, str], dict] = {}
    for tool in TOOLS:
        for manifest in sorted(manifests, key=lambda m: m.path):
            manager = _manager_of(manifest)
            component = component_of(manifest.path)
            key = (tool["ref"], component or "")
            if manager is None or component is None or key in found:
                continue
            package = next((p for p in tool.get(manager, []) if p in manifest.deps), None)
            if package:
                section = (manifest.sections or {}).get(package, "dependencies")
                found[key] = {"ref": tool["ref"], "via": "dev-dependency", "component": component,
                              "evidence": f"{manifest.path} {section}: {package}"}
        path = next((f for f in tool.get("files", []) if f in files), None)
        if path and (tool["ref"], "") not in found:
            found[(tool["ref"], "")] = {"ref": tool["ref"], "via": "file", "evidence": path}
    return [found[key] for key in sorted(found)]
