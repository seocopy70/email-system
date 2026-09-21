# 배포 가이드

## 1. API (Render)

환경변수:
- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS` = `https://your-frontend.vercel.app`
- `SESSION_SECRET` = 긴 무작위 문자열 (필수 권장. 없으면 서버 재시작 때마다 전원 로그아웃)
  - 생성: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `SESSION_TTL_HOURS` = 12 (선택, 로그인 유지 시간)

**방법 A — Blueprint (가장 빠름)**
1. render.com에 GitHub으로 로그인 → **New → Blueprint**
2. 이 레포(`seocopy70/email-system`)를 선택합니다. 루트의 `render.yaml`을 인식해 `email-system-api` 서비스가 만들어집니다.
3. `TURSO_URL`, `TURSO_AUTH_TOKEN`, `ADMIN_EMAIL`, `CORS_ORIGINS` 값을 입력합니다. `SESSION_SECRET`은 자동으로 생성됩니다.
4. **Apply**를 누르면 빌드가 시작됩니다.

**방법 B — 수동으로 Web Service 만들기**
1. render.com → **New → Web Service** → 이 레포를 선택합니다.
2. **Root Directory**: `backend`
3. **Runtime**: `Docker` (Dockerfile이 자동으로 인식됩니다)
4. **Instance Type**: `Free`
5. **Environment**에 위 환경변수를 모두 넣습니다.
6. **Create Web Service**로 배포합니다.

배포되면 `https://email-system-api-xxxx.onrender.com` 같은 주소가 생깁니다.

**Free 플랜 참고 사항**
- 15분간 요청이 없으면 서버가 잠들고, 다음 요청에서 다시 깨어나는 데 30초~1분 정도 걸립니다. 폰에서 오랜만에 열면 첫 로그인이 느릴 수 있습니다.
- 월 750시간 무료로, 서비스 하나를 계속 켜 두는 정도는 충분합니다.

## 2. 프론트## 2. 프론트 (Vercel)

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
