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

# 구글 앱 비밀번호는 정해진 16자리를 그대로 넣어야 하므로, 브라우저가 새 비밀번호로
# 오인해 "안전한 비밀번호 제안"을 띄우지 않도록 autocomplete 속성을 보정합니다.
# (Streamlit의 text_input은 이 속성을 직접 지정할 방법이 없어 스크립트로 보정)
st.iframe(
    """
    <script>
    (function () {
      function fixAutocomplete() {
        var doc = window.parent.document;
        doc.querySelectorAll('input[type="password"]').forEach(function (el) {
          if (el.getAttribute('autocomplete') !== 'current-password') {
            el.setAttribute('autocomplete', 'current-password');
          }
        });
        doc.querySelectorAll('input[aria-label="Gmail 주소"]').forEach(function (el) {
          if (el.getAttribute('autocomplete') !== 'username') {
            el.setAttribute('autocomplete', 'username');
          }
        });
      }
      fixAutocomplete();
      new MutationObserver(fixAutocomplete).observe(window.parent.document.body, {
        childList: true, subtree: true,
      });

      // 셀렉트박스/라디오 등을 고르면(예: 변수 삽입, 템플릿 선택) 그 값이
      // 다른 입력창(제목/본문 등)에 프로그램적으로 반영되면서, 사용자가
      // 직접 탭하지 않은 그 입력창으로 포커스가 넘어가 모바일 키보드가
      // 갑자기 뜨는 현상을 막습니다. 실제로 손가락/클릭이 닿은 요소로
      // 옮겨가는 포커스만 허용하고, 나머지는 즉시 블러 처리합니다.
      var lastPointerTarget = null;
      var allowKeyboardFocus = false;
      doc.addEventListener('pointerdown', function (e) { lastPointerTarget = e.target; }, true);
      doc.addEventListener('keydown', function (e) {
        if (e.key === 'Tab') allowKeyboardFocus = true;
      }, true);
      doc.addEventListener('focusin', function (e) {
        var el = e.target;
        var tag = el.tagName;
        var textTypes = ['text', 'password', 'search', 'email', 'url', 'tel', ''];
        var isTextField = tag === 'TEXTAREA' || (tag === 'INPUT' && textTypes.indexOf(el.type) !== -1);
        if (!isTextField) return;
        if (allowKeyboardFocus) { allowKeyboardFocus = false; return; }
        if (lastPointerTarget && el.contains(lastPointerTarget)) return;
        el.blur();
      }, true);
    })();
    </script>
    """,
    height=1,
)

st.markdown("""
<style>
/* 전체 여백·타이포 */
.block-container { padding-top: 3.4rem !important; padding-bottom: 2rem !important; max-width: 1400px; }
h1, h2, h3 { letter-spacing: -0.02em; }
div[data-testid="stVerticalBlock"] > div { gap: 0.35rem; }

/* 헤더 바 */
.app-header {
  background: #ffffff;
  color: #0f172a;
  padding: 14px 22px;
  border: 1px solid #e2e8f0;
  border-left: 5px solid #2563eb;
  border-radius: 12px;
  margin-bottom: 18px;
  display: flex;
  align-items: baseline;
  gap: 14px;
}
.app-header h1 {
  font-size: 1.25rem; margin: 0; padding: 0; font-weight: 700; color: #0f172a;
}
.app-header span { font-size: 0.85rem; color: #64748b; }

/* 카드: st.container(border=True, key="card_...") */
[class*="st-key-card_"] {
  background: #ffffff;
  border-radius: 12px !important;
  box-shadow: 0 1px 2px rgba(15,23,42,.04);
}
.dash-card-title {
  font-size: 0.85rem;
  font-weight: 650;
  color: #64748b;
  margin-bottom: 8px;
}
.preview-meta {
  font-size: 0.8rem;
  color: #475569;
  margin-bottom: 8px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}

/* 탭 */
div[data-baseweb="tab-list"] {
  gap: 4px;
  background: #f1f5f9;
  padding: 4px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}
button[data-baseweb="tab"] {
  border-radius: 8px !important;
  font-weight: 550 !important;
  font-size: 0.9rem !important;
  padding: 6px 14px !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
  background: #fff !important;
  box-shadow: 0 1px 3px rgba(15,23,42,.1);
  color: #0f172a !important;
}

/* 입력 밀도 */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea,
div[data-testid="stSelectbox"] > div {
  border-radius: 8px !important;
}
div[data-testid="stRadio"] > label {
  font-size: 0.85rem;
}

/* 사이드바 */
section[data-testid="stSidebar"] {
  background: #f8fafc;
}
section[data-testid="stSidebar"] .block-container {
  padding-top: 1.5rem;
}

/* 전체 재실행 시 흰 화면 깜빡임 완화 */
.stApp, .stApp > header { background: #f8fafc !important; }
[data-testid="stStatusWidget"] {
  visibility: hidden;
  height: 0;
  position: fixed;
}
div[data-testid="stDecoration"] { display: none; }
/* 위젯 전환 시 부드러운 유지 */
.block-container { transition: none !important; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="app-header"><h1>기업 이메일 발송 시스템</h1>'
    '<span>맞춤 메일 작성 · 중복 발송 방지 · 다중 계정</span></div>',
    unsafe_allow_html=True,
)

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
        "use_plain_text": False,
        "use_html": True,
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
        "use_plain_text": False,
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
        "use_plain_text": False,
        "use_html": True,
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 70,
        "image_align": "가운데",
    },
}

BODY_MODE_LABELS = {"html": "HTML", "text": "텍스트", "both": "HTML + 텍스트"}
FOOTER_MODE_LABELS = {"text": "텍스트", "image": "이미지", "none": "사용 안 함"}

VAR_CHIPS = [
    ("회사명", "{회사명}"),
    ("대표자명", "{대표자명}"),
    ("산업분류", "{산업분류}"),
    ("AI판정", "{AI_판정}"),
    ("발신자", "{발신자}"),
    ("이미지", "{이미지}"),
    ("설문링크", "{구글설문링크}"),
    ("설문버튼", "{구글설문버튼}"),
]

SAMPLE_ROW = {
    "회사명": "샘플기업", "대표자명": "홍길동", "산업분류": "제조업",
    "AI_판정": "A", "이메일": "sample@example.com",
}

# 아무것도 고르거나 입력하지 않은 빈 칸에 회색으로 보여줄 기본 예시.
# placeholder로도 쓰고, 미리보기가 빈 칸을 채울 때도 이 값을 그대로 쓴다.
_EXAMPLE_PRESET = EMAIL_PRESETS["기본형"]
EXAMPLE_SUBJECT = _EXAMPLE_PRESET["subject"]
EXAMPLE_PLAIN_BODY = _EXAMPLE_PRESET["plain_body"]
EXAMPLE_HTML_BODY = _EXAMPLE_PRESET["html_body"]
EXAMPLE_FOOTER_TEXT = "감사합니다.\n{발신자}"

# 템플릿 드롭다운의 첫 항목: 아무 템플릿도 적용하지 않고 직접 쓰는 상태
NO_TEMPLATE = "직접 작성"


def apply_preset(preset_name: str, custom: dict = None):
    """내장/사용자 템플릿을 session_state에 반영"""
    if custom:
        st.session_state["email_subject_template"] = custom.get("subject") or ""
        st.session_state["email_body_template"] = custom.get("plain_body") or ""
        st.session_state["email_html_template"] = custom.get("html_body") or ""
        st.session_state["body_mode"] = custom.get("body_mode") or "html"
        st.session_state["image_insert_mode"] = custom.get("image_insert_mode") or "본문 하단 첨부"
        st.session_state["image_width_pct"] = int(custom.get("image_width_pct") or 80)
        st.session_state["image_align"] = custom.get("image_align") or "가운데"
        st.session_state["active_preset"] = preset_name
        return
    preset = EMAIL_PRESETS.get(preset_name) or EMAIL_PRESETS["기본형"]
    st.session_state["email_subject_template"] = preset["subject"]
    st.session_state["email_body_template"] = preset["plain_body"]
    st.session_state["email_html_template"] = preset["html_body"]
    if preset.get("use_html") and preset.get("use_plain_text"):
        st.session_state["body_mode"] = "both"
    elif preset.get("use_plain_text"):
        st.session_state["body_mode"] = "text"
    else:
        st.session_state["body_mode"] = "html"
    st.session_state["image_insert_mode"] = preset["image_insert_mode"]
    st.session_state["image_width_pct"] = preset["image_width_pct"]
    st.session_state["image_align"] = preset["image_align"]
    st.session_state["active_preset"] = preset_name


def clear_compose_fields():
    """아무 템플릿도 선택하지 않은 '직접 작성' 상태로 되돌린다 (빈 칸 + 회색 예시)."""
    st.session_state["email_subject_template"] = ""
    st.session_state["email_body_template"] = ""
    st.session_state["email_html_template"] = ""
    st.session_state["active_preset"] = NO_TEMPLATE


def _append_to_field(field_key: str, text: str):
    st.session_state[field_key] = (st.session_state.get(field_key) or "") + text


def render_var_insert(target_key: str, widget_key: str = None):
    """변수 삽입: 드롭다운에서 고르면 해당 필드 끝에 태그 추가"""
    wk = widget_key or f"var_ins_{target_key}"
    labels = ["변수 삽입…"] + [n for n, _ in VAR_CHIPS]
    tag_map = {n: t for n, t in VAR_CHIPS}

    def _on_pick():
        sel = st.session_state.get(wk)
        if sel and sel != "변수 삽입…" and sel in tag_map:
            _append_to_field(target_key, tag_map[sel])
            st.session_state[wk] = "변수 삽입…"

    st.selectbox(
        "변수",
        labels,
        key=wk,
        on_change=_on_pick,
        label_visibility="collapsed",
    )

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


def build_plain_text(row, body_tmpl, footer_text_tmpl, sender_nm):
    """multipart/alternative의 text/plain 파트용 순수 텍스트 본문"""
    def _fill(t):
        t = str(t or "").replace("{구글설문버튼}", "{구글설문링크}")
        t = t.replace("{이미지}", "").replace("{푸터이미지}", "")
        return replace_email_placeholders(t, row, sender_nm).replace("\r\n", "\n").strip()

    parts = [_fill(body_tmpl)]
    form_url = ""
    if st.session_state.get("include_google_form"):
        form_url = st.session_state.get("google_form_url", "") or ""
    if form_url and form_url not in parts[0]:
        parts.append(f"설문 링크: {form_url}")
    footer = _fill(footer_text_tmpl)
    if footer:
        parts.append(footer)
    return "\n\n".join(x for x in parts if x)


def build_email_html(row, subject_tmpl, body_tmpl, sender_nm, html_tmpl="", use_plain_text=True, use_html_body=False,
                     has_body_image=False, has_footer_image=False, is_preview=False,
                     body_img_base64=None, footer_img_base64=None,
                     image_insert_mode="본문 하단 첨부", image_width_pct=80, image_align="가운데",
                     footer_text_tmpl="", footer_html_tmpl="", footer_image_width_pct=60, footer_image_align="가운데"):
    """본문/푸터 이미지를 별도로 반영한 최종 HTML 메일 생성"""
    subj = replace_email_placeholders(subject_tmpl, row, sender_nm)
    marker_mode = image_insert_mode == "본문 중간 삽입 (마커: {이미지})"
    if not has_body_image:
        # 이미지를 쓰지 않을 땐 마커 글자가 본문에 그대로 남지 않게 지운다.
        body_tmpl = (body_tmpl or "").replace("{이미지}", "")
        html_tmpl = (html_tmpl or "").replace("{이미지}", "")
    if not has_footer_image:
        footer_text_tmpl = (footer_text_tmpl or "").replace("{푸터이미지}", "")
        footer_html_tmpl = (footer_html_tmpl or "").replace("{푸터이미지}", "")

    body_sections = []
    if use_plain_text and body_tmpl and not (use_html_body and html_tmpl):
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
    st.caption("🔎 " + db.diagnose())
    st.stop()

if "auth" not in st.session_state:
    st.subheader("발신자 로그인")
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
    st.header("발신자")
    st.success(sender_email if sender_name == sender_email else f"{sender_name}\n\n{sender_email}")
    try:
        today_cnt = db.sent_today_by_sender().get(sender_email, 0)
        st.caption(f"오늘 이 계정 발송: {today_cnt} / {GMAIL_DAILY_LIMIT}건 (Gmail 일반 계정 한도 기준)")
    except Exception:
        pass
    send_delay = st.slider("메일 간 발송 지연(초)", min_value=1, max_value=10, value=3,
                           help="스팸 차단 방지를 위한 권장 대기시간 (3~5초)")
    if st.button("로그아웃", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("_") or k in (
                "auth", "synced_hash", "recipient_ids", "last_send_result",
                "saved_footer_image_b64", "saved_footer_image_name",
            ):
                st.session_state.pop(k, None)
        st.rerun()

    if auth["is_admin"]:
        with st.expander("발신 계정 관리 (관리자)"):
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
# 발신자 기본 설정 로드 (1회)
# ==========================================
if not st.session_state.get("_prefs_loaded"):
    try:
        prefs = db.get_sender_prefs(sender_email)
    except Exception:
        prefs = {}
    _base = EMAIL_PRESETS["기본형"]
    st.session_state.setdefault("email_subject_template", _base["subject"])
    st.session_state.setdefault("email_body_template", _base["plain_body"])
    st.session_state.setdefault("email_html_template", _base["html_body"])
    st.session_state.setdefault("body_mode", prefs.get("body_mode") or "html")
    _fm = prefs.get("footer_mode") or "text"
    if _fm in ("html", "both"):
        _fm = "text"
    st.session_state.setdefault("footer_mode", _fm)
    st.session_state.setdefault("footer_text_template", prefs.get("footer_text") or "감사합니다.\n{발신자}")
    st.session_state.setdefault("footer_html_template", "")
    st.session_state.setdefault("use_body_image", False)
    st.session_state.setdefault("use_footer_image", bool(prefs.get("use_footer_image")))
    st.session_state.setdefault("image_insert_mode", "본문 하단 첨부")
    st.session_state.setdefault("image_width_pct", 80)
    st.session_state.setdefault("image_align", "가운데")
    st.session_state.setdefault("footer_image_width_pct", int(prefs.get("footer_image_width") or 60))
    st.session_state.setdefault("footer_image_align", prefs.get("footer_image_align") or "가운데")
    st.session_state.setdefault("active_preset", "기본형")
    if prefs.get("footer_image_b64") and not st.session_state.get("saved_footer_image_b64"):
        st.session_state["saved_footer_image_b64"] = prefs["footer_image_b64"]
        st.session_state["saved_footer_image_name"] = prefs.get("footer_image_name") or "footer.png"
        if prefs.get("use_footer_image"):
            st.session_state["use_footer_image"] = True
    st.session_state["_prefs_loaded"] = True

# 사이드바: 내 기본 설정 저장
with st.sidebar:
    with st.expander("내 기본 설정", expanded=False):
        st.caption("푸터·본문 방식 등을 계정별로 저장해 다음 로그인 시 자동 적용합니다.")
        if st.button("현재 설정을 기본값으로 저장", use_container_width=True):
            try:
                img_b64 = st.session_state.get("saved_footer_image_b64")
                img_name = st.session_state.get("saved_footer_image_name")
                # 업로드된 푸터가 있으면 그걸 저장
                if st.session_state.get("_footer_bytes_for_save"):
                    img_b64 = base64.b64encode(st.session_state["_footer_bytes_for_save"]).decode("utf-8")
                    img_name = st.session_state.get("_footer_name_for_save") or "footer.png"
                    st.session_state["saved_footer_image_b64"] = img_b64
                    st.session_state["saved_footer_image_name"] = img_name
                db.save_sender_prefs(sender_email, {
                    "body_mode": st.session_state.get("body_mode", "html"),
                    "footer_mode": st.session_state.get("footer_mode", "html"),
                    "footer_text": st.session_state.get("footer_text_template"),
                    "footer_html": st.session_state.get("footer_html_template"),
                    "footer_image_b64": img_b64,
                    "footer_image_name": img_name,
                    "footer_image_width": st.session_state.get("footer_image_width_pct", 60),
                    "footer_image_align": st.session_state.get("footer_image_align", "가운데"),
                    "use_footer_image": st.session_state.get("use_footer_image", False),
                })
                st.success("저장했습니다.")
            except Exception as e:
                st.error(f"저장 실패: {e}")
        if st.session_state.get("saved_footer_image_b64"):
            st.caption(f"저장된 푸터 이미지: {st.session_state.get('saved_footer_image_name', 'footer')}")
            if st.button("저장된 푸터 이미지 삭제", use_container_width=True):
                st.session_state.pop("saved_footer_image_b64", None)
                st.session_state.pop("saved_footer_image_name", None)
                try:
                    db.save_sender_prefs(sender_email, {
                        "body_mode": st.session_state.get("body_mode", "html"),
                        "footer_mode": st.session_state.get("footer_mode", "html"),
                        "footer_text": st.session_state.get("footer_text_template"),
                        "footer_html": st.session_state.get("footer_html_template"),
                        "footer_image_b64": None,
                        "footer_image_name": None,
                        "footer_image_width": st.session_state.get("footer_image_width_pct", 60),
                        "footer_image_align": st.session_state.get("footer_image_align", "가운데"),
                        "use_footer_image": False,
                    })
                except Exception:
                    pass
                st.rerun()

# ==========================================
# 주제 / 템플릿 데이터
# ==========================================
try:
    topics = db.list_topics()
except Exception as e:
    st.error(f"주제를 불러오지 못했습니다: {e}")
    st.stop()

topic_names = {t["id"]: t["name"] for t in topics}
topic_presets = {t["id"]: t.get("default_preset") for t in topics}
# 템플릿은 주제별로 따로 저장되므로, 어느 주제가 선택됐는지 알아야 목록을
# 정할 수 있다 -> 아래 _compose_and_preview() 안에서 topic_id가 정해진
# 뒤에 db.list_mail_templates(sender_email, topic_id)로 그때 불러온다.


def _on_new_topic():
    name = (st.session_state.get("new_topic_name") or "").strip()
    if not name:
        return
    try:
        tid = db.create_topic(name, sender_email)
        st.session_state["topic_id_sel"] = tid
        st.session_state["show_new_topic_form"] = False
        clear_compose_fields()
        st.session_state["_last_topic_for_preset"] = tid
    except Exception as e:
        st.session_state["topic_error"] = str(e)
        return
    # 새 주제 목록은 이 함수 바깥(전체 스크립트 상단)에서 한 번만 불러오므로,
    # 이 안에서 끝내면(기본 fragment 전용 재실행) 방금 만든 주제가 선택 목록에
    # 아직 안 보인다. 전체를 다시 실행해 목록을 최신으로 갱신한다.
    st.rerun()


def _on_template_change():
    sel = st.session_state.get("template_picker")
    if not sel or sel == NO_TEMPLATE:
        clear_compose_fields()
        return
    tid = st.session_state.get("topic_id_sel")
    if sel.startswith("★ ") and tid is not None:
        try:
            custom = db.get_mail_template(sender_email, tid, sel[2:])
            if custom:
                apply_preset(sel, custom=custom)
        except Exception:
            pass
    elif sel in EMAIL_PRESETS:
        apply_preset(sel)
    if tid is not None:
        try:
            db.set_topic_preset(tid, sel if not sel.startswith("★ ") else sel[2:])
        except Exception:
            pass


# ==========================================
# 좌측 편집 | 우측 미리보기  (fragment: 옵션 변경 시 이 영역만 갱신)
# ==========================================
def _compose_and_preview():
    left, right = st.columns([1, 1], gap="large")

    with left:
        # ---- 주제 선택 ----
        with st.container(border=True, key="card_topic"):
            t1, t2, t3 = st.columns([2.6, 0.5, 0.5])
            with t1:
                if topics:
                    topic_id = st.selectbox(
                        "주제 선택", options=list(topic_names.keys()),
                        format_func=lambda i: topic_names[i], key="topic_id_sel")
                else:
                    topic_id = None
                    st.caption("아직 주제가 없습니다. 오른쪽 + 버튼으로 만들어 주세요.")
                # 이 영역은 fragment라 주제만 바꿔도 아래 명단/현황은 예전 주제 기준으로 남는다.
                # 주제가 바뀌면 앱 전체를 다시 실행해 명단·상태·발송 대상을 함께 갱신한다.
                _prev_topic = st.session_state.get("_topic_seen")
                st.session_state["_topic_seen"] = topic_id
                if _prev_topic is not None and _prev_topic != topic_id:
                    st.rerun(scope="app")
            with t2:
                st.markdown('<div style="height:1.6em;"></div>', unsafe_allow_html=True)
                if st.button(":material/add:", key="add_topic_btn", help="새 주제 만들기", use_container_width=True):
                    st.session_state["show_new_topic_form"] = not st.session_state.get("show_new_topic_form", False)
            with t3:
                st.markdown('<div style="height:1.6em;"></div>', unsafe_allow_html=True)
                if topic_id is not None:
                    if st.button(":material/delete:", key="del_topic_btn", help="이 주제 삭제", use_container_width=True):
                        try:
                            if db.topic_has_send_history(topic_id):
                                st.session_state["topic_delete_blocked"] = topic_id
                                st.session_state.pop("confirm_delete_topic", None)
                            else:
                                st.session_state["confirm_delete_topic"] = topic_id
                                st.session_state.pop("topic_delete_blocked", None)
                        except Exception as e:
                            st.error(f"확인 실패: {e}")

            if st.session_state.get("show_new_topic_form"):
                n1, n2, n3 = st.columns([2.6, 0.5, 0.5])
                with n1:
                    st.text_input("새 주제 이름", key="new_topic_name",
                                  placeholder="예: 2026 세제개편 세미나 초청",
                                  label_visibility="collapsed")
                with n2:
                    # 주제 선택 selectbox가 이 버튼보다 먼저 그려지므로, 여기서
                    # 곧장 함수를 부르면(같은 실행 안에서) 그 selectbox의
                    # session_state를 더는 못 바꾼다 -> on_click 콜백으로 등록해
                    # 다음 실행이 시작되기 전(위젯이 그려지기 전)에 처리되게 한다.
                    st.button("확인", key="confirm_new_topic", use_container_width=True,
                             on_click=_on_new_topic)
                with n3:
                    if st.button("취소", key="cancel_new_topic", use_container_width=True):
                        st.session_state["show_new_topic_form"] = False
                        st.rerun()

            if st.session_state.get("topic_delete_blocked") == topic_id and topic_id is not None:
                st.error("이미 발송 기록이 있는 주제는 삭제할 수 없습니다. 발송 내역은 그대로 보존됩니다.")
                if st.button("확인", key="ack_topic_delete_blocked"):
                    st.session_state.pop("topic_delete_blocked", None)
                    st.rerun()
            elif st.session_state.get("confirm_delete_topic") == topic_id and topic_id is not None:
                st.warning(f"「{topic_names[topic_id]}」 주제와 그 안의 템플릿을 삭제할까요? 되돌릴 수 없습니다.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("삭제", key="confirm_del_topic", type="primary", use_container_width=True):
                        try:
                            db.delete_topic(topic_id)
                            st.session_state.pop("confirm_delete_topic", None)
                            st.session_state.pop("topic_id_sel", None)
                            st.session_state.pop("_last_topic_for_preset", None)
                            st.rerun()
                        except ValueError as e:
                            st.session_state.pop("confirm_delete_topic", None)
                            st.session_state["topic_delete_blocked"] = topic_id
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")
                with c2:
                    if st.button("취소", key="cancel_del_topic", use_container_width=True):
                        st.session_state.pop("confirm_delete_topic", None)
                        st.rerun()
            if st.session_state.get("topic_error"):
                st.error(st.session_state.pop("topic_error"))

        # 이 주제에 연결된 기본 템플릿을 이 주제로 처음 들어왔을 때 한 번 적용
        if topic_id is not None:
            linked = topic_presets.get(topic_id)
            last_applied = st.session_state.get("_last_topic_for_preset")
            if last_applied != topic_id:
                if linked in EMAIL_PRESETS:
                    apply_preset(linked)
                elif linked:
                    custom = db.get_mail_template(sender_email, topic_id, linked)
                    if custom:
                        apply_preset(f"★ {linked}", custom=custom)
                    else:
                        clear_compose_fields()
                else:
                    clear_compose_fields()
                st.session_state["_last_topic_for_preset"] = topic_id

        # ---- 템플릿 선택 (주제별로 따로 저장됨) ----
        if topic_id is not None:
            try:
                user_tmpls = db.list_mail_templates(sender_email, topic_id)
            except Exception:
                user_tmpls = []
        else:
            user_tmpls = []
        user_tmpl_names = [t["name"] for t in user_tmpls]
        all_tmpl_opts = [NO_TEMPLATE] + list(EMAIL_PRESETS.keys()) + [f"★ {n}" for n in user_tmpl_names]

        with st.container(border=True, key="card_template"):

            cur = st.session_state.get("active_preset", NO_TEMPLATE)
            if cur not in all_tmpl_opts:
                cur = NO_TEMPLATE
            is_user_tmpl = cur.startswith("★ ")
            # selectbox는 key가 한 번 쓰이고 나면 index= 인자를 매번 무시하고 이전
            # 선택값을 그대로 유지하므로, 템플릿 저장/삭제 등으로 active_preset이
            # 바뀐 경우 위젯 값을 직접 맞춰줘야 드롭다운에도 바로 반영된다.
            st.session_state["template_picker"] = cur
            c_tmpl, c_add, c_del = st.columns([2.6, 0.5, 0.5])
            with c_tmpl:
                st.selectbox(
                    "템플릿 선택", all_tmpl_opts,
                    key="template_picker", on_change=_on_template_change)
            with c_add:
                st.markdown('<div style="height:1.6em;"></div>', unsafe_allow_html=True)
                if st.button(":material/add:", key="add_tmpl_btn", help="현재 내용을 새 템플릿으로 저장",
                             use_container_width=True, disabled=topic_id is None):
                    st.session_state["show_new_tmpl_form"] = not st.session_state.get("show_new_tmpl_form", False)
            with c_del:
                st.markdown('<div style="height:1.6em;"></div>', unsafe_allow_html=True)
                if is_user_tmpl:
                    if st.button(":material/delete:", key="del_tmpl_btn", help="이 템플릿 삭제",
                                 use_container_width=True):
                        st.session_state["confirm_delete_tmpl"] = cur

            if st.session_state.get("show_new_tmpl_form") and topic_id is not None:
                m1, m2, m3 = st.columns([2.6, 0.5, 0.5])
                with m1:
                    st.text_input("새 템플릿 이름", key="new_tmpl_name",
                                  placeholder="예: 세미나 초청", label_visibility="collapsed")
                with m2:
                    if st.button("확인", key="confirm_new_tmpl", use_container_width=True):
                        tname = (st.session_state.get("new_tmpl_name") or "").strip()
                        if tname:
                            try:
                                db.save_mail_template(sender_email, topic_id, tname, {
                                    "subject": st.session_state.get("email_subject_template"),
                                    "body_mode": st.session_state.get("body_mode", "html"),
                                    "plain_body": st.session_state.get("email_body_template"),
                                    "html_body": st.session_state.get("email_html_template"),
                                    "image_insert_mode": st.session_state.get("image_insert_mode"),
                                    "image_width_pct": st.session_state.get("image_width_pct", 80),
                                    "image_align": st.session_state.get("image_align", "가운데"),
                                })
                                st.session_state["active_preset"] = f"★ {tname}"
                                st.session_state["show_new_tmpl_form"] = False
                                st.rerun()
                            except Exception as e:
                                st.error(f"저장 실패: {e}")
                        else:
                            st.warning("이름을 입력하세요.")
                with m3:
                    if st.button("취소", key="cancel_new_tmpl", use_container_width=True):
                        st.session_state["show_new_tmpl_form"] = False
                        st.rerun()

            if st.session_state.get("confirm_delete_tmpl") == cur and is_user_tmpl and topic_id is not None:
                st.warning(f"「{cur[2:]}」 템플릿을 삭제할까요? 되돌릴 수 없습니다.")
                d1, d2 = st.columns(2)
                with d1:
                    if st.button("삭제", key="confirm_del_tmpl", type="primary", use_container_width=True):
                        try:
                            db.delete_mail_template(sender_email, topic_id, cur[2:])
                            st.session_state.pop("confirm_delete_tmpl", None)
                            clear_compose_fields()
                            st.rerun()
                        except Exception as e:
                            st.error(f"삭제 실패: {e}")
                with d2:
                    if st.button("취소", key="cancel_del_tmpl", use_container_width=True):
                        st.session_state.pop("confirm_delete_tmpl", None)
                        st.rerun()

            with st.container(height=560, border=False):
                s1, s2 = st.columns([4, 1.2])
                with s1:
                    email_subject_template = st.text_input(
                        "제목", key="email_subject_template", label_visibility="collapsed",
                        placeholder=EXAMPLE_SUBJECT)
                with s2:
                    render_var_insert("email_subject_template", "var_subj")

                tab_body, tab_footer, tab_form = st.tabs(["본문", "푸터", "설문지"])

                with tab_body:
                    body_mode = st.radio(
                        "형식", list(BODY_MODE_LABELS.keys()),
                        format_func=lambda k: BODY_MODE_LABELS[k],
                        horizontal=True, key="body_mode", label_visibility="collapsed")
                    use_plain_text_body = body_mode in ("text", "both")
                    use_html_body = body_mode in ("html", "both")
                    email_body_template = st.session_state.get("email_body_template", "")
                    email_html_template = st.session_state.get("email_html_template", "")

                    if use_plain_text_body:
                        v1, v2 = st.columns([5, 1.3])
                        with v2:
                            render_var_insert("email_body_template", "var_body_txt")
                        with v1:
                            st.caption("텍스트 본문")
                        email_body_template = st.text_area(
                            "텍스트 본문", key="email_body_template", height=160, label_visibility="collapsed",
                            placeholder=EXAMPLE_PLAIN_BODY)
                    if use_html_body:
                        v1, v2 = st.columns([5, 1.3])
                        with v2:
                            render_var_insert("email_html_template", "var_body_html")
                        with v1:
                            st.caption("HTML 본문")
                        email_html_template = st.text_area(
                            "HTML 본문", key="email_html_template", height=160, label_visibility="collapsed",
                            placeholder=EXAMPLE_HTML_BODY)

                    st.toggle("본문 이미지", key="use_body_image")
                    use_body_image = st.session_state.get("use_body_image", False)
                    image_insert_mode = st.session_state.get("image_insert_mode", "본문 하단 첨부")
                    image_width_pct = st.session_state.get("image_width_pct", 80)
                    image_align = st.session_state.get("image_align", "가운데")
                    uploaded_body_image = None
                    body_image_bytes = None

                    if use_body_image:
                        # 이미지는 오른쪽 미리보기에서 바로 보이므로, 여기서는 파일만
                        # 받고 화면에 다시 보여주지 않는다. 실제 위치(본문 중간의
                        # {이미지} 자리 또는 본문 하단)는 발송/미리보기를 만들 때 정해진다.
                        uploaded_body_image = st.file_uploader(
                            "이미지 파일", type=["png", "jpg", "jpeg"], key="body_img_uploader")
                        if uploaded_body_image:
                            body_image_bytes = uploaded_body_image.getvalue()
                        ic1, ic2, ic3 = st.columns(3)
                        with ic1:
                            image_insert_mode = st.selectbox(
                                "삽입", ["본문 하단 첨부", "본문 중간 삽입 (마커: {이미지})"],
                                key="image_insert_mode")
                        with ic2:
                            image_width_pct = st.slider("너비%", 20, 100, step=5, key="image_width_pct")
                        with ic3:
                            image_align = st.selectbox("정렬", ["가운데", "왼쪽", "오른쪽"], key="image_align")

                with tab_footer:
                    footer_mode = st.radio(
                        "푸터", list(FOOTER_MODE_LABELS.keys()),
                        format_func=lambda k: FOOTER_MODE_LABELS[k],
                        horizontal=True, key="footer_mode", label_visibility="collapsed")
                    footer_text_template = ""
                    footer_html_template = ""
                    use_footer_image = False
                    uploaded_footer_image = None
                    footer_image_bytes = None
                    footer_image_width_pct = st.session_state.get("footer_image_width_pct", 60)
                    footer_image_align = st.session_state.get("footer_image_align", "가운데")

                    if footer_mode == "text":
                        fv1, fv2 = st.columns([5, 1.3])
                        with fv2:
                            render_var_insert("footer_text_template", "var_footer")
                        with fv1:
                            st.caption("푸터 텍스트")
                        footer_text_template = st.text_area(
                            "푸터 텍스트", key="footer_text_template", height=90, label_visibility="collapsed",
                            placeholder=EXAMPLE_FOOTER_TEXT)
                        st.session_state["use_footer_image"] = False
                    elif footer_mode == "image":
                        st.session_state["use_footer_image"] = True
                        use_footer_image = True
                        if st.session_state.get("saved_footer_image_b64") and not st.session_state.get("_footer_upload_override"):
                            try:
                                footer_image_bytes = base64.b64decode(st.session_state["saved_footer_image_b64"])
                                st.caption(f"기본 이미지: {st.session_state.get('saved_footer_image_name', '')}")
                            except Exception:
                                footer_image_bytes = None
                        uploaded_footer_image = st.file_uploader(
                            "푸터 이미지", type=["png", "jpg", "jpeg"], key="footer_img_uploader")
                        if uploaded_footer_image:
                            footer_image_bytes = uploaded_footer_image.getvalue()
                            st.session_state["_footer_bytes_for_save"] = footer_image_bytes
                            st.session_state["_footer_name_for_save"] = uploaded_footer_image.name
                            st.session_state["_footer_upload_override"] = True
                        fc1, fc2 = st.columns(2)
                        with fc1:
                            footer_image_width_pct = st.slider(
                                "너비%", 20, 100, step=5, key="footer_image_width_pct")
                        with fc2:
                            footer_image_align = st.selectbox(
                                "정렬", ["가운데", "왼쪽", "오른쪽"], key="footer_image_align")
                        footer_text_template = st.text_area(
                            "이미지 아래 문구", key="footer_text_template", height=70,
                            placeholder="선택 사항")
                    else:
                        st.session_state["use_footer_image"] = False
                        st.caption("푸터 없음")

                with tab_form:
                    form_mode = st.radio(
                        "설문", ["사용 안 함", "기존 링크", "새 폼 생성(API)"],
                        horizontal=True, key="form_mode_radio", label_visibility="collapsed")
                    if form_mode == "기존 링크":
                        form_url_input = st.text_input(
                            "Forms 링크", key="google_form_input",
                            placeholder="https://docs.google.com/forms/...")
                        if form_url_input:
                            st.session_state["google_form_url"] = form_url_input.strip()
                        st.session_state["include_google_form"] = bool(form_url_input)
                    elif form_mode == "새 폼 생성(API)":
                        uploaded_cred = st.file_uploader("서비스 계정 JSON", type=["json"], key="forms_cred")
                        form_title = st.text_input("설문 제목", value="참석 신청서")
                        form_description = st.text_area("설명", value="간단한 사전 문항입니다.", height=60)
                        if st.button("설문지 생성"):
                            if not uploaded_cred:
                                st.error("JSON을 업로드하세요.")
                            else:
                                try:
                                    from google.oauth2 import service_account
                                    from googleapiclient.discovery import build
                                    cred_json = json.loads(uploaded_cred.getvalue().decode("utf-8"))
                                    scopes = ["https://www.googleapis.com/auth/forms.body",
                                              "https://www.googleapis.com/auth/drive"]
                                    creds = service_account.Credentials.from_service_account_info(
                                        cred_json, scopes=scopes)
                                    service = build("forms", "v1", credentials=creds)
                                    create_body = {"info": {"title": form_title, "documentTitle": form_title,
                                                            "description": form_description}}
                                    form = service.forms().create(body=create_body).execute()
                                    form_name = form.get("name") or ""
                                    form_id = form_name.split("/")[-1] if "/" in form_name else form.get("formId") or ""
                                    form_url = (form.get("responderUri")
                                                or (f"https://docs.google.com/forms/d/{form_id}/viewform" if form_id else ""))
                                    if form_url:
                                        st.session_state["google_form_url"] = form_url
                                        st.session_state["include_google_form"] = True
                                        st.success("생성 완료")
                                        st.write(form_url)
                                    else:
                                        st.error("링크를 확인하지 못했습니다.")
                                except ImportError:
                                    st.error("google-api-python-client, google-auth 설치 필요")
                                except Exception as e:
                                    st.error(str(e))
                    else:
                        st.session_state["include_google_form"] = False


    # ---- 우측 미리보기 ----
    with right:
        st.markdown('<div class="dash-card-title" style="margin-bottom:6px;">실시간 미리보기</div>',
                    unsafe_allow_html=True)
        st.caption("아직 아무것도 입력하지 않은 항목은 회색 예시로 보여줍니다. 입력하면 바로 반영됩니다.")

        # 제목/본문/푸터를 입력하지 않았으면 placeholder와 같은 예시로 대신 채워서
        # 보여준다 (실제 저장/발송 내용은 그대로 빈 값 - 아래 _compose에 원본을 담음).
        preview_subject_src = email_subject_template.strip() or EXAMPLE_SUBJECT
        preview_plain_src = (email_body_template.strip() or EXAMPLE_PLAIN_BODY) if use_plain_text_body else ""
        preview_html_src = (email_html_template.strip() or EXAMPLE_HTML_BODY) if use_html_body else ""
        preview_footer_src = footer_text_template.strip() or EXAMPLE_FOOTER_TEXT if footer_mode == "text" else footer_text_template

        b64_body_img = base64.b64encode(body_image_bytes).decode("utf-8") if body_image_bytes else None
        b64_footer_img = base64.b64encode(footer_image_bytes).decode("utf-8") if footer_image_bytes else None
        preview_subj, preview_html = build_email_html(
            SAMPLE_ROW, preview_subject_src, preview_plain_src, sender_name,
            html_tmpl=preview_html_src,
            use_plain_text=use_plain_text_body, use_html_body=use_html_body,
            has_body_image=bool(body_image_bytes), has_footer_image=bool(footer_image_bytes),
            is_preview=True, body_img_base64=b64_body_img, footer_img_base64=b64_footer_img,
            image_insert_mode=image_insert_mode, image_width_pct=image_width_pct, image_align=image_align,
            footer_text_tmpl=preview_footer_src, footer_html_tmpl=footer_html_template,
            footer_image_width_pct=footer_image_width_pct, footer_image_align=footer_image_align,
        )
        st.markdown(
            f'<div class="preview-meta"><b>제목</b> {preview_subj}</div>',
            unsafe_allow_html=True,
        )
        with st.container(border=True, key="card_preview"):
            st.components.v1.html(preview_html, height=560, scrolling=True)

    # 발송 구간에서 쓰도록 상태 저장
    st.session_state["_compose"] = {
        "topic_id": topic_id,
        "email_subject_template": email_subject_template,
        "email_body_template": email_body_template if use_plain_text_body else "",
        "email_html_template": email_html_template if use_html_body else "",
        "use_plain_text_body": use_plain_text_body,
        "use_html_body": use_html_body,
        "body_image_bytes": body_image_bytes,
        "footer_image_bytes": footer_image_bytes,
        "uploaded_body_image": uploaded_body_image,
        "uploaded_footer_image": uploaded_footer_image,
        "image_insert_mode": image_insert_mode,
        "image_width_pct": image_width_pct,
        "image_align": image_align,
        "footer_text_template": footer_text_template,
        "footer_html_template": footer_html_template,
        "footer_image_width_pct": footer_image_width_pct,
        "footer_image_align": footer_image_align,
    }

# 옵션 변경 시 이 영역만 부분 갱신 (전체 페이지 흰 깜빡임 감소)
if hasattr(st, "fragment"):
    _compose_and_preview = st.fragment(_compose_and_preview)
_compose_and_preview()

# fragment 결과를 바깥 스코프로
_c = st.session_state.get("_compose") or {}
topic_id = _c.get("topic_id")
email_subject_template = _c.get("email_subject_template") or st.session_state.get("email_subject_template", "")
email_body_template = _c.get("email_body_template") or ""
email_html_template = _c.get("email_html_template") or ""
use_plain_text_body = _c.get("use_plain_text_body", False)
use_html_body = _c.get("use_html_body", True)
body_image_bytes = _c.get("body_image_bytes")
footer_image_bytes = _c.get("footer_image_bytes")
uploaded_body_image = _c.get("uploaded_body_image")
uploaded_footer_image = _c.get("uploaded_footer_image")
image_insert_mode = _c.get("image_insert_mode", "본문 하단 첨부")
image_width_pct = _c.get("image_width_pct", 80)
image_align = _c.get("image_align", "가운데")
footer_text_template = _c.get("footer_text_template") or ""
footer_html_template = _c.get("footer_html_template") or ""
footer_image_width_pct = _c.get("footer_image_width_pct", 60)
footer_image_align = _c.get("footer_image_align", "가운데")

st.divider()

# ==========================================
# 수신 대상 · 현황
# ==========================================
st.markdown(
    '<div class="dash-card-title" style="margin-bottom:8px;">수신 대상 · 현황 · 발송</div>',
    unsafe_allow_html=True,
)
with st.container(height=560, border=False):
    uploaded_file = st.file_uploader("거래처 엑셀 (.xlsx)", type=["xlsx"], label_visibility="collapsed")
    st.caption("엑셀 파일을 업로드하세요 (필수 열: 회사명, 대표자명, 이메일)")

    tab_list, tab_dash, tab_hist = st.tabs(["발송 명단", "주제별 현황", "발송 내역"])

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
            st.session_state["valid_df_cache"] = valid_df

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
    st.subheader(f"발송 실행 · {topic_names[topic_id]} · {len(targets)}건")

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

    _no_subject = not email_subject_template.strip()
    _no_body = ((use_plain_text_body and not email_body_template.strip()) or
               (use_html_body and not email_html_template.strip()))
    if _no_subject or _no_body:
        st.info("미리보기는 예시로 채워져 보이지만, 실제로 보내려면 제목과 본문을 직접 입력해야 합니다.")

    _pending_n = int(targets["_code"].isin(["none", "failed"]).sum())
    try:
        _today_sent = int(today_cnt)
    except NameError:
        _today_sent = 0
    _over_limit = _today_sent + _pending_n > GMAIL_DAILY_LIMIT
    _allow_over = False
    if _over_limit:
        st.warning(f"오늘 이 계정 발송 {_today_sent}건 + 이번 {_pending_n}건 = {_today_sent + _pending_n}건으로 "
                   f"일일 한도({GMAIL_DAILY_LIMIT}건)를 넘습니다. Gmail이 중간에 발송을 막을 수 있습니다.")
        _allow_over = st.checkbox("그래도 진행 (Google Workspace 등 한도가 더 큰 계정)", key="allow_over_limit")

    if st.button("확인 완료 및 이메일 일괄 발송 시작", type="primary"):
        if _no_subject or _no_body:
            st.error("제목과 본문을 직접 입력해야 발송할 수 있습니다.")
        elif len(targets) == 0:
            st.warning("선택된 발송 대상이 없습니다.")
        elif _over_limit and not _allow_over:
            st.error("일일 한도를 넘습니다. 대상을 줄이거나 위 체크박스로 진행을 허용해 주세요.")
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
                    if use_plain_text_body and email_body_template.strip():
                        plain_content = build_plain_text(r, email_body_template, footer_text_template, sender_name)
                        msg_alt.attach(MIMEText(plain_content, "plain", "utf-8"))
                    msg_alt.attach(MIMEText(html_content, "html", "utf-8"))

                    if body_image_bytes:
                        part = MIMEImage(body_image_bytes)
                        part.add_header("Content-ID", "<body_image>")
                        body_fn = (uploaded_body_image.name if uploaded_body_image
                                   else "body_image.png")
                        part.add_header("Content-Disposition", "inline", filename=body_fn)
                        msg_root.attach(part)
                    if footer_image_bytes:
                        part = MIMEImage(footer_image_bytes)
                        part.add_header("Content-ID", "<footer_image>")
                        footer_fn = (uploaded_footer_image.name if uploaded_footer_image
                                     else st.session_state.get("saved_footer_image_name") or "footer.png")
                        part.add_header("Content-Disposition", "inline", filename=footer_fn)
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
