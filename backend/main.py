"""
기업 이메일 발송 API (FastAPI)
환경변수: TURSO_URL, TURSO_AUTH_TOKEN, ADMIN_EMAIL, CORS_ORIGINS
"""
from __future__ import annotations

import base64
import os
import re
import smtplib
import time
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

import db
from mail_builder import EMAIL_PRESETS, VAR_TAGS, build_email_html

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GMAIL_DAILY_LIMIT = 500

app = FastAPI(title="Email System API", version="1.0.0")

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginBody(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class TopicCreate(BaseModel):
    name: str
    created_by: str
    default_preset: Optional[str] = "기본형"


class TemplateSave(BaseModel):
    owner_email: str
    name: str
    subject: str = ""
    body_mode: str = "html"
    plain_body: str = ""
    html_body: str = ""
    image_insert_mode: str = "본문 하단 첨부"
    image_width_pct: int = 80
    image_align: str = "가운데"


class PreviewBody(BaseModel):
    subject: str = ""
    plain_body: str = ""
    html_body: str = ""
    sender_name: str = "발신자"
    body_mode: str = "html"
    footer_mode: str = "text"
    footer_text: str = ""
    image_insert_mode: str = "본문 하단 첨부"
    image_width_pct: int = 80
    image_align: str = "가운데"
    footer_image_width_pct: int = 60
    footer_image_align: str = "가운데"
    form_url: str = ""
    include_form: bool = False
    body_image_b64: Optional[str] = None
    footer_image_b64: Optional[str] = None
    row: dict = Field(default_factory=lambda: {
        "회사명": "샘플기업", "대표자명": "홍길동", "산업분류": "제조업",
        "AI_판정": "A", "이메일": "sample@example.com",
    })


class RecipientItem(BaseModel):
    회사명: str = ""
    대표자명: str = ""
    이메일: str
    산업분류: str = ""
    AI_판정: str = ""


class UpsertRecipientsBody(BaseModel):
    items: list[RecipientItem]


class SendItem(BaseModel):
    recipient_id: int
    이메일: str
    회사명: str = ""
    대표자명: str = ""
    산업분류: str = ""
    AI_판정: str = ""


class SendBody(BaseModel):
    topic_id: int
    sender_email: str
    sender_name: str
    sender_password: str
    subject: str
    plain_body: str = ""
    html_body: str = ""
    body_mode: str = "html"
    footer_mode: str = "text"
    footer_text: str = ""
    image_insert_mode: str = "본문 하단 첨부"
    image_width_pct: int = 80
    image_align: str = "가운데"
    footer_image_width_pct: int = 60
    footer_image_align: str = "가운데"
    form_url: str = ""
    include_form: bool = False
    body_image_b64: Optional[str] = None
    footer_image_b64: Optional[str] = None
    delay_sec: float = 3
    targets: list[SendItem]


def smtp_connect(email: str, password: str):
    server = smtplib.SMTP("smtp.gmail.com", 587, timeout=30)
    server.starttls()
    server.login(email, password.replace(" ", "").strip())
    return server


@app.on_event("startup")
def startup():
    if not db.secrets_ok():
        print("WARNING: TURSO_URL / TURSO_AUTH_TOKEN 미설정")
        return
    db.init()


@app.get("/api/health")
def health():
    return {"ok": True, "turso": db.secrets_ok()}


@app.get("/api/meta")
def meta():
    return {
        "presets": EMAIL_PRESETS,
        "var_tags": VAR_TAGS,
        "gmail_daily_limit": GMAIL_DAILY_LIMIT,
    }


@app.post("/api/auth/login")
def login(body: LoginBody):
    if not db.secrets_ok():
        raise HTTPException(503, "DB 설정이 없습니다")
    email = body.email.lower().strip()
    sender = db.get_sender(email)
    if not sender or not sender.get("is_active"):
        raise HTTPException(403, "등록되지 않았거나 비활성 계정입니다")
    try:
        s = smtp_connect(email, body.password)
        s.quit()
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(401, "Gmail 인증 실패 (앱 비밀번호 확인)")
    except Exception as e:
        raise HTTPException(400, f"Gmail 접속 오류: {e}")
    today = 0
    try:
        today = db.sent_today_by_sender().get(email, 0)
    except Exception:
        pass
    return {
        "email": email,
        "name": (body.display_name or "").strip() or sender.get("display_name") or email,
        "is_admin": bool(sender.get("is_admin")),
        "sent_today": today,
        "daily_limit": GMAIL_DAILY_LIMIT,
    }


@app.get("/api/topics")
def list_topics():
    return db.list_topics()


@app.post("/api/topics")
def create_topic(body: TopicCreate):
    tid = db.create_topic(body.name, body.created_by, body.default_preset or "기본형")
    return {"id": tid}


@app.patch("/api/topics/{topic_id}/preset")
def set_preset(topic_id: int, preset: str):
    db.set_topic_preset(topic_id, preset)
    return {"ok": True}


@app.get("/api/templates")
def list_templates(owner_email: str):
    return db.list_mail_templates(owner_email)


@app.post("/api/templates")
def save_template(body: TemplateSave):
    tid = db.save_mail_template(body.owner_email, body.name, body.model_dump())
    return {"id": tid}


@app.get("/api/templates/{name}")
def get_template(name: str, owner_email: str):
    t = db.get_mail_template(owner_email, name)
    if not t:
        raise HTTPException(404, "템플릿 없음")
    return t


@app.get("/api/senders")
def list_senders():
    return db.list_senders()


class SenderBody(BaseModel):
    email: EmailStr
    display_name: str = ""
    is_admin: bool = False
    is_active: bool = True


@app.post("/api/senders")
def upsert_sender(body: SenderBody):
    db.upsert_sender(body.email, body.display_name, body.is_admin, body.is_active)
    return {"ok": True}


class PrefsBody(BaseModel):
    email: EmailStr
    prefs: dict[str, Any] = Field(default_factory=dict)


@app.get("/api/prefs")
def get_prefs(email: str):
    return db.get_sender_prefs(email) or {}


@app.post("/api/prefs")
def save_prefs(body: PrefsBody):
    db.save_sender_prefs(body.email, body.prefs)
    return {"ok": True}


@app.post("/api/recipients/upsert")
def upsert_recipients(body: UpsertRecipientsBody):
    import pandas as pd
    rows = [r.model_dump() for r in body.items]
    df = pd.DataFrame(rows)
    for c in ("산업분류", "AI_판정"):
        if c not in df.columns:
            df[c] = ""
    df["이메일"] = df["이메일"].astype(str).str.strip().str.lower()
    df = df[df["이메일"].apply(lambda x: bool(EMAIL_RE.match(x)))]
    df = df.drop_duplicates(subset="이메일").reset_index(drop=True)
    id_map = db.upsert_recipients(df)
    return {"id_map": id_map, "count": len(id_map)}


@app.get("/api/topics/{topic_id}/status")
def topic_status(topic_id: int):
    return db.topic_status(topic_id)


@app.get("/api/topics/{topic_id}/logs")
def topic_logs(topic_id: int, sender_email: Optional[str] = None, limit: int = 200):
    return db.log_detail(topic_id, sender_email, limit)


@app.get("/api/stats")
def stats():
    return {
        "recipients": db.count_recipients(),
        "sent_today": dict(db.sent_today_by_sender()),
        "logs_lite": db.all_log_lite(),
    }


@app.post("/api/preview")
def preview(body: PreviewBody):
    use_plain = body.body_mode in ("text", "both")
    use_html = body.body_mode in ("html", "both")
    body_src = f"data:image/png;base64,{body.body_image_b64}" if body.body_image_b64 else None
    footer_src = None
    footer_text = body.footer_text if body.footer_mode in ("text", "image") else ""
    if body.footer_mode == "image" and body.footer_image_b64:
        footer_src = f"data:image/png;base64,{body.footer_image_b64}"
    subj, html = build_email_html(
        body.row,
        body.subject,
        plain_body=body.plain_body if use_plain else "",
        html_body=body.html_body if use_html else "",
        sender_name=body.sender_name,
        use_plain=use_plain,
        use_html=use_html,
        body_img_src=body_src,
        footer_img_src=footer_src,
        image_insert_mode=body.image_insert_mode,
        image_width_pct=body.image_width_pct,
        image_align=body.image_align,
        footer_text=footer_text,
        footer_image_width_pct=body.footer_image_width_pct,
        footer_image_align=body.footer_image_align,
        form_url=body.form_url,
        include_form=body.include_form,
    )
    return {"subject": subj, "html": html}


@app.post("/api/send")
def send_mail(body: SendBody):
    use_plain = body.body_mode in ("text", "both")
    use_html = body.body_mode in ("html", "both")
    body_bytes = base64.b64decode(body.body_image_b64) if body.body_image_b64 else None
    footer_bytes = base64.b64decode(body.footer_image_b64) if body.footer_image_b64 else None
    body_src = f"data:image/png;base64,{body.body_image_b64}" if body.body_image_b64 else None
    footer_src = f"data:image/png;base64,{body.footer_image_b64}" if body.footer_image_b64 else None
    footer_text = body.footer_text if body.footer_mode in ("text", "image") else ""

    try:
        server = smtp_connect(body.sender_email, body.sender_password)
    except Exception as e:
        raise HTTPException(400, f"Gmail 접속 실패: {e}")

    sent = skipped = failed = 0
    errors: list[str] = []

    for t in body.targets:
        row = {
            "회사명": t.회사명, "대표자명": t.대표자명, "산업분류": t.산업분류,
            "AI_판정": t.AI_판정, "이메일": t.이메일,
        }
        try:
            log_id = db.claim_send(body.topic_id, t.recipient_id, body.sender_email, body.sender_name)
        except Exception as e:
            errors.append(f"DB: {e}")
            break
        if log_id is None:
            skipped += 1
            continue
        try:
            subj, html = build_email_html(
                row, body.subject,
                plain_body=body.plain_body if use_plain else "",
                html_body=body.html_body if use_html else "",
                sender_name=body.sender_name,
                use_plain=use_plain, use_html=use_html,
                body_img_src=body_src, footer_img_src=footer_src,
                image_insert_mode=body.image_insert_mode,
                image_width_pct=body.image_width_pct, image_align=body.image_align,
                footer_text=footer_text,
                footer_image_width_pct=body.footer_image_width_pct,
                footer_image_align=body.footer_image_align,
                form_url=body.form_url, include_form=body.include_form,
            )
            # 발송용: cid 이미지 사용
            send_html = html
            if body_bytes:
                send_html = send_html.replace(body_src or "", "cid:body_image")
            if footer_bytes:
                send_html = send_html.replace(footer_src or "", "cid:footer_image")

            msg_root = MIMEMultipart("related")
            msg_root["Subject"] = subj
            msg_root["From"] = f"{body.sender_name} <{body.sender_email}>"
            msg_root["To"] = t.이메일
            msg_alt = MIMEMultipart("alternative")
            msg_root.attach(msg_alt)
            msg_alt.attach(MIMEText(send_html, "html", "utf-8"))
            if body_bytes:
                part = MIMEImage(body_bytes)
                part.add_header("Content-ID", "<body_image>")
                part.add_header("Content-Disposition", "inline", filename="body.png")
                msg_root.attach(part)
            if footer_bytes:
                part = MIMEImage(footer_bytes)
                part.add_header("Content-ID", "<footer_image>")
                part.add_header("Content-Disposition", "inline", filename="footer.png")
                msg_root.attach(part)
            try:
                server.sendmail(body.sender_email, t.이메일, msg_root.as_string())
            except smtplib.SMTPServerDisconnected:
                server = smtp_connect(body.sender_email, body.sender_password)
                server.sendmail(body.sender_email, t.이메일, msg_root.as_string())
            db.mark_sent(log_id, subj, html)
            sent += 1
            time.sleep(max(0.5, body.delay_sec))
        except Exception as e:
            failed += 1
            errors.append(f"{t.회사명} ({t.이메일}): {e}")
            try:
                db.mark_failed(log_id, str(e))
            except Exception:
                pass
            if isinstance(e, smtplib.SMTPAuthenticationError):
                break

    try:
        server.quit()
    except Exception:
        pass
    return {"sent": sent, "skipped": skipped, "failed": failed, "errors": errors}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), reload=True)
