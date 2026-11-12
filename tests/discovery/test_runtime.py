"""Discovery, runtime per component and compose reading (spec 12, section 2.3)."""

import json
from pathlib import Path

import pytest

from peo.discovery import discover
from peo.discovery.compose import Service, read_services
from peo.runner import Result

LARAVEL = {"require": {"laravel/framework": "^11.9"}}
VUE = {"dependencies": {"vue": "^3.5.0"}}


def no_git(args, cwd):
    return Result(128, b"", b"")


def on_path(*names):
    return lambda name: f"/usr/bin/{name}" if name in names else None


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)


def runtime_of(root: Path, component: str, which) -> dict:
    profile = discover(root, run=no_git, which=which)
    return {c["id"]: c for c in profile["components"]}[component]["runtime"]


COMPOSE = """\
# local stack
services:
  api:
    build:
      context: ./backend
    volumes:
      - ./backend:/var/www/html
      - type: bind
        source: ./other
        target: /other
    environment:
      DB_PASSWORD: never-read
  db:
    image: postgres:16
x-anchor: &default
  restart: always
"""


def test_read_services_object_build_and_short_volumes(tmp_path):
    write(tmp_path, {"docker-compose.yml": COMPOSE})
    assert read_services(tmp_path, ["docker-compose.yml"]) == [
        Service("docker-compose.yml", "api", "./backend", ["./backend:/var/www/html"], None),
        Service("docker-compose.yml", "db", None, [], "postgres:16"),
    ]


def test_read_services_scalar_build_quotes_and_two_files(tmp_path):
    write(tmp_path, {"compose.yaml": 'services:\n  web:\n    build: "."\n    volumes:\n      - ".:/app"\n',
                     "docker-compose.yml": "services:\n  worker:\n    build: ./worker # comment\n"})
    services = read_services(tmp_path, ["compose.yaml", "docker-compose.yml"])
    assert services == [Service("compose.yaml", "web", ".", [".:/app"], None),
                        Service("docker-compose.yml", "worker", "./worker", [], None)]


def test_read_services_image_quoted(tmp_path):
    write(tmp_path, {"compose.yaml": 'services:\n  cache:\n    image: "redis:7"\n'})
    assert read_services(tmp_path, ["compose.yaml"])[0].image == "redis:7"


def test_environment_is_never_read(tmp_path):
    write(tmp_path, {"docker-compose.yml": COMPOSE})
    assert "never-read" not in repr(read_services(tmp_path, ["docker-compose.yml"]))


@pytest.mark.parametrize("which, value, confidence, evidence", [
    (on_path(), "docker:api", "fact",
     "docker-compose.yml: api build.context ./backend, volume ./backend:/var/www/html; php not on PATH"),
    (on_path("php"), "docker:api", "likely",
     "docker-compose.yml: api build.context ./backend, volume ./backend:/var/www/html; php on PATH"),
])
def test_backend_built_by_a_service(tmp_path, which, value, confidence, evidence):
    write(tmp_path, {"backend/composer.json": LARAVEL, "docker-compose.yml": COMPOSE})
    assert runtime_of(tmp_path, "backend", which) == {"value": value, "confidence": confidence,
                                                      "evidence": evidence}


@pytest.mark.parametrize("which, confidence, word", [(on_path("php"), "fact", "on"),
                                                     (on_path(), "unknown", "not on")])
def test_no_service(tmp_path, which, confidence, word):
    write(tmp_path, {"backend/composer.json": LARAVEL})
    assert runtime_of(tmp_path, "backend", which) == {
        "value": "host", "confidence": confidence,
        "evidence": f"no compose service builds or mounts 'backend'; php {word} PATH"}


def test_node_only_on_host(tmp_path):
    write(tmp_path, {"package.json": VUE})
    assert runtime_of(tmp_path, "root", on_path("node")) == {
        "value": "host", "confidence": "fact", "evidence": "no compose service builds '.'; node on PATH"}
    assert runtime_of(tmp_path, "root", on_path())["confidence"] == "unknown"


def test_node_only_built_by_a_service_without_node(tmp_path):
    write(tmp_path, {"package.json": VUE, "compose.yaml": "services:\n  web:\n    build: .\n"})
    assert runtime_of(tmp_path, "root", on_path()) == {
        "value": "docker:web", "confidence": "fact", "evidence": "compose.yaml: web build.context .; node not on PATH"}


def test_node_only_mounted_is_not_enough(tmp_path):
    write(tmp_path, {"package.json": VUE, "compose.yaml": "services:\n  web:\n    volumes:\n      - .:/app\n"})
    assert runtime_of(tmp_path, "root", on_path())["value"] == "host"


@pytest.mark.parametrize("which, confidence", [(on_path(), "fact"), (on_path("node"), "likely")])
def test_multi_ecosystem_uses_general_rule_and_first_binary(tmp_path, which, confidence):
    write(tmp_path, {"package.json": VUE, "composer.json": LARAVEL,
                     "compose.yaml": "services:\n  app:\n    volumes:\n      - ./:/app\n"})
    rt = runtime_of(tmp_path, "root", which)
    assert (rt["value"], rt["confidence"]) == ("docker:app", confidence)


def test_first_matching_service_in_file_order(tmp_path):
    write(tmp_path, {"backend/composer.json": LARAVEL,
                     "compose.yaml": "services:\n  zeta:\n    build: ./backend\n  alpha:\n    build: ./backend\n"})
    assert runtime_of(tmp_path, "backend", on_path())["value"] == "docker:zeta"
