#!/usr/bin/env bash

set -euo pipefail

SKILL_NAME="skill-creator"
DEFAULT_REPO="feddericovonwernich/opencode-skill-creator"
DEFAULT_REF="main"

SCOPE="project"
PROJECT_DIR=""
CLONE_DIR=""
FORCE=0
CLEAN=0
DRY_RUN=0
NO_PROMPT=0
REPO="${DEFAULT_REPO}"
REF="${DEFAULT_REF}"

SOURCE_SKILL_DIR=""
VALIDATOR=""

usage() {
  cat <<'EOF'
Install the skill-creator OpenCode skill using a git clone + symlink workflow.

Usage:
  bash install.sh [options]

Options:
  --scope <project|user|both>  Install target scope (default: project)
  --project-dir <path>         Project root for project/both scope (default: current directory)
  --clone-dir <path>           Local checkout path (default: prompt or ~/.local/share/opencode/sources/opencode-skill-creator)
  --repo <owner/name>          GitHub repo to clone (default: feddericovonwernich/opencode-skill-creator)
  --ref <git-ref>              Git branch/tag/commit for first clone (default: main)
  --force                      Replace an existing installation target
  --clean                      Remove current install targets and backup folders before linking
  --dry-run                    Show what would happen without making changes
  --no-prompt                  Never prompt; use defaults for omitted values
  -h, --help                   Show this help text

Examples:
  bash install.sh --scope project --project-dir /path/to/project
  bash install.sh --scope both --clone-dir ~/.local/share/opencode/sources/opencode-skill-creator --clean
  curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install.sh | bash -s -- --scope user --clean
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*"
}

require_command() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "Required command not found: ${cmd}"
}

abs_path() {
  python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$1"
}

default_clone_dir() {
  local repo_name
  repo_name="${REPO##*/}"
  printf '%s\n' "${HOME}/.local/share/opencode/sources/${repo_name}"
}

resolve_clone_dir() {
  local default_dir
  default_dir="$(default_clone_dir)"

  if [[ -n "${CLONE_DIR}" ]]; then
    CLONE_DIR="$(abs_path "${CLONE_DIR}")"
    return
  fi

  if [[ "${NO_PROMPT}" -eq 1 || ! -t 0 ]]; then
    CLONE_DIR="$(abs_path "${default_dir}")"
    return
  fi

  info ""
  info "Clone location for ${REPO}:"
  read -r -p "Directory [${default_dir}]: " CLONE_DIR
  if [[ -z "${CLONE_DIR}" ]]; then
    CLONE_DIR="${default_dir}"
  fi
  CLONE_DIR="$(abs_path "${CLONE_DIR}")"
}

ensure_clone_repo() {
  require_command git

  if [[ -d "${CLONE_DIR}" ]]; then
    [[ -d "${CLONE_DIR}/.git" ]] || die "Clone directory exists but is not a git repository: ${CLONE_DIR}"
    info "Using existing clone: ${CLONE_DIR}"
    info "Update later with: git -C ${CLONE_DIR} pull"
    return
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    info "[dry-run] Would clone https://github.com/${REPO}.git -> ${CLONE_DIR}"
    return
  fi

  mkdir -p "$(dirname "${CLONE_DIR}")"
  git clone --branch "${REF}" "https://github.com/${REPO}.git" "${CLONE_DIR}"
  info "Cloned ${REPO}@${REF} to ${CLONE_DIR}"
}

validate_skill() {
  local skill_dir="$1"
  local output
  if ! output="$(python3 "${VALIDATOR}" "${skill_dir}" 2>&1)"; then
    die "Validation failed for ${skill_dir}: ${output}"
  fi
  info "   ${output}"
}

remove_path() {
  local path="$1"
  local label="$2"

  if [[ ! -e "${path}" && ! -L "${path}" ]]; then
    return
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    info "   [dry-run] Would remove ${label}: ${path}"
    return
  fi

  rm -rf "${path}"
  info "   Removed ${label}: ${path}"
}

ensure_target_link() {
  local source="$1"
  local target="$2"

  info ""
  info "-> Target: ${target}"

  local target_exists=0
  if [[ -e "${target}" || -L "${target}" ]]; then
    target_exists=1
  fi

  if [[ "${CLEAN}" -eq 1 ]]; then
    remove_path "${target}" "existing install"
    target_exists=0
  fi

  if [[ "${target_exists}" -eq 1 ]]; then
    if [[ -L "${target}" ]]; then
      local current_link
      current_link="$(readlink "${target}")"
      if [[ "${current_link}" == "${source}" ]]; then
        info "   Already linked"
        return
      fi
    fi

    if [[ "${FORCE}" -ne 1 ]]; then
      die "Target already exists. Re-run with --force or --clean: ${target}"
    fi
    remove_path "${target}" "existing install"
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    info "   [dry-run] Would link ${source} -> ${target}"
    return
  fi

  mkdir -p "$(dirname "${target}")"
  ln -s "${source}" "${target}"
  validate_skill "${target}"
  info "   Linked successfully"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --scope)
        [[ $# -ge 2 ]] || die "Missing value for --scope"
        SCOPE="$2"
        shift 2
        ;;
      --project-dir)
        [[ $# -ge 2 ]] || die "Missing value for --project-dir"
        PROJECT_DIR="$2"
        shift 2
        ;;
      --clone-dir)
        [[ $# -ge 2 ]] || die "Missing value for --clone-dir"
        CLONE_DIR="$2"
        shift 2
        ;;
      --repo)
        [[ $# -ge 2 ]] || die "Missing value for --repo"
        REPO="$2"
        shift 2
        ;;
      --ref)
        [[ $# -ge 2 ]] || die "Missing value for --ref"
        REF="$2"
        shift 2
        ;;
      --force)
        FORCE=1
        shift
        ;;
      --clean)
        CLEAN=1
        shift
        ;;
      --dry-run)
        DRY_RUN=1
        shift
        ;;
      --no-prompt)
        NO_PROMPT=1
        shift
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown argument: $1"
        ;;
    esac
  done
}

main() {
  parse_args "$@"
  require_command python3

  case "${SCOPE}" in
    project|user|both) ;;
    *) die "Invalid --scope '${SCOPE}'. Use project, user, or both." ;;
  esac

  local resolved_project_dir=""
  if [[ -n "${PROJECT_DIR}" ]]; then
    resolved_project_dir="$(abs_path "${PROJECT_DIR}")"
  else
    resolved_project_dir="$(pwd)"
  fi

  resolve_clone_dir
  ensure_clone_repo

  SOURCE_SKILL_DIR="${CLONE_DIR}/${SKILL_NAME}"
  VALIDATOR="${SOURCE_SKILL_DIR}/scripts/quick_validate.py"

  if [[ "${DRY_RUN}" -ne 1 ]]; then
    [[ -f "${SOURCE_SKILL_DIR}/SKILL.md" ]] || die "Source skill not found: ${SOURCE_SKILL_DIR}/SKILL.md"
    [[ -f "${VALIDATOR}" ]] || die "Validator not found: ${VALIDATOR}"
    info "Using source: ${SOURCE_SKILL_DIR}"
    validate_skill "${SOURCE_SKILL_DIR}"
  else
    info "Using source: ${SOURCE_SKILL_DIR}"
  fi

  local targets=()
  local backups=()

  if [[ "${SCOPE}" == "project" || "${SCOPE}" == "both" ]]; then
    targets+=("${resolved_project_dir}/.opencode/skills/${SKILL_NAME}")
    backups+=("${resolved_project_dir}/.opencode-install-backups/skills/${SKILL_NAME}")
  fi
  if [[ "${SCOPE}" == "user" || "${SCOPE}" == "both" ]]; then
    targets+=("${HOME}/.config/opencode/skills/${SKILL_NAME}")
    backups+=("${HOME}/.config/opencode-install-backups/skills/${SKILL_NAME}")
  fi

  local i
  for i in "${!targets[@]}"; do
    if [[ "${CLEAN}" -eq 1 ]]; then
      info ""
      info "-> Cleaning backup path"
      remove_path "${backups[$i]}" "backup"
    fi
    ensure_target_link "${SOURCE_SKILL_DIR}" "${targets[$i]}"
  done

  info ""
  info "Done."
  for i in "${!targets[@]}"; do
    info "- ${targets[$i]}"
  done
  info "Update source later with: git -C ${CLONE_DIR} pull"
}

main "$@"
