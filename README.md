# skill-creator for OpenCode

This repository contains the migrated `skill-creator` skill package for OpenCode.

## One-line install

Install to your **user** OpenCode skills folder (`~/.config/opencode/skills`):

```bash
curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install_skill.sh | bash -s -- --scope user --force
```

Install to your **current project** (`$PWD/.opencode/skills`):

```bash
curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install_skill.sh | bash -s -- --scope project --project-dir "$PWD" --force
```

## Installer usage

```bash
bash install_skill.sh --scope project --project-dir /path/to/project
bash install_skill.sh --scope user
bash install_skill.sh --scope both --project-dir /path/to/project --force
curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install_skill.sh | bash -s -- --scope both --project-dir "$PWD" --force
```

### Options

- `--scope <project|user|both>`: install location scope (default `project`)
- `--project-dir <path>`: project root for `project`/`both` scope (default current directory)
- `--repo <owner/name>`: GitHub repo to fetch when script is piped (default `feddericovonwernich/opencode-skill-creator`)
- `--ref <git-ref>`: branch/tag/commit for remote download when piped (default `main`)
- `--force`: replace existing installation target
- `--dry-run`: print planned actions without modifying files

## Installed path

- Project scope: `<project>/.opencode/skills/skill-creator`
- User scope: `~/.config/opencode/skills/skill-creator`

## Notes

- The installer validates `SKILL.md` before and after install.
- Piped `curl` installs work without `git`; the script downloads the skill bundle from GitHub automatically.
- Transient artifacts (`__pycache__`, `*.pyc`, `.pytest_cache`, `node_modules`, `.DS_Store`) are excluded during installation.
