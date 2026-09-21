# 배포 가이드

## 1. API (Railway / Render / Fly)

환경변수:
- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS` = `https://your-frontend.vercel.app`

Railway 예:
1. New Project → Deploy from GitHub → root directory `backend`
2. 위 환경변수 설정
3. Public URL 확인 (예: `https://email-api.up.railway.app`)

## 2. 프론트 (Vercel)

1. Import GitHub repo
2. Root Directory: `frontend`
3. Environment Variable:
   - `NEXT_PUBLIC_API_URL` = API Public URL (슬래시 없이)
4. Deploy

로컬 연동:
```bash
# terminal 1
cd backend && source .venv/bin/activate
export TURSO_URL=... TURSO_AUTH_TOKEN=... ADMIN_EMAIL=...
uvicorn main:app --reload --port 8000

# terminal 2
cd frontend && npm i && npm run dev
```
