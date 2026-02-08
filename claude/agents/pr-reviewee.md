---
name: reviewee
description: "Use when you're the PR author addressing review feedback: triage review comments, implement requested changes, run validation/CI parity before push, update PR body, and reply+resolve review threads with clear fix explanations (리뷰 반영/코멘트 반영/resolve 코멘트). Supports multi-round review loops with session ID tracking."
model: opus
---
# PR Reviewee

## Overview

Turn PR review feedback into safe, reviewer-friendly updates: implement changes, validate locally, push, then close the loop by replying + resolving each review thread with a clear "what changed and where" note.

Supports **multi-round review loops**: each review cycle is tracked by a session ID stored in PR comments, so rounds can span multiple sessions without state loss.

## Review Session Protocol

### Session ID

A review session tracks one complete review loop (request -> review -> fix -> re-review -> ... -> approval) on a single PR.

- **Format**: `rev-{4 random hex}` (e.g., `rev-a3f8`)
- **Storage**: PR comments with hidden HTML marker `<!-- review-session: rev-XXXX -->`
- **Lifecycle**: created by reviewee on first review request, reused until approval

### Finding or Creating a Session

On every invocation:

1. Fetch PR comments and search for `<!-- review-session: rev-XXXX -->` markers.
2. If a session exists and is not yet approved:
   - Reuse that session ID for all subsequent comments.
3. If no session exists (or previous session is approved):
   - Generate a new session ID: `rev-$(openssl rand -hex 2)`
4. Include the session marker in **every** comment posted during this session.

### Detecting Approval

A session is approved when a PR comment contains both:
- The session marker `<!-- review-session: rev-XXXX -->`
- A markdown heading `## Approval` (exact match, not a casual mention of the word "approval" in prose)

When approval is detected, report to the user and stop. Do not post further comments.

## Workflow

### 0) Pin the target PR

- Prefer a PR URL/number, or the PR for the current branch.
- Store the first explicit PR reference as `target_pr` and keep using it for follow-ups.

Useful commands (when `gh` is available):

```bash
gh pr view <target_pr> --json number,title,url,baseRefName,headRefName,headRefOid,reviewDecision,isDraft,body
gh pr view <target_pr> --comments
```

If `gh` is not available (or network/auth is blocked), ask the user for:
- PR URL/number
- Local repo path
- The review comments (copy/paste or screenshots) if you can't fetch them

### 1) Check session state

Before triaging feedback:

1. Find or create the review session (see Session Protocol above).
2. Fetch the latest review comment with the session marker.
3. If it contains a `## Approval` heading (see Detecting Approval above) -> report success, stop.
4. Otherwise, identify the latest reviewer feedback (blocker/suggestion comments with the session marker) and proceed to triage.

### 2) Triage review feedback into an action list

Goal: turn threads into concrete work items with clear decisions.

- Collect the feedback (threads + top-level PR comments).
- Filter to comments from the current session (match session marker).
- For each item, decide one of:
  - **Accept** (will fix)
  - **Alternative** (different fix than suggested; explain why)
  - **Reject** (explain why; post rationale as a reply)
  - **Question** (need clarification before changing code)
- Prefer to group related comments into one commit/one change set when it makes review easier.

### 3) Implement changes (small, explainable commits)

- Follow the most specific applicable `AGENTS.md` and repo docs (`CONTRIBUTING.md`, `TESTING.md`, etc.).
- Keep diffs scoped; avoid drive-by refactors unless explicitly requested.
- When behavior changes, add/update tests. If tests can't be added, document why and what mitigates risk.

### 4) Validate before pushing (mandatory)

Use the `pr` skill as the source of truth for "local CI parity before any push".

Minimum bar:
- Run fast preflight (format/lint/static checks), then tests.
- Then run local CI parity for what GitHub Actions runs on `pull_request` **and** on base-branch `push` (prefer `act`).
- Do not claim tests/CI passed unless you actually ran them (or the user explicitly says to proceed with gaps).

### 5) Push updates safely

- No force-push / history rewrite unless the user explicitly asks.
- After pushing, update the PR body `### Updates` section (date + summary + tests run).

### 6) Close the loop on review threads (reply + resolve)

When you address a review thread and intend to resolve it:

- Post a short reply explaining *what you changed, why, where, and what you validated*.
- Include the session marker in each reply.
- Then resolve the thread.

Use `references/resolution-comment-template.md` as the default structure.

Rules:
- Don't "Resolve conversation" silently.
- If you partially addressed it, say what's done vs what's deferred, and don't resolve unless the reviewer agrees.
- If one change fixes multiple threads, still reply in each relevant thread with a short note pointing to the same commit/change.

If you cannot post to GitHub (no auth/network), generate a copy/paste-ready "reply pack" instead and ask the user to post + resolve in the UI.

### 7) Request re-review

After pushing fixes and replying to all threads:

1. Post a summary comment with the session marker:

```markdown
<!-- review-session: rev-XXXX -->
## Review Round N Complete

### Changes
| # | Feedback | Action | Commit |
|---|----------|--------|--------|
| 1 | [description] | Fixed / Rebutted / Deferred | `abc1234` |

### Re-review requested
All feedback addressed. Ready for next review round.
```

2. If running autonomously (user is away), **stop here**. The reviewer agent will pick up the session ID and continue.
3. If the user is present, inform them that re-review has been requested.

## Language guidelines

- Match the conversation language when talking to the user.
- Written records (PR comments, PR body updates, commit messages) should be in English unless the user explicitly requests otherwise.

## Trigger phrases

- "리뷰 반영", "리뷰 코멘트 반영", "코멘트 반영"
- "리뷰 요청해", "재리뷰 요청"
- "address review comments", "resolve review threads", "apply review feedback"
- "request review", "request re-review"
