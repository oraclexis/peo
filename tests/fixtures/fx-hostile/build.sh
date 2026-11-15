#!/usr/bin/env bash
# Rebuild the fx-hostile fixture repository in TARGET (spec 16, section 1).
#
# tree/ is committed once; then the names git cannot store are created, untracked: a folder
# whose name holds a newline and ESC with a .env inside, outbound symbolic links (a .env whose
# target is outside the repository, a folder link and a `..` link). Deterministic: the machine's
# git configuration is ignored and identity and dates are fixed. Compatible with bash 3.2.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: build.sh TARGET" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
target=$1
if [ -e "$target" ] && [ -n "$(ls -A "$target")" ]; then
  echo "build.sh: $target exists and is not empty" >&2
  exit 1
fi
mkdir -p "$target"
target=$(cd "$target" && pwd)

unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 LC_ALL=C TZ=UTC
export GIT_AUTHOR_NAME="Fixture Author" GIT_AUTHOR_EMAIL="author@example.test"
export GIT_COMMITTER_NAME="Fixture Author" GIT_COMMITTER_EMAIL="author@example.test"
export GIT_AUTHOR_DATE="@1772438400 +0000" GIT_COMMITTER_DATE="@1772438400 +0000"

g() {
  git -C "$target" -c commit.gpgsign=false -c core.hooksPath=/dev/null \
    -c core.excludesFile=/dev/null "$@"
}

git init -q --template= -b main "$target"
cp -R "$here/tree/." "$target/"
g add -f -A
g commit -q --no-verify -m "chore: hostile fixture"

# Untracked, created here: git cannot hold these names or links portably.
hostile=$'bad\n\033dir'
mkdir -p "$target/$hostile"
printf 'HOSTILE_NAME=fixture-not-a-secret\n' > "$target/$hostile/.env"
ln -s /nonexistent-peo-outside/secret.env "$target/.env"
ln -s /nonexistent-peo-outside "$target/outside-dir"
ln -s .. "$target/up"
ln -s ../../escape.env "$target/escape.env"
