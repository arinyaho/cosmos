# Claude To Codex

## Workflow
1) Preview changes (dry-run):
   - `python3 ~/.claude/skills/claude-to-codex/scripts/sync_claude_to_codex.py --dry-run`
2) Apply the sync:
   - `python3 ~/.claude/skills/claude-to-codex/scripts/sync_claude_to_codex.py --apply`
3) Re-run anytime after you edit files under `~/.claude/agents` or `~/.claude/skills`.

## What it converts
- **Claude agents**: `~/.claude/agents/*.md` → `~/.claude/skills/<name>/SKILL.md`
  - Reads the agent frontmatter, keeps only `name`/`description` (Codex format), and preserves the body as the skill instructions.
- **Claude skills**: `~/.claude/skills/<skill>/...` → `~/.claude/skills/<skill>/...`
  - Copies the directory (including `scripts/`, etc.) and ensures `SKILL.md` has valid Codex YAML frontmatter.

## Safety defaults
- Dry-run is the default unless `--apply` is provided.
- Never overwrites an existing destination skill unless `--overwrite` is provided.
- Writes only under `~/.claude/skills` by default (or `--dst`).

## Useful flags
- Convert only one side: `--only agents` or `--only skills`
- Custom locations: `--src <path-to-.claude>` and `--dst <path-to-codex-skills>`
- Replace existing: `--overwrite` (dangerous)
