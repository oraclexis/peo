"""Where the commands of a component run: host or docker:<service> (spec 12, section 2.3)."""

from __future__ import annotations

from collections.abc import Callable

from peo.discovery.compose import Service, norm


def component_runtime(path: str, ecosystems: list[str], services: list[Service],
                      which: Callable[[str], str | None], binaries: dict[str, str]) -> dict:
    if not ecosystems:
        return {"value": "host", "confidence": "unknown", "evidence": "no manifest"}
    binary = binaries[ecosystems[0]]
    node_only = ecosystems == ["node"]
    present = which(binary) is not None
    where = f"{binary} {'on' if present else 'not on'} PATH"
    for service in services:
        builds = service.build_context is not None and norm(service.build_context) == path
        mounts = [v for v in service.volumes if norm(v.split(":", 1)[0]) == path]
        if not (builds if node_only else builds or mounts):
            continue
        parts = [f"build.context {service.build_context}"] if builds else []
        parts += [f"volume {v}" for v in mounts]
        evidence = f"{service.file}: {service.name} {', '.join(parts)}; {where}"
        if node_only and present:
            return {"value": "host", "confidence": "fact", "evidence": evidence}
        return {"value": f"docker:{service.name}", "confidence": "likely" if present else "fact",
                "evidence": evidence}
    verb = "builds" if node_only else "builds or mounts"
    return {"value": "host", "confidence": "fact" if present else "unknown",
            "evidence": f"no compose service {verb} '{path}'; {where}"}
