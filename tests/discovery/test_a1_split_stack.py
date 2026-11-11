"""F1 acceptance tests on the fx-split-stack reference fixture (spec 16, A1.1 to A1.5).

They are expected to fail until Discovery exists (xfail, strict): when one starts passing,
pytest reports it and the marker must be removed. They are skipped until the hand-written
fixture exists in tests/fixtures/fx-split-stack/ (spec 16, section 2.1; step P1.2).
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "fx-split-stack"
GOLDEN = json.loads((ROOT / "tests" / "golden" / "fx-split-stack" / "profile.json").read_text())

pytestmark = [
    pytest.mark.skipif(not (FIXTURE / "build.sh").exists(), reason="fx-split-stack fixture not built yet"),
    pytest.mark.xfail(reason="Discovery not implemented (phase P1)", raises=(ImportError, AttributeError)),
]


@pytest.fixture(scope="module")
def split_stack_repo(tmp_path_factory):
    target = tmp_path_factory.mktemp("fx") / "split-stack"
    subprocess.run(["bash", str(FIXTURE / "build.sh"), str(target)], check=True, capture_output=True)
    yield target
    shutil.rmtree(target, ignore_errors=True)


@pytest.fixture(scope="module")
def profile(split_stack_repo):
    # Resolved at call time so that the xfail marker catches the missing module.
    return lambda: __import__("peo.discovery", fromlist=["discover"]).discover(split_stack_repo)


def strip_volatile(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "generated"}


def test_a1_1_profile_matches_golden(profile):
    profile = profile()
    assert strip_volatile(profile) == strip_volatile(GOLDEN)


def test_a1_3_two_components_backend_in_docker(profile):
    profile = profile()
    comps = {c["id"]: c for c in profile["components"]}
    assert set(comps) == {"root", "backend"}
    assert comps["backend"]["runtime"]["value"] == "docker:api"


def test_a1_4_conventions_survive_merge_commits(profile):
    profile = profile()
    assert profile["conventions"]["branches"]["id_style"] == "mixed"
    assert profile["conventions"]["branches"]["pattern"] == "^(feat|fix)/[A-Za-z0-9-]+$"
    assert profile["conventions"]["commits"]["style"] == "conventional"


def test_a1_5_documentation_drift(profile):
    profile = profile()
    rules = sorted((d["rule"], d["file"]) for d in profile["docs_drift"])
    assert ("D4", "HANDOFF.md") in rules
    assert ("D1", "README.md") in rules
