import streamlit as st
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import time
from datetime import datetime
import base64
import json

st.set_page_config(page_title="기업 이메일 발송 시스템", layout="wide")

st.title("📧 기업 맞춤형 이메일 발송 시스템")
st.markdown("엑셀 데이터를 업로드하고 **본문 문구 수정 및 이미지 삽입** 후 최종 완성본을 검토하여 발송합니다.")

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
        "image_align": "가운데"
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
        "image_align": "가운데"
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
        "image_align": "가운데"
    }
}

# ==========================================
# 1. 사이드바: Gmail 계정 및 발송 설정
# ==========================================
with st.sidebar:
    st.header("⚙️ Gmail 발신자 설정")
    sender_email = st.text_input("Gmail 주소", placeholder="example@gmail.com")
    sender_password = st.text_input("구글 앱 비밀번호 (16자리)", type="password", help="구글 계정 2단계 인증 후 발급받은 16자리 앱 비밀번호")
    sender_name = st.text_input("발신자 표시 이름", value="서영교 컨설턴트")
    send_delay = st.slider("메일 간 발송 지연(초)", min_value=1, max_value=10, value=3, help="스팸 차단 방지를 위한 권장 대기시간 (3~5초)")

# ==========================================
# 2. 메일 본문 및 이미지 편집 섹션
# ==========================================
st.subheader("📝 1. 메일 양식 편집 및 이미지 등록")

with st.expander("💡 사용 가능한 자동 치환 태그 안내 (클릭하여 열기)", expanded=False):
    st.markdown("""
    본문이나 제목에 아래 태그를 입력하면 엑셀의 각 행 데이터로 자동 변경됩니다:
    - `{회사명}` : (주)선샤인, 파미셀(주) 등
    - `{대표자명}` : 황대현, 김현수 등
    - `{산업분류}` : 호텔업, 의약품 제조업 등
    - `{AI_판정}` : A_우수, B_양호 등
    - `{발신자}` : 사이드바에 입력한 발신자 이름
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

    default_subject = "[{회사명}] {대표자명} 대표님께 드리는 기업 가업승계 및 세무 전략 안내"
    if "email_subject_template" not in st.session_state:
        st.session_state["email_subject_template"] = default_subject
    email_subject_template = st.text_input("메일 제목 템플릿", key="email_subject_template")

    st.caption("본문은 일반 텍스트, HTML, 또는 둘 다 함께 작성할 수 있습니다.")
    if "use_plain_text_body" not in st.session_state:
        st.session_state["use_plain_text_body"] = True
    if "use_html_body" not in st.session_state:
        st.session_state["use_html_body"] = False
    use_plain_text_body = st.checkbox("일반 텍스트 본문 사용", key="use_plain_text_body")
    use_html_body = st.checkbox("HTML 본문 사용", key="use_html_body")

    if "image_insert_mode" not in st.session_state:
        st.session_state["image_insert_mode"] = "본문 하단 첨부"
    if "image_width_pct" not in st.session_state:
        st.session_state["image_width_pct"] = 80
    if "image_align" not in st.session_state:
        st.session_state["image_align"] = "가운데"

    image_insert_mode = st.selectbox(
        "이미지 삽입 방식",
        ["본문 하단 첨부", "본문 중간 삽입 (마커: {이미지})"],
        index=["본문 하단 첨부", "본문 중간 삽입 (마커: {이미지})"].index(st.session_state["image_insert_mode"]),
        key="image_insert_mode",
        help="본문 중간에 넣고 싶다면 본문에 {이미지}를 입력해 주세요."
    )
    image_width_pct = st.slider("이미지 너비 비율(%)", min_value=20, max_value=100, value=st.session_state["image_width_pct"], step=5, key="image_width_pct")
    image_align = st.selectbox("이미지 정렬", ["가운데", "왼쪽", "오른쪽"], index=["가운데", "왼쪽", "오른쪽"].index(st.session_state["image_align"]), key="image_align")

    default_body = """안녕하십니까, {회사명} {대표자명} 대표님.
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
{발신자} 배상"""

    default_html_body = """<p>안녕하십니까, {회사명} {대표자명} 대표님.</p>
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
<p>감사합니다.<br>{발신자} 배상</p>"""

    if "email_body_template" not in st.session_state:
        st.session_state["email_body_template"] = default_body
    if "email_html_template" not in st.session_state:
        st.session_state["email_html_template"] = default_html_body

    email_body_template = st.text_area(
        "메일 본문 내용 (일반 텍스트 모드)",
        key="email_body_template",
        height=220,
        disabled=not use_plain_text_body,
        help="이미지를 본문 중간에 넣고 싶으면 {이미지}를 입력하세요."
    )
    email_html_template = st.text_area(
        "메일 본문 내용 (HTML 모드)",
        key="email_html_template",
        height=220,
        disabled=not use_html_body,
        help="HTML에서 이미지를 넣고 싶으면 {이미지}를 입력하세요."
    )

with col_temp2:
    st.write("🖼️ **본문 이미지 / 푸터 이미지 분리 첨부**")
    uploaded_body_image = st.file_uploader(
        "본문에 삽입할 이미지 (JPG, PNG)",
        type=["png", "jpg", "jpeg"]
    )
    uploaded_footer_image = st.file_uploader(
        "푸터에 삽입할 이미지 (JPG, PNG)",
        type=["png", "jpg", "jpeg"]
    )

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
        "푸터 문구 (텍스트)",
        value="감사합니다.\n{발신자}",
        height=120,
        help="푸터 하단에 들어갈 문구를 입력하세요. {발신자} 같은 치환 태그를 사용할 수 있습니다."
    )
    footer_html_template = st.text_area(
        "푸터 문구 (HTML)",
        value="<p>감사합니다.<br>{발신자}</p>",
        height=120,
        help="푸터에 HTML을 넣고 싶다면 여기에 작성하세요. {푸터이미지} 마커를 넣으면 푸터 이미지가 위치합니다."
    )
    footer_image_width_pct = st.slider("푸터 이미지 너비 비율(%)", min_value=20, max_value=100, value=60, step=5)
    footer_image_align = st.selectbox("푸터 이미지 정렬", ["가운데", "왼쪽", "오른쪽"], index=0)

# ==========================================
# 2-1. 구글 설문지 설정 (기존 링크 또는 API 생성)
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
                    create_body = {
                        "info": {
                            "title": form_title,
                            "documentTitle": form_title,
                            "description": form_description
                        }
                    }
                    form = service.forms().create(body=create_body).execute()
                    # API 반환값에서 formId 추출
                    form_name = form.get("name") or ""
                    form_id = form_name.split("/")[-1] if "/" in form_name else form.get("formId") or ""
                    if form_id:
                        form_url = f"https://docs.google.com/forms/d/e/{form_id}/viewform"
                    else:
                        # fallback: 일부 API 응답은 responderUri 제공
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

    # 이메일에 설문 포함 여부 (템플릿 내 치환태그를 사용하거나 직접 링크를 본문에 삽입)
    include_form = st.checkbox("이메일에 설문지 링크/버튼 포함", value=False, help="템플릿에 {구글설문링크} 또는 {구글설문버튼} 태그를 넣어 사용하세요.")
    st.session_state["include_google_form"] = include_form

st.markdown("---")

# ==========================================
# 3. 엑셀 업로드 및 대상 검토
# ==========================================
st.subheader("📂 2. 수신 대상 엑셀 업로드 및 검토")
uploaded_file = st.file_uploader("거래처 엑셀 파일(.xlsx)을 업로드하세요", type=["xlsx"])

def replace_email_placeholders(template, row, sender_nm):
    """메일 템플릿에서 자동 치환 태그를 실제 값으로 변환"""
    company = str(row.get("회사명", "대표님 회사")).strip()
    ceo = str(row.get("대표자명", "대표")).strip()
    industry = str(row.get("산업분류", "")).strip()
    rating = str(row.get("AI_판정", "")).strip()

    # 구글 설문 링크/버튼은 세션에 저장된 값을 사용
    form_url = ""
    try:
        form_url = st.session_state.get("google_form_url", "") or ""
    except Exception:
        form_url = ""

    form_button_html = ""
    if form_url:
        # 현재 위치의 가로 폭 기준 70%로 설정하고 가운데 정렬
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
        "{구글설문버튼}": form_button_html
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
        "오른쪽": "margin: 18px 0 18px auto; display: block;"
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

    body_sections = []
    if use_plain_text and body_tmpl:
        plain_body = replace_email_placeholders(body_tmpl, row, sender_nm)
        if has_body_image and image_insert_mode == "본문 중간 삽입 (마커: {이미지})":
            plain_body = plain_body.replace("{이미지}", build_image_tag(is_preview=is_preview, img_base64=body_img_base64, width_pct=image_width_pct, align=image_align, image_cid="body_image"))
        plain_body = plain_body.replace("\r\n", "\n")
        body_sections.append(f"<div style='white-space: pre-line;'>{plain_body.replace(chr(10), '<br>')}</div>")

    if use_html_body and html_tmpl:
        html_body = replace_email_placeholders(html_tmpl, row, sender_nm).strip()
        if has_body_image and image_insert_mode == "본문 중간 삽입 (마커: {이미지})":
            html_body = html_body.replace("{이미지}", build_image_tag(is_preview=is_preview, img_base64=body_img_base64, width_pct=image_width_pct, align=image_align, image_cid="body_image"))
        body_sections.append(html_body)

    if not body_sections:
        body_sections.append("<p>본문 내용이 비어 있습니다.</p>")

    body_html = "\n".join(body_sections)

    body_image_tag = ""
    if has_body_image:
        if image_insert_mode != "본문 중간 삽입 (마커: {이미지})" or ("{이미지}" not in str(body_tmpl) and "{이미지}" not in str(html_tmpl)):
            body_image_tag = f'<br>{build_image_tag(is_preview=is_preview, img_base64=body_img_base64, width_pct=image_width_pct, align=image_align, image_cid="body_image")}'

    # 템플릿에 구글 설문 태그가 없고 include_google_form 설정이 켜져 있으면 자동으로 본문 하단에 설문 링크/버튼을 추가
    try:
        include_form_flag = st.session_state.get("include_google_form", False)
        form_url_for_insert = st.session_state.get("google_form_url", "")
    except Exception:
        include_form_flag = False
        form_url_for_insert = ""

    form_block = ""
    if include_form_flag and form_url_for_insert:
        # 템플릿에 이미 태그가 있으면 중복 삽입하지 않음
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
    if not footer_html_content and not footer_text_tmpl and not footer_html_tmpl and not has_footer_image:
        footer_html_content = ""

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

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    # 이메일 유효성 검사
    df["유효이메일"] = df["이메일"].apply(lambda x: True if pd.notnull(x) and "@" in str(x) else False)
    valid_df = df[df["유효이메일"]].copy().reset_index(drop=True)
    invalid_count = len(df) - len(valid_df)

    st.success(f"총 {len(df)}개 업체 중 **발송 가능(이메일 보유): {len(valid_df)}건** (이메일 없음: {invalid_count}건 자동 제외)")
    valid_df.insert(0, "발송선택", True)

    tab_list, tab_preview = st.tabs(["📋 발송 명단 선택", "👁️ 최종 완성본 미리보기"])

    with tab_list:
        st.caption("발송을 원하지 않는 업체는 체크박스를 해제하세요.")
        edited_df = st.data_editor(
            valid_df[["발송선택", "회사명", "대표자명", "이메일", "산업분류", "AI_판정"]],
            disabled=["회사명", "대표자명", "이메일", "산업분류", "AI_판정"],
            hide_index=True,
            use_container_width=True
        )

    with tab_preview:
        target_company = st.selectbox("미리보기할 업체를 선택하세요:", valid_df["회사명"].tolist())
        if target_company:
            row_data = valid_df[valid_df["회사명"] == target_company].iloc[0]
            
            # 미리보기용 base64 인코딩
            b64_body_img = base64.b64encode(body_image_bytes).decode('utf-8') if body_image_bytes else None
            b64_footer_img = base64.b64encode(footer_image_bytes).decode('utf-8') if footer_image_bytes else None
            preview_subj, preview_html = build_email_html(
                row_data,
                email_subject_template,
                email_body_template,
                sender_name,
                html_tmpl=email_html_template,
                use_plain_text=use_plain_text_body,
                use_html_body=use_html_body,
                has_body_image=(body_image_bytes is not None),
                has_footer_image=(footer_image_bytes is not None),
                is_preview=True,
                body_img_base64=b64_body_img,
                footer_img_base64=b64_footer_img,
                image_insert_mode=image_insert_mode,
                image_width_pct=image_width_pct,
                image_align=image_align,
                footer_text_tmpl=footer_text_template,
                footer_html_tmpl=footer_html_template,
                footer_image_width_pct=footer_image_width_pct,
                footer_image_align=footer_image_align
            )

            st.markdown(f"**제목:** `{preview_subj}`")
            st.markdown(f"**받는사람:** `{row_data['이메일']}` ({row_data['대표자명']} 대표)")
            st.subheader("👀 전체 이메일 미리보기")
            st.components.v1.html(preview_html, height=550, scrolling=True)

    # ==========================================
    # 4. 발송 실행
    # ==========================================
    targets = edited_df[edited_df["발송선택"]]
    st.markdown("---")
    st.subheader(f"🚀 3. 최종 발송 실행 (대상: {len(targets)}개 업체)")

    if st.button("확인 완료 및 이메일 일괄 발송 시작", type="primary"):
        if not sender_email or not sender_password:
            st.error("좌측 사이드바에 Gmail 주소와 구글 16자리 앱 비밀번호를 입력해주세요.")
        elif len(targets) == 0:
            st.warning("선택된 발송 대상이 없습니다.")
        else:
            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(sender_email, sender_password)

                sent_count = 0
                for idx, (_, r) in enumerate(targets.iterrows()):
                    subj, html_content = build_email_html(
                        r,
                        email_subject_template,
                        email_body_template,
                        sender_name,
                        html_tmpl=email_html_template,
                        use_plain_text=use_plain_text_body,
                        use_html_body=use_html_body,
                        has_body_image=(body_image_bytes is not None),
                        has_footer_image=(footer_image_bytes is not None),
                        is_preview=False,
                        image_insert_mode=image_insert_mode,
                        image_width_pct=image_width_pct,
                        image_align=image_align,
                        footer_text_tmpl=footer_text_template,
                        footer_html_tmpl=footer_html_template,
                        footer_image_width_pct=footer_image_width_pct,
                        footer_image_align=footer_image_align
                    )

                    # MIME 구성 (본문 + 인라인 이미지 연결)
                    msg_root = MIMEMultipart("related")
                    msg_root["Subject"] = subj
                    msg_root["From"] = f"{sender_name} <{sender_email}>"
                    msg_root["To"] = r["이메일"]

                    # HTML 본문 파트
                    msg_alt = MIMEMultipart("alternative")
                    msg_root.attach(msg_alt)
                    msg_alt.attach(MIMEText(html_content, "html", "utf-8"))

                    # 본문 이미지 파트
                    if body_image_bytes:
                        body_img_part = MIMEImage(body_image_bytes)
                        body_img_part.add_header("Content-ID", "<body_image>")
                        body_img_part.add_header("Content-Disposition", "inline", filename=uploaded_body_image.name)
                        msg_root.attach(body_img_part)

                    # 푸터 이미지 파트
                    if footer_image_bytes:
                        footer_img_part = MIMEImage(footer_image_bytes)
                        footer_img_part.add_header("Content-ID", "<footer_image>")
                        footer_img_part.add_header("Content-Disposition", "inline", filename=uploaded_footer_image.name)
                        msg_root.attach(footer_img_part)

                    server.sendmail(sender_email, r["이메일"], msg_root.as_string())
                    sent_count += 1

                    # 진행 상태 업데이트
                    pct = (idx + 1) / len(targets)
                    progress_bar.progress(pct)
                    status_text.text(f"[{idx+1}/{len(targets)}] {r['회사명']} ({r['이메일']}) 전송 완료")
                    time.sleep(send_delay)

                server.quit()
                st.success(f"🎉 총 {sent_count}개 업체에 이메일 발송이 성공적으로 완료되었습니다!")

            except Exception as err:
                st.error(f"메일 발송 중 오류가 발생했습니다: {err}")