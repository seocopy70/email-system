# email-system

엑셀 명단으로 기업 맞춤형 메일을 일괄 발송하는 Streamlit 앱입니다.
발송 이력은 Supabase(Postgres) DB에 저장되어 여러 발신 계정이 공유하며, 같은 주제로는 같은 수신자에게 중복 발송되지 않습니다.

## 주요 기능
- 발신자 로그인: 등록된 Gmail 계정 + 구글 앱 비밀번호(DB에 저장하지 않음)
- 주제(캠페인)별 발송 상태 표시: 미발송 / 발송완료(누가, 언제) / 발송중 / 실패
- 중복 발송 차단: 발송 직전 DB에서 (주제, 수신자)를 선점, 이미 발송됐거나 다른 계정이 진행 중이면 건너뜀
- 발신자별 발송 내용(제목, 본문 전체) 저장 및 조회
- 주제별 / 발신 계정별 / 오늘 발송량 현황

## 설치
1. Supabase 프로젝트 생성 후 SQL Editor에서 `schema.sql` 실행
2. `schema.sql` 마지막 주석의 관리자 INSERT를 본인 Gmail로 바꿔 실행
3. `.streamlit/secrets.toml.example` 을 `.streamlit/secrets.toml` 로 복사하고 URL과 service_role 키 입력
   (배포 시에는 배포 환경의 Secrets에 동일하게 입력. 이 키는 GitHub에 올리지 마세요)
4. `pip install -r requirements.txt` 후 `streamlit run auto_em.py`

## 엑셀 형식
필수 열: `회사명`, `대표자명`, `이메일` / 선택 열: `산업분류`, `AI_판정`

## 파일
- `auto_em.py`: 앱 본체
- `db.py`: Supabase 접근 계층
- `schema.sql`: 테이블과 발송 선점 함수(`claim_send`)
