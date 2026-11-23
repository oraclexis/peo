"""A5.2: the six properties of spec 13 section 8.5, on generated catalogs."""

import itertools
import json

from hypothesis import HealthCheck, given, settings

from peo import expr, selector
from peo.catalog import Catalog
from peo.selector import TooManyCandidates

from .conftest import NO_BACKBONE, make_catalog_doc, tool
from .strategies import EXCLUSIVE, worlds

CONFIG = settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def run(entries, rules, prof, catalog=None):
    catalog = catalog or make_catalog_doc(entries, rules, exclusive=EXCLUSIVE)
    return selector.select(catalog, prof, {}, {}, backbone="none", backbones=NO_BACKBONE), catalog


def dump(out):
    return json.dumps(out, sort_keys=True)


@CONFIG
@given(worlds())
def test_a5_2_determinism_and_independence_of_insertion_order(world):
    entries, rules, prof = world
    first, catalog = run(entries, rules, prof)
    assert dump(first) == dump(run(entries, rules, prof, catalog)[0])
    reversed_catalog = Catalog(capabilities=catalog.capabilities, rules=catalog.rules, questions=(),
                               entries=dict(reversed(list(catalog.entries.items()))))
    again = selector.select(reversed_catalog, prof, {}, {}, backbone="none", backbones=NO_BACKBONE)
    assert dump(first) == dump(again)


@CONFIG
@given(worlds())
def test_a5_2_no_conflict_and_exclusive_capabilities_once(world):
    entries, rules, prof = world
    out, catalog = run(entries, rules, prof)
    chosen = [e["ref"] for e in out["selected"]]
    present = [r["ref"] for r in prof["present_tools"]]
    docs = catalog.entries

    def clash(a, b):
        return b in docs[a]["relations"]["conflicts"] or a in docs[b]["relations"]["conflicts"]

    for a in chosen:
        assert not any(clash(a, b) for b in chosen + present if b != a), (a, chosen, present)
    for cap in EXCLUSIVE:
        mine = [r for r in chosen if cap in docs[r]["capabilities"]["provides"]]
        theirs = [r for r in present if cap in docs[r]["capabilities"]["provides"]]
        assert len(mine) <= 1 and (not mine or not theirs)


@CONFIG
@given(worlds())
def test_a5_2_coverage_every_hard_requirement_is_covered_or_cited(world):
    out, _ = run(*world)
    cited = {u["capability"] for u in out["uncovered"]}
    for req in out["requirements"]:
        if req["covered_by"] is None:
            assert req["capability"] in cited
            assert req["strength"] == "soft" or out["ok"] is False
        else:
            assert req["capability"] not in cited
    assert out["ok"] is (not any(u["strength"] == "hard" for u in out["uncovered"]))


def _objective(docs, present, wanted, chosen):
    covered = {c for r in chosen | present for c in docs[r]["capabilities"]["provides"]}
    hard = sum(1 for cap, s in wanted if s == "hard" and cap not in covered)
    soft = sum(1 for cap, s in wanted if s == "soft" and cap not in covered)
    cost = sum(selector.cost(docs[r], []) for r in chosen)
    return (hard, soft, cost, len(chosen), sorted(chosen))


def _closure(docs, present, refs):
    out, todo = set(), list(refs)
    while todo:
        ref = todo.pop()
        if ref in out or ref in present:
            continue
        out.add(ref)
        todo += docs[ref]["relations"]["requires"]
    return out


def _valid(docs, present, chosen):
    pool = list(chosen) + list(present)
    for a in chosen:
        if any(b != a and (b in docs[a]["relations"]["conflicts"] or a in docs[b]["relations"]["conflicts"])
               for b in pool):
            return False
    for cap in EXCLUSIVE:
        providers = [r for r in pool if cap in docs[r]["capabilities"]["provides"]]
        if len(providers) > 1 and any(r in chosen for r in providers):
            return False
    return True


def _candidates(docs, present, wanted, prof):
    """The tools the search may pick: usable, not present, `when` true, useful, not redundant."""
    caps = {cap for cap, _ in wanted}
    covered = {c for r in present for c in docs[r]["capabilities"]["provides"]}
    ctx = {"profile": prof, "answers": {}, "selection": {}}

    def ok(texts, want):
        return all(expr.holds(expr.parse(x), ctx) is want for x in texts)

    def usable(ref):
        return docs[ref]["status"] not in ("watch", "rejected", "backbone-alt")

    found = set()
    for ref, doc in docs.items():
        when = doc["selection"]["when"]
        provides = set(doc["capabilities"]["provides"])
        deps = _closure(docs, present, [ref]) - {ref}
        if (usable(ref) and ref not in present and ok(when["all"], True)
                and (not when["any"] or any(ok([x], True) for x in when["any"]))
                and ok(when["not"], False) and (provides & caps) - covered
                and not provides & covered & set(EXCLUSIVE) and all(usable(d) for d in deps)):
            found.add(ref)
    return found


@CONFIG
@given(worlds(max_tools=7))
def test_a5_2_optimality_against_exhaustive_search(world):
    out, catalog = run(*world)
    docs, present = catalog.entries, {r["ref"] for r in world[2]["present_tools"]}
    wanted = [(r["capability"], r["strength"]) for r in out["requirements"]]
    chosen = {e["ref"] for e in out["selected"]}
    candidates = sorted(_candidates(docs, present, wanted, world[2]))
    best = None
    for size in range(len(candidates) + 1):
        for subset in itertools.combinations(candidates, size):
            full = _closure(docs, present, subset)
            if _valid(docs, present, full):
                score = _objective(docs, present, wanted, full)
                best = score if best is None or score < best else best
    assert _objective(docs, present, wanted, chosen) == best


@CONFIG
@given(worlds())
def test_a5_2_minimality_every_tool_is_needed(world):
    out, catalog = run(*world)
    docs, present = catalog.entries, {r["ref"] for r in world[2]["present_tools"]}
    chosen = [e["ref"] for e in out["selected"]]
    needed = {c["capability"] for c in out["requirements"]}
    pulled = {dep for r in chosen for dep in docs[r]["relations"]["requires"]}
    roots = [r for r in chosen if r not in pulled]

    def covered(refs):
        return {c for r in set(refs) | present for c in docs[r]["capabilities"]["provides"]} & needed

    for ref in roots:       # dropping a tool drops what only it pulled in
        rest = _closure(docs, present, [r for r in roots if r != ref])
        assert covered(chosen) != covered(rest), ref


@CONFIG
@given(worlds())
def test_a5_2_traceability_every_entry_exactly_once(world):
    out, catalog = run(*world)
    seen = [e["ref"] for e in out["selected"]] + [e["ref"] for e in out["reused"]] \
        + [e["ref"] for e in out["rejected"]]
    assert sorted(seen) == sorted(catalog.entries)


@CONFIG
@given(worlds())
def test_a5_2_stability_an_entry_whose_when_is_false_changes_nothing(world):
    entries, rules, prof = world
    before, _ = run(entries, rules, prof)
    extra = tool("cli:never", ["x.c0", "x.c2"], any_=["profile.never == true"])
    after, _ = run(entries + [extra], rules, prof)
    for part in ("selected", "reused", "uncovered", "requirements", "cost_total", "ok"):
        assert before[part] == after[part], part
    assert [e for e in after["rejected"] if e["ref"] != "cli:never"] == before["rejected"]


def test_a_catalog_of_25_candidates_is_a_defect_not_a_search():
    entries = [tool(f"cli:t{i:02d}", [f"x.c{i:02d}"]) for i in range(25)]
    rules = [{"id": f"r{i:02d}", "require": {"capability": f"x.c{i:02d}", "strength": "soft"}}
             for i in range(25)]
    try:
        run(entries, rules, {"present_tools": []})
    except TooManyCandidates as error:
        assert error.candidates == 25
    else:
        raise AssertionError("expected TooManyCandidates")
