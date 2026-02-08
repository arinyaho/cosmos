---
name: git-worktree-side-task
description: "Use git worktree to spin up a separate directory for a \"side task\" in the same repo (parallel work on another branch) and to clean it up when finished. Trigger when the user says \"사이드 태스크로 하자\", \"worktree로 분리하자\", \"두 브랜치에서 동시에 작업\", or \"정리하자\" to remove the side worktree."
model: opus
---
# Git Worktree Side Task

## Quick Start

Create a side-task worktree (from repo root):
- `python3 ~/.claude/skills/git-worktree-side-task/scripts/worktree_side_task.py create --branch BRANCH`
- If re-running for the same branch: add `--reuse` to print the existing worktree path instead of erroring.
- Optional start point: `--from origin/main` or `--from HEAD`

Clean up when done:
- `python3 ~/.claude/skills/git-worktree-side-task/scripts/worktree_side_task.py cleanup --branch BRANCH`

List worktrees:
- `python3 ~/.claude/skills/git-worktree-side-task/scripts/worktree_side_task.py list`

## Assistant Workflow (Natural Language)

### A) When the user says “사이드 태스크로 하자”
1) Determine the side-task branch name:
   - If the user specifies a branch name, use it.
   - Otherwise, do **not** ask by default. Pick a reasonable default:
      - If the current task is tied to a GitHub PR and you can infer the PR number, use `review/<pr-number>` (example: `review/123`).
        - If another active skill already pinned a `target_pr`, reuse it to infer the PR number.
        - Prefer simple inference:
          - If you have a PR URL, parse `/pull/<number>` from it.
          - Otherwise (and only if it helps), use `gh pr view <pr> --json number` to fetch the PR number.
      - Otherwise, use `side-task/<short-topic>` (derive from the user request) or `side-task/<date>` as a fallback.
2) Determine the start point (optional; default to `origin/HEAD` if available, otherwise `HEAD`).
3) Create a worktree directory next to the repo (not inside it):
   - default worktrees dir: `REPO_ROOT-parent/REPO_NAME-worktrees/`
   - Use `--reuse` to avoid errors when the branch already has a worktree.
4) Switch context to the new worktree path for all commands related to the side task.

### B) When the user says “완료됐으니 정리하자”
1) Ensure the side worktree is clean (no uncommitted changes). If not clean, ask whether to commit/stash or force-remove.
2) Remove the worktree directory via `git worktree remove` (and prune).
3) Do not delete the branch unless the user explicitly asks.

## Conventions
- Worktree paths must be outside the current worktree; Git does not allow nested worktrees.
- Prefer naming branches explicitly (e.g., `chore/side-fix`, `fix/typo`, `feat/side-task-123`).

## Script
- Use `~/.claude/skills/git-worktree-side-task/scripts/worktree_side_task.py` for reliable creation/cleanup.
