# code-assistant

Shared Claude Code agents and OpenAI Codex skills for the team.

## Structure

```
code-assistant/
├── claude/
│   ├── agents/          # Claude Code custom agents
│   └── skills/          # Claude Code skills
├── codex/
│   └── skills/          # OpenAI Codex custom skills
└── install.sh           # Symlink installer
```

## Installation

```bash
git clone https://github.com/arinyaho/cosmos.git ~/.code-assistant
~/.code-assistant/install.sh
```

## Notes

- This repo is intended to be project-agnostic.
- Project-specific assistants should live in the project repo (e.g. `./.codex/skills`, `./.claude/agents`).

## Claude Agents

| Agent | Description |
|-------|-------------|
| `pr` | PR creation and management |
| `pr-reviewer` | Review GitHub Pull Requests as a reviewer |
| `pr-reviewee` | Address review feedback as an author |
| `jira` | Jira ticket workflow |
| `gcp-secret-manager` | GCP secrets management |
| `gcp-project` | Switch GCP project/profile |
| `git-worktree-side-task` | Side-task workflow via git worktree |
| `static-analysis-auditor` | Static analysis for distributed/async pipelines |
| `claude-to-codex` | Sync Claude configuration → Codex skills |
| `codex-to-claude` | Sync Codex skills → Claude configuration |
| `codex-dsl-gate` | Require a YAML task card before actions |

## Claude Skills

| Skill | Description |
|-------|-------------|
| `sdd-spec-updater` | GAP ID auto-assignment + cross-reference checker for SDD docs |

## Codex Skills

| Skill | Description |
|-------|-------------|
| `pr` | PR workflow |
| `pr-reviewer` | Code review automation |
| `pr-reviewee` | Review response handling |
| `jira` | Jira integration |
| `gcp-secret-manager` | GCP secrets management |
| `gcp-project` | Switch GCP project/profile |
| `git-worktree-side-task` | Side-task workflow via git worktree |
| `static-analysis-auditor` | Static analysis for distributed/async pipelines |
| `claude-to-codex` | Sync Claude agents to Codex |
| `codex-to-claude` | Sync Codex skills to Claude |
| `codex-dsl-gate` | Require a YAML task card before actions |

## Adding New Agents/Skills

1. Add to appropriate directory
2. Commit and push
3. Team members run `git pull` in `~/.code-assistant`

## Updating

```bash
cd ~/.code-assistant && git pull
```

Symlinks mean changes are immediately available after pull.
