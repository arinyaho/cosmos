---
name: gcp-project
description: "GCP 프로젝트를 쉽게 전환하는 스킬입니다."
model: opus
---
# GCP Project Switcher

GCP 프로젝트를 쉽게 전환하는 스킬입니다.

## 사용법

```
/gcp-project           # 현재 프로젝트 확인 및 전환
/gcp-project list      # 프로젝트 목록만 조회
/gcp-project <ID>      # 특정 프로젝트로 바로 전환
```

## 기능

1. **현재 프로젝트 확인**: 현재 설정된 프로젝트와 quota 프로젝트 표시
2. **프로젝트 목록 조회**: 접근 가능한 모든 GCP 프로젝트 표시
3. **프로젝트 전환**: 선택한 프로젝트로 config와 quota 모두 설정

## 설정되는 항목

- `gcloud config set project <ID>`: 기본 프로젝트
- `gcloud auth application-default set-quota-project <ID>`: ADC quota 프로젝트

## 요구사항

- gcloud CLI 설치 및 인증 완료
- `gcloud auth login` 실행됨
- `gcloud auth application-default login` 실행됨
