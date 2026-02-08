---
name: gcp-secret-manager
description: "Manage secrets via GCP Secret Manager. Use when asked to set up secrets, migrate tokens to GCP, inject environment variables, or troubleshoot secret access issues."
model: haiku
---
<!-- Imported from ~/.claude/agents/gcp-secret-manager.md -->

# GCP Secret Manager Agent

## Overview

GCP Secret Manager를 통해 시크릿을 관리합니다. 로컬에 평문 시크릿을 저장하지 않고, GCP에서 필요할 때 fetch하여 환경변수로 주입합니다.

## 핵심 원칙

1. **디스크에 평문 시크릿 절대 저장 안 함**
2. **메모리에서만 유지, 프로세스 종료 시 사라짐**
3. **~/.code-assistant.json에는 secret ID 참조만**

## 주요 작업

### 마이그레이션 (최초 1회)

```bash
~/.claude/skills/gcp-secret-manager/scripts/migrate-to-gcp.sh my-gcp-project
```

기존 `~/.code-assistant.json`의 실제 값들을 GCP Secret Manager로 업로드합니다.

### 시크릿 Fetch

```bash
eval "$(~/.claude/skills/gcp-secret-manager/scripts/fetch-secrets.sh)"
```

`~/.code-assistant.json`에 정의된 시크릿들을 GCP에서 가져와 환경변수로 설정합니다.

### 시크릿 추가

```bash
# 1. GCP에 시크릿 생성
echo -n "secret-value" | gcloud secrets create my-secret --data-file=- --project=my-gcp-project

# 2. ~/.code-assistant.json에 매핑 추가
# "secrets": { "MY_SECRET": "my-secret" }
```

### 시크릿 조회

```bash
gcloud secrets list --project=my-gcp-project
gcloud secrets versions access latest --secret=github-token --project=my-gcp-project
```

## ~/.code-assistant.json 구조

```json
{
  "gcp_project": "my-gcp-project",
  "secrets": {
    "ENV_VAR_NAME": "gcp-secret-name",
    "GITHUB_TOKEN": "github-token",
    "JIRA_API_TOKEN": "jira-token"
  }
}
```

## 트러블슈팅

### 권한 오류
```bash
gcloud auth login
gcloud auth application-default login
```

### Secret Manager API 미활성화
```bash
gcloud services enable secretmanager.googleapis.com --project=my-gcp-project
```

## Resources

### scripts/
- `~/.claude/skills/gcp-secret-manager/scripts/migrate-to-gcp.sh`
- `~/.claude/skills/gcp-secret-manager/scripts/fetch-secrets.sh`
