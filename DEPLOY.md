# 배포 가이드

## 1. API (Railway / Render / Fly)

환경변수:
- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS` = `https://your-frontend.vercel.app`
- `SESSION_SECRET` = 긴 무작위 문자열 (필수 권장. 없으면 서버 재시작 때마다 전원 로그아웃)
  - 생성: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `SESSION_TTL_HOURS` = 12 (선택, 로그인 유지 시간)

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

## 접속/인증 점검
- `GET https://<API 주소>/api/health` : `db_ok`가 `true`여야 정상입니다. `false`이면 `db_error`에 원인이 나오고(예: Turso 401), 값을 고치면 재시작 없이 자동 복구됩니다. 서버 로그에는 접속 대상 호스트와 토큰 형식 진단이 함께 출력됩니다(토큰 값은 출력하지 않음).
- `TURSO_URL` / `TURSO_AUTH_TOKEN`의 앞뒤 공백, 줄바꿈, 따옴표, `Bearer ` 접두어는 자동으로 제거됩니다.
- 로그인(허용 목록 + Gmail 확인) 후에만 API를 쓸 수 있습니다. 발신 계정 등록/조회는 관리자만 가능하고, 템플릿·설정은 본인 것만 접근할 수 있습니다.
