#!/usr/bin/env bash
# Grant Secret Manager create permission to team members
# Usage: ./grant-team-access.sh [project] < team-emails.txt
#    or: ./grant-team-access.sh [project] user1@example.com user2@example.com
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PROJECT="${1:-my-gcp-project}"
shift 2>/dev/null || true

echo "Project: $PROJECT"
echo

grant_access() {
  local email="$1"

  # Skip empty lines and comments
  [[ -z "$email" || "$email" == \#* ]] && return

  echo "==> $email"

  # Grant custom secretCreator role (can create secrets and manage IAM on their own secrets)
  if gcloud projects add-iam-policy-binding "$PROJECT" \
    --member="user:$email" \
    --role="projects/$PROJECT/roles/secretCreator" \
    --quiet >/dev/null 2>&1; then
    echo "  [ok] projects/$PROJECT/roles/secretCreator granted"
  else
    echo "  [fail] could not grant permission" >&2
  fi
}

if [ $# -gt 0 ]; then
  # Arguments provided
  for email in "$@"; do
    grant_access "$email"
  done
else
  # Read from stdin
  while IFS= read -r email || [ -n "$email" ]; do
    grant_access "$email"
  done
fi

echo
echo "Done! Team members can now run:"
echo "  $SKILL_DIR/scripts/migrate-to-gcp.sh $PROJECT"
