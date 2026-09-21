import base64
import hashlib
import json
import re
import smtplib
import time
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import streamlit as st

import db

st.set_page_config(page_title="기업 이메일 발송 시스템", layout="wide")

st.title("📧 기업 맞춤형 이메일 발송 시스템")
st.markdown("엑셀 데이터를 업로드하고 **본문 문구 수정 및 이미지 삽입** 후 최종 완성본을 검토하여 발송합니다.")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GMAIL_DAILY_LIMIT = 500

EMAIL_PRESETS = {
    "기본형": {
        "subject": "[{회사명}] {대표자명} 대표님께 드리는 기업 가업승계 및 세무 전략 안내",
        "plain_body": """안녕하십니까, {회사명} {대표자명} 대표님.

귀사의 무궁한 발전과 번영을 기원합니다.

급변하는 경영 환경 속에서 안정적인 기업 재무구조 확립과 가업승계 및 법인 세무 전략의 중요성이 커지고 있습니다.

{이미지}

저희는 {산업분류} 분야 우수 기업을 대상으로 다음과 같은 맞춤형 컨설팅을 제공하고 있습니다.

■ 주요 자문 분야

1. 가업승계 지원제도 및 증여·상속세 특례 검토

2. 가지급금 및 미처분이익잉여금 구조 개선

3. 법인 자금 운용 및 CEO 은퇴 자산 플랜

상세 자문 및 기초 분석 자료가 필요하시면 본 메일로 편하게 회신 주시기 바랍니다.

감사합니다.

{발신자} 배상""",
        "html_body": """<p>안녕하십니까, {회사명} {대표자명} 대표님.</p>
<p>귀사의 무궁한 발전과 번영을 기원합니다.</p>
<p>급변하는 경영 환경 속에서 안정적인 기업 재무구조 확립과 가업승계 및 법인 세무 전략의 중요성이 커지고 있습니다.</p>
{이미지}
<p><strong>저희는 {산업분류} 분야 우수 기업을 대상으로 다음과 같은 맞춤형 컨설팅을 제공하고 있습니다.</strong></p>
<ul>
<li>가업승계 지원제도 및 증여·상속세 특례 검토</li>
<li>가지급금 및 미처분이익잉여금 구조 개선</li>
<li>법인 자금 운용 및 CEO 은퇴 자산 플랜</li>
</ul>
<p>상세 자문 및 기초 분석 자료가 필요하시면 본 메일로 편하게 회신 주시기 바랍니다.</p>
<p>감사합니다.<br>{발신자} 배상</p>""",
        "use_plain_text": True,
        "use_html": False,
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 80,
        "image_align": "가운데",
    },
    "브로슈어형": {
        "subject": "[{회사명}] {대표자명} 대표님과 함께하는 기업 성장 전략 제안",
        "plain_body": """안녕하십니까, {회사명} {대표자명} 대표님.

최근 기업 환경 변화와 가업승계, 세무 전략의 중요성이 점점 더 커지고 있습니다.

{이미지}

저희는 {산업분류} 산업군별 맞춤형 전략 컨설팅을 통해 기업의 안정성과 성장 기반을 함께 설계하고 있습니다.

■ 핵심 제안

1. 법인 구조 및 세무 리스크 점검

2. 가업승계 시나리오 설계

3. 자금 운용 및 경영 안정화 수립

필요하시면 간단한 기업 현황 자료를 바탕으로 맞춤 상담을 진행드릴 수 있습니다.

감사합니다.

{발신자}""",
        "html_body": """<p>안녕하십니까, {회사명} {대표자명} 대표님.</p>
<p>최근 기업 환경 변화와 가업승계, 세무 전략의 중요성이 점점 더 커지고 있습니다.</p>
{이미지}
<p>저희는 {산업분류} 산업군별 맞춤형 전략 컨설팅을 통해 기업의 안정성과 성장 기반을 함께 설계하고 있습니다.</p>
<div style="background:#f7f7f7; padding:18px; border-radius:8px; margin:14px 0;">
<p><strong>■ 핵심 제안</strong></p>
<ul>
<li>법인 구조 및 세무 리스크 점검</li>
<li>가업승계 시나리오 설계</li>
<li>자금 운용 및 경영 안정화 수립</li>
</ul>
</div>
<p>필요하시면 간단한 기업 현황 자료를 바탕으로 맞춤 상담을 진행드릴 수 있습니다.</p>
<p>감사합니다.<br>{발신자}</p>""",
        "use_plain_text": True,
        "use_html": True,
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 75,
        "image_align": "가운데",
    },
    "간단 제안형": {
        "subject": "[{회사명}] {대표자명} 대표님께 드리는 간단한 제안 안내",
        "plain_body": """안녕하십니까, {회사명} {대표자명} 대표님.

바쁘신 와중에도 시간 내어 읽어주셔서 감사합니다.

{이미지}

저희는 {산업분류} 업종 기업을 대상으로 법인 구조, 세무, 자금 운용 측면에서 실질적인 개선 방안을 제안드리고 있습니다.

필요한 자료를 전달해주시면 빠르게 검토 후 맞춤형 상담을 제안드리겠습니다.

감사합니다.

{발신자}""",
        "html_body": """<p>안녕하십니까, {회사명} {대표자명} 대표님.</p>
<p>바쁘신 와중에도 시간 내어 읽어주셔서 감사합니다.</p>
{이미지}
<p>저희는 {산업분류} 업종 기업을 대상으로 법인 구조, 세무, 자금 운용 측면에서 실질적인 개선 방안을 제안드리고 있습니다.</p>
<p>필요한 자료를 전달해주시면 빠르게 검토 후 맞춤형 상담을 제안드리겠습니다.</p>
<p>감사합니다.<br>{발신자}</p>""",
        "use_plain_text": True,
        "use_html": True,
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 70,
        "image_align": "가운데",
    },
}

# ==========================================
# 0. 메일 생성 헬퍼
# ==========================================
def replace_email_placeholders(template, row, sender_nm):
    """메일 템플릿에서 자동 치환 태그를 실제 값으로 변환"""
    company = str(row.get("회사명", "대표님 회사")).strip()
    ceo = str(row.get("대표자명", "대표")).strip()
    industry = str(row.get("산업분류", "")).strip()
    rating = str(row.get("AI_판정", "")).strip()

    form_url = ""
    try:
        form_url = st.session_state.get("google_form_url", "") or ""
    except Exception:
        form_url = ""

    form_button_html = ""
    if form_url:
        form_button_html = (
            f'<div style="display:flex;justify-content:center;margin-top:12px;">'
            f'<a href="{form_url}" target="_blank" '
            f'style="display:block;width:70%;max-width:520px;margin:0 auto;background:#0b66c3;color:#fff;padding:12px 16px;border-radius:8px;text-align:center;text-decoration:none;font-weight:600;line-height:1.5;white-space:normal;box-sizing:border-box;">'
            f'참석자 좌석배치 및 사전준비를 위해<br>설문을 작성해 주세요.<br>'
            f'<span style="font-size:0.95em;">(이 버튼을 눌러서 작성해 주시면 됩니다)</span>'
            f'</a></div>'
        )

    replacements = {
        "{회사명}": company,
        "{대표자명}": ceo,
        "{산업분류}": industry,
        "{AI_판정}": rating,
        "{발신자}": sender_nm,
        "{구글설문링크}": form_url,
        "{구글설문버튼}": form_button_html,
    }
    rendered = str(template or "")
    for tag, val in replacements.items():
        rendered = rendered.replace(tag, val)
    return rendered


def build_image_tag(is_preview=False, img_base64=None, width_pct=80, align="가운데", image_cid="body_image"):
    """이미지 태그 생성 (본문/푸터별 cid 구분)"""
    img_src = f"cid:{image_cid}"
    if is_preview and img_base64:
        img_src = f"data:image/png;base64,{img_base64}"

    align_map = {
        "가운데": "margin: 18px auto; display: block;",
        "왼쪽": "margin: 18px 0; display: block;",
        "오른쪽": "margin: 18px 0 18px auto; display: block;",
    }
    style = (
        f"max-width: {width_pct}%; height: auto; border: 1px solid #ddd; border-radius: 4px; "
        f"{align_map.get(align, align_map['가운데'])};"
    )
    return f'<img src="{img_src}" style="{style}">'


def build_email_html(row, subject_tmpl, body_tmpl, sender_nm, html_tmpl="", use_plain_text=True, use_html_body=False,
                     has_body_image=False, has_footer_image=False, is_preview=False,
                     body_img_base64=None, footer_img_base64=None,
                     image_insert_mode="본문 하단 첨부", image_width_pct=80, image_align="가운데",
                     footer_text_tmpl="", footer_html_tmpl="", footer_image_width_pct=60, footer_image_align="가운데"):
    """본문/푸터 이미지를 별도로 반영한 최종 HTML 메일 생성"""
    subj = replace_email_placeholders(subject_tmpl, row, sender_nm)
    marker_mode = image_insert_mode == "본문 중간 삽입 (마커: {이미지})"

    body_sections = []
    if use_plain_text and body_tmpl:
        plain_body = replace_email_placeholders(body_tmpl, row, sender_nm)
        if has_body_image and marker_mode:
            plain_body = plain_body.replace("{이미지}", build_image_tag(is_preview=is_preview, img_base64=body_img_base64, width_pct=image_width_pct, align=image_align, image_cid="body_image"))
        plain_body = plain_body.replace("\r\n", "\n")
        body_sections.append(f"<div style='white-space: pre-line;'>{plain_body.replace(chr(10), '<br>')}</div>")

    if use_html_body and html_tmpl:
        html_body = replace_email_placeholders(html_tmpl, row, sender_nm).strip()
        if has_body_image and marker_mode:
            html_body = html_body.replace("{이미지}", build_image_tag(is_preview=is_preview, img_base64=body_img_base64, width_pct=image_width_pct, align=image_align, image_cid="body_image"))
        body_sections.append(html_body)

    if not body_sections:
        body_sections.append("<p>본문 내용이 비어 있습니다.</p>")

    body_html = "\n".join(body_sections)

    body_image_tag = ""
    if has_body_image:
        if not marker_mode or ("{이미지}" not in str(body_tmpl) and "{이미지}" not in str(html_tmpl)):
            body_image_tag = f'<br>{build_image_tag(is_preview=is_preview, img_base64=body_img_base64, width_pct=image_width_pct, align=image_align, image_cid="body_image")}'

    include_form_flag = st.session_state.get("include_google_form", False)
    form_url_for_insert = st.session_state.get("google_form_url", "")

    form_block = ""
    if include_form_flag and form_url_for_insert:
        if ("{구글설문링크}" not in str(body_tmpl) and "{구글설문버튼}" not in str(body_tmpl)
                and "{구글설문링크}" not in str(html_tmpl) and "{구글설문버튼}" not in str(html_tmpl)):
            form_block = (
                f'<div style="display:flex;justify-content:center;margin-top:18px;">'
                f'<a href="{form_url_for_insert}" target="_blank" '
                f'style="display:block;width:70%;max-width:520px;margin:0 auto;background:#0b66c3;color:#fff;padding:12px 16px;border-radius:8px;text-align:center;text-decoration:none;font-weight:600;line-height:1.5;white-space:normal;box-sizing:border-box;">'
                f'참석자 좌석배치 및 사전준비를 위해<br>설문을 작성해 주세요.<br>'
                f'<span style="font-size:0.95em;">(이 버튼을 눌러서 작성해 주시면 됩니다)</span>'
                f'</a></div>'
                f'<div style="display:flex;justify-content:center;margin-top:8px;color:#666;font-size:12px;">'
                f'<div style="width:70%;max-width:520px;margin:0 auto;text-align:center;line-height:1.5;">설문에 참여해주시면 감사하겠습니다.</div></div>'
            )

    footer_parts = []
    if footer_text_tmpl:
        footer_text = replace_email_placeholders(footer_text_tmpl, row, sender_nm)
        if has_footer_image and "{푸터이미지}" in footer_text:
            footer_text = footer_text.replace("{푸터이미지}", build_image_tag(is_preview=is_preview, img_base64=footer_img_base64, width_pct=footer_image_width_pct, align=footer_image_align, image_cid="footer_image"))
        footer_parts.append(f"<div style='white-space: pre-line; margin-top: 18px; color: #444;'>{footer_text.replace(chr(10), '<br>')}</div>")

    if footer_html_tmpl:
        footer_html = replace_email_placeholders(footer_html_tmpl, row, sender_nm).strip()
        if has_footer_image and "{푸터이미지}" in footer_html:
            footer_html = footer_html.replace("{푸터이미지}", build_image_tag(is_preview=is_preview, img_base64=footer_img_base64, width_pct=footer_image_width_pct, align=footer_image_align, image_cid="footer_image"))
        footer_parts.append(footer_html)

    if has_footer_image and "{푸터이미지}" not in str(footer_text_tmpl) and "{푸터이미지}" not in str(footer_html_tmpl):
        footer_parts.append(f'<div style="margin-top: 22px;">{build_image_tag(is_preview=is_preview, img_base64=footer_img_base64, width_pct=footer_image_width_pct, align=footer_image_align, image_cid="footer_image")}</div>')

    footer_html_content = "\n".join(footer_parts)

    full_html = f"""
<html>
<body style="font-family: 'Malgun Gothic', Arial, sans-serif; line-height: 1.7; color: #222; font-size: 14px;">
<div style="max-width: 650px; margin: 0 auto; padding: 20px; border: 1px solid #eee; border-radius: 6px;">
{body_html}
{body_image_tag}
{form_block}
{footer_html_content}
</div>
</body>
</html>
"""
    return subj, full_html


def smtp_connect(email, password):
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    server.starttls()
    server.login(email, password)
    return server


def fmt_kst(ts):
    try:
        return pd.to_datetime(ts, utc=True).tz_convert("Asia/Seoul").strftime("%m-%d %H:%M")
    except Exception:
        return "-"


def status_of(log):
    """(코드, 화면 표시용 문구)"""
    if not log:
        return "none", "⚪ 미발송"
    who = log.get("sender_name") or log.get("sender_email")
    s = log["status"]
    if s == "sent":
        return "sent", f"✅ 발송완료 · {who} · {fmt_kst(log.get('sent_at'))}"
    if s == "pending":
        return "pending", f"⏳ 발송중 · {who}"
    return "failed", "❌ 실패 (재발송 가능)"


# ==========================================
# 1. DB 연결 확인 + 로그인(발신자 입력 = 로그인)
# ==========================================
if not db.secrets_ok():
    st.error("Turso 접속 정보가 없습니다. `.streamlit/secrets.toml`(또는 배포 환경의 Secrets)에 [turso] 항목을 설정하세요.")
    st.code('[turso]\nurl = "libsql://데이터베이스이름-조직.turso.io"\nauth_token = "토큰"\nadmin_email = "본인@gmail.com"', language="toml")
    st.stop()

try:
    db.init()  # 테이블 자동 생성 + 관리자 계정 등록 (프로세스당 1회)
except Exception as e:
    st.error(f"Turso DB 초기화에 실패했습니다: {e}")
    st.stop()

if "auth" not in st.session_state:
    st.subheader("🔐 발신자 로그인")
    st.caption("등록된 발신 계정만 사용할 수 있습니다. 구글 앱 비밀번호는 로그인 확인과 발송에만 쓰이며 DB에 저장되지 않습니다.")
    try:
        if db.count_senders() == 0:
            st.warning("등록된 발신 계정이 없습니다. secrets의 [turso] admin_email에 본인 Gmail을 넣고 다시 실행하세요.")
    except Exception:
        pass
    with st.form("login_form"):
        login_email = st.text_input("Gmail 주소", placeholder="example@gmail.com")
        login_pw = st.text_input("구글 앱 비밀번호 (16자리)", type="password",
                                 help="구글 계정 2단계 인증 후 발급받은 16자리 앱 비밀번호")
        login_name = st.text_input("발신자 표시 이름 (선택, 비우면 등록된 이름 사용)")
        submitted = st.form_submit_button("로그인", type="primary")

    if submitted:
        email = login_email.strip().lower()
        pw = login_pw.replace(" ", "").strip()
        if not email or not pw:
            st.error("Gmail 주소와 앱 비밀번호를 모두 입력해 주세요.")
        else:
            try:
                sender = db.get_sender(email)
            except Exception as e:
                sender = None
                st.error(f"DB 연결 오류: {e}")
            else:
                if not sender or not sender.get("is_active"):
                    st.error("등록되지 않았거나 비활성화된 발신 계정입니다. 관리자에게 등록을 요청하세요.")
                else:
                    try:
                        test = smtp_connect(email, pw)
                        test.quit()
                    except smtplib.SMTPAuthenticationError:
                        st.error("Gmail 인증에 실패했습니다. 앱 비밀번호를 확인해 주세요.")
                    except Exception as e:
                        st.error(f"Gmail 접속 오류: {e}")
                    else:
                        st.session_state["auth"] = {
                            "email": email,
                            "password": pw,
                            "name": login_name.strip() or sender.get("display_name") or email,
                            "is_admin": bool(sender.get("is_admin")),
                        }
                        st.rerun()
    st.stop()

auth = st.session_state["auth"]
sender_email = auth["email"]
sender_name = auth["name"]
sender_password = auth["password"]

with st.sidebar:
    st.header("⚙️ 발신자")
    st.success(f"{sender_name}\n\n{sender_email}")
    try:
        today_cnt = db.sent_today_by_sender().get(sender_email, 0)
        st.caption(f"오늘 이 계정 발송: {today_cnt} / {GMAIL_DAILY_LIMIT}건 (Gmail 일반 계정 한도 기준)")
    except Exception:
        pass
    send_delay = st.slider("메일 간 발송 지연(초)", min_value=1, max_value=10, value=3,
                           help="스팸 차단 방지를 위한 권장 대기시간 (3~5초)")
    if st.button("로그아웃", use_container_width=True):
        for k in ("auth", "synced_hash", "recipient_ids", "last_send_result"):
            st.session_state.pop(k, None)
        st.rerun()

    if auth["is_admin"]:
        with st.expander("👑 발신 계정 관리 (관리자)"):
            try:
                st.dataframe(pd.DataFrame(db.list_senders())[["email", "display_name", "is_active", "is_admin"]],
                             hide_index=True, use_container_width=True)
            except Exception:
                st.caption("등록된 계정이 없습니다.")
            with st.form("sender_admin_form", clear_on_submit=True):
                adm_email = st.text_input("Gmail 주소")
                adm_name = st.text_input("표시 이름")
                adm_active = st.checkbox("활성", value=True)
                adm_admin = st.checkbox("관리자", value=False)
                if st.form_submit_button("등록 / 수정"):
                    if EMAIL_RE.match(adm_email.strip()):
                        db.upsert_sender(adm_email, adm_name, adm_admin, adm_active)
                        st.success("저장했습니다.")
                        st.rerun()
                    else:
                        st.error("올바른 이메일 형식이 아닙니다.")

# ==========================================
# 2. 발송 주제 선택 (중복발송 판단의 기준)
# ==========================================
st.subheader("🏷️ 0. 발송 주제 선택")
st.caption("같은 주제로는 같은 수신자에게 한 번만 발송됩니다. 다른 주제는 다시 발송할 수 있습니다.")

try:
    topics = db.list_topics()
except Exception as e:
    st.error(f"주제를 불러오지 못했습니다: {e}")
    st.stop()

topic_names = {t["id"]: t["name"] for t in topics}


def _create_topic_cb():
    name = st.session_state.get("new_topic_name", "").strip()
    if not name:
        return
    try:
        st.session_state["topic_id_sel"] = db.create_topic(name, sender_email)
        st.session_state["new_topic_name"] = ""
    except Exception as e:
        st.session_state["topic_error"] = str(e)


col_t1, col_t2 = st.columns([1, 1])
with col_t1:
    if topics:
        topic_id = st.selectbox("주제", options=list(topic_names.keys()),
                                format_func=lambda i: topic_names[i], key="topic_id_sel")
    else:
        topic_id = None
        st.info("아직 주제가 없습니다. 오른쪽에서 새 주제를 만들어 주세요.")
with col_t2:
    st.text_input("새 주제 이름", key="new_topic_name", placeholder="예: 2026 세제개편 세미나 초청")
    st.button("주제 추가", on_click=_create_topic_cb)
    if st.session_state.get("topic_error"):
        st.error(st.session_state.pop("topic_error"))

st.markdown("---")

# ==========================================
# 3. 메일 본문 및 이미지 편집 섹션
# ==========================================
st.subheader("📝 1. 메일 양식 편집 및 이미지 등록")

with st.expander("💡 사용 가능한 자동 치환 태그 안내 (클릭하여 열기)", expanded=False):
    st.markdown("""
본문이나 제목에 아래 태그를 입력하면 엑셀의 각 행 데이터로 자동 변경됩니다:
- `{회사명}` : (주)선샤인, 파미셀(주) 등
- `{대표자명}` : 황대현, 김현수 등
- `{산업분류}` : 호텔업, 의약품 제조업 등
- `{AI_판정}` : A_우수, B_양호 등
- `{발신자}` : 로그인한 발신자 표시 이름
- `{구글설문링크}` : 이메일에 삽입할 Google Forms 링크
- `{구글설문버튼}` : 클릭 가능한 설문 참여 버튼(HTML 전용)
""")

col_temp1, col_temp2 = st.columns([1.2, 0.8])

with col_temp1:
    st.caption("기본 레이아웃을 바로 적용하거나, 본문을 직접 수정해 사용하세요.")
    preset_name = st.selectbox("메일 템플릿 프리셋", list(EMAIL_PRESETS.keys()), index=0)

    if st.button("선택 템플릿 적용", use_container_width=True):
        preset = EMAIL_PRESETS[preset_name]
        st.session_state["email_subject_template"] = preset["subject"]
        st.session_state["email_body_template"] = preset["plain_body"]
        st.session_state["email_html_template"] = preset["html_body"]
        st.session_state["use_plain_text_body"] = preset["use_plain_text"]
        st.session_state["use_html_body"] = preset["use_html"]
        st.session_state["image_insert_mode"] = preset["image_insert_mode"]
        st.session_state["image_width_pct"] = preset["image_width_pct"]
        st.session_state["image_align"] = preset["image_align"]

    # 기본값은 '기본형' 프리셋을 그대로 사용 (중복 정의 제거)
    _base = EMAIL_PRESETS["기본형"]
    st.session_state.setdefault("email_subject_template", _base["subject"])
    st.session_state.setdefault("email_body_template", _base["plain_body"])
    st.session_state.setdefault("email_html_template", _base["html_body"])
    st.session_state.setdefault("use_plain_text_body", True)
    st.session_state.setdefault("use_html_body", False)
    st.session_state.setdefault("image_insert_mode", "본문 하단 첨부")
    st.session_state.setdefault("image_width_pct", 80)
    st.session_state.setdefault("image_align", "가운데")

    email_subject_template = st.text_input("메일 제목 템플릿", key="email_subject_template")

    st.caption("본문은 일반 텍스트, HTML, 또는 둘 다 함께 작성할 수 있습니다.")
    use_plain_text_body = st.checkbox("일반 텍스트 본문 사용", key="use_plain_text_body")
    use_html_body = st.checkbox("HTML 본문 사용", key="use_html_body")

    insert_modes = ["본문 하단 첨부", "본문 중간 삽입 (마커: {이미지})"]
    image_insert_mode = st.selectbox(
        "이미지 삽입 방식", insert_modes,
        key="image_insert_mode",
        help="본문 중간에 넣고 싶다면 본문에 {이미지}를 입력해 주세요.",
    )
    image_width_pct = st.slider("이미지 너비 비율(%)", min_value=20, max_value=100,
                                step=5, key="image_width_pct")
    aligns = ["가운데", "왼쪽", "오른쪽"]
    image_align = st.selectbox("이미지 정렬", aligns, key="image_align")

    email_body_template = st.text_area(
        "메일 본문 내용 (일반 텍스트 모드)", key="email_body_template", height=220,
        disabled=not use_plain_text_body,
        help="이미지를 본문 중간에 넣고 싶으면 {이미지}를 입력하세요.")
    email_html_template = st.text_area(
        "메일 본문 내용 (HTML 모드)", key="email_html_template", height=220,
        disabled=not use_html_body,
        help="HTML에서 이미지를 넣고 싶으면 {이미지}를 입력하세요.")

with col_temp2:
    st.write("🖼️ **본문 이미지 / 푸터 이미지 분리 첨부**")
    uploaded_body_image = st.file_uploader("본문에 삽입할 이미지 (JPG, PNG)", type=["png", "jpg", "jpeg"])
    uploaded_footer_image = st.file_uploader("푸터에 삽입할 이미지 (JPG, PNG)", type=["png", "jpg", "jpeg"])

    body_image_bytes = None
    if uploaded_body_image:
        body_image_bytes = uploaded_body_image.getvalue()
        st.image(body_image_bytes, caption="본문 이미지 미리보기", use_container_width=True)

    footer_image_bytes = None
    if uploaded_footer_image:
        footer_image_bytes = uploaded_footer_image.getvalue()
        st.image(footer_image_bytes, caption="푸터 이미지 미리보기", use_container_width=True)

    if not (uploaded_body_image or uploaded_footer_image):
        st.info("이미지 없이 텍스트만 보내실 수도 있습니다.")

    footer_text_template = st.text_area(
        "푸터 문구 (텍스트)", value="감사합니다.\n{발신자}", height=120,
        help="푸터 하단에 들어갈 문구를 입력하세요. {발신자} 같은 치환 태그를 사용할 수 있습니다.")
    footer_html_template = st.text_area(
        "푸터 문구 (HTML)", value="<p>감사합니다.<br>{발신자}</p>", height=120,
        help="푸터에 HTML을 넣고 싶다면 여기에 작성하세요. {푸터이미지} 마커를 넣으면 푸터 이미지가 위치합니다.")
    footer_image_width_pct = st.slider("푸터 이미지 너비 비율(%)", min_value=20, max_value=100, value=60, step=5)
    footer_image_align = st.selectbox("푸터 이미지 정렬", ["가운데", "왼쪽", "오른쪽"], index=0)

# ==========================================
# 3-1. 구글 설문지 설정 (기존 링크 또는 API 생성)
# ==========================================
st.subheader("📝 1-1. 구글 설문지 설정 (선택)")

with st.expander("구글 설문지 설정(기존 링크 사용 또는 새 폼 생성)", expanded=False):
    form_mode = st.radio("설문지 선택 방식:", ["기존 설문지 링크 사용", "새 설문지 생성 (Google Forms API 사용, 선택 사항)"], index=0)

    if form_mode == "기존 설문지 링크 사용":
        form_url_input = st.text_input("기존 Google Forms 링크를 입력하세요 (예: https://docs.google.com/forms/...)", key="google_form_input")
        if form_url_input:
            st.session_state["google_form_url"] = form_url_input.strip()
            st.success("설문지 링크가 저장되었습니다.")
    else:
        st.info("Google Forms API를 통해 새 설문지를 생성하려면 서비스 계정 JSON 파일이 필요합니다.")
        uploaded_cred = st.file_uploader("서비스 계정 JSON 업로드 (선택)", type=["json"], key="forms_cred")
        form_title = st.text_input("신규 설문지 제목", value="[삼성금융네트웍스] 2026 세제개편 대응 가업승계 세미나 신청서")
        form_description = st.text_area("설문지 설명 (선택)", value="참석 신청을 위한 간단한 사전문항입니다.")

        if st.button("새 설문지 생성 (API 호출)"):
            if not uploaded_cred:
                st.error("서비스 계정 JSON 파일을 업로드해 주세요.")
            else:
                try:
                    from google.oauth2 import service_account
                    from googleapiclient.discovery import build

                    cred_json = json.loads(uploaded_cred.getvalue().decode("utf-8"))
                    scopes = ["https://www.googleapis.com/auth/forms.body", "https://www.googleapis.com/auth/drive"]
                    creds = service_account.Credentials.from_service_account_info(cred_json, scopes=scopes)
                    service = build("forms", "v1", credentials=creds)

                    create_body = {"info": {"title": form_title, "documentTitle": form_title, "description": form_description}}
                    form = service.forms().create(body=create_body).execute()

                    form_name = form.get("name") or ""
                    form_id = form_name.split("/")[-1] if "/" in form_name else form.get("formId") or ""

                    if form_id:
                        form_url = f"https://docs.google.com/forms/d/e/{form_id}/viewform"
                    else:
                        form_url = form.get("responderUri") or ""

                    if form_url:
                        st.session_state["google_form_url"] = form_url
                        st.success("설문지가 생성되어 링크가 저장되었습니다.")
                        st.write(form_url)
                    else:
                        st.error("생성된 설문지의 링크를 확인할 수 없습니다. API 응답을 확인하세요.")
                except ImportError:
                    st.error("google-api-python-client 및 google-auth 라이브러리가 필요합니다. `pip install google-api-python-client google-auth` 를 실행하세요.")
                except Exception as e:
                    st.error(f"설문지 생성 중 오류가 발생했습니다: {e}")

    include_form = st.checkbox("이메일에 설문지 링크/버튼 포함", value=False,
                               help="템플릿에 {구글설문링크} 또는 {구글설문버튼} 태그를 넣어 사용하세요.")
    st.session_state["include_google_form"] = include_form

st.markdown("---")

# ==========================================
# 4. 엑셀 업로드 → DB 반영 → 주제별 상태 표시
# ==========================================
st.subheader("📂 2. 수신 대상 엑셀 업로드 및 검토")
uploaded_file = st.file_uploader("거래처 엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx"])

tab_list, tab_preview, tab_dash, tab_hist = st.tabs(
    ["📋 발송 명단 선택", "👁️ 최종 완성본 미리보기", "📊 주제별 현황", "📨 발송 내역"])

view_df = None
edited_df = None
valid_df = None

with tab_list:
    if not uploaded_file:
        st.info("엑셀 파일을 업로드하면 주제별 발송 여부가 함께 표시됩니다.")
    elif topic_id is None:
        st.warning("먼저 위에서 발송 주제를 선택하거나 만들어 주세요.")
    else:
        df = pd.read_excel(uploaded_file)
        missing_cols = [c for c in ("회사명", "대표자명", "이메일") if c not in df.columns]
        if missing_cols:
            st.error(f"엑셀에 필수 열이 없습니다: {', '.join(missing_cols)}")
            st.stop()
        for c in ("산업분류", "AI_판정"):
            if c not in df.columns:
                df[c] = ""
        df = df.fillna("")
        df["이메일"] = df["이메일"].astype(str).str.strip().str.lower()

        mask_valid = df["이메일"].apply(lambda x: bool(EMAIL_RE.match(x)))
        valid_all = df[mask_valid]
        valid_df = valid_all.drop_duplicates(subset="이메일").reset_index(drop=True)
        dup_count = len(valid_all) - len(valid_df)
        invalid_count = len(df) - len(valid_all)

        st.success(f"총 {len(df)}개 중 **발송 가능: {len(valid_df)}건** "
                   f"(이메일 없음/형식 오류 {invalid_count}건, 엑셀 내 중복 {dup_count}건 자동 제외)")

        # 엑셀 → recipients 반영 (파일이 바뀔 때만)
        file_hash = hashlib.md5(uploaded_file.getvalue()).hexdigest()
        if st.session_state.get("synced_hash") != file_hash:
            try:
                with st.spinner("수신자 정보를 DB에 반영하는 중..."):
                    st.session_state["recipient_ids"] = db.upsert_recipients(valid_df)
                st.session_state["synced_hash"] = file_hash
            except Exception as e:
                st.error(f"DB 반영 중 오류가 발생했습니다: {e}")
                st.stop()
        id_map = st.session_state["recipient_ids"]

        try:
            logs = db.topic_status(topic_id)
        except Exception as e:
            st.error(f"발송 기록을 불러오지 못했습니다: {e}")
            st.stop()

        valid_df["recipient_id"] = valid_df["이메일"].map(id_map)
        coded = valid_df["recipient_id"].map(lambda rid: status_of(logs.get(rid)))
        valid_df["_code"] = coded.map(lambda x: x[0])
        valid_df["상태"] = coded.map(lambda x: x[1])
        valid_df["발송선택"] = valid_df["_code"].isin(["none", "failed"])

        counts = valid_df["_code"].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("미발송", int(counts.get("none", 0)))
        c2.metric("발송완료", int(counts.get("sent", 0)))
        c3.metric("발송중", int(counts.get("pending", 0)))
        c4.metric("실패", int(counts.get("failed", 0)))

        flt = st.radio("보기", ["전체", "미발송", "발송완료", "실패/발송중"], horizontal=True)
        if flt == "미발송":
            view_df = valid_df[valid_df["_code"] == "none"]
        elif flt == "발송완료":
            view_df = valid_df[valid_df["_code"] == "sent"]
        elif flt == "실패/발송중":
            view_df = valid_df[valid_df["_code"].isin(["failed", "pending"])]
        else:
            view_df = valid_df

        st.caption("기본으로 미발송·실패 건만 체크됩니다. 이미 발송된 건은 체크해도 발송 시 자동으로 건너뜁니다.")
        cols = ["발송선택", "상태", "회사명", "대표자명", "이메일", "산업분류", "AI_판정"]
        edited_df = st.data_editor(
            view_df[cols],
            disabled=[c for c in cols if c != "발송선택"],
            hide_index=True,
            use_container_width=True,
        )

with tab_preview:
    if valid_df is None or valid_df.empty:
        st.info("엑셀을 업로드하고 주제를 선택하면 미리보기를 볼 수 있습니다.")
    else:
        pick = st.selectbox(
            "미리보기할 업체를 선택하세요:", options=list(valid_df.index),
            format_func=lambda i: f"{valid_df.loc[i, '회사명']} ({valid_df.loc[i, '이메일']})")
        row_data = valid_df.loc[pick]

        b64_body_img = base64.b64encode(body_image_bytes).decode("utf-8") if body_image_bytes else None
        b64_footer_img = base64.b64encode(footer_image_bytes).decode("utf-8") if footer_image_bytes else None

        preview_subj, preview_html = build_email_html(
            row_data, email_subject_template, email_body_template, sender_name,
            html_tmpl=email_html_template,
            use_plain_text=use_plain_text_body, use_html_body=use_html_body,
            has_body_image=(body_image_bytes is not None),
            has_footer_image=(footer_image_bytes is not None),
            is_preview=True,
            body_img_base64=b64_body_img, footer_img_base64=b64_footer_img,
            image_insert_mode=image_insert_mode, image_width_pct=image_width_pct, image_align=image_align,
            footer_text_tmpl=footer_text_template, footer_html_tmpl=footer_html_template,
            footer_image_width_pct=footer_image_width_pct, footer_image_align=footer_image_align,
        )
        st.markdown(f"**제목:** `{preview_subj}`")
        st.markdown(f"**받는사람:** `{row_data['이메일']}` ({row_data['대표자명']} 대표)")
        st.markdown(f"**상태:** {row_data['상태']}")
        st.subheader("👀 전체 이메일 미리보기")
        st.components.v1.html(preview_html, height=550, scrolling=True)

with tab_dash:
    try:
        total_rcp = db.count_recipients()
        log_rows = db.all_log_lite()
        today_by_sender = db.sent_today_by_sender()
    except Exception as e:
        st.error(f"현황을 불러오지 못했습니다: {e}")
        log_rows, total_rcp, today_by_sender = [], 0, {}

    st.metric("DB에 등록된 전체 수신자", total_rcp)

    if not topics:
        st.info("아직 주제가 없습니다.")
    else:
        ldf = pd.DataFrame(log_rows, columns=["id", "topic_id", "status", "sender_email"])
        pivot = (ldf.pivot_table(index="topic_id", columns="status", values="id", aggfunc="count", fill_value=0)
                 if not ldf.empty else pd.DataFrame())
        for c in ("sent", "pending", "failed"):
            if c not in pivot.columns:
                pivot[c] = 0
        pivot = pivot.reindex([t["id"] for t in topics], fill_value=0)
        pivot["미발송"] = (total_rcp - pivot[["sent", "pending", "failed"]].sum(axis=1)).clip(lower=0)
        summary = pivot[["sent", "pending", "failed", "미발송"]].astype(int)
        summary.columns = ["발송완료", "발송중", "실패", "미발송"]
        summary.index = [topic_names[i] for i in summary.index]
        summary.index.name = "주제"
        st.markdown("**주제별 발송 현황** (미발송 = 전체 수신자 − 기록된 건수)")
        st.dataframe(summary, use_container_width=True)

        if topic_id is not None and not ldf.empty:
            cur = ldf[ldf["topic_id"] == topic_id]
            if not cur.empty:
                st.markdown(f"**「{topic_names[topic_id]}」 발신 계정별 현황**")
                by_sender = cur.pivot_table(index="sender_email", columns="status", values="id",
                                            aggfunc="count", fill_value=0)
                st.dataframe(by_sender, use_container_width=True)

    if today_by_sender:
        st.markdown("**오늘 발신 계정별 발송량**")
        st.dataframe(pd.DataFrame({"오늘 발송": pd.Series(today_by_sender)}), use_container_width=True)

with tab_hist:
    if topic_id is None:
        st.info("주제를 선택해 주세요.")
    else:
        scope = st.radio("보기", ["내 발송", "전체"], horizontal=True, key="hist_scope")
        try:
            details = db.log_detail(topic_id, sender_email if scope == "내 발송" else None)
        except Exception as e:
            details = []
            st.error(f"발송 내역을 불러오지 못했습니다: {e}")
        if not details:
            st.info("발송 내역이 없습니다.")
        else:
            table = pd.DataFrame([{
                "시각": fmt_kst(d.get("sent_at") or d.get("claimed_at")),
                "발신자": d.get("sender_name") or d.get("sender_email"),
                "수신 회사": (d.get("recipients") or {}).get("company"),
                "수신 이메일": (d.get("recipients") or {}).get("email"),
                "상태": d.get("status"),
                "제목": d.get("subject"),
                "오류": d.get("error"),
            } for d in details])
            st.dataframe(table, hide_index=True, use_container_width=True)

            sent_rows = [d for d in details if d.get("status") == "sent"]
            if sent_rows:
                sel = st.selectbox(
                    "발송된 본문 보기", options=[d["id"] for d in sent_rows],
                    format_func=lambda i: next(
                        f"{(d.get('recipients') or {}).get('company')} · {fmt_kst(d.get('sent_at'))}"
                        for d in sent_rows if d["id"] == i))
                if st.button("본문 불러오기"):
                    st.components.v1.html(db.get_body(sel), height=500, scrolling=True)

# ==========================================
# 5. 발송 실행
# ==========================================
if edited_df is not None and view_df is not None:
    selected_idx = edited_df.index[edited_df["발송선택"]]
    targets = view_df.loc[selected_idx]

    st.markdown("---")
    st.subheader(f"🚀 3. 최종 발송 실행 (주제: {topic_names[topic_id]} / 선택: {len(targets)}건)")

    last = st.session_state.get("last_send_result")
    if last:
        msg = f"직전 발송 결과 — 성공 {last['sent']}건 · 건너뜀(이미 발송/진행 중) {last['skipped']}건 · 실패 {last['failed']}건"
        (st.warning if last["failed"] or last.get("aborted") else st.success)(msg)
        if last.get("aborted"):
            st.error(f"중단 사유: {last['aborted']}")
        if last["errors"]:
            with st.expander("실패 상세"):
                for line in last["errors"]:
                    st.write(line)

    if st.button("확인 완료 및 이메일 일괄 발송 시작", type="primary"):
        if len(targets) == 0:
            st.warning("선택된 발송 대상이 없습니다.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()
            sent_n = failed_n = skipped_n = 0
            errors = []
            aborted = None
            total = len(targets)

            try:
                server = smtp_connect(sender_email, sender_password)
            except Exception as err:
                st.error(f"Gmail 접속에 실패했습니다: {err}")
                st.stop()

            for idx, (_, r) in enumerate(targets.iterrows()):
                progress_bar.progress(idx / total)
                label = f"[{idx + 1}/{total}] {r['회사명']} ({r['이메일']})"

                # 1) 발송 권한 선점 (이미 발송/진행 중이면 None → 건너뜀)
                try:
                    log_id = db.claim_send(topic_id, int(r["recipient_id"]), sender_email, sender_name)
                except Exception as err:
                    aborted = f"DB 오류: {err}"
                    break
                if log_id is None:
                    skipped_n += 1
                    status_text.text(f"{label} 이미 발송됐거나 다른 계정이 진행 중 → 건너뜀")
                    continue

                # 2) 메일 생성 및 발송
                try:
                    subj, html_content = build_email_html(
                        r, email_subject_template, email_body_template, sender_name,
                        html_tmpl=email_html_template,
                        use_plain_text=use_plain_text_body, use_html_body=use_html_body,
                        has_body_image=(body_image_bytes is not None),
                        has_footer_image=(footer_image_bytes is not None),
                        is_preview=False,
                        image_insert_mode=image_insert_mode, image_width_pct=image_width_pct, image_align=image_align,
                        footer_text_tmpl=footer_text_template, footer_html_tmpl=footer_html_template,
                        footer_image_width_pct=footer_image_width_pct, footer_image_align=footer_image_align,
                    )

                    msg_root = MIMEMultipart("related")
                    msg_root["Subject"] = subj
                    msg_root["From"] = f"{sender_name} <{sender_email}>"
                    msg_root["To"] = r["이메일"]

                    msg_alt = MIMEMultipart("alternative")
                    msg_root.attach(msg_alt)
                    msg_alt.attach(MIMEText(html_content, "html", "utf-8"))

                    if body_image_bytes:
                        part = MIMEImage(body_image_bytes)
                        part.add_header("Content-ID", "<body_image>")
                        part.add_header("Content-Disposition", "inline", filename=uploaded_body_image.name)
                        msg_root.attach(part)
                    if footer_image_bytes:
                        part = MIMEImage(footer_image_bytes)
                        part.add_header("Content-ID", "<footer_image>")
                        part.add_header("Content-Disposition", "inline", filename=uploaded_footer_image.name)
                        msg_root.attach(part)

                    try:
                        server.sendmail(sender_email, r["이메일"], msg_root.as_string())
                    except smtplib.SMTPServerDisconnected:
                        server = smtp_connect(sender_email, sender_password)
                        server.sendmail(sender_email, r["이메일"], msg_root.as_string())
                except Exception as err:
                    failed_n += 1
                    errors.append(f"{r['회사명']} ({r['이메일']}): {err}")
                    try:
                        db.mark_failed(log_id, str(err))
                    except Exception:
                        pass
                    status_text.text(f"{label} 실패: {err}")
                    if isinstance(err, smtplib.SMTPAuthenticationError):
                        aborted = "Gmail 인증 오류로 발송을 중단했습니다."
                        break
                    continue

                # 3) 발송 성공 기록 (제목/본문 전문 저장)
                try:
                    db.mark_sent(log_id, subj, html_content)
                except Exception as err:
                    errors.append(f"{r['회사명']}: 메일은 발송됐지만 기록 저장에 실패했습니다 ({err})")
                sent_n += 1
                status_text.text(f"{label} 전송 완료")
                time.sleep(send_delay)

            try:
                server.quit()
            except Exception:
                pass
            progress_bar.progress(1.0)

            st.session_state["last_send_result"] = {
                "sent": sent_n, "skipped": skipped_n, "failed": failed_n,
                "errors": errors, "aborted": aborted,
            }
            st.rerun()
