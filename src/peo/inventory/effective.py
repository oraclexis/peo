"""Effective value of a scalar Claude Code setting (spec 14 §3.6).

Pure function over the Inventory output: no file, no command, no import outside typing.
"""

from typing import Any

# Precedence of spec 10 §5, strongest first. The managed sources form one group whose merge
# order is not verified on Claude Code: none of them counts as stronger than another.
_ORDER = ("settings:managed", "settings:managed.d", "settings:cli", "settings:local",
          "settings:project", "settings:user")
_MANAGED = 2   # the first two ranks are the managed sources


def _rank(sid: str) -> int | None:
    base = sid.split("/", 1)[0]
    return _ORDER.index(base) if base in _ORDER else None


def _readable(src: dict) -> bool:
    return src["status"] == "read" and "flags" not in src["invalid_families"]


def _skipped(src: dict) -> bool:
    return src["reason"] == "out-of-scope" or src["status"] == "absent"


def effective(key: str, sources: list[dict], flags: list[dict], *,
              managed_only: bool = False) -> dict[str, Any]:
    """{"value": bool | None | "unknown", "source", "unreadable": [ids], "conflict": [ids]}.

    None: no source sets the key (Claude Code default). "unknown": a source at least as strong
    as the retained one cannot be read, its flags family is invalid, or managed sources disagree.
    """
    limit = _MANAGED if managed_only else len(_ORDER)
    ranked = [(r, s) for s in sources if (r := _rank(s["id"])) is not None and r < limit]
    chain = [s for _, s in sorted(ranked, key=lambda pair: pair[0])]   # stable sort

    def value_of(src: dict) -> list:
        return [f["value"] for f in flags if f["source"] == src["id"] and f["key"] == key]

    managed = [s for s in chain if _rank(s["id"]) < _MANAGED and not _skipped(s)]
    unreadable = [s["id"] for s in managed if not _readable(s)]
    found = [(s["id"], v[0]) for s in managed if _readable(s) and (v := value_of(s))]
    if found:
        conflict = [sid for sid, _ in found] if len({v for _, v in found}) > 1 else []
        unknown = bool(conflict or unreadable)
        return {"value": "unknown" if unknown else found[0][1], "source": found[0][0],
                "unreadable": unreadable, "conflict": conflict}
    for src in chain[len([s for s in chain if _rank(s["id"]) < _MANAGED]):]:
        if _skipped(src):
            continue
        if not _readable(src):
            unreadable.append(src["id"])
            continue
        if value := value_of(src):
            return {"value": "unknown" if unreadable else value[0], "source": src["id"],
                    "unreadable": unreadable, "conflict": []}
    return {"value": "unknown" if unreadable else None, "source": None,
            "unreadable": unreadable, "conflict": []}
