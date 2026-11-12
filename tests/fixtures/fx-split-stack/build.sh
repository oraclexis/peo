#!/usr/bin/env bash
# Rebuild the fx-split-stack fixture repository in TARGET (spec 16, section 2.1).
#
# History: one initial commit with every file of tree/ not listed in history.tsv, then for each
# line of history.tsv a branch, one commit adding the listed files, and a --no-ff merge
# "merge: <branch>" into main. Deterministic: the machine's git configuration is ignored and
# identity, dates and file modes are fixed. Compatible with bash 3.2 (macOS).
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: build.sh TARGET" >&2
  exit 2
fi
here=$(cd "$(dirname "$0")" && pwd)
tree="$here/tree"
target=$1
if [ -e "$target" ] && [ -n "$(ls -A "$target")" ]; then
  echo "build.sh: $target exists and is not empty" >&2
  exit 1
fi
mkdir -p "$target"
target=$(cd "$target" && pwd)

# Isolate git from the machine: no global/system config, no env-provided config.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_CONFIG_COUNT GIT_CONFIG_PARAMETERS
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_LITERAL_PATHSPECS=1
export LC_ALL=C TZ=UTC
export GIT_AUTHOR_NAME="Fixture Author" GIT_AUTHOR_EMAIL="author@example.test"
export GIT_COMMITTER_NAME="Fixture Author" GIT_COMMITTER_EMAIL="author@example.test"

g() {
  git -C "$target" -c commit.gpgsign=false -c tag.gpgsign=false -c core.hooksPath=/dev/null \
    -c core.autocrlf=false -c core.excludesFile=/dev/null -c core.attributesFile=/dev/null \
    -c core.fileMode=true "$@"
}

tick=0
stamp() {
  # Fixed origin, one commit every 30 minutes.
  local when=$((1772438400 + tick * 1800))
  export GIT_AUTHOR_DATE="@$when +0000" GIT_COMMITTER_DATE="@$when +0000"
  tick=$((tick + 1))
}

put() {
  local f
  for f in "$@"; do
    case "$f" in */*) mkdir -p "$target/${f%/*}" ;; esac
    cp "$tree/$f" "$target/$f"
  done
  (cd "$target" && chmod 644 "$@")
  g add -f -- "$@"
}

git init -q --template= -b main "$target"

listed=$(cut -f3 "$here/history.tsv" | tr ' ' '\n' | sed '/^$/d' | sort)
initial=$(cd "$tree" && find . -type f | sed 's|^\./||' | sort | comm -23 - <(printf '%s\n' "$listed"))
initial_paths=()
while IFS= read -r f; do
  initial_paths+=("$f")
done <<< "$initial"
put "${initial_paths[@]}"
stamp
g commit -q --no-verify -m "chore: initialisation du projet"

while IFS=$'\t' read -r branch subject files; do
  read -ra paths <<< "$files"
  g switch -q -c "$branch"
  put "${paths[@]}"
  stamp
  g commit -q --no-verify -m "$subject"
  g switch -q main
  stamp
  g merge -q --no-ff --no-verify -m "merge: $branch" "$branch"
done < "$here/history.tsv"
