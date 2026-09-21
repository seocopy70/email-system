# 기업 이메일 발송 시스템

엑셀 명단으로 맞춤 메일을 일괄 발송합니다.
발송 이력은 Turso(libSQL)에 저장되며, **같은 주제 + 같은 수신자** 중복 발송을 막습니다.

## 구성 (권장)

| 경로 | 역할 |
|------|------|
| `frontend/` | **Next.js** UI — 옵션 변경 시 깜빡임 없는 SPA |
| `backend/` | **FastAPI** API — Turso, Gmail SMTP, 발송 로직 |
| `auto_em.py` | 기존 Streamlit 앱 (레거시, 선택) |

### 1) 백엔드

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# .env에 TURSO_URL, TURSO_AUTH_TOKEN, ADMIN_EMAIL 입력 후
export $(grep -v '^#' .env | xargs)
uvicorn main:app --reload --port 8000
```

### 2) 프론트엔드

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

브라우저: http://localhost:3000

### 배포 예시

- 프론트: Vercel (`frontend/`), 환경변수 `NEXT_PUBLIC_API_URL`
- API: Railway / Render / Fly.io (`backend/`), Turso·CORS 설정

## 엑셀 형식

필수: `회사명`, `대표자명`, `이메일` / 선택: `산업분류`, `AI_판정`

## Streamlit (레거시)

```bash
pip install -r requirements.txt
streamlit run auto_em.py
```

자세한 배포: [DEPLOY.md](./DEPLOY.md)

