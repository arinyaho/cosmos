#!/usr/bin/env bash
set -euo pipefail

# GCP Project Switcher
# Usage: ./switch.sh [list|<project-id>]

ACTION="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_current() {
    echo -e "${BLUE}=== Current GCP Configuration ===${NC}"
    echo ""

    CURRENT_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "Not set")
    echo -e "Project:       ${GREEN}${CURRENT_PROJECT}${NC}"

    # Check ADC quota project
    ADC_FILE="${HOME}/.config/gcloud/application_default_credentials.json"
    if [ -f "$ADC_FILE" ]; then
        QUOTA_PROJECT=$(grep -o '"quota_project_id": *"[^"]*"' "$ADC_FILE" 2>/dev/null | cut -d'"' -f4 || echo "Not set")
        echo -e "Quota Project: ${GREEN}${QUOTA_PROJECT}${NC}"
    else
        echo -e "Quota Project: ${YELLOW}ADC not configured${NC}"
    fi

    # Check account
    ACCOUNT=$(gcloud config get-value account 2>/dev/null || echo "Not set")
    echo -e "Account:       ${GREEN}${ACCOUNT}${NC}"
    echo ""
}

list_projects() {
    echo -e "${BLUE}=== Available Projects ===${NC}"
    echo ""
    gcloud projects list --format="table(projectId,name,projectNumber)" 2>/dev/null
    echo ""
}

switch_project() {
    local PROJECT_ID="$1"

    echo -e "${BLUE}=== Switching to: ${PROJECT_ID} ===${NC}"
    echo ""

    # Verify project exists
    if ! gcloud projects describe "$PROJECT_ID" &>/dev/null; then
        echo -e "${RED}Error: Project '$PROJECT_ID' not found or not accessible${NC}"
        exit 1
    fi

    # Set default project
    echo "Setting default project..."
    gcloud config set project "$PROJECT_ID"

    # Set quota project for ADC
    echo "Setting ADC quota project..."
    gcloud auth application-default set-quota-project "$PROJECT_ID" 2>/dev/null || true

    echo ""
    echo -e "${GREEN}Successfully switched to: ${PROJECT_ID}${NC}"
    echo ""

    show_current
}

# Main
case "$ACTION" in
    "")
        show_current
        list_projects
        echo -e "${YELLOW}To switch: ./switch.sh <project-id>${NC}"
        ;;
    "list")
        list_projects
        ;;
    *)
        switch_project "$ACTION"
        ;;
esac
