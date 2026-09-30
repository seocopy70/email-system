# 기업 이메일 발송 시스템

기업 대상 맞춤 이메일 일괄 발송 시스템입니다.

## 현재 운영 구조

> **중요: 이 저장소의 `main` 브랜치는 React/Next.js + FastAPI 운영본만 관리합니다.**

| 구성 | 역할 | 현재 운영 위치 |
|---|---|---|
| `frontend/` | Next.js/React 웹 UI | **Vercel** |
| `backend/` | FastAPI API, Turso DB 연동, Gmail SMTP 발송 | **Oracle Cloud** |
| `legacy/streamlit` 브랜치 | 과거 Streamlit 버전 보관용 | **운영하지 않음** |

현재 사용자 접속 주소:
**https://email-system-jet.vercel.app**

### 브랜치 구분 규칙

- **`main`** → 현재 운영본. Vercel 프론트 + Oracle 백엔드
- **`legacy/streamlit`** → 과거 Streamlit 버전의 보관본. 수정·배포하지 않음

따라서 새로운 기능 수정은 원칙적으로 **`main`의 `frontend/` 또는 `backend/`만 대상으로 합니다.**

## 배포

### Frontend — Vercel

Vercel에서 이 저장소의 Root Directory를 `frontend`로 설정합니다.

필수 환경변수:

- `NEXT_PUBLIC_API_URL` = 현재 Oracle FastAPI 백엔드 주소

### Backend — Oracle Cloud

Oracle 서버에서 `backend/`를 실행합니다.

필수 환경변수:

- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS`
- `SESSION_SECRET`

상세 배포 절차는 [DEPLOY.md](./DEPLOY.md)를 참고하세요.

## 로컬 개발

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

브라우저: http://localhost:3000

## 엑셀 형식

필수: `회사명`, `대표자명`, `이메일`

선택: `산업분류`, `AI_판정`

---

**Streamlit 버전은 현재 운영 시스템이 아닙니다. 필요한 경우 GitHub의 `legacy/streamlit` 브랜치에서만 확인합니다.**
