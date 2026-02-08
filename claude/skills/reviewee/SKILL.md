---
name: reviewee
description: "Use when addressing PR review feedback: triage comments, implement fixes, validate, push, reply+resolve threads. Invoke via Task(subagent_type=reviewee)."
---

# PR Reviewee (Skill)

## SSOT

The canonical workflow is `~/.claude/agents/pr-reviewee.md`.
Read it before proceeding — do NOT rely on this file for workflow steps.

## Quick Invocation

- **As agent**: `Task(subagent_type=reviewee)` — full autonomous review-fix loop
- **Trigger phrases**: "리뷰 반영", "코멘트 반영", "address review comments"

## Assets (consumed by the agent)

- `references/resolution-comment-template.md` — reply template for resolved threads
