#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_ROOT="$(mktemp -d)"
PASS_COUNT=0

cleanup() {
  rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

assert_path_exists() {
  local path="$1"
  if [[ ! -e "$path" && ! -L "$path" ]]; then
    printf 'FAIL: expected path to exist: %s\n' "$path" >&2
    exit 1
  fi
  PASS_COUNT=$((PASS_COUNT + 1))
}

assert_path_missing() {
  local path="$1"
  if [[ -e "$path" || -L "$path" ]]; then
    printf 'FAIL: expected path to be missing: %s\n' "$path" >&2
    exit 1
  fi
  PASS_COUNT=$((PASS_COUNT + 1))
}

assert_is_symlink_to() {
  local link_path="$1"
  local expected_target="$2"

  if [[ ! -L "$link_path" ]]; then
    printf 'FAIL: expected symlink: %s\n' "$link_path" >&2
    exit 1
  fi

  local actual_target
  actual_target="$(readlink "$link_path")"
  if [[ "$actual_target" != "$expected_target" ]]; then
    printf 'FAIL: symlink target mismatch for %s\n' "$link_path" >&2
    printf 'Expected: %s\n' "$expected_target" >&2
    printf 'Actual:   %s\n' "$actual_target" >&2
    exit 1
  fi

  PASS_COUNT=$((PASS_COUNT + 1))
}

assert_contains() {
  local file="$1"
  local expected="$2"
  if ! grep -Fq -- "$expected" "$file"; then
    printf 'FAIL: expected text not found in %s\n' "$file" >&2
    printf 'Expected: %s\n' "$expected" >&2
    exit 1
  fi
  PASS_COUNT=$((PASS_COUNT + 1))
}

assert_command_fails() {
  local cwd="$1"
  shift
  if (cd "$cwd" && bash "$@" >/dev/null 2>&1); then
    printf 'FAIL: expected command to fail: %s\n' "$*" >&2
    exit 1
  fi
  PASS_COUNT=$((PASS_COUNT + 1))
}

run_install() {
  local cwd="$1"
  shift
  (cd "$cwd" && bash "$@")
}

printf 'Running installer regression tests ...\n'

SOURCE_SKILL_DIR="$ROOT_DIR/skill-creator"

# Case 1: project install creates a symlink to local clone source.
case1_dir="$TMP_ROOT/case1-project"
mkdir -p "$case1_dir"
run_install "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case1_dir" --clone-dir "$ROOT_DIR"

assert_is_symlink_to "$case1_dir/.opencode/skills/skill-creator" "$SOURCE_SKILL_DIR"
assert_path_exists "$case1_dir/.opencode/skills/skill-creator/SKILL.md"

# Case 2: install fails when target exists and is not the expected symlink.
case2_dir="$TMP_ROOT/case2-project"
mkdir -p "$case2_dir"
run_install "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case2_dir" --clone-dir "$ROOT_DIR"
rm -f "$case2_dir/.opencode/skills/skill-creator"
mkdir -p "$case2_dir/.opencode/skills/skill-creator"
printf 'local file\n' >"$case2_dir/.opencode/skills/skill-creator/custom.txt"
assert_command_fails "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case2_dir" --clone-dir "$ROOT_DIR"

# Case 3: --force replaces existing target.
run_install "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case2_dir" --clone-dir "$ROOT_DIR" --force
assert_is_symlink_to "$case2_dir/.opencode/skills/skill-creator" "$SOURCE_SKILL_DIR"

# Case 4: --clean removes backup path and relinks.
case4_dir="$TMP_ROOT/case4-project"
case4_backup="$case4_dir/.opencode-install-backups/skills/skill-creator"
mkdir -p "$case4_backup"
printf 'old backup\n' >"$case4_backup/old.txt"
run_install "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case4_dir" --clone-dir "$ROOT_DIR"
run_install "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case4_dir" --clone-dir "$ROOT_DIR" --clean

assert_is_symlink_to "$case4_dir/.opencode/skills/skill-creator" "$SOURCE_SKILL_DIR"
assert_path_missing "$case4_backup"

# Case 5: dry-run with missing clone path reports planned clone/link work.
case5_dir="$TMP_ROOT/case5-project"
case5_out="$TMP_ROOT/case5.out"
case5_clone="$TMP_ROOT/case5-clone"
mkdir -p "$case5_dir"
run_install "$ROOT_DIR" "$ROOT_DIR/install.sh" --scope project --project-dir "$case5_dir" --clone-dir "$case5_clone" --dry-run --no-prompt >"$case5_out"

assert_contains "$case5_out" "[dry-run] Would clone https://github.com/feddericovonwernich/opencode-skill-creator.git -> $case5_clone"
assert_contains "$case5_out" "[dry-run] Would link $case5_clone/skill-creator -> $case5_dir/.opencode/skills/skill-creator"

printf 'PASS: %d installer checks\n' "$PASS_COUNT"
