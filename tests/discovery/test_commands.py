"""Discovery, commands per component and verify (spec 12, section 3)."""

import json
from pathlib import Path

import pytest
from peo.discovery.commands import is_test_file, makefile_targets

from peo.discovery import discover
from peo.runner import Result


def no_git(args, cwd):
    return Result(128, b"", b"")


def on_path(*names):
    return lambda name: f"/usr/bin/{name}" if name in names else None


def write(root: Path, files: dict) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)


HOST = on_path("node", "php", "python3")


def profile(root: Path, which=HOST) -> dict:
    return discover(root, run=no_git, which=which)


def commands(root: Path, component: str = "root", **kw) -> dict:
    return {c["id"]: c for c in profile(root, **kw)["components"]}[component]["commands"]


def fact(value, evidence):
    return {"value": value, "confidence": "fact", "evidence": evidence}


NPM = {"scripts": {"test": "vitest run", "typecheck": "nuxt typecheck", "test:e2e": "playwright test",
                   "build": "nuxt build", "dev": "nuxt dev"},
       "dependencies": {"vue": "^3.5.0"}}
LARAVEL = {"require": {"laravel/framework": "^11.9"}, "require-dev": {"phpunit/phpunit": "^11.0"}}
VUE = {"dependencies": {"vue": "^3.5.0"}}


def test_cmd_npm_scripts(tmp_path):
    write(tmp_path, {"package.json": NPM})
    c = commands(tmp_path)
    assert c["test"] == fact("npm test", "package.json scripts.test")
    assert c["typecheck"] == fact("npm run typecheck", "package.json scripts.typecheck")
    assert c["e2e"] == fact("npm run test:e2e", "package.json scripts.test:e2e")
    assert c["build"] == fact("npm run build", "package.json scripts.build")
    assert "dev" not in c


def test_cmd_type_check_and_e2e_aliases(tmp_path):
    write(tmp_path, {"package.json": {"scripts": {"type-check": "tsc", "e2e": "playwright test"}}})
    c = commands(tmp_path)
    assert c["typecheck"]["value"] == "npm run type-check"
    assert c["e2e"]["value"] == "npm run e2e"


@pytest.mark.parametrize("lockfile, test, build", [("pnpm-lock.yaml", "pnpm test", "pnpm run build"),
                                                   ("yarn.lock", "yarn test", "yarn run build")])
def test_cmd_package_manager_from_lockfile(tmp_path, lockfile, test, build):
    write(tmp_path, {"package.json": NPM, lockfile: ""})
    c = commands(tmp_path)
    assert (c["test"]["value"], c["build"]["value"]) == (test, build)


def test_cmd_npm_placeholder_test_ignored(tmp_path):
    write(tmp_path, {"package.json": {"scripts": {"test": 'echo "Error: no test specified" && exit 1'}}})
    assert commands(tmp_path)["test"]["value"] is None


def test_cmd_composer_script(tmp_path):
    write(tmp_path, {"composer.json": {"require": {"laravel/framework": "^11.9"}, "scripts": {"test": "phpunit"}}})
    assert commands(tmp_path)["test"] == fact("composer test", "composer.json scripts.test")


def test_cmd_makefile_target(tmp_path):
    write(tmp_path, {"package.json": VUE, "Makefile": ".PHONY: lint\nFOO := 1\nlint:\n\techo lint\n.hidden:\n"})
    assert commands(tmp_path)["lint"] == fact("make lint", "Makefile target lint")


def test_makefile_targets_syntax():
    assert makefile_targets(".PHONY: a b\nFOO := 1\nBAR ?= 2\na: b\nb:\n.x:\nc.d-e_f: \n") == ["a", "b", "c.d-e_f"]


def test_cmd_script_before_makefile(tmp_path):
    write(tmp_path, {"package.json": {"scripts": {"lint": "eslint ."}}, "Makefile": "lint:\n\ttrue\n"})
    assert commands(tmp_path)["lint"]["value"] == "npm run lint"


@pytest.mark.parametrize("framework, stack", [("phpunit/phpunit", "phpunit"), ("pestphp/pest", "pest")])
def test_cmd_artisan_fallback(tmp_path, framework, stack):
    write(tmp_path, {"composer.json": {"require": {"laravel/framework": "^11.9"}, "require-dev": {framework: "*"}},
                     "artisan": "#!/usr/bin/env php\n"})
    assert commands(tmp_path)["test"] == {"value": "php artisan test", "confidence": "likely",
                                          "evidence": f"{stack} declared, artisan present, no test script"}


def test_cmd_pytest_fallback(tmp_path):
    write(tmp_path, {"pyproject.toml": '[project]\nname = "x"\ndependencies = ["pytest>=8"]\n'})
    assert commands(tmp_path)["test"] == {"value": "pytest", "confidence": "likely",
                                          "evidence": "pytest declared, no test script"}


@pytest.mark.parametrize("files, value, stack", [
    ({"composer.json": {"require-dev": {"phpstan/phpstan": "*", "laravel/pint": "*"}}},
     "vendor/bin/pint --test", "pint"),
    ({"composer.json": {"require-dev": {"phpstan/phpstan": "*"}}}, "vendor/bin/phpstan analyse", "phpstan"),
    ({"package.json": {"devDependencies": {"eslint": "^9"}}}, "npx eslint .", "eslint"),
    ({"pyproject.toml": '[project]\nname = "x"\ndependencies = ["ruff"]\n'}, "ruff check .", "ruff"),
])
def test_cmd_lint_fallback_order(tmp_path, files, value, stack):
    write(tmp_path, files)
    assert commands(tmp_path)["lint"] == {"value": value, "confidence": "likely",
                                          "evidence": f"{stack} declared"}


@pytest.mark.parametrize("files, lint_evidence", [
    ({"package.json": VUE}, "no eslint, no lint script"),
    ({"composer.json": {"require": {"laravel/framework": "^11.9"}}}, "no pint/phpstan, no lint script"),
    ({"go.mod": "module example.test/x\n"}, "no lint script"),
    ({"README.md": "x"}, "no lint script"),
])
def test_cmd_test_and_lint_always_present(tmp_path, files, lint_evidence):
    write(tmp_path, files)
    c = commands(tmp_path)
    assert c["test"] == {"value": None, "confidence": "unknown",
                         "evidence": "no test script, no test framework declared"}
    assert c["lint"] == {"value": None, "confidence": "unknown", "evidence": lint_evidence}


def test_cmd_other_roles_only_with_source(tmp_path):
    write(tmp_path, {"package.json": VUE})
    assert set(commands(tmp_path)) == {"test", "lint"}


COMPOSE = "services:\n  api:\n    build: ./backend\n  web:\n    build: .\n"


def test_cmd_docker_prefix(tmp_path):
    write(tmp_path, {"backend/composer.json": LARAVEL, "backend/artisan": "", "docker-compose.yml": COMPOSE})
    assert commands(tmp_path, "backend", which=on_path())["test"]["value"] == \
        "docker compose exec -T api php artisan test"


def test_cmd_root_makefile_never_prefixed(tmp_path):
    write(tmp_path, {"package.json": VUE, "Makefile": "lint:\n\ttrue\n", "docker-compose.yml": COMPOSE})
    p = profile(tmp_path, which=on_path())
    root = p["components"][0]
    assert root["runtime"]["value"] == "docker:web"
    assert root["commands"]["lint"]["value"] == "make lint"


def test_cmd_unknown_runtime_no_prefix(tmp_path):
    write(tmp_path, {"composer.json": {"require": {"laravel/framework": "^11.9"}, "scripts": {"test": "phpunit"}}})
    c = commands(tmp_path, which=on_path())
    assert c["test"]["value"] == "composer test"


@pytest.mark.parametrize("files, verify", [
    ({"Makefile": "verify:\n\ttrue\n"}, fact("make verify", "Makefile target verify")),
    ({"Makefile": "check:\n\ttrue\n"}, fact("make check", "Makefile target check")),
    ({"package.json": {"scripts": {"verify": "npm test"}}}, fact("npm run verify", "package.json scripts.verify")),
    ({"Makefile": "up:\n\ttrue\n"},
     {"value": None, "confidence": "unknown", "evidence": "no verify/check target in Makefile"}),
    ({}, {"value": None, "confidence": "unknown", "evidence": "no Makefile, no verify script"}),
])
def test_cmd_verify(tmp_path, files, verify):
    write(tmp_path, {"package.json": VUE, **files})
    write(tmp_path, {"docker-compose.yml": COMPOSE})
    assert profile(tmp_path, which=on_path())["commands"] == {"verify": verify}


@pytest.mark.parametrize("rel, expected", [
    ("e2e/smoke.spec.ts", True), ("src/a.test.js", True), ("tests/Feature/X.php", True),
    ("test/format.spec.ts", True), ("pkg/test_x.py", True), ("pkg/x_test.py", True), ("x_test.go", True),
    ("app/FooTest.php", True), ("src/__tests__/a.js", True), ("spec/a_spec.rb", True),
    ("src/app.ts", False), ("src/latest.ts", False), ("contest/a.ts", False),
])
def test_cmd_test_files(rel, expected):
    assert is_test_file(rel) is expected
