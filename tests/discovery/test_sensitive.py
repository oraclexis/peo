"""Discovery, sensitive surfaces (spec 12, section 7 bis) and the no-value rule (NF14, A14.2)."""

import json
import secrets
from pathlib import Path

import pytest

from peo.discovery import discover
from peo.discovery.compose import read_services
from peo.runner import Result


def no_git(args, cwd):
    return Result(128, b"", b"")


def tracked(*paths):
    listing = "".join(f"{p}\0" for p in paths).encode()

    def run(args, cwd):
        return Result(0, listing, b"") if list(args) == ["git", "ls-files", "-z"] else Result(128, b"", b"")
    return run


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(json.dumps(content) if isinstance(content, dict) else content)


def sensitive(root: Path, run=no_git, warnings=None) -> dict:
    return discover(root, run=run, which=lambda name: None, warnings=warnings)["sensitive"]


def test_sens_env_names_only(tmp_path):
    write(tmp_path, {".env": "A=1\nexport B=2\n# C=3\n\n1BAD=x\nnoequal\n"})
    assert sensitive(tmp_path)["secret_files"] == [{"path": ".env", "tracked": False, "variables": ["A", "B"]}]


def test_sens_env_variables_sorted_unique(tmp_path):
    write(tmp_path, {".env": "Z=1\nA=2\nZ=3\n"})
    assert sensitive(tmp_path)["secret_files"][0]["variables"] == ["A", "Z"]


def test_sens_env_200_names_max(tmp_path):
    names = [f"V{i:03}" for i in range(201)]
    write(tmp_path, {".env": "".join(f"{n}=x\n" for n in reversed(names))})
    got = sensitive(tmp_path)["secret_files"][0]["variables"]
    assert len(got) == 200 and "V000" not in got        # V000 is the 201st line of the file


@pytest.mark.parametrize("name", [".env.example", ".env.sample", ".env.template", ".env.dist"])
def test_a1_8_env_examples_are_not_secret_files(tmp_path, name):
    write(tmp_path, {name: "A=1\n"})
    assert sensitive(tmp_path)["secret_files"] == []


def test_sens_other_secret_patterns(tmp_path):
    names = ["a.pem", "b.key", "c.p12", "d.pfx", "credentials-x.json", "id_rsa", "id_ed25519.pub"]
    write(tmp_path, {n: "x" for n in names})
    got = sensitive(tmp_path)["secret_files"]
    assert [f["path"] for f in got] == sorted(names)
    assert all(f["variables"] == [] for f in got)


def test_sens_untracked_found(tmp_path):
    write(tmp_path, {"README.md": "x\n", "backend/.env": "A=1\n"})
    got = sensitive(tmp_path, run=tracked("README.md"))["secret_files"]
    assert got == [{"path": "backend/.env", "tracked": False, "variables": ["A"]}]


def test_sens_tracked_true(tmp_path):
    write(tmp_path, {".env": "A=1\n"})
    assert sensitive(tmp_path, run=tracked(".env"))["secret_files"][0]["tracked"] is True


def test_sens_depth_3_max(tmp_path):
    write(tmp_path, {"a/b/c/.env": "A=1\n", "a/b/c/d/.env": "B=1\n"})
    assert [f["path"] for f in sensitive(tmp_path)["secret_files"]] == ["a/b/c/.env"]


def test_sens_exclusions_are_discovery_exclusions():
    import peo.discovery
    import peo.discovery.sensitive
    assert peo.discovery.EXCLUDED is peo.discovery.sensitive.EXCLUDED


def test_sens_excluded_dirs(tmp_path):
    write(tmp_path, {"node_modules/x/.env": "A=1\n", "vendor/.env": "B=1\n", ".peo/.env": "C=1\n"})
    assert sensitive(tmp_path)["secret_files"] == []


COMPOSE = """services:
  web:
    image: nginx:1.27
  db:
    image: docker.io/library/postgres:16
  geo:
    image: postgis/postgis:16-3.4
  docs:
    image: "mongo:7"
  cache:
    image: valkey/valkey:8
  sql:
    image: mcr.microsoft.com/mssql/server:2022-latest
"""


def test_sens_data_stores(tmp_path):
    write(tmp_path, {"docker-compose.yml": COMPOSE, "compose.yaml": "services:\n  a:\n    image: mysql:8\n"})
    assert sensitive(tmp_path)["data_stores"] == [
        {"kind": "mysql", "source": "compose.yaml", "service": "a"},
        {"kind": "redis", "source": "docker-compose.yml", "service": "cache"},
        {"kind": "postgres", "source": "docker-compose.yml", "service": "db"},
        {"kind": "mongodb", "source": "docker-compose.yml", "service": "docs"},
        {"kind": "postgres", "source": "docker-compose.yml", "service": "geo"},
        {"kind": "sqlserver", "source": "docker-compose.yml", "service": "sql"},
    ]


def test_sens_data_dumps(tmp_path):
    write(tmp_path, {"dump.sql": "x" * 10, "data/app.sqlite": "y",
                     "database/migrations/x.sql": "z", "migrations/y.sql": "z"})
    assert sensitive(tmp_path)["data_dumps"] == [{"path": "data/app.sqlite", "tracked": False, "bytes": 1},
                                                 {"path": "dump.sql", "tracked": False, "bytes": 10}]


def test_sens_log_dirs(tmp_path):
    write(tmp_path, {"logs/a.log": "x", "api/log/x": "x", "storage/logs/b.log": "x"})
    assert sensitive(tmp_path, run=tracked("logs/a.log"))["log_dirs"] == [
        {"path": "api/log", "tracked": False}, {"path": "logs", "tracked": True},
        {"path": "storage/logs", "tracked": False}]


def test_sens_log_file_at_root_is_not_a_log_dir(tmp_path):
    write(tmp_path, {"app.log": "x", "backend/worker.log": "x"})
    assert sensitive(tmp_path)["log_dirs"] == []


def test_sens_binary_env(tmp_path):
    marker = secrets.token_hex(16)
    write(tmp_path, {".env": b"\x00A=" + marker.encode()})
    warnings: list = []
    got = sensitive(tmp_path, warnings=warnings)["secret_files"]
    assert got == [{"path": ".env", "tracked": False, "variables": []}]
    assert marker not in json.dumps(warnings)


def test_a14_2_discover_no_value(tmp_path):
    decoys = [secrets.token_hex(16) for _ in range(3)]
    write(tmp_path, {"package.json": {"dependencies": {"vue": "^3.5.0"}},
                     "backend/.env": f"APP_KEY={decoys[0]}\nexport DB_PASSWORD='{decoys[1]}'\n#OLD={decoys[2]}\n"})
    warnings: list = []
    profile = discover(tmp_path, run=no_git, which=lambda name: None, warnings=warnings)
    dumped = json.dumps(profile) + json.dumps(warnings)
    assert not [d for d in decoys if d in dumped]
    assert profile["sensitive"]["secret_files"][0]["variables"] == ["APP_KEY", "DB_PASSWORD"]


def test_a1_8_compose_environment_never_read(tmp_path):
    decoy = secrets.token_hex(16)
    compose = f"services:\n  db:\n    image: postgres:16\n    environment:\n      POSTGRES_PASSWORD: {decoy}\n"
    write(tmp_path, {"docker-compose.yml": compose})
    profile = discover(tmp_path, run=no_git, which=lambda name: None)
    assert decoy not in json.dumps(profile)
    assert decoy not in repr(read_services(tmp_path, ["docker-compose.yml"]))
