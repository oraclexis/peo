"""Generator of fx-large (spec 16, section 1), shared by A1.7 and A14.10.

100 000 tracked lines of code; since R3 also an untracked backend/.env with fake values, a
docker-compose.yml with a database, a CI workflow and a .claude/settings.json with a deny rule.
"""

import json
import os
import subprocess
from pathlib import Path

FAKE_ENV = "APP_KEY=fixture-not-a-secret\nDB_PASSWORD=fixture-not-a-secret\n"
EXTENSIONS = ("ts", "vue", "php", "py")


def build_large(target: Path) -> Path:
    (target / "package.json").write_text('{"name": "fx-large", "version": "1.0.0"}\n')
    body = "".join(f"// line {n}\n" for n in range(100))
    for i in range(1000):
        d = target / "src" / f"m{i // 100}"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"f{i}.{EXTENSIONS[i % 4]}").write_text(body)
    (target / ".github" / "workflows").mkdir(parents=True)
    (target / ".github" / "workflows" / "ci.yml").write_text(
        "name: ci\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: npm test\n")
    (target / "docker-compose.yml").write_text("services:\n  db:\n    image: postgres:16\n")
    (target / ".claude").mkdir()
    (target / ".claude" / "settings.json").write_text(
        json.dumps({"permissions": {"deny": ["Read(./backend/.env)"]}}))
    env = {k: v for k, v in os.environ.items()
           if k not in {"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_CONFIG_COUNT",
                        "GIT_CONFIG_PARAMETERS"}}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1",
               GIT_AUTHOR_NAME="Fixture Author", GIT_COMMITTER_NAME="Fixture Author",
               GIT_AUTHOR_EMAIL="author@example.test", GIT_COMMITTER_EMAIL="author@example.test",
               GIT_AUTHOR_DATE="@1772438400 +0000", GIT_COMMITTER_DATE="@1772438400 +0000")
    git = ["git", "-C", str(target), "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "feat: large"]):
        subprocess.run(git + args, check=True, capture_output=True, env=env)
    (target / "backend").mkdir()
    (target / "backend" / ".env").write_text(FAKE_ENV)   # after the commit: untracked
    return target
