# 배포 가이드 — 현재 운영본

> **이 문서는 현재 운영되는 React/Next.js + FastAPI 구조만 설명합니다.**
>
> Streamlit 버전은 `legacy/streamlit` 브랜치에 보관되어 있으며 현재 운영·배포 대상이 아닙니다.

## 1. 전체 구조

```
사용자 브라우저
      │
      ▼
Vercel
frontend/ (Next.js / React)
      │
      │ NEXT_PUBLIC_API_URL
      ▼
Oracle Cloud
backend/ (FastAPI)
      │
      ├── Turso / libSQL
      └── Gmail SMTP
```

현재 프론트 주소:

`https://email-system-jet.vercel.app`

## 2. Backend — Oracle Cloud

Oracle 서버에서 `backend/`를 실행합니다.

필수 환경변수:

- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS` — Vercel 프론트 주소
- `SESSION_SECRET`
- `SESSION_TTL_HOURS` — 선택, 기본 12시간
- `PORT` — 선택, 기본 8000

### Docker 실행

```bash
cd email-system/backend

sudo docker build -t email-system-api .

sudo docker run -d \
  --name email-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  email-system-api
```

### 동작 확인

```bash
curl http://<ORACLE_PUBLIC_IP>:8000/api/health
```

정상적으로 API가 응답하면 백엔드가 동작하는 것입니다.

## 3. Frontend — Vercel

Vercel 프로젝트의 Root Directory:

`frontend`

필수 환경변수:

`NEXT_PUBLIC_API_URL`

값에는 현재 Oracle FastAPI 백엔드의 공개 주소를 넣습니다.

예:

`http://<ORACLE_PUBLIC_IP>:8000`

GitHub의 `main` 브랜치에 프론트 변경사항을 반영하면 Vercel이 해당 프론트를 배포합니다.

## 4. 작업 원칙

### 현재 운영본

- 프론트 수정 → `frontend/`
- 백엔드 수정 → `backend/`
- 기본 작업 브랜치 → `main`
- 프론트 배포 → Vercel
- 백엔드 배포 → Oracle

### 레거시

- Streamlit 코드 → `legacy/streamlit`
- 운영 배포 금지
- 새로운 기능을 Streamlit에 추가하지 않음

**앞으로 "이메일 시스템 수정"이라고 하면 별도 지시가 없는 한 `main`의 React/Next.js + Oracle FastAPI 구조를 의미합니다.**
