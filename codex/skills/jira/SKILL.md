---
name: jira
description: "Create and manage Jira issues via API/CLI: create issues, link issues, transition status, update fields, and fetch issue details. Use when the user asks to file or manage Jira tickets, or to automate Jira operations. Default all Jira content to English unless explicitly requested otherwise."
---

# Jira Operations Skill

## Defaults

- Write issue content in English unless the user explicitly requests another language.
- Never echo tokens or secrets in responses.
- Prefer Jira REST API with `curl` + `jq` when no Jira CLI is installed.
- Jira descriptions must be sent in ADF (Atlassian Document Format), not Markdown.

## Required Inputs

Collect these from the user if not already available:

- `JIRA_BASE_URL` (e.g., `https://<YOUR_ORG>.atlassian.net`)
- `JIRA_EMAIL`
- `JIRA_API_TOKEN`
- `JIRA_PROJECT_KEY` (e.g., `ES2`)

## Secret Management (GCP)

Follow `SECRETS.md` at repo root. Recommended secret name:

- `${USERNAME}-jira-token`

Add it to `~/.tokens.json` under `secrets` like the other entries, then rely on the session bootstrap to inject it as `JIRA_API_TOKEN`.

## Example Setup

- `~/.tokens.json` stores non-secret Jira config under `jira`:
  - `base_url`, `email`, `project_key`
- `JIRA_API_TOKEN` is fetched via GCP Secret Manager (e.g., `<USERNAME>-jira-token`).

## Common Workflows

### 1) Create Issue

1. Confirm summary, description, issue type, priority, labels, assignee.
2. Build description in ADF (headings/bullets render correctly).
3. POST to `/rest/api/3/issue`.

ADF snippet example (headings + bullets):
```json
{
  "type": "doc",
  "version": 1,
  "content": [
    {"type": "heading","attrs":{"level":2},"content":[{"type":"text","text":"Scope / Tasks"}]},
    {"type": "bulletList","content":[
      {"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"First task"}]}]},
      {"type":"listItem","content":[{"type":"paragraph","content":[{"type":"text","text":"Second task"}]}]}
    ]}
  ]
}
```

Example:
```bash
curl -sS -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
  -H "Content-Type: application/json" \
  -X POST "$JIRA_BASE_URL/rest/api/3/issue" \
  -d @- <<'JSON'
{
  "fields": {
    "project": {"key": "MYPROJ"},
    "summary": "<Summary>",
    "description": {
      "type": "doc",
      "version": 1,
      "content": [{"type": "paragraph","content": [{"type": "text","text": "<Description>"}]}]
    },
    "issuetype": {"name": "Task"},
    "labels": ["vct", "design"],
    "priority": {"name": "Medium"}
  }
}
JSON
```

### 2) Link Issues

1. Use `/rest/api/3/issueLink`.
2. Provide link type (e.g., `Relates`, `Blocks`).

### 3) Transition Status

1. GET transitions: `/rest/api/3/issue/{key}/transitions`.
2. POST transition id to move status.

### 4) Update Fields

Use `PUT /rest/api/3/issue/{key}` with `fields` payload.

## Validation

- Ensure required fields exist for the project (issue type, priority, components).
- If unsure, GET `/rest/api/3/issue/createmeta` for allowed fields.
- Confirm the payload is English unless the user requested otherwise.

## Output Checklist

Before submitting:

- Summary is concise and specific
- Description has clear context and acceptance criteria
- Labels and priority are set (if provided)
- Assignee is set (if provided)
- English language verified
