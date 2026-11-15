"""Effective value of a scalar Claude Code setting (spec 14 §3.6).

Pure function over the Inventory output: no file, no command, no import outside typing.
"""

from typing import Any

# Precedence of spec 10 §5, strongest first; settings:managed.d/#<n> keep their name order.
_ORDER = ("settings:managed", "settings:managed.d", "settings:cli", "settings:local",
          "settings:project", "settings:user")
_MANAGED = 2   # the first two ranks are the managed sources


def _rank(sid: str) -> int | None:
    base = sid.split("/", 1)[0]
    return _ORDER.index(base) if base in _ORDER else None


def effective(key: str, sources: list[dict], flags: list[dict], *,
              managed_only: bool = False) -> dict[str, Any]:
    """{"value": bool | None | "unknown", "source": id | None, "unreadable": [ids]}.

    None: no source sets the key (Claude Code default). "unknown": a source at least as strong
    as the retained one cannot be read, or its flags family is invalid.
    """
    limit = _MANAGED if managed_only else len(_ORDER)
    ranked = [(r, s) for s in sources if (r := _rank(s["id"])) is not None and r < limit]
    chain = [s for _, s in sorted(ranked, key=lambda pair: pair[0])]   # stable sort
    unreadable: list[str] = []
    for src in chain:
        if src["reason"] == "out-of-scope" or src["status"] == "absent":
            continue
        if src["status"] != "read" or "flags" in src["invalid_families"]:
            unreadable.append(src["id"])
            continue
        found = [f["value"] for f in flags if f["source"] == src["id"] and f["key"] == key]
        if found:
            value = "unknown" if unreadable else found[0]
            return {"value": value, "source": src["id"], "unreadable": unreadable}
    return {"value": "unknown" if unreadable else None, "source": None, "unreadable": unreadable}
