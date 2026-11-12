"""Discovery, signals, present tools and metrics (spec 12, sections 7 and 7 ter)."""

import json
from pathlib import Path

import pytest

from peo.discovery import discover
from peo.runner import Result


def no_git(args, cwd):
    return Result(128, b"", b"")


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)


def disc(root: Path, run=no_git) -> dict:
    return discover(root, run=run, which=lambda name: None)


def sig(root: Path, name: str) -> dict:
    return disc(root)["signals"][name]


def lines(n: int) -> str:
    return "".join(f"// {i}\n" for i in range(n))


# --- signals (US2) ---------------------------------------------------------------------------

def test_sig_auth_dependency(tmp_path):
    write(tmp_path, {"composer.json": {"require": {"laravel/sanctum": "^4"}}})
    assert sig(tmp_path, "auth") == {"value": True, "confidence": "fact",
                                     "evidence": "composer.json: laravel/sanctum"}


def test_sig_auth_dependency_prefix(tmp_path):
    write(tmp_path, {"package.json": {"dependencies": {"keycloak-js": "^26"}}})
    assert sig(tmp_path, "auth")["evidence"] == "package.json: keycloak-js"


def test_sig_auth_mention(tmp_path):
    write(tmp_path, {"README.md": "# App\nLogin with OIDC later.\n"})
    assert sig(tmp_path, "auth") == {"value": True, "confidence": "likely",
                                     "evidence": "README.md:2 mentions OIDC"}


def test_sig_dependency_before_mention(tmp_path):
    write(tmp_path, {"README.md": "SSO planned\n", "package.json": {"dependencies": {"next-auth": "^4"}}})
    assert sig(tmp_path, "auth")["confidence"] == "fact"


def test_sig_public_surface_code(tmp_path):
    write(tmp_path, {"src/a.vue": "<template>\n  <form @submit=\"x\">\n</template>\n"})
    assert sig(tmp_path, "public_surface") == {"value": True, "confidence": "fact",
                                               "evidence": "src/a.vue:2 contains <form"}


def test_sig_public_surface_first_mention_in_reading_order(tmp_path):
    write(tmp_path, {"README.md": "a\nb\nPage de Contact\nd\nUn formulaire\n", "docs/x.md": "contact\n"})
    assert sig(tmp_path, "public_surface")["evidence"] == "README.md:3 mentions Contact"


@pytest.mark.parametrize("text", ["contacts list", "ssource", "unsso"])
def test_sig_mention_whole_word(tmp_path, text):
    write(tmp_path, {"README.md": text + "\n"})
    assert sig(tmp_path, "auth")["value"] is False
    assert sig(tmp_path, "public_surface")["value"] is False


def test_sig_frontend_heavy_dependency(tmp_path):
    write(tmp_path, {"package.json": {"dependencies": {"three": "^0.169"}}})
    assert sig(tmp_path, "frontend_heavy") == {"value": True, "confidence": "fact",
                                               "evidence": "package.json: three"}


def test_sig_frontend_heavy_41_percent(tmp_path):
    write(tmp_path, {"a.vue": lines(41), "b.ts": lines(59)})
    assert sig(tmp_path, "frontend_heavy") == {"value": True, "confidence": "fact",
                                               "evidence": "41% of code lines in .vue/.tsx/.jsx"}


def test_sig_frontend_heavy_40_percent_is_not(tmp_path):
    write(tmp_path, {"a.vue": lines(40), "b.ts": lines(60)})
    assert sig(tmp_path, "frontend_heavy")["value"] is False


RULES = "# Rules\n- Use color tokens.\n- Spacing scale only.\n- One font.\n- Tests first.\n"


def test_sig_design_rules_3_rules(tmp_path):
    write(tmp_path, {"CLAUDE.md": RULES})
    assert sig(tmp_path, "design_rules_in_instructions") == {
        "value": True, "confidence": "fact", "evidence": "CLAUDE.md: 3 design rules"}


def test_sig_design_rules_2_rules_is_not(tmp_path):
    write(tmp_path, {"CLAUDE.md": "- Use color tokens.\n- One font.\n- Tests first.\n"})
    assert sig(tmp_path, "design_rules_in_instructions")["value"] is False


def test_sig_design_rules_agents_md(tmp_path):
    write(tmp_path, {"AGENTS.md": RULES})
    assert sig(tmp_path, "design_rules_in_instructions")["evidence"] == "AGENTS.md: 3 design rules"


def test_sig_no_indicator(tmp_path):
    write(tmp_path, {"README.md": "Nothing here\n"})
    assert disc(tmp_path)["signals"] == {
        name: {"value": False, "confidence": "fact", "evidence": f"no {name} indicator"}
        for name in ("auth", "public_surface", "frontend_heavy", "design_rules_in_instructions")}


# --- present tools and metrics (US3) ---------------------------------------------------------

def test_present_dev_dependency(tmp_path):
    write(tmp_path, {"package.json": {"devDependencies": {"@playwright/test": "^1.48"}}})
    assert disc(tmp_path)["present_tools"] == [{
        "ref": "cli:playwright", "via": "dev-dependency", "component": "root",
        "evidence": "package.json devDependencies: @playwright/test"}]


def test_present_pip_section(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "x"\ndependencies = ["semgrep>=1"]\n'})
    assert disc(tmp_path)["present_tools"][0]["evidence"] == "pyproject.toml dependencies: semgrep"


def test_present_file(tmp_path):
    write(tmp_path, {".gitleaks.toml": "x\n"})
    assert disc(tmp_path)["present_tools"] == [{"ref": "ci-check:gitleaks", "via": "file",
                                                "evidence": ".gitleaks.toml"}]


def test_present_one_entry_per_tool_and_component(tmp_path):
    write(tmp_path, {"package.json": {"devDependencies": {"@playwright/test": "1", "playwright": "1"}},
                     "e2e/package.json": {"devDependencies": {"playwright": "1"}}})
    got = [(t["ref"], t.get("component")) for t in disc(tmp_path)["present_tools"]]
    assert got == [("cli:playwright", "e2e"), ("cli:playwright", "root")]


def test_present_sorted(tmp_path):
    write(tmp_path, {".serena/project.yml": "x", ".gitleaks.toml": "x"})
    assert [t["ref"] for t in disc(tmp_path)["present_tools"]] == ["ci-check:gitleaks", "mcp:serena"]


def test_metrics_loc_per_extension(tmp_path):
    write(tmp_path, {"a.vue": "a\n\nb\n", "b.ts": "c\n", "README.md": "x\ny\n"})
    m = disc(tmp_path)["metrics"]
    assert m["loc"] == {"ts": 1, "vue": 2} and m["loc_total"] == 3
    assert list(m["loc"]) == sorted(m["loc"])


def test_metrics_outside_git(tmp_path):
    write(tmp_path, {"a.ts": "x\n"})
    m = disc(tmp_path)["metrics"]
    assert (m["commits"], m["contributors"], m["tracked_files"]) == (0, 0, 1)


def test_metrics_contributors(tmp_path):
    write(tmp_path, {"a.ts": "x\n"})

    def run(args, cwd):
        answers = {("git", "ls-files", "-z"): "a.ts\0", ("git", "rev-list", "--count", "HEAD"): "3\n",
                   ("git", "log", "--format=%ae"): "a@x.test\nb@x.test\na@x.test\n"}
        out = answers.get(tuple(args))
        return Result(0, out.encode(), b"") if out else Result(128, b"", b"")

    m = disc(tmp_path, run=run)["metrics"]
    assert (m["commits"], m["contributors"]) == (3, 2)
