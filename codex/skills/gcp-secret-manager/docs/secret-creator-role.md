# Secret Creator Custom Role

GCP Secret Manager에서 팀원들이 개인 시크릿을 생성하고 관리할 수 있도록 하는 커스텀 IAM role입니다.

## Role 정보

| 항목 | 값 |
|------|-----|
| **Name** | `projects/my-gcp-project/roles/secretCreator` |
| **Title** | Secret Creator |
| **Project** | my-gcp-project |

## 포함된 권한

| Permission | 설명 |
|------------|------|
| `secretmanager.secrets.create` | 새 시크릿 생성 |
| `secretmanager.secrets.get` | 시크릿 메타데이터 조회 |
| `secretmanager.secrets.list` | 시크릿 목록 조회 |
| `secretmanager.secrets.setIamPolicy` | 시크릿별 IAM 설정 (자기 시크릿에 권한 부여) |
| `secretmanager.secrets.getIamPolicy` | 시크릿별 IAM 조회 |
| `secretmanager.versions.add` | 시크릿 버전 추가 (값 업데이트) |
| `secretmanager.versions.access` | 시크릿 값 읽기 |
| `resourcemanager.projects.get` | 프로젝트 정보 조회 (기본 요구사항) |

## 권한 범위

### 할 수 있는 것

- ✅ 새 시크릿 생성
- ✅ 자기 시크릿에 본인만 접근하도록 IAM 설정
- ✅ 자기 시크릿 값 읽기/업데이트
- ✅ 시크릿 목록 조회 (이름만, 값은 IAM 있어야)

### 할 수 없는 것

- ❌ 다른 사람 시크릿 값 읽기 (해당 시크릿에 IAM 없으면)
- ❌ 시크릿 삭제 (`secrets.delete` 없음)
- ❌ 프로젝트 IAM 변경 (시크릿별 IAM만 가능)

## 사용 시나리오

1. **관리자**가 팀원에게 이 role 부여:
   ```bash
   gcloud projects add-iam-policy-binding my-gcp-project \
     --member="user:teammate@example.com" \
     --role="projects/my-gcp-project/roles/secretCreator"
   ```

2. **팀원**이 시크릿 생성:
   ```bash
   echo -n "my-secret-value" | gcloud secrets create teammate-github-token \
     --project=my-gcp-project \
     --data-file=-
   ```

3. **팀원**이 본인에게만 접근 권한 부여:
   ```bash
   gcloud secrets add-iam-policy-binding teammate-github-token \
     --project=my-gcp-project \
     --member="user:teammate@example.com" \
     --role="roles/secretmanager.secretAccessor"
   ```

4. 이제 다른 팀원은 `teammate-github-token` 값을 읽을 수 없음

## 보안 고려사항

### 시크릿 목록은 보임

이 role로 `gcloud secrets list`를 실행하면 **모든 시크릿 이름**이 보입니다.
하지만 **값**은 해당 시크릿에 `secretAccessor` IAM이 있어야만 읽을 수 있습니다.

```bash
# 목록은 보임
$ gcloud secrets list
NAME                    CREATED
<USERNAME>-github-token      2024-01-01
teammate-github-token   2024-01-02

# 값은 권한 없으면 에러
$ gcloud secrets versions access latest --secret=<USERNAME>-github-token
ERROR: Permission denied
```

### Audit 로그

모든 접근 시도는 Cloud Audit Logs에 기록됩니다:
- Admin Activity: 시크릿 생성/삭제/IAM 변경
- Data Access: 시크릿 값 읽기 (활성화 필요)

## Role 관리

### 권한 추가

```bash
gcloud iam roles update secretCreator \
  --project=my-gcp-project \
  --add-permissions="secretmanager.secrets.delete"
```

### 권한 제거

```bash
gcloud iam roles update secretCreator \
  --project=my-gcp-project \
  --remove-permissions="secretmanager.versions.access"
```

### Role 삭제

```bash
gcloud iam roles delete secretCreator --project=my-gcp-project
```

## 관련 파일

- `scripts/grant-team-access.sh` - 팀원 권한 부여 스크립트
- `scripts/migrate-to-gcp.sh` - 시크릿 마이그레이션 스크립트
