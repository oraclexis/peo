"""Discovery, components (spec 12, sections 1, 2.1 and 2.2). Small repositories in tmp_path."""

import json
import os
from pathlib import Path

import pytest

from peo.discovery import discover
from peo.runner import Result


def no_git(args, cwd):
    return Result(128, b"", b"not a git repository")


def nothing_on_path(name):
    return None


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            content = json.dumps(content)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)


def lines(n: int) -> str:
    return "".join(f"// line {i}\n\n" for i in range(1, n + 1))  # blank lines never count


def disc(root: Path, **kw) -> dict:
    kw.setdefault("run", no_git)
    kw.setdefault("which", nothing_on_path)
    return discover(root, **kw)


def comps(profile: dict) -> dict:
    return {c["id"]: c for c in profile["components"]}


VUE = {"dependencies": {"vue": "^3.5.0"}}
LARAVEL = {"require": {"php": "^8.2", "laravel/framework": "^11.9"}}


def test_single_manifest_at_root(tmp_path):
    write(tmp_path, {"package.json": VUE})
    p = disc(tmp_path)
    assert [c["id"] for c in p["components"]] == ["root"]
    root = p["components"][0]
    assert root["path"] == "."
    assert root["ecosystems"] == ["node"]
    assert root["stacks"] == [{"id": "vue", "version": "3", "confidence": "fact",
                               "evidence": "package.json: vue"}]
    assert p["monorepo"] is False and p["multi_component"] is False
    assert p["schema"] == 1


def test_manifest_without_dependency_or_script_opens_no_component(tmp_path):
    write(tmp_path, {"package.json": {"name": "x"}, "src/a.ts": lines(60)})
    root = disc(tmp_path)["components"]
    assert [c["id"] for c in root] == ["root"]
    assert root[0]["ecosystems"] == [] and root[0]["stacks"] == []
    assert root[0]["kind"] == "library"
    assert root[0]["languages"] == ["typescript"]
    assert root[0]["runtime"] == {"value": "host", "confidence": "unknown", "evidence": "no manifest"}


def test_composer_platform_packages_are_not_dependencies(tmp_path):
    write(tmp_path, {"composer.json": {"require": {"php": "^8.2", "ext-json": "*"}}})
    assert disc(tmp_path)["components"][0]["ecosystems"] == []


def test_go_mod_without_require_is_a_component(tmp_path):
    write(tmp_path, {"go.mod": "module example.test/x\n\ngo 1.22\n"})
    root = disc(tmp_path)["components"][0]
    assert root["ecosystems"] == ["go"]
    assert root["stacks"] == [{"id": "go", "confidence": "fact", "evidence": "go.mod"}]


def test_workspaces_root_manifest_opens_no_component(tmp_path):
    write(tmp_path, {"package.json": {"workspaces": ["apps/*"], "devDependencies": {"turbo": "^2"}},
                     "apps/web/package.json": VUE,
                     "apps/api/package.json": {"dependencies": {"express": "^4.19.0"}}})
    p = disc(tmp_path)
    assert [c["id"] for c in p["components"]] == ["apps-api", "apps-web"]
    assert comps(p)["apps-web"]["path"] == "apps/web"
    assert p["monorepo"] is True and p["multi_component"] is True


def test_pnpm_workspace(tmp_path):
    write(tmp_path, {"package.json": {"scripts": {"build": "turbo run build"}},
                     "pnpm-workspace.yaml": "packages:\n  - 'apps/*'\n",
                     "apps/web/package.json": VUE,
                     "apps/api/package.json": {"dependencies": {"express": "^4.19.0"}}})
    p = disc(tmp_path)
    assert [c["id"] for c in p["components"]] == ["apps-api", "apps-web"]
    assert p["monorepo"] is True


def test_two_components_without_workspace_tool(tmp_path):
    write(tmp_path, {"package.json": VUE, "backend/composer.json": LARAVEL})
    p = disc(tmp_path)
    assert [c["id"] for c in p["components"]] == ["root", "backend"]
    assert p["monorepo"] is False and p["multi_component"] is True


def test_depth_and_excluded_directories(tmp_path):
    write(tmp_path, {"a/b/c/package.json": VUE, "a/b/c/d/package.json": VUE,
                     "node_modules/x/package.json": VUE})
    assert [c["id"] for c in disc(tmp_path)["components"]] == ["a-b-c"]


def test_large_and_binary_manifests_are_ignored(tmp_path):
    big = {"dependencies": {"vue": "^3.5.0"}, "padding": "x" * (1024 * 1024)}
    write(tmp_path, {"package.json": big, "backend/composer.json": b"\x00" + json.dumps(LARAVEL).encode()})
    assert disc(tmp_path)["components"][0]["ecosystems"] == []


def test_unreadable_manifest_warns(tmp_path):
    write(tmp_path, {"package.json": "{not json"})
    warnings: list = []
    p = disc(tmp_path, warnings=warnings)
    assert p["components"][0]["ecosystems"] == []
    assert [(w["code"], w["path"]) for w in warnings] == [("W_MANIFEST_UNREADABLE", "package.json")]


def test_two_manifests_in_one_directory_make_one_component(tmp_path):
    write(tmp_path, {"package.json": VUE, "composer.json": LARAVEL})
    p = disc(tmp_path)
    assert [c["id"] for c in p["components"]] == ["root"]
    assert p["components"][0]["ecosystems"] == ["node", "php"]


def test_nested_component_is_excluded_from_parent_paths(tmp_path):
    write(tmp_path, {"package.json": VUE, "src/App.vue": lines(60),
                     "backend/composer.json": LARAVEL, "backend/app/User.php": lines(60)})
    c = comps(disc(tmp_path))
    assert c["root"]["paths"]["code"] == ["**/*.vue", "!backend/**"]
    assert c["root"]["languages"] == ["typescript"]
    assert c["backend"]["paths"]["code"] == ["backend/**/*.php"]
    assert c["backend"]["languages"] == ["php"]


@pytest.mark.parametrize("constraint, version", [
    ("^4.1.0", "4"), ("~3.5", "3"), ("3.x", "3"), ("3.*", "3"), ("3", "3"), ("3.5.1", "3"),
    (">=3 <5", None), ("*", None), ("dev-main", None), ("^3 || ^4", None), ("latest", None),
])
def test_framework_version(tmp_path, constraint, version):
    write(tmp_path, {"package.json": {"dependencies": {"vue": constraint}}})
    stack = disc(tmp_path)["components"][0]["stacks"][0]
    assert stack.get("version") == version


def test_tool_stacks_have_no_version_and_sorted_evidence(tmp_path):
    write(tmp_path, {"package.json": {"devDependencies": {"vue-tsc": "^2.1.0", "typescript": "^5.6.0"}}})
    stack = disc(tmp_path)["components"][0]["stacks"][0]
    assert stack == {"id": "typescript", "confidence": "fact", "evidence": "package.json: typescript, vue-tsc"}


def test_language_threshold_counts_non_empty_lines(tmp_path):
    write(tmp_path, {"package.json": VUE, "a.ts": lines(49)})
    assert disc(tmp_path)["components"][0]["languages"] == []
    write(tmp_path, {"b.ts": lines(1)})
    assert disc(tmp_path)["components"][0]["languages"] == ["typescript"]


def test_language_and_pattern_order(tmp_path):
    write(tmp_path, {"package.json": VUE, "a.css": lines(60), "b.ts": lines(60)})
    root = disc(tmp_path)["components"][0]
    assert root["languages"] == ["typescript", "css"]
    assert root["paths"]["code"] == ["**/*.ts", "**/*.css"]


@pytest.mark.parametrize("deps, kind", [
    ({"vue": "^3.5.0"}, "frontend"),
    ({"nuxt": "^4.1.0", "express": "^4.19.0"}, "fullstack"),
    ({"typescript": "^5.6.0"}, "library"),
])
def test_node_kind(tmp_path, deps, kind):
    write(tmp_path, {"package.json": {"dependencies": deps}})
    assert disc(tmp_path)["components"][0]["kind"] == kind


def test_backend_kind(tmp_path):
    write(tmp_path, {"composer.json": LARAVEL})
    assert disc(tmp_path)["components"][0]["kind"] == "backend"


def test_python_dependencies(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "x"\ndependencies = ["FastAPI>=0.110", "Django==5.0"]\n'
                                       '[dependency-groups]\ndev = ["pytest>=8"]\n'})
    stacks = disc(tmp_path)["components"][0]["stacks"]
    assert [s["id"] for s in stacks] == ["django", "fastapi", "pytest"]
    assert stacks[0]["version"] == "5"       # "==5.0": exact pin, univocal
    assert "version" not in stacks[1]        # ">=0.110": range
    assert stacks[0]["evidence"] == "pyproject.toml: django"


def test_git_mode_reads_tracked_files_only(tmp_path):
    write(tmp_path, {"package.json": VUE, "backend/composer.json": LARAVEL})
    calls = []

    def git(args, cwd):
        calls.append(list(args))
        if list(args) == ["git", "ls-files", "-z"]:
            return Result(0, b"package.json\x00", b"")
        return Result(128, b"", b"")

    p = disc(tmp_path, run=git)
    assert [c["id"] for c in p["components"]] == ["root"]
    assert calls[0] == ["git", "ls-files", "-z"]


def test_symlink_outside_root_is_ignored(tmp_path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside") / "package.json"
    outside.write_text(json.dumps(VUE))
    os.symlink(outside, tmp_path / "package.json")
    assert disc(tmp_path)["components"][0]["ecosystems"] == []


# --- US3: deterministic, no side effect, commands only through the runner (spec 003) ---------

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "fx-split-stack"


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    import subprocess
    target = tmp_path_factory.mktemp("fx3") / "split-stack"
    subprocess.run(["bash", str(FIXTURE / "build.sh"), str(target)], check=True, capture_output=True)
    return target


def snapshot(root: Path) -> list:
    return sorted((p.relative_to(root).as_posix(), p.stat().st_mtime_ns)
                  for p in root.rglob("*") if ".git" not in p.parts)


def test_determinism(fx):
    first = json.dumps(discover(fx, which=nothing_on_path), sort_keys=True)
    assert json.dumps(discover(fx, which=nothing_on_path), sort_keys=True) == first


def test_no_side_effect(fx):
    before = snapshot(fx)
    discover(fx)
    assert snapshot(fx) == before


def test_runner_calls(fx):
    from peo.runner import run
    calls = []

    def recording(args, cwd):
        assert isinstance(args, list)
        calls.append(args)
        return run(args, cwd)

    discover(fx, run=recording)
    assert calls[0] == ["git", "ls-files", "-z"]
    assert all(c[0] == "git" for c in calls)


def test_which_never_executes(fx):
    asked, calls = [], []

    def which(name):
        asked.append(name)
        return None

    def recording(args, cwd):
        calls.append(args)
        return Result(0, b"package.json\x00backend/composer.json\x00docker-compose.yml\x00", b"")

    discover(fx, run=recording, which=which)
    assert set(asked) == {"node", "php"}
    assert all(c[0] == "git" for c in calls)


def test_no_network(fx, monkeypatch):
    import socket

    def refuse(*args, **kwargs):
        raise OSError("network access during discover")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert len(discover(fx)["components"]) == 2
