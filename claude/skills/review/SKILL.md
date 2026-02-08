---
name: review
description: "Use when reviewing a GitHub PR: fetch diff, check spec drift, produce B/S findings, post comments. Invoke via /review or Task(subagent_type=pr-reviewer)."
---

# PR Reviewer (Skill)

## SSOT

The canonical workflow is `~/.claude/agents/pr-reviewer.md`.
Read it before proceeding — do NOT rely on this file for workflow steps.

## Quick Invocation

- **As agent**: `Task(subagent_type=pr-reviewer)` — full autonomous review
- **As skill**: `/review <PR-number-or-URL>` — interactive review in conversation

## Assets (consumed by the agent)

- `references/pr-body-template.md` — PR body template for missing descriptions
- `references/review-output-template.md` — fixed review output structure
- `scripts/reviewpack.py` — bundle PR context into a single markdown file
- `scripts/post_pr_comments.py` — post global + inline review comments
