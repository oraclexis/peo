"""Generated catalogs, profiles and rules for the properties of spec 13 section 8.5."""

from hypothesis import strategies as st

from .conftest import profile, rule, tool

CAPS = [f"x.c{i}" for i in range(5)]
EXCLUSIVE = ("x.c0", "x.c1")
FLAGS = ("profile.f1 == true", "profile.f2 == true", "profile.f3 == true")


@st.composite
def worlds(draw, max_tools: int = 9):
    """(entries, rules, profile) with acyclic `requires`, symmetric or not `conflicts`, present tools."""
    n = draw(st.integers(1, max_tools))
    refs = [f"cli:t{i}" for i in range(n)]
    entries = []
    for i, ref in enumerate(refs):
        entries.append(tool(
            ref,
            provides=draw(st.lists(st.sampled_from(CAPS), max_size=3, unique=True)),
            requires=draw(st.lists(st.sampled_from(refs[:i]), max_size=2, unique=True)) if i else [],
            conflicts=draw(st.lists(st.sampled_from([r for r in refs if r != ref] or [ref]), max_size=1))
            if n > 1 else [],
            status=draw(st.sampled_from(["conditional"] * 7 + ["watch", "backbone-alt", "reuse", "core"])),
            any_=draw(st.lists(st.sampled_from(FLAGS), max_size=2, unique=True)),
            not_=draw(st.lists(st.sampled_from(FLAGS), max_size=1)),
            tokens=draw(st.integers(0, 1500)),
            hooks=draw(st.lists(st.just("PreToolUse"), max_size=1))))
    rules = []
    for j, cap in enumerate(draw(st.lists(st.sampled_from(CAPS), max_size=5, unique=True))):
        rules.append(rule(f"r{j}", cap, draw(st.sampled_from(["hard", "soft"])),
                          when=draw(st.one_of(st.none(), st.sampled_from(FLAGS)))))
    present = draw(st.lists(st.sampled_from(refs), max_size=2, unique=True))
    prof = profile(present_tools=[{"ref": r, "evidence": "e"} for r in present],
                   f1=draw(st.booleans()), f2=draw(st.booleans()), f3=draw(st.booleans()))
    return entries, rules, prof
