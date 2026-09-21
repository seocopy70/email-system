"""메일 HTML 생성 (Streamlit 비의존)."""
from __future__ import annotations

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


def replace_placeholders(template: str, row: dict, sender_nm: str, form_url: str = "") -> str:
    form_button = ""
    if form_url:
        form_button = (
            f'<div style="text-align:center;margin-top:12px;">'
            f'<a href="{form_url}" target="_blank" style="display:inline-block;background:#0b66c3;color:#fff;'
            f'padding:12px 16px;border-radius:8px;text-decoration:none;font-weight:600;">설문 작성하기</a></div>'
        )
    reps = {
        "{회사명}": str(row.get("회사명") or row.get("company") or ""),
        "{대표자명}": str(row.get("대표자명") or row.get("ceo") or ""),
        "{산업분류}": str(row.get("산업분류") or row.get("industry") or ""),
        "{AI_판정}": str(row.get("AI_판정") or row.get("rating") or ""),
        "{발신자}": sender_nm or "",
        "{구글설문링크}": form_url or "",
        "{구글설문버튼}": form_button,
    }
    out = str(template or "")
    for k, v in reps.items():
        out = out.replace(k, v)
    return out


def build_image_tag(src: str, width_pct: int = 80, align: str = "가운데") -> str:
    align_map = {
        "가운데": "margin:18px auto;display:block;",
        "왼쪽": "margin:18px 0;display:block;",
        "오른쪽": "margin:18px 0 18px auto;display:block;",
    }
    style = f"max-width:{width_pct}%;height:auto;border:1px solid #ddd;border-radius:4px;{align_map.get(align, align_map['가운데'])}"
    return f'<img src="{src}" style="{style}">'


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
    image_insert_mode: str = "본문 하단 첨부",
    image_width_pct: int = 80,
    image_align: str = "가운데",
    footer_text: str = "",
    footer_image_width_pct: int = 60,
    footer_image_align: str = "가운데",
    form_url: str = "",
    include_form: bool = False,
) -> tuple[str, str]:
    subj = replace_placeholders(subject_tmpl, row, sender_name, form_url)
    marker = image_insert_mode.startswith("본문 중간")
    sections: list[str] = []

    if use_plain and plain_body:
        body = replace_placeholders(plain_body, row, sender_name, form_url)
        if body_img_src and marker and "{이미지}" in body:
            body = body.replace("{이미지}", build_image_tag(body_img_src, image_width_pct, image_align))
        body = body.replace("\r\n", "\n").replace("\n", "<br>")
        sections.append(f"<div style='white-space:pre-line'>{body}</div>")

    if use_html and html_body:
        body = replace_placeholders(html_body, row, sender_name, form_url)
        if body_img_src and marker and "{이미지}" in body:
            body = body.replace("{이미지}", build_image_tag(body_img_src, image_width_pct, image_align))
        sections.append(body)

    if not sections:
        sections.append("<p>본문이 비어 있습니다.</p>")

    body_html = "\n".join(sections)
    extra_img = ""
    if body_img_src and (not marker or ("{이미지}" not in (plain_body or "") and "{이미지}" not in (html_body or ""))):
        extra_img = "<br>" + build_image_tag(body_img_src, image_width_pct, image_align)

    form_block = ""
    if include_form and form_url:
        form_block = (
            f'<div style="text-align:center;margin-top:18px;">'
            f'<a href="{form_url}" target="_blank" style="display:inline-block;background:#0b66c3;color:#fff;'
            f'padding:12px 16px;border-radius:8px;text-decoration:none;font-weight:600;">설문 작성하기</a></div>'
        )

    footer_parts: list[str] = []
    if footer_text:
        ft = replace_placeholders(footer_text, row, sender_name, form_url).replace("\n", "<br>")
        footer_parts.append(f"<div style='margin-top:18px;color:#444'>{ft}</div>")
    if footer_img_src:
        footer_parts.append(
            f'<div style="margin-top:16px">{build_image_tag(footer_img_src, footer_image_width_pct, footer_image_align)}</div>'
        )

    full = f"""
<html><body style="font-family:'Malgun Gothic',Arial,sans-serif;line-height:1.7;color:#222;font-size:14px;">
<div style="max-width:650px;margin:0 auto;padding:20px;border:1px solid #eee;border-radius:6px;">
{body_html}
{extra_img}
{form_block}
{"".join(footer_parts)}
</div></body></html>
"""
    return subj, full
