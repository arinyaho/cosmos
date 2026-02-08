# Codex To Claude

## Overview

Export Codex skills into Claude-compatible copies: a Claude agent (`~/.claude/agents/*.md`) and a Claude skill directory (`~/.claude/skills/<name>/`).

## Workflow

### 1) Dry-run (recommended)

Preview changes without writing:

```bash
python3 ~/.claude/skills/codex-to-claude/scripts/sync_codex_to_claude.py \
  --skill pr-reviewer \
  --map pr-reviewer=review \
  --dry-run
```

### 2) Apply export

Write changes to `~/.claude` (overwriting existing copies):

```bash
python3 ~/.claude/skills/codex-to-claude/scripts/sync_codex_to_claude.py \
  --skill pr-reviewer \
  --map pr-reviewer=review \
  --apply --overwrite
```

### Useful flags

- Export everything: omit `--skill` (still skips hidden dirs and `.system/`)
- Export only one side: `--only agent` or `--only skill`
- Set Claude agent model: `--model opus` (default: `opus`)
- Change locations: `--src ~/.claude/skills --dst ~/.claude`

## What it exports

- **Claude agent**: `~/.claude/agents/<name>.md`
  - Uses the Codex skill `SKILL.md` frontmatter (`name`, `description`) and the body as the agent instructions.
- **Claude skill**: `~/.claude/skills/<name>/`
  - Copies the whole skill directory (scripts/references/assets).
  - Rewrites `SKILL.md` to remove Codex YAML frontmatter (Claude skills typically use plain Markdown).
  - Rewrites common path references from `~/.claude/skills` to `~/.claude/skills` for teammate portability.

## Resources

### scripts/

- `scripts/sync_codex_to_claude.py`: Main sync script (dry-run by default; use `--apply` to write).

### references/

Keep this minimal; the script itself documents its flags via `--help`.
