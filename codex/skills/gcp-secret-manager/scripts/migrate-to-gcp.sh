#!/usr/bin/env bash
# Migrate secrets from ~/.tokens.json to GCP Secret Manager
# - Adds user prefix to secret names (e.g., <USERNAME>-github-token)
# - Grants secretAccessor only to the current user
set -euo pipefail

PROJECT="${1:-my-gcp-project}"
TOKENS_FILE="${HOME}/.tokens.json"

if [ ! -f "$TOKENS_FILE" ]; then
  echo "ERROR: $TOKENS_FILE not found" >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud CLI required" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq required" >&2
  exit 1
fi

# Get current user email for prefix and IAM
USER_EMAIL=$(gcloud config get-value account 2>/dev/null)
if [ -z "$USER_EMAIL" ]; then
  echo "ERROR: Not logged in. Run 'gcloud auth login' first" >&2
  exit 1
fi

# Extract username from email (before @)
USER_PREFIX="${USER_EMAIL%%@*}"

echo "Project: $PROJECT"
echo "User: $USER_EMAIL"
echo "Prefix: $USER_PREFIX"
echo "Source: $TOKENS_FILE"
echo

create_secret() {
  local base_name="$1"
  local value="$2"
  local secret_name="${USER_PREFIX}-${base_name}"

  if [ -z "$value" ]; then
    echo "  [skip] $secret_name - empty value"
    return
  fi

  if gcloud secrets describe "$secret_name" --project="$PROJECT" >/dev/null 2>&1; then
    echo "  [exists] $secret_name - adding new version"
    echo -n "$value" | gcloud secrets versions add "$secret_name" --project="$PROJECT" --data-file=-
  else
    echo "  [create] $secret_name"
    echo -n "$value" | gcloud secrets create "$secret_name" --project="$PROJECT" --data-file=- --replication-policy="automatic"

    # Grant access only to current user
    echo "  [iam] granting secretAccessor to $USER_EMAIL"
    gcloud secrets add-iam-policy-binding "$secret_name" \
      --project="$PROJECT" \
      --member="user:$USER_EMAIL" \
      --role="roles/secretmanager.secretAccessor" \
      --quiet >/dev/null
  fi
}

echo "==> Google OAuth"
val=$(jq -r '.google.client_secret // empty' "$TOKENS_FILE")
create_secret "google-client-secret" "$val"

echo "==> Slack"
val=$(jq -r '.slack.app_token // empty' "$TOKENS_FILE")
create_secret "slack-app-token" "$val"

val=$(jq -r '.slack.bot_token // empty' "$TOKENS_FILE")
create_secret "slack-bot-token" "$val"

val=$(jq -r '.slack.webhook_url // empty' "$TOKENS_FILE")
create_secret "slack-webhook-url" "$val"

echo "==> Jira"
val=$(jq -r '.jira.token // empty' "$TOKENS_FILE")
create_secret "jira-token" "$val"

echo "==> GitHub"
val=$(jq -r '.github[0].token // empty' "$TOKENS_FILE")
create_secret "github-token" "$val"

echo "==> Docker"
val=$(jq -r '.docker[0].token // empty' "$TOKENS_FILE")
create_secret "docker-registry-token" "$val"

val=$(jq -r '.docker[1].token // empty' "$TOKENS_FILE")
create_secret "docker-ocir-token" "$val"

val=$(jq -r '.docker[1].username // empty' "$TOKENS_FILE")
create_secret "docker-ocir-username" "$val"

echo
echo "==> Done!"
echo
echo "Your secrets are prefixed with '$USER_PREFIX-'"
echo "Only you ($USER_EMAIL) have access."
echo
echo "Next steps:"
echo "1. Verify: gcloud secrets list --project=$PROJECT --filter=\"name~$USER_PREFIX\""
echo "2. Update ~/.tokens.json with this content:"
echo
cat << EOF
{
  "gcp_project": "$PROJECT",
  "secrets": {
    "GOOGLE_CLIENT_SECRET": "${USER_PREFIX}-google-client-secret",
    "SLACK_APP_TOKEN": "${USER_PREFIX}-slack-app-token",
    "SLACK_BOT_TOKEN": "${USER_PREFIX}-slack-bot-token",
    "SLACK_WEBHOOK_URL": "${USER_PREFIX}-slack-webhook-url",
    "JIRA_TOKEN": "${USER_PREFIX}-jira-token",
    "GITHUB_TOKEN": "${USER_PREFIX}-github-token",
    "DOCKER_REGISTRY_TOKEN": "${USER_PREFIX}-docker-registry-token",
    "DOCKER_OCIR_TOKEN": "${USER_PREFIX}-docker-ocir-token",
    "DOCKER_OCIR_USERNAME": "${USER_PREFIX}-docker-ocir-username"
  }
}
EOF
echo
echo "3. Backup and replace: cp ~/.tokens.json ~/.tokens.json.backup"
echo "4. Delete backup after confirming everything works"
