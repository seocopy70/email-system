# email-system

엑셀 명단으로 기업 맞춤형 메일을 일괄 발송하는 Streamlit 앱입니다.
발송 이력은 Turso(libSQL) DB에 저장되어 여러 발신 계정이 공유하며, 같은 주제로는 같은 수신자에게 중복 발송되지 않습니다.

## 주요 기능
- 발신자 로그인: 등록된 Gmail 계정 + 구글 앱 비밀번호(DB에 저장하지 않음)
- 주제(캠페인)별 발송 상태 표시: 미발송 / 발송완료(누가, 언제) / 발송중 / 실패
- 중복 발송 차단: 발송 직전 DB에서 (주제, 수신자)를 선점, 이미 발송됐거나 다른 계정이 진행 중이면 건너뜀
- 발신자별 발송 내용(제목, 본문 전체) 저장 및 조회
- 주제별 / 발신 계정별 / 오늘 발송량 현황

## 설치
1. Turso에서 새 데이터베이스를 만들고 URL과 토큰을 발급합니다. (다른 앱과 테이블 이름이 겹치지 않게 새 DB를 권장)
   ```
   turso db create email-system
   turso db show email-system --url          # libsql://... 주소
   turso db tokens create email-system       # auth_token
   ```
   CLI 대신 turso.tech 웹 대시보드에서 만들어도 됩니다.
2. `.streamlit/secrets.toml.example` 을 `.streamlit/secrets.toml` 로 복사하고 값을 입력합니다.
   (배포 시에는 배포 환경의 Secrets에 동일하게 입력. 토큰은 GitHub에 올리지 마세요)
   - `admin_email`: 이 Gmail이 최초 관리자 발신 계정으로 자동 등록됩니다.
3. `pip install -r requirements.txt` 후 `streamlit run auto_em.py`
   - 테이블은 앱 시작 시 자동으로 생성됩니다. 별도 SQL 실행은 필요 없습니다.
4. 다른 발신 계정은 관리자로 로그인한 뒤 사이드바 「발신 계정 관리」에서 등록합니다.

## 엑셀 형식
필수 열: `회사명`, `대표자명`, `이메일` / 선택 열: `산업분류`, `AI_판정`

## 파일
- `auto_em.py`: 앱 본체
- `db.py`: Turso 접근 계층 (HTTP API 사용, 스키마 자동 생성, 발송 선점 `claim_send`)
