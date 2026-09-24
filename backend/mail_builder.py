"""메일 HTML 생성 (Streamlit 비의존)."""
from __future__ import annotations

import base64
import hashlib
import html as _html
import re

EMAIL_PRESETS = {
    "기본형": {
        "subject": "[{회사명}] {대표자명} 대표님께 드리는 기업 가업승계 및 세무 전략 안내",
        "plain_body": "안녕하십니까, {회사명} {대표자명} 대표님.\n\n귀사의 무궁한 발전과 번영을 기원합니다.\n\n{이미지}\n\n저희는 {산업분류} 분야 우수 기업을 대상으로 맞춤형 컨설팅을 제공하고 있습니다.\n\n감사합니다.\n{발신자} 배상",
        "html_body": "<p>안녕하십니까, {회사명} {대표자명} 대표님.</p><p>귀사의 무궁한 발전과 번영을 기원합니다.</p>{이미지}<p><strong>저희는 {산업분류} 분야 우수 기업을 대상으로 맞춤형 컨설팅을 제공하고 있습니다.</strong></p><p>감사합니다.<br>{발신자} 배상</p>",
        "body_mode": "html",
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 80,
        "image_align": "가운데",
    },
    "브로슈어형": {
        "subject": "[{회사명}] {대표자명} 대표님과 함께하는 기업 성장 전략 제안",
        "plain_body": "안녕하십니까, {회사명} {대표자명} 대표님.\n\n{이미지}\n\n저희는 {산업분류} 산업군별 맞춤형 전략 컨설팅을 제공합니다.\n\n감사합니다.\n{발신자}",
        "html_body": "<p>안녕하십니까, {회사명} {대표자명} 대표님.</p>{이미지}<p>저희는 {산업분류} 산업군별 맞춤형 전략 컨설팅을 제공합니다.</p><p>감사합니다.<br>{발신자}</p>",
        "body_mode": "html",
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 75,
        "image_align": "가운데",
    },
    "간단 제안형": {
        "subject": "[{회사명}] {대표자명} 대표님께 드리는 간단한 제안 안내",
        "plain_body": "안녕하십니까, {회사명} {대표자명} 대표님.\n\n{이미지}\n\n필요한 자료를 전달해주시면 맞춤 상담을 제안드리겠습니다.\n\n감사합니다.\n{발신자}",
        "html_body": "<p>안녕하십니까, {회사명} {대표자명} 대표님.</p>{이미지}<p>필요한 자료를 전달해주시면 맞춤 상담을 제안드리겠습니다.</p><p>감사합니다.<br>{발신자}</p>",
        "body_mode": "html",
        "image_insert_mode": "본문 중간 삽입 (마커: {이미지})",
        "image_width_pct": 70,
        "image_align": "가운데",
    },
}

VAR_TAGS = [
    {"label": "회사명", "tag": "{회사명}"},
    {"label": "대표자명", "tag": "{대표자명}"},
    {"label": "산업분류", "tag": "{산업분류}"},
    {"label": "AI판정", "tag": "{AI_판정}"},
    {"label": "발신자", "tag": "{발신자}"},
    {"label": "이미지", "tag": "{이미지}"},
    {"label": "설문링크", "tag": "{구글설문링크}"},
    {"label": "설문버튼", "tag": "{구글설문버튼}"},
]


IMG_MARKER = "{이미지}"


def sniff_image_subtype(data: bytes) -> str:
    """이미지 바이트에서 MIME 하위 타입을 판별 (png/jpeg/gif/webp)."""
    if data.startswith(b"\x89PNG"):
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return "png"


def safe_url(url: str | None) -> str:
    """http/https 링크만 허용 (javascript: 등 차단)."""
    u = (url or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


_FORM_EDIT = re.compile(r"^(https?://docs\.google\.com/forms/d/(?:e/)?[\w-]+)/(?:edit|viewform)?(?:[?#].*)?$", re.I)


def normalize_form_url(url: str | None) -> str:
    """구글 폼 링크 정리: 공백 제거, 응답자용 주소로 통일, http(s)만 허용.

    - 편집 주소(.../forms/d/<id>/edit)를 붙여 넣어도 응답자용 .../viewform 으로 바꿔 줍니다.
      (편집 주소는 받는 사람이 열 수 없음)
    - forms.gle 짧은 주소와 그 밖의 http(s) 주소는 그대로 둡니다.
    """
    u = safe_url(url)
    if not u:
        return ""
    m = _FORM_EDIT.match(u)
    if m:
        return m.group(1) + "/viewform"
    return u


def replace_placeholders(template: str, row: dict, sender_nm: str, form_url: str = "",
                         mode: str = "html") -> str:
    """치환 태그를 실제 값으로 변환.

    mode="subject": 메일 제목용 (줄바꿈만 제거, HTML 이스케이프 없음)
    mode="plain"  : 일반 텍스트 본문 (템플릿과 값 모두 HTML 이스케이프)
    mode="html"   : HTML 본문 (템플릿은 그대로, 엑셀/발신자 값만 이스케이프)
    mode="raw"    : text/plain 파트용 순수 텍스트 (이스케이프 없음, 설문 버튼은 링크로)
    """
    text = str(template or "")
    if mode == "plain":
        text = _html.escape(text, quote=False)

    if mode in ("subject", "raw"):
        def esc(s: str) -> str:
            return re.sub(r"[\r\n]+", " ", s) if mode == "subject" else s
    else:
        def esc(s: str) -> str:
            return _html.escape(s, quote=False)

    def val(*keys: str) -> str:
        for k in keys:
            v = row.get(k)
            if v not in (None, ""):
                return str(v)
        return ""

    url = normalize_form_url(form_url)
    button = ""
    if url and mode == "raw":
        button = url
    elif url and mode != "subject":
        button = (
            f'<div style="text-align:center;margin-top:12px;">'
            f'<a href="{_html.escape(url, quote=True)}" target="_blank" '
            f'style="display:inline-block;background:#0b66c3;color:#fff;'
            f'padding:12px 16px;border-radius:8px;text-decoration:none;font-weight:600;">설문 작성하기</a></div>'
        )
    link = url if mode in ("subject", "raw") else _html.escape(url, quote=True)

    reps = {
        "{회사명}": esc(val("회사명", "company")),
        "{대표자명}": esc(val("대표자명", "ceo")),
        "{산업분류}": esc(val("산업분류", "industry")),
        "{AI_판정}": esc(val("AI_판정", "rating")),
        "{발신자}": esc(sender_nm or ""),
        "{구글설문링크}": link,
        "{구글설문버튼}": button,
    }
    for k, v in reps.items():
        text = text.replace(k, v)
    return text


def build_image_tag(src: str, width_pct: int = 80, align: str = "가운데") -> str:
    align_map = {
        "가운데": "margin:18px auto;display:block;",
        "왼쪽": "margin:18px 0;display:block;",
        "오른쪽": "margin:18px 0 18px auto;display:block;",
    }
    width = max(10, min(100, int(width_pct or 80)))
    style = (f"max-width:{width}%;height:auto;border:1px solid #ddd;border-radius:4px;"
             f"{align_map.get(align, align_map['가운데'])}")
    return f'<img src="{_html.escape(src, quote=True)}" style="{style}">'


def build_email_html(
    row: dict,
    subject_tmpl: str,
    plain_body: str = "",
    html_body: str = "",
    sender_name: str = "",
    use_plain: bool = False,
    use_html: bool = True,
    body_img_src: str | None = None,
    footer_img_src: str | None = None,
    image_insert_mode: str = "",  # 하위 호환용(무시): 본문에 {이미지}가 있으면 그 자리, 없으면 본문 아래
    image_width_pct: int = 80,
    image_align: str = "가운데",
    footer_text: str = "",
    footer_image_width_pct: int = 60,
    footer_image_align: str = "가운데",
    form_url: str = "",
    include_form: bool = False,
) -> tuple[str, str]:
    """(제목, 완성 HTML) 반환.

    - 본문 이미지: 본문에 {이미지}가 있으면 그 자리에 한 번만 넣고, 없으면 본문 아래에 붙입니다.
      이미지를 쓰지 않으면 {이미지} 글자는 깨끗하게 제거됩니다.
    - 엑셀/발신자 값은 HTML 이스케이프, 설문 링크는 http(s)만 허용합니다.
    """
    subj = replace_placeholders(subject_tmpl, row, sender_name, form_url, mode="subject")
    subj = re.sub(r"\s+", " ", subj.replace(IMG_MARKER, "")).strip()

    img_tag = build_image_tag(body_img_src, image_width_pct, image_align) if body_img_src else ""
    placed = False

    def fill(body: str) -> str:
        nonlocal placed
        if IMG_MARKER not in body:
            return body
        if img_tag and not placed:
            placed = True
            head, _, tail = body.partition(IMG_MARKER)
            return head + img_tag + tail.replace(IMG_MARKER, "")
        return body.replace(IMG_MARKER, "")

    sections: list[str] = []
    used_templates: list[str] = []

    if use_plain and plain_body:
        used_templates.append(plain_body)
        body = replace_placeholders(plain_body, row, sender_name, form_url, mode="plain")
        body = fill(body).replace("\r\n", "\n").replace("\n", "<br>")
        sections.append(f"<div>{body}</div>")

    if use_html and html_body:
        used_templates.append(html_body)
        body = replace_placeholders(html_body, row, sender_name, form_url, mode="html")
        sections.append(fill(body))

    if not sections:
        sections.append("<p>본문이 비어 있습니다.</p>")

    extra_img = f"<div>{img_tag}</div>" if img_tag and not placed else ""

    footer_parts: list[str] = []
    if footer_text:
        used_templates.append(footer_text)
        ft = replace_placeholders(footer_text, row, sender_name, form_url, mode="plain")
        ft = ft.replace(IMG_MARKER, "").replace("\r\n", "\n").replace("\n", "<br>")
        footer_parts.append(f"<div style='margin-top:18px;color:#444'>{ft}</div>")
    if footer_img_src:
        footer_parts.append(
            f'<div style="margin-top:16px">'
            f'{build_image_tag(footer_img_src, footer_image_width_pct, footer_image_align)}</div>'
        )

    form_block = ""
    form_tags = ("{구글설문링크}", "{구글설문버튼}")
    if include_form and normalize_form_url(form_url) and not any(t in tpl for tpl in used_templates for t in form_tags):
        form_block = (
            f'<div style="text-align:center;margin-top:18px;">'
            f'<a href="{_html.escape(normalize_form_url(form_url), quote=True)}" target="_blank" '
            f'style="display:inline-block;background:#0b66c3;color:#fff;padding:12px 16px;'
            f'border-radius:8px;text-decoration:none;font-weight:600;">설문 작성하기</a></div>'
        )

    full = f"""
<html><body style="font-family:'Malgun Gothic',Arial,sans-serif;line-height:1.7;color:#222;font-size:14px;">
<div style="max-width:650px;margin:0 auto;padding:20px;border:1px solid #eee;border-radius:6px;">
{chr(10).join(sections)}
{extra_img}
{form_block}
{"".join(footer_parts)}
</div></body></html>
"""
    return subj, full


def build_plain_text(row: dict, plain_body: str, footer_text: str = "", sender_name: str = "",
                     form_url: str = "", include_form: bool = False) -> str:
    """multipart/alternative 의 text/plain 파트용 순수 텍스트 (HTML 이스케이프 없음)."""
    def fill(t: str) -> str:
        t = str(t or "").replace("{구글설문버튼}", "{구글설문링크}")
        t = t.replace(IMG_MARKER, "").replace("{푸터이미지}", "")
        t = replace_placeholders(t, row, sender_name, form_url, mode="raw")
        return t.replace("\r\n", "\n").strip()

    parts = [fill(plain_body)]
    url = normalize_form_url(form_url)
    if include_form and url and url not in parts[0]:
        parts.append(f"설문 링크: {url}")
    footer = fill(footer_text)
    if footer:
        parts.append(footer)
    return "\n\n".join(x for x in parts if x)


_DATA_IMG = re.compile(
    r"""(src\s*=\s*)(["'])data:image/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=\s]+?)\2""", re.I)


def extract_data_uri_images(html: str) -> tuple[str, list[tuple[str, bytes, str]]]:
    """HTML 안의 data:image 이미지를 cid: 참조로 바꾸고 (cid, 바이트, 하위타입) 목록을 반환.

    Gmail 등은 data: 이미지를 표시하지 않으므로, 본문에 직접 붙여 넣은 이미지도 첨부(CID)로 보냅니다.
    """
    found: dict[str, tuple[str, bytes, str]] = {}

    def repl(m: re.Match) -> str:
        try:
            data = base64.b64decode(re.sub(r"\s+", "", m.group(3)))
        except Exception:
            return m.group(0)
        if not data:
            return m.group(0)
        key = hashlib.sha1(data).hexdigest()
        if key not in found:
            found[key] = (f"inline_{len(found) + 1}", data, sniff_image_subtype(data))
        return f"{m.group(1)}{m.group(2)}cid:{found[key][0]}{m.group(2)}"

    return _DATA_IMG.sub(repl, html), list(found.values())
