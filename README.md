# skill-creator for OpenCode

This repository contains the migrated `skill-creator` skill package for OpenCode.

## One-line install

Install to your **user** OpenCode skills folder (`~/.config/opencode/skills`):

```bash
curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install.sh | bash -s -- --scope user --clean
```

Install to your **current project** (`$PWD/.opencode/skills`):

```bash
curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install.sh | bash -s -- --scope project --project-dir "$PWD" --clean
```

## Installer usage

```bash
bash install.sh --scope project --project-dir /path/to/project
bash install.sh --scope user
bash install.sh --scope both --clone-dir ~/.local/share/opencode/sources/opencode-skill-creator --clean
curl -fsSL https://raw.githubusercontent.com/feddericovonwernich/opencode-skill-creator/main/install.sh | bash -s -- --scope both --project-dir "$PWD" --clean
```

### Options

- `--scope <project|user|both>`: install location scope (default `project`)
- `--project-dir <path>`: project root for `project`/`both` scope (default current directory)
- `--clone-dir <path>`: local git checkout path used for symlinks (prompted in interactive mode)
- `--repo <owner/name>`: GitHub repo to clone (default `feddericovonwernich/opencode-skill-creator`)
- `--ref <git-ref>`: branch/tag/commit used for the initial clone (default `main`)
- `--force`: replace existing installation target
- `--clean`: remove current installation and backup path before linking
- `--dry-run`: print planned actions without modifying files
- `--no-prompt`: disable prompts and use defaults

## Installed path

- Project scope: `<project>/.opencode/skills/skill-creator`
- User scope: `~/.config/opencode/skills/skill-creator`

## Notes

- Install targets are symlinks to your local clone path.
- The installer validates `SKILL.md` before and after linking.
- To update, run `git -C <clone-dir> pull`; no reinstall is required.
- `--clean` also removes backup path(s): `<project>/.opencode-install-backups/skills/skill-creator` and/or `~/.config/opencode-install-backups/skills/skill-creator`.
