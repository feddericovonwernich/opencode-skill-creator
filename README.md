# skill-creator for OpenCode

This repository contains the migrated `skill-creator` skill package for OpenCode.

## One-line install

Install to your **user** OpenCode skills folder (`~/.config/opencode/skills`):

```bash
tmp="$(mktemp -d)" && git clone --depth 1 https://github.com/feddericovonwernich/opencode-skill-creator.git "$tmp/repo" && bash "$tmp/repo/install_skill.sh" --scope user --force && rm -rf "$tmp"
```

Install to your **current project** (`$PWD/.opencode/skills`):

```bash
tmp="$(mktemp -d)" && git clone --depth 1 https://github.com/feddericovonwernich/opencode-skill-creator.git "$tmp/repo" && bash "$tmp/repo/install_skill.sh" --scope project --project-dir "$PWD" --force && rm -rf "$tmp"
```

## Installer usage

```bash
bash install_skill.sh --scope project --project-dir /path/to/project
bash install_skill.sh --scope user
bash install_skill.sh --scope both --project-dir /path/to/project --force
```

### Options

- `--scope <project|user|both>`: install location scope (default `project`)
- `--project-dir <path>`: project root for `project`/`both` scope (default current directory)
- `--force`: replace existing installation target
- `--dry-run`: print planned actions without modifying files

## Installed path

- Project scope: `<project>/.opencode/skills/skill-creator`
- User scope: `~/.config/opencode/skills/skill-creator`

## Notes

- The installer validates `SKILL.md` before and after install.
- Transient artifacts (`__pycache__`, `*.pyc`, `.pytest_cache`, `node_modules`, `.DS_Store`) are excluded during installation.
