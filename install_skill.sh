#!/usr/bin/env bash

set -euo pipefail

SKILL_NAME="skill-creator"
SCRIPT_SOURCE="${BASH_SOURCE[0]:-$0}"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_SOURCE}")" && pwd)"
DEFAULT_REPO="feddericovonwernich/opencode-skill-creator"
DEFAULT_REF="main"

SOURCE_SKILL_DIR=""
VALIDATOR=""
TMP_ROOT=""

SCOPE="project"
PROJECT_DIR=""
FORCE=0
DRY_RUN=0
REPO="${DEFAULT_REPO}"
REF="${DEFAULT_REF}"

usage() {
  cat <<'EOF'
Install the skill-creator OpenCode skill.

Usage:
  bash install_skill.sh [options]

Options:
  --scope <project|user|both>  Install target scope (default: project)
  --project-dir <path>         Project root for project/both scope (default: current directory)
  --repo <owner/name>          GitHub repo to download from when piped (default: feddericovonwernich/opencode-skill-creator)
  --ref <git-ref>              Git branch/tag/commit for remote download (default: main)
  --force                      Replace an existing installation target
  --dry-run                    Show what would happen without making changes
  -h, --help                   Show this help text

Examples:
  bash install_skill.sh --scope project --project-dir /path/to/project
  bash install_skill.sh --scope user
  bash install_skill.sh --scope both --project-dir /path/to/project --force
  curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install_skill.sh | bash -s -- --scope user --force
EOF
}

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*"
}

require_python() {
  command -v python3 >/dev/null 2>&1 || die "python3 is required to validate SKILL.md"
}

require_command() {
  local cmd="$1"
  command -v "${cmd}" >/dev/null 2>&1 || die "Required command not found: ${cmd}"
}

cleanup() {
  if [[ -n "${TMP_ROOT}" && -d "${TMP_ROOT}" ]]; then
    rm -rf "${TMP_ROOT}"
  fi
}

abs_path() {
  python3 -c 'import os,sys; print(os.path.abspath(os.path.expanduser(sys.argv[1])))' "$1"
}

validate_skill() {
  local skill_dir="$1"
  local output
  if ! output="$(python3 "${VALIDATOR}" "${skill_dir}" 2>&1)"; then
    die "Validation failed for ${skill_dir}: ${output}"
  fi
  info "   ${output}"
}

resolve_source_skill() {
  local local_source="${SCRIPT_DIR}/${SKILL_NAME}"
  local local_validator="${local_source}/scripts/quick_validate.py"

  if [[ -f "${local_source}/SKILL.md" && -f "${local_validator}" ]]; then
    SOURCE_SKILL_DIR="${local_source}"
    VALIDATOR="${local_validator}"
    return
  fi

  require_command curl
  require_command tar

  TMP_ROOT="$(mktemp -d)"
  local archive_url="https://github.com/${REPO}/archive/${REF}.tar.gz"
  info "Local skill bundle not found. Downloading ${REPO}@${REF}..."

  if ! curl -fsSL "${archive_url}" | tar -xz -C "${TMP_ROOT}"; then
    die "Unable to download or extract ${archive_url}"
  fi

  local extracted_repo
  extracted_repo="$(find "${TMP_ROOT}" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  [[ -n "${extracted_repo}" ]] || die "Could not locate extracted repository directory"

  SOURCE_SKILL_DIR="${extracted_repo}/${SKILL_NAME}"
  VALIDATOR="${SOURCE_SKILL_DIR}/scripts/quick_validate.py"

  [[ -f "${SOURCE_SKILL_DIR}/SKILL.md" ]] || die "Downloaded repository does not contain ${SKILL_NAME}/SKILL.md"
  [[ -f "${VALIDATOR}" ]] || die "Downloaded repository does not contain ${SKILL_NAME}/scripts/quick_validate.py"
}

copy_skill() {
  local destination="$1"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a \
      --exclude='__pycache__/' \
      --exclude='node_modules/' \
      --exclude='.pytest_cache/' \
      --exclude='*.pyc' \
      --exclude='.DS_Store' \
      "${SOURCE_SKILL_DIR}/" "${destination}/"
    return
  fi

  cp -a "${SOURCE_SKILL_DIR}" "${destination}"
  find "${destination}" -type d \( -name '__pycache__' -o -name 'node_modules' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
  find "${destination}" -type f -name '*.pyc' -delete
  find "${destination}" -type f -name '.DS_Store' -delete
}

install_target() {
  local target="$1"

  info ""
  info "-> Target: ${target}"

  if [[ -e "${target}" ]]; then
    if [[ "${FORCE}" -ne 1 ]]; then
      die "Target already exists. Re-run with --force to replace: ${target}"
    fi

    if [[ "${DRY_RUN}" -eq 1 ]]; then
      info "   [dry-run] Would remove existing target"
    else
      rm -rf "${target}"
      info "   Removed existing target"
    fi
  fi

  if [[ "${DRY_RUN}" -eq 1 ]]; then
    info "   [dry-run] Would copy ${SOURCE_SKILL_DIR} -> ${target}"
    return
  fi

  mkdir -p "$(dirname "${target}")"
  copy_skill "${target}"
  validate_skill "${target}"
  info "   Installed successfully"
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
      --dry-run)
        DRY_RUN=1
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
  trap cleanup EXIT
  parse_args "$@"
  require_python
  resolve_source_skill

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

  info "Using source: ${SOURCE_SKILL_DIR}"
  validate_skill "${SOURCE_SKILL_DIR}"

  local targets=()
  if [[ "${SCOPE}" == "project" || "${SCOPE}" == "both" ]]; then
    targets+=("${resolved_project_dir}/.opencode/skills/${SKILL_NAME}")
  fi
  if [[ "${SCOPE}" == "user" || "${SCOPE}" == "both" ]]; then
    targets+=("${HOME}/.config/opencode/skills/${SKILL_NAME}")
  fi

  local target
  for target in "${targets[@]}"; do
    install_target "${target}"
  done

  info ""
  info "Done."
  for target in "${targets[@]}"; do
    info "- ${target}"
  done
}

main "$@"
