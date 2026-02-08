---
name: setup-tokens
description: "Set up session environment variables for tokens and config when a task fails due to missing credentials or when the user asks to initialize tokens. Use for checking ~/.tokens.json, fetching secrets from GCP Secret Manager, and exporting env vars for the current session."
---

# Setup Tokens

## Overview

Use this skill when a task needs tokens/config and they are missing. It verifies `~/.tokens.json`, fetches required secrets from GCP, and exports environment variables for the current session.

## Workflow

### 1) Detect Missing Setup

Trigger when any of these are true:
- A command fails due to missing token/env var.
- The user asks to set up tokens or environment variables.
- The workflow explicitly requires Jira/GitHub/Docker/GCP secrets.

### 2) Read Non-Secret Config

- Read `~/.tokens.json`.
- Use non-secret values from service sections (e.g., `jira.base_url`, `jira.email`, `jira.project_key`).
- Never store secrets directly in `~/.tokens.json` unless the user explicitly instructs.

### 3) Fetch Secrets from GCP

- Use the secret mapping in `~/.tokens.json` under `secrets`.
- Fetch with:
```bash
gcloud secrets versions access latest --secret=<secret-name> --project=<gcp_project>
```
- Do not print secret values in logs or responses.

### 4) Export Env Vars (Session Only)

- Export for the current session only (no shell profile edits unless requested).
- Example for Jira:
```bash
export JIRA_BASE_URL="https://<YOUR_ORG>.atlassian.net"
export JIRA_EMAIL="user@example.com"
export JIRA_PROJECT_KEY="MYPROJ"
export JIRA_API_TOKEN="<from gcloud>"
```

### 5) Validate

- Confirm required vars exist in the environment.
- Retry the original command or next step.

## Defaults

- Keep outputs in English unless the user asks otherwise.
- Never echo or log secret values.
- Prefer session-only exports.

## Output Checklist

- Non-secret config sourced from `~/.tokens.json`
- Secrets fetched via GCP Secret Manager
- Exports performed for the current session
- No secret printed or stored in repo files
