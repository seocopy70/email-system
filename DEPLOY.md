# 배포 가이드

## 1. API 백엔드 배포

환경변수 (공통):
- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS` = `https://your-frontend.vercel.app` (여러 개면 콤마로 구분)
- `SESSION_SECRET` = 긴 무작위 문자열 (필수 권장. 없으면 서버 재시작 때마다 전원 로그아웃)
  - 생성: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
- `SESSION_TTL_HOURS` = 12 (선택, 로그인 유지 시간)
- `PORT` = 8000 (기본값)

### 방법 A — Oracle Cloud Always Free (추천, SMTP 제한 없음)

Oracle Cloud Always Free Ampere A1 또는 AMD 인스턴스에 배포하면 **Gmail SMTP(포트 587/465)가 차단되지 않습니다**.  
완전 무료로 계속 사용 가능합니다.

#### 1) Oracle Cloud 계정 및 인스턴스 생성
1. [https://cloud.oracle.com](https://cloud.oracle.com) 에서 Always Free 계정 생성 (신용카드 등록 필요하지만 Always Free 리소스는 과금되지 않음)
2. **Compute → Instances → Create Instance**
   - Name: `email-system-api`
   - Image: **Canonical Ubuntu 22.04** 또는 24.04
   - Shape: **VM.Standard.A1.Flex** (Ampere, Always Free) — OCPU 1~4, Memory 6~24GB 중 여유분 사용  
     (또는 AMD `VM.Standard.E2.1.Micro` — 더 작지만 충분)
   - Networking: Public subnet, **Assign a public IPv4 address** 체크
   - SSH keys: 본인 공개키 등록 (또는 새 키 생성 후 다운로드)
3. 인스턴스 생성 후 **Public IP** 기록
4. **Networking → Virtual Cloud Networks → Security Lists** 에서 Ingress Rule 추가:
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: TCP
   - Destination Port Range: `8000`
   - Description: `email-system-api`

#### 2) 서버 접속 및 설치
```bash
ssh -i your-key.pem ubuntu@<PUBLIC_IP>

# 시스템 업데이트
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git docker.io

# (선택) Docker로 실행하는 경우
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
# 로그아웃 후 다시 로그인
```

#### 3-A) Docker로 실행 (권장)
```bash
# 레포 클론
git clone https://github.com/seocopy70/email-system.git
cd email-system/backend

# 환경변수 파일 생성
cp .env.example .env
nano .env   # TURSO_URL, TURSO_AUTH_TOKEN, ADMIN_EMAIL, CORS_ORIGINS, SESSION_SECRET 입력

# 이미지 빌드 & 실행
sudo docker build -t email-system-api .
sudo docker run -d \
  --name email-api \
  --restart unless-stopped \
  -p 8000:8000 \
  --env-file .env \
  email-system-api
```

#### 3-B) Docker 없이 Python으로 직접 실행
```bash
git clone https://github.com/seocopy70/email-system.git
cd email-system/backend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env   # 환경변수 입력

# 테스트 실행
uvicorn main:app --host 0.0.0.0 --port 8000

# 백그라운드 상시 실행 (systemd)
sudo tee /etc/systemd/system/email-api.service > /dev/null <<EOF
[Unit]
Description=Email System API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/email-system/backend
EnvironmentFile=/home/ubuntu/email-system/backend/.env
ExecStart=/home/ubuntu/email-system/backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now email-api
sudo systemctl status email-api
```

#### 4) 확인
```bash
curl http://<PUBLIC_IP>:8000/api/health
# {"ok":true,"turso":true,"db_ok":true,"db_error":null} 이면 성공
```

- API 주소 예: `http://150.230.xxx.xxx:8000`  
  (HTTPS가 필요하면 Cloudflare Tunnel 또는 Nginx + Let's Encrypt 추가 가능)

### 방법 B — Render (기존 방식)

**주의: Render Free 플랜은 2025년 9월부터 outbound SMTP(25/465/587)가 차단됩니다.**  
Gmail SMTP를 쓰려면 **유료 인스턴스**(최소 약 $7/월)로 올려야 합니다.

환경변수:
- `TURSO_URL`
- `TURSO_AUTH_TOKEN`
- `ADMIN_EMAIL`
- `CORS_ORIGINS` = `https://your-frontend.vercel.app`
- `SESSION_SECRET` = 긴 무작위 문자열
- `SESSION_TTL_HOURS` = 12

**방법 B-1 — Blueprint (가장 빠름)**
1. render.com에 GitHub으로 로그인 → **New → Blueprint**
2. 이 레포를 선택합니다. 루트의 `render.yaml`을 인식해 `email-system-api` 서비스가 만들어집니다.
3. 환경변수 입력 후 **Apply**

**방법 B-2 — 수동 Web Service**
1. render.com → **New → Web Service** → 이 레포 선택
2. **Root Directory**: `backend`
3. **Runtime**: `Docker`
4. **Instance Type**: Free 또는 Starter 이상 (SMTP 필요 시 유료)
5. Environment에 위 변수 입력 후 배포

배포되면 `https://email-system-api-xxxx.onrender.com` 같은 주소가 생깁니다.

**Free 플랜 참고**
- 15분 무요청 시 슬립 → 깨어나는 데 30초~1분
- SMTP 포트 차단으로 Gmail 발송 불가 (유료 필요)

---

## 2. 프론트엔드 (Vercel)

1. [vercel.com](https://vercel.com) → Import GitHub repo
2. **Root Directory**: `frontend`
3. Environment Variable:
   - `NEXT_PUBLIC_API_URL` = 백엔드 Public URL (슬래시 없이)  
     예: `http://150.230.xxx.xxx:8000` 또는 `https://your-api.onrender.com`
4. Deploy

로컬 연동:
```bash
# terminal 1
cd backend && source .venv/bin/activate
export TURSO_URL=... TURSO_AUTH_TOKEN=... ADMIN_EMAIL=... SESSION_SECRET=...
uvicorn main:app --reload --port 8000

# terminal 2
cd frontend && npm i && npm run dev
```

브라우저: http://localhost:3000

---

## 접속/인증 점검
- `GET https://<API 주소>/api/health` : `db_ok`가 `true`여야 정상입니다. `false`이면 `db_error`에 원인이 나오고(예: Turso 401), 값을 고치면 재시작 없이 자동 복구됩니다.
- `TURSO_URL` / `TURSO_AUTH_TOKEN`의 앞뒤 공백, 줄바꿈, 따옴표, `Bearer ` 접두어는 자동으로 제거됩니다.
- 로그인(허용 목록 + Gmail 확인) 후에만 API를 쓸 수 있습니다. 발신 계정 등록/조회는 관리자만 가능하고, 템플릿·설정은 본인 것만 접근할 수 있습니다.
