"""F1 acceptance tests on the fx-split-stack reference fixture (spec 16, A1.1 to A1.5).

Each step of phase P1 removes the xfail marker of the tests it makes pass (P1.3: A1.3).
The host is fixed by injection: node present, php absent, as assumed by the golden profile.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from peo.discovery import discover

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "fx-split-stack"
GOLDEN = json.loads((ROOT / "tests" / "golden" / "fx-split-stack" / "profile.json").read_text())
ON_PATH = {"node", "git"}


def fake_which(name: str) -> str | None:
    return f"/usr/bin/{name}" if name in ON_PATH else None


@pytest.fixture(scope="module")
def split_stack_repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("fx") / "split-stack"
    subprocess.run(["bash", str(FIXTURE / "build.sh"), str(target)], check=True, capture_output=True)
    yield target
    shutil.rmtree(target, ignore_errors=True)


@pytest.fixture(scope="module")
def profile(split_stack_repo):
    return discover(split_stack_repo, which=fake_which)


def strip_volatile(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "generated"}


def without(component: dict, *keys: str) -> dict:
    return {k: v for k, v in component.items() if k not in keys}


@pytest.mark.xfail(strict=True, reason="full profile: docs, signals, sensitive, metrics (P1.5 to P1.7)")
def test_a1_1_profile_matches_golden(profile):
    assert strip_volatile(profile) == strip_volatile(GOLDEN)


def test_a1_3_two_components_backend_in_docker(profile):
    comps = {c["id"]: c for c in profile["components"]}
    assert set(comps) == {"root", "backend"}
    assert comps["backend"]["runtime"]["value"] == "docker:api"


def test_a1_3_components_match_golden(profile):
    got = [without(c, "runtime") for c in profile["components"]]
    assert got == [without(c, "runtime") for c in GOLDEN["components"]]
    assert profile["monorepo"] == GOLDEN["monorepo"]
    assert profile["multi_component"] == GOLDEN["multi_component"]


def test_a1_3_runtime_matches_golden(profile):
    assert [c["runtime"] for c in profile["components"]] == [c["runtime"] for c in GOLDEN["components"]]


def test_a1_4_conventions_survive_merge_commits(profile):
    assert profile["conventions"]["branches"]["id_style"] == "mixed"
    assert profile["conventions"]["branches"]["pattern"] == "^(feat|fix)/[A-Za-z0-9-]+$"
    assert profile["conventions"]["commits"]["style"] == "conventional"


def test_a1_commands_match_golden(profile):
    assert [c["commands"] for c in profile["components"]] == [c["commands"] for c in GOLDEN["components"]]
    assert profile["commands"] == GOLDEN["commands"]


def test_a1_4_conventions_match_golden(profile):
    assert profile["conventions"] == GOLDEN["conventions"]


def test_a1_repository_match_golden(profile):
    assert {k: profile[k] for k in ("kind", "git", "ci")} == {k: GOLDEN[k] for k in ("kind", "git", "ci")}


def test_a1_gaps(profile):
    later = {"no-agents-md", "no-adr"}   # P1.5
    assert profile["gaps"] == [g for g in GOLDEN["gaps"] if g not in later]


@pytest.mark.xfail(strict=True, reason="documentation drift (P1.5)")
def test_a1_5_documentation_drift(profile):
    rules = sorted((d["rule"], d["file"]) for d in profile["docs_drift"])
    assert ("D4", "HANDOFF.md") in rules
    assert ("D1", "README.md") in rules


def test_a1_3_duration(split_stack_repo):
    # SC-005: < 1 s measured by hand; 3 s here for slow CI machines.
    import time
    start = time.perf_counter()
    discover(split_stack_repo, which=fake_which)
    assert time.perf_counter() - start < 3
