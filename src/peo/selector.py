"""Selector (spec 13, section 8). Standard library only; pure: no file, no process, no clock.

`select` turns a catalog, a project profile, the answers and the tracked declarations into the
justified selection of 13 section 8.4. Not imported by gate.py or context.py.
"""

import math
import re
from functools import cache
from typing import NamedTuple

from peo import expr
from peo.catalog import Catalog

DEFAULT_BACKBONE = "speckit-egm-mattpocock"
# Backbone id -> its tools. Only the default exists in R4b; recipes and alternatives are R6.
BACKBONES = {DEFAULT_BACKBONE: ("framework:spec-kit", "claude-plugin:egm",
                                "claude-plugin:mattpocock-skills")}
MAX_CANDIDATES = 24
LABEL = re.compile(r" \([^)]*\)$")


class SelectorError(Exception):
    code = ""


class BackboneConflict(SelectorError):
    code = "E_BACKBONE_CONFLICT"

    def __init__(self, refs: list[str]):
        super().__init__("alternative backbone declared by the project: " + ", ".join(refs))
        self.refs = refs


class BackboneUnknown(SelectorError):
    code = "E_BACKBONE_UNKNOWN"


class TooManyCandidates(SelectorError):
    code = "E_TOO_MANY_CANDIDATES"

    def __init__(self, candidates: int):
        super().__init__(f"{candidates} candidates, at most {MAX_CANDIDATES}: "
                         "the catalog conditions are too wide")
        self.candidates = candidates


class Requirement(NamedTuple):
    capability: str
    strength: str       # hard | soft
    source: str         # backbone | always | rule id, plus " (<element>)" for a for_each rule


class Prerequisite(NamedTuple):
    check: str
    status: str         # met | unmet
    action: str         # none | fix | hint
    fix: str | None
    blocking: bool


@cache
def _parsed(text: str, it: bool = False) -> tuple:
    return expr.parse(text, it=it)


def _provides(doc: dict) -> list[str]:
    return list(doc["capabilities"]["provides"])


def _list(doc: dict, *path: str) -> list:
    node = doc
    for key in path:
        node = node.get(key, {}) if isinstance(node, dict) else {}
    return node if isinstance(node, list) else []


def _label(item: object) -> str:
    return str(item.get("id", "")) if isinstance(item, dict) else str(item)


def requirements(catalog: Catalog, profile: dict, answers: dict, backbone_tools,
                 selection: dict) -> list[Requirement]:
    """One requirement per capability, the strongest wins; in the order of capabilities.toml."""
    found: dict[str, Requirement] = {}

    def add(capability: str, strength: str, source: str) -> None:
        old = found.get(capability)
        if old is None or (strength == "hard" and old.strength == "soft"):
            found[capability] = Requirement(capability, strength, source)

    for ref in backbone_tools:
        for capability in _provides(catalog.entries[ref]):
            add(capability, "hard", "backbone")
    add("process.gates", "hard", "always")
    ctx = {"profile": profile, "answers": answers, "selection": selection}
    for rule in catalog.rules:
        need = rule["require"]
        if "for_each" in rule:
            items = expr.evaluate(_parsed(rule["for_each"]), ctx)
            node = _parsed(rule["when"], True) if "when" in rule else None
            for item in items if isinstance(items, list) else []:
                if node is None or expr.holds(node, {**ctx, "it": item}):
                    add(need["capability"], need["strength"], f"{rule['id']} ({_label(item)})")
        elif "when" not in rule or expr.holds(_parsed(rule["when"]), ctx):
            add(need["capability"], need["strength"], rule["id"])
    rank = {capability: i for i, capability in enumerate(catalog.capabilities)}
    return sorted(found.values(), key=lambda r: (rank.get(r.capability, len(rank)), r.capability))


def _plugin_matches(plugin_id: object, tokens: list) -> bool:
    return isinstance(plugin_id, str) and (plugin_id in tokens or plugin_id.split("@")[0] in tokens)


def _declared_refs(catalog: Catalog, declared: dict) -> dict[str, str]:
    """Catalog reference -> evidence, for every tracked declaration the catalog recognises."""
    found: dict[str, str] = {}
    for plugin in declared.get("plugins", []):
        if not isinstance(plugin, dict):
            continue
        for ref, doc in catalog.entries.items():
            if _plugin_matches(plugin.get("id"), _list(doc, "detect", "plugin")):
                found.setdefault(ref, f"declared plugin {plugin.get('id')}")
    for server in declared.get("mcp_servers", []):
        if isinstance(server, dict) and server.get("ref") in catalog.entries:
            found.setdefault(server["ref"], "declared MCP server")
    return found


def declared_backbones(catalog: Catalog, declared: dict) -> list[str]:
    return sorted(ref for ref in _declared_refs(catalog, declared)
                  if catalog.entries[ref]["status"] == "backbone-alt")


def present_tools(catalog: Catalog, profile: dict, declared: dict) -> dict[str, str]:
    """Tools already there: Discovery's list plus tracked declarations (13 section 8.1, step 3)."""
    found: dict[str, str] = {}
    for item in profile.get("present_tools", []):
        if isinstance(item, dict) and item.get("ref") in catalog.entries:
            found[item["ref"]] = str(item.get("evidence", ""))
    for ref, evidence in _declared_refs(catalog, declared).items():
        if catalog.entries[ref]["status"] != "backbone-alt":
            found.setdefault(ref, evidence)
    return dict(sorted(found.items()))


def _component_path(components: list, name: str) -> str | None:
    for comp in components:
        if name == comp.get("id") or name in comp.get("languages", []) or name in comp.get(
                "ecosystems", []):
            return comp.get("path")
    return None


def prerequisites(catalog: Catalog, entry: dict, profile: dict, present) -> list[Prerequisite]:
    """Status of each prerequisite from the profile alone (13 section 8.1 step 5, research D10)."""
    components = profile.get("components") or []
    binaries = {b for ref in present if ref in catalog.entries
                for b in _list(catalog.entries[ref], "detect", "bin")}

    def resolve(check: str) -> str:
        def one(m: re.Match) -> str:
            path = _component_path(components, m.group(1))
            return m.group(0) if path is None else path
        return re.sub(r"\{component:([^}]+)\}", one, check).replace("./", "")

    out = []
    for item in entry.get("prerequisites", []):
        check = resolve(item["check"])
        kind, _, arg = check.partition(":")
        if kind == "bin":
            met = arg in binaries
        elif kind == "path":
            met = any(arg == comp.get("path") for comp in components)
        elif kind == "runtime":
            met = arg == "host" and any(
                (comp.get("runtime") or {}).get("value") == "host" for comp in components)
        else:
            met = False
        action = "none" if met else "fix" if "fix" in item else "hint" if "hint" in item else "none"
        out.append(Prerequisite(check, "met" if met else "unmet", action,
                                item["fix"] if action == "fix" else None,
                                item.get("blocking", True)))
    return out


def cost(entry: dict, prereqs: list[Prerequisite]) -> int:
    """Cost of one tool (13 section 8.2): an integer."""
    surface = entry.get("surface", {})
    tokens = entry.get("cost", {}).get("context_static_tokens", 0)
    return (1 + math.ceil(tokens / 500) + 3 * len(surface.get("hooks", []))
            + 2 * (surface.get("network") == "runtime") + sum(p.action == "fix" for p in prereqs))


class _Cand(NamedTuple):
    ref: str
    gain: frozenset       # wanted capabilities it would newly cover
    cost: int
    closure: frozenset    # what it pulls in (requires and fixes), present tools excluded
    potential: frozenset  # wanted capabilities it or its closure provide


def _clash_map(catalog: Catalog) -> dict[str, set[str]]:
    clash: dict[str, set[str]] = {ref: set() for ref in catalog.entries}
    for ref, doc in catalog.entries.items():
        for other in _list(doc, "relations", "conflicts"):
            clash[ref].add(other)
            clash.setdefault(other, set()).add(ref)
    return clash


def _first_false(texts: list[str], ctx: dict, want: bool) -> str | None:
    for text in texts:
        if expr.holds(_parsed(text), ctx) is want:
            return text
    return None


def select(catalog: Catalog, profile: dict, answers: dict, declared: dict, *,
           backbone: str | None = None, backbones: dict | None = None) -> dict:
    """The selection of 13 section 8.4 for one project; raises SelectorError subclasses."""
    backbones = BACKBONES if backbones is None else backbones
    alternatives = declared_backbones(catalog, declared)
    answer = answers.get("q.backbone_conflict")
    if alternatives and answer is None:
        raise BackboneConflict(alternatives)
    chosen_id = answer if answer is not None else (backbone or DEFAULT_BACKBONE)
    if not isinstance(chosen_id, str) or chosen_id not in backbones:
        raise BackboneUnknown(f"unknown backbone {str(chosen_id)[:80]!r}")
    tools = tuple(backbones[chosen_id])
    absent = [t for t in tools if t not in catalog.entries]
    if absent:
        raise BackboneUnknown(f"backbone tool absent from the catalog: {', '.join(absent)}")

    present = present_tools(catalog, profile, declared)
    docs = catalog.entries
    present_cover: dict[str, str] = {}
    for ref in present:
        for capability in _provides(docs[ref]):
            present_cover.setdefault(capability, ref)
    selection = {"selected": [*tools, *present], "covered": sorted(present_cover)}
    reqs = requirements(catalog, profile, answers, tools, selection)
    wanted = {r.capability: r for r in reqs}
    ctx = {"profile": profile, "answers": answers, "selection": selection}
    exclusive = {c for c, flag in catalog.capabilities.items() if flag}
    clash = _clash_map(catalog)

    rejected: dict[str, tuple[str, str]] = {}
    reused: dict[str, list[str]] = {}
    candidates: dict[str, tuple] = {}     # ref -> (gain, prerequisites)
    helpers: dict[str, list[Prerequisite]] = {}     # fit only as a dependency
    blocked: set[str] = set()
    prereq_of: dict[str, list[Prerequisite]] = {}
    for ref, doc in docs.items():
        if ref in present:
            continue
        prereq_of[ref] = prerequisites(catalog, doc, profile, present)
        if any(p.blocking and p.status == "unmet" and p.fix is None for p in prereq_of[ref]):
            blocked.add(ref)
    for ref, doc in docs.items():
        status, provides = doc["status"], _provides(doc)
        if status in ("rejected", "watch"):
            rejected[ref] = ("STATUS", f"status {status}")
        elif status == "backbone-alt":
            rejected[ref] = ("BACKBONE_EXCLUSIVE", "alternative backbone")
        elif ref in present:
            covers = [c for c in provides if c in wanted and present_cover.get(c) == ref]
            if covers:
                reused[ref] = covers
            else:
                rejected[ref] = ("NOT_REQUIRED", f"{', '.join(provides) or 'nothing'} not required")
        else:
            gain = frozenset(c for c in provides if c in wanted and c not in present_cover)
            ALL, ANY, NOT = (_list(doc, "selection", "when", k) for k in ("all", "any", "not"))
            failing = _first_false(ALL, ctx, False)
            if failing is None and ANY and _first_false(ANY, ctx, True) is None:
                failing = " or ".join(ANY)
            contra = _first_false(NOT, ctx, True)
            redundant = next((c for c in provides if c in exclusive and c in present_cover), None)
            unmet = next((p for p in prereq_of[ref] if p.blocking and p.status == "unmet"
                          and p.fix is None), None)
            if failing is not None:
                rejected[ref] = ("CONDITION_FALSE", f"{failing} is false")
            elif contra is not None:
                rejected[ref] = ("CONTRAINDICATED", f"{contra} is true")
            elif not gain:
                helpers[ref] = prereq_of[ref]
            elif redundant is not None:
                rejected[ref] = ("REDUNDANT", f"{redundant} already provided by "
                                 f"{present_cover[redundant]}")
            elif unmet is not None:
                rejected[ref] = ("PREREQ_UNMET", f"{unmet.check} unmet and no fix")
            else:
                candidates[ref] = (gain, prereq_of[ref])

    def usable(ref: str) -> bool:
        doc = docs.get(ref)
        return doc is not None and doc["status"] not in ("rejected", "watch", "backbone-alt") \
            and ref not in blocked

    def direct(ref: str) -> list[str]:
        fixes = [p.fix for p in prereq_of.get(ref, []) if p.action == "fix" and p.fix]
        return sorted(set(_list(docs[ref], "relations", "requires")) | set(fixes))

    def closure_of(ref: str) -> frozenset | None:
        seen: set[str] = set()
        todo = direct(ref)
        while todo:
            dep = todo.pop()
            if dep in seen or dep in present:
                continue
            if not usable(dep):
                rejected[ref] = ("PREREQ_UNMET", f"requires {dep} unavailable")
                return None
            seen.add(dep)
            todo += direct(dep)
        return frozenset(seen)

    cands: list[_Cand] = []
    for ref, (gain, prereqs) in sorted(candidates.items()):
        closure = closure_of(ref)
        if closure is None:
            continue
        power = set(_provides(docs[ref]))
        for dep in closure:
            power |= set(_provides(docs[dep]))
        cands.append(_Cand(ref, gain, cost(docs[ref], prereqs), closure,
                           frozenset(power & wanted.keys())))
    if len(cands) > MAX_CANDIDATES:
        raise TooManyCandidates(len(cands))

    def dep_cost(ref: str) -> int:
        return cost(docs[ref], prereq_of[ref])

    best = _search(cands, wanted, present_cover, docs, clash, exclusive, set(present), dep_cost)
    chosen = best if best is not None else frozenset()

    for cand in cands:
        if cand.ref in chosen:
            continue
        blockers = sorted((clash[cand.ref] & (chosen | set(present))) - {cand.ref})
        if blockers:
            rejected[cand.ref] = ("CONFLICT", f"conflicts with {blockers[0]}")
            continue
        overlap = sorted(r for r in chosen if set(_provides(docs[r])) & cand.gain)
        rejected[cand.ref] = ("COST", "same coverage at a higher cost than " + ", ".join(overlap)
                              if overlap else "not needed by the cheapest set")
    for ref in helpers:
        if ref not in chosen:
            provides = _provides(docs[ref])
            rejected[ref] = ("NOT_REQUIRED", f"{', '.join(provides)} not required" if provides
                             else "not required by a selected tool")
    for ref in chosen:
        rejected.pop(ref, None)

    return _output(chosen, tools, chosen_id, reqs, present, present_cover, reused, rejected, docs,
                   prereq_of, direct)


def _search(cands, wanted, present_cover, docs, clash, exclusive, present, dep_cost):
    """Branch and bound over `cands`; the best set of references (closures included), or None."""
    order = sorted(cands, key=lambda c: (-len(c.gain), c.ref))
    hard = {c for c, r in wanted.items() if r.strength == "hard"}
    soft = set(wanted) - hard
    base = set(present_cover)
    suffix: list[frozenset] = [frozenset()] * (len(order) + 1)
    for i in range(len(order) - 1, -1, -1):
        suffix[i] = suffix[i + 1] | order[i].potential
    own_cost: dict[str, int] = {c.ref: c.cost for c in order}
    for c in order:
        for dep in c.closure:
            own_cost.setdefault(dep, dep_cost(dep))
    provides = {r: set(_provides(docs[r])) for r in own_cost}
    best: list = [None, None]      # objective, references

    def try_add(new: set[str], held: set[str], counts: dict[str, int]) -> dict[str, int] | None:
        pool = held | present | new
        counts = dict(counts)
        for ref in new:
            if clash[ref] & (pool - {ref}):
                return None
            for cap in provides[ref] & exclusive:
                if counts.get(cap, 0) > 0:
                    return None
                counts[cap] = 1
        return counts

    base_counts = {cap: 1 for r in present for cap in _provides(docs[r]) if cap in exclusive}

    def walk(i: int, held: set[str], counts: dict[str, int], covered: set[str], spent: int) -> None:
        reach = covered | suffix[i]
        key = (len(hard - reach), len(soft - reach), spent)
        if best[0] is not None and key > best[0][:3]:
            return
        if i == len(order):
            objective = (len(hard - covered), len(soft - covered), spent, len(held),
                         tuple(sorted(held)))
            if best[0] is None or objective < best[0]:
                best[0], best[1] = objective, frozenset(held)
            return
        cand = order[i]
        if cand.ref in held:
            walk(i + 1, held, counts, covered, spent)
            return
        new = {cand.ref} | (cand.closure - held)
        grown = try_add(new, held, counts)
        if grown is not None:
            gained = set().union(*(provides[r] for r in new)) & wanted.keys()
            walk(i + 1, held | new, grown, covered | gained, spent + sum(own_cost[r] for r in new))
        walk(i + 1, held, counts, covered, spent)

    walk(0, set(), base_counts, base, 0)
    return best[1]


def _output(chosen, tools, backbone_id, reqs, present, present_cover, reused, rejected, docs,
            prereq_of, direct):
    provisional = [t for t in tools if t in chosen] + sorted(r for r in chosen if r not in tools)
    covered_by: dict[str, str | None] = {}
    for req in reqs:
        covered_by[req.capability] = present_cover.get(req.capability) or next(
            (r for r in provisional if req.capability in _provides(docs[r])), None)
    covers = {r: [q.capability for q in reqs if covered_by[q.capability] == r] for r in chosen}
    rank = {q.capability: i for i, q in enumerate(reqs)}

    primaries = sorted((r for r in chosen if covers[r]),
                       key=lambda r: (r not in tools, tools.index(r) if r in tools else 0,
                                      rank[covers[r][0]], r))
    ordered: list[str] = []
    via: dict[str, tuple[str, str]] = {}

    def place(ref: str) -> None:
        ordered.append(ref)
        for dep in direct(ref):
            if dep in chosen and dep not in ordered and not covers[dep]:
                fixed = any(p.fix == dep for p in prereq_of.get(ref, []))
                via[dep] = ("prerequisite" if fixed else "requires", ref)
                place(dep)

    for ref in primaries:
        if ref not in ordered:
            place(ref)
    for ref in sorted(chosen):
        if ref not in ordered:
            place(ref)

    selected = []
    for ref in ordered:
        doc, prereqs = docs[ref], prereq_of[ref]
        if covers[ref]:
            first = next(q for q in reqs if q.capability == covers[ref][0])
            rule, reason = LABEL.sub("", first.source), "covers " + ", ".join(covers[ref])
        else:
            kind, parent = via.get(ref, ("requires", "another selected tool"))
            rule = f"{kind} ({parent})"
            reason = f"required by {parent}" if kind == "requires" else f"prerequisite of {parent}"
        item = {"ref": ref, "covers": covers[ref], "rule": rule, "reason": reason,
                "cost": cost(doc, prereqs)}
        if prereqs:
            item["prerequisites"] = [{"check": p.check, "status": p.status, "action": p.action,
                                      **({"fix": p.fix} if p.fix else {})} for p in prereqs]
        selected.append(item)
    uncovered = [{"capability": q.capability, "strength": q.strength} for q in reqs
                 if covered_by[q.capability] is None]
    return {
        "schema": 1,
        "ok": not any(u["strength"] == "hard" for u in uncovered),
        "backbone": {"id": backbone_id, "tools": list(tools)},
        "requirements": [{"capability": q.capability, "strength": q.strength, "source": q.source,
                          "covered_by": covered_by[q.capability]} for q in reqs],
        "selected": selected,
        "reused": [{"ref": r, "covers": reused[r], "evidence": present[r]} for r in sorted(reused)],
        "rejected": [{"ref": r, "code": code, "detail": detail}
                     for r, (code, detail) in sorted(rejected.items())],
        "uncovered": uncovered,
        "cost_total": sum(item["cost"] for item in selected),
    }
