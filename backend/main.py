"""
기업 이메일 발송 API (FastAPI)
환경변수: TURSO_URL, TURSO_AUTH_TOKEN, ADMIN_EMAIL, CORS_ORIGINS, SESSION_SECRET, SESSION_TTL_HOURS

인증: /api/auth/login (허용 목록 + Gmail SMTP 확인) 성공 시 세션 토큰을 발급하고,
      그 외 모든 API(health, meta 제외)는 `Authorization: Bearer <토큰>` 이 필요합니다.
"""
from __future__ import annotations

import base64
import os
import re
import smtplib
import socket
import ssl
import time
from email.header import Header
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any, Optional

from fastapi import Depends, FastAPI, Header as HeaderParam, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

import auth
import db
from mail_builder import (
    EMAIL_PRESETS,
    VAR_TAGS,
    build_email_html,
    extract_data_uri_images,
    sniff_image_subtype,
)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GMAIL_DAILY_LIMIT = 500
MAX_IMAGE_BYTES = 6 * 1024 * 1024

app = FastAPI(title="Email System API", version="1.1.0")

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=False,  # 쿠키가 아니라 Authorization 헤더로 인증
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


# ------------------------------------------------------------------ 요청 모델
class LoginBody(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class TopicCreate(BaseModel):
    name: str
    created_by: Optional[str] = None  # 무시됨 (로그인한 계정으로 기록)
    default_preset: Optional[str] = None  # 비우면 빈 "직접 작성" 상태로 시작


class TemplateSave(BaseModel):
    owner_email: Optional[str] = None  # 무시/검증됨 (본인 것만 저장 가능)
    topic_id: int  # 템플릿은 주제별로 따로 저장됨
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
    image_insert_mode: str = ""
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
    items: list[RecipientItem] = Field(max_length=5000)


class SendItem(BaseModel):
    recipient_id: int
    이메일: str
    회사명: str = ""
    대표자명: str = ""
    산업분류: str = ""
    AI_판정: str = ""


class SendBody(BaseModel):
    topic_id: int
    sender_email: Optional[str] = None  # 무시됨 (로그인한 계정으로 발송)
    sender_name: str = ""
    sender_password: str
    subject: str
    plain_body: str = ""
    html_body: str = ""
    body_mode: str = "html"
    footer_mode: str = "text"
    footer_text: str = ""
    image_insert_mode: str = ""
    image_width_pct: int = 80
    image_align: str = "가운데"
    footer_image_width_pct: int = 60
    footer_image_align: str = "가운데"
    form_url: str = ""
    include_form: bool = False
    body_image_b64: Optional[str] = None
    footer_image_b64: Optional[str] = None
    delay_sec: float = 3
    targets: list[SendItem] = Field(max_length=2000)


class SenderBody(BaseModel):
    email: EmailStr
    display_name: str = ""
    is_admin: bool = False
    is_active: bool = True


class PrefsBody(BaseModel):
    email: Optional[str] = None  # 무시/검증됨 (본인 설정만 저장 가능)
    prefs: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------ DB 준비 / 인증
_db_ready = False


def ensure_db() -> None:
    """DB 초기화(테이블 생성). 실패해도 서버는 떠 있고, 다음 요청에서 다시 시도합니다."""
    global _db_ready
    if _db_ready:
        return
    if not db.secrets_ok():
        raise HTTPException(503, "DB 설정이 없습니다 (TURSO_URL / TURSO_AUTH_TOKEN)")
    try:
        db.init()
        _db_ready = True
    except Exception as e:
        print("DB init failed:", e, "|", db.diagnose())
        raise HTTPException(503, f"DB 초기화 실패: {str(e)[:200]}")


_sender_cache: dict = {}
_SENDER_TTL = 60


def _get_sender_cached(email: str) -> Optional[dict]:
    hit = _sender_cache.get(email)
    now = time.time()
    if hit and now - hit[0] < _SENDER_TTL:
        return hit[1]
    sender = db.get_sender(email)
    _sender_cache[email] = (now, sender)
    return sender


def current_user(authorization: Optional[str] = HeaderParam(None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "로그인이 필요합니다")
    email = auth.verify(authorization[7:].strip())
    if not email:
        raise HTTPException(401, "세션이 만료되었거나 유효하지 않습니다. 다시 로그인해 주세요.")
    ensure_db()
    sender = _get_sender_cached(email)
    if not sender or not sender.get("is_active"):
        raise HTTPException(403, "등록되지 않았거나 비활성화된 계정입니다")
    return {
        "email": email,
        "name": sender.get("display_name") or email,
        "is_admin": bool(sender.get("is_admin")),
    }


def admin_user(user: dict = Depends(current_user)) -> dict:
    if not user["is_admin"]:
        raise HTTPException(403, "관리자 권한이 필요합니다")
    return user


def _own(user: dict, email: Optional[str]) -> str:
    """요청에 다른 계정 이메일이 오면 거부하고, 항상 로그인한 본인 계정을 사용."""
    e = (email or user["email"]).strip().lower()
    if e != user["email"]:
        raise HTTPException(403, "본인 계정의 데이터만 접근할 수 있습니다")
    return e


# ------------------------------------------------------------------ 유틸
class _IPv4SMTP(smtplib.SMTP):
    """IPv4로만 접속하는 SMTP 클라이언트.

    일부 서버(Oracle Cloud 등)는 IPv6 경로가 없어 smtp.gmail.com의 IPv6 주소로
    붙다가 실패합니다. 소켓만 IPv4로 만들고 나머지(첫 인사 응답 읽기, STARTTLS,
    호스트명 검증)는 smtplib 기본 흐름을 그대로 탑니다.
    """

    def _get_socket(self, host, port, timeout):
        last = None
        for af, socktype, proto, _canon, sockaddr in socket.getaddrinfo(
                host, port, socket.AF_INET, socket.SOCK_STREAM):
            sock = socket.socket(af, socktype, proto)
            try:
                sock.settimeout(timeout)
                if self.source_address:
                    sock.bind(self.source_address)
                sock.connect(sockaddr)
                return sock
            except OSError as e:
                last = e
                sock.close()
        raise last or OSError(f"{host}의 IPv4 주소를 찾지 못했습니다")


def smtp_connect(email: str, password: str):
    server = _IPv4SMTP("smtp.gmail.com", 587, timeout=30)
    try:
        server.starttls(context=ssl.create_default_context())
        server.login(email, password.replace(" ", "").strip())
    except Exception:
        try:
            server.close()
        except Exception:
            pass
        raise
    return server


def decode_image(b64: Optional[str]) -> Optional[bytes]:
    if not b64:
        return None
    s = b64.strip()
    if s.startswith("data:"):
        s = s.split(",", 1)[-1]
    try:
        data = base64.b64decode(s)
    except Exception:
        raise HTTPException(400, "이미지 데이터가 올바르지 않습니다")
    if not data:
        return None
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "이미지가 너무 큽니다 (최대 6MB)")
    return data


def to_data_uri(data: Optional[bytes]) -> Optional[str]:
    if not data:
        return None
    return f"data:image/{sniff_image_subtype(data)};base64,{base64.b64encode(data).decode()}"


def _clean_name(name: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]+", " ", name or "").strip()[:80]


def build_mime(sender_name: str, sender_email: str, to_addr: str, subject: str,
               html: str, images: list) -> MIMEMultipart:
    msg = MIMEMultipart("related")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = formataddr((sender_name, sender_email)) if sender_name else sender_email
    msg["To"] = to_addr
    alt = MIMEMultipart("alternative")
    msg.attach(alt)
    alt.attach(MIMEText(html, "html", "utf-8"))
    for cid, data, subtype in images:
        part = MIMEImage(data, _subtype=subtype)
        part.add_header("Content-ID", f"<{cid}>")
        part.add_header("Content-Disposition", "inline", filename=f"{cid}.{subtype}")
        msg.attach(part)
    return msg


# ------------------------------------------------------------------ 시작 / 공개 엔드포인트
@app.on_event("startup")
def startup():
    if auth.SECRET_IS_EPHEMERAL:
        print("WARNING: SESSION_SECRET 미설정 — 임시 키를 사용합니다(서버 재시작 시 모두 로그아웃). "
              "운영에서는 긴 무작위 문자열로 설정하세요.")
    try:
        ensure_db()
    except HTTPException as e:
        print("WARNING:", e.detail)


@app.get("/api/health")
def health():
    ok, err = False, None
    if db.secrets_ok():
        try:
            ensure_db()
            db.ping()
            ok = True
        except HTTPException as e:
            err = str(e.detail)[:200]
        except Exception as e:
            err = str(e)[:200]
    return {"ok": True, "turso": db.secrets_ok(), "db_ok": ok, "db_error": None if ok else err}


@app.get("/api/meta")
def meta():
    return {
        "presets": EMAIL_PRESETS,
        "var_tags": VAR_TAGS,
        "gmail_daily_limit": GMAIL_DAILY_LIMIT,
    }


@app.post("/api/auth/login")
def login(body: LoginBody):
    ensure_db()
    email = body.email.lower().strip()
    if auth.too_many_failures(email):
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 10분 뒤 다시 시도해 주세요.")
    sender = db.get_sender(email)
    if not sender or not sender.get("is_active"):
        auth.record_failure(email)
        raise HTTPException(403, "등록되지 않았거나 비활성 계정입니다")
    try:
        s = smtp_connect(email, body.password)
        s.quit()
    except smtplib.SMTPAuthenticationError:
        auth.record_failure(email)
        raise HTTPException(401, "Gmail 인증 실패 (앱 비밀번호 확인)")
    except Exception as e:
        raise HTTPException(400, f"Gmail 접속 오류: {e}")
    auth.clear_failures(email)
    _sender_cache[email] = (time.time(), sender)
    today = 0
    try:
        today = db.sent_today_by_sender().get(email, 0)
    except Exception:
        pass
    return {
        "email": email,
        "name": _clean_name(body.display_name or "") or sender.get("display_name") or email,
        "is_admin": bool(sender.get("is_admin")),
        "sent_today": today,
        "daily_limit": GMAIL_DAILY_LIMIT,
        "token": auth.issue(email),
        "expires_in": auth.TTL_SECONDS,
    }


# ------------------------------------------------------------------ 로그인 필요 엔드포인트
@app.get("/api/topics")
def list_topics(user: dict = Depends(current_user)):
    return db.list_topics()


@app.post("/api/topics")
def create_topic(body: TopicCreate, user: dict = Depends(current_user)):
    name = body.name.strip()
    if not name or len(name) > 200:
        raise HTTPException(400, "주제 이름을 1~200자로 입력해 주세요")
    # 새 주제는 기본 템플릿을 미리 연결하지 않고 빈 "직접 작성" 상태로 시작한다.
    tid = db.create_topic(name, user["email"], body.default_preset or None)
    return {"id": tid}


@app.patch("/api/topics/{topic_id}/preset")
def set_preset(topic_id: int, preset: str, user: dict = Depends(current_user)):
    db.set_topic_preset(topic_id, preset)
    return {"ok": True}


@app.get("/api/templates")
def list_templates(topic_id: int, owner_email: Optional[str] = None,
                   user: dict = Depends(current_user)):
    return db.list_mail_templates(_own(user, owner_email), topic_id)


@app.post("/api/templates")
def save_template(body: TemplateSave, user: dict = Depends(current_user)):
    name = body.name.strip()
    if not name or len(name) > 100:
        raise HTTPException(400, "템플릿 이름을 1~100자로 입력해 주세요")
    tid = db.save_mail_template(_own(user, body.owner_email), body.topic_id, name,
                                body.model_dump())
    return {"id": tid}


@app.get("/api/templates/{name}")
def get_template(name: str, topic_id: int, owner_email: Optional[str] = None,
                 user: dict = Depends(current_user)):
    t = db.get_mail_template(_own(user, owner_email), topic_id, name)
    if not t:
        raise HTTPException(404, "템플릿 없음")
    return t


@app.delete("/api/templates/{name}")
def delete_template(name: str, topic_id: int, owner_email: Optional[str] = None,
                    user: dict = Depends(current_user)):
    db.delete_mail_template(_own(user, owner_email), topic_id, name)
    return {"ok": True}


@app.delete("/api/topics/{topic_id}")
def delete_topic(topic_id: int, user: dict = Depends(current_user)):
    try:
        db.delete_topic(topic_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return {"ok": True}


@app.get("/api/senders")
def list_senders(user: dict = Depends(admin_user)):
    return db.list_senders()


@app.post("/api/senders")
def upsert_sender(body: SenderBody, user: dict = Depends(admin_user)):
    db.upsert_sender(body.email, body.display_name, body.is_admin, body.is_active)
    _sender_cache.pop(body.email.lower().strip(), None)
    return {"ok": True}


@app.get("/api/prefs")
def get_prefs(email: Optional[str] = None, user: dict = Depends(current_user)):
    return db.get_sender_prefs(_own(user, email)) or {}


@app.post("/api/prefs")
def save_prefs(body: PrefsBody, user: dict = Depends(current_user)):
    prefs = body.prefs
    if len(str(prefs.get("footer_image_b64") or "")) > MAX_IMAGE_BYTES * 4 // 3:
        raise HTTPException(413, "푸터 이미지가 너무 큽니다 (최대 6MB)")
    db.save_sender_prefs(_own(user, body.email), prefs)
    return {"ok": True}


@app.post("/api/recipients/upsert")
def upsert_recipients(body: UpsertRecipientsBody, user: dict = Depends(current_user)):
    import pandas as pd
    rows = [r.model_dump() for r in body.items]
    if not rows:
        return {"id_map": {}, "count": 0}
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
def topic_status(topic_id: int, user: dict = Depends(current_user)):
    return db.topic_status(topic_id)


@app.get("/api/topics/{topic_id}/logs")
def topic_logs(topic_id: int, sender_email: Optional[str] = None, limit: int = 200,
               user: dict = Depends(current_user)):
    return db.log_detail(topic_id, sender_email, max(1, min(limit, 500)))


@app.get("/api/stats")
def stats(user: dict = Depends(current_user)):
    return {
        "recipients": db.count_recipients(),
        "sent_today": dict(db.sent_today_by_sender()),
        "logs_lite": db.all_log_lite(),
    }


@app.post("/api/preview")
def preview(body: PreviewBody, user: dict = Depends(current_user)):
    use_plain = body.body_mode in ("text", "both")
    use_html = body.body_mode in ("html", "both")
    body_src = to_data_uri(decode_image(body.body_image_b64))
    footer_src = None
    footer_text = body.footer_text if body.footer_mode in ("text", "image") else ""
    if body.footer_mode == "image":
        footer_src = to_data_uri(decode_image(body.footer_image_b64))
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
def send_mail(body: SendBody, user: dict = Depends(current_user)):
    sender_email = user["email"]  # 요청 본문의 sender_email은 신뢰하지 않음
    sender_name = _clean_name(body.sender_name) or user["name"]
    use_plain = body.body_mode in ("text", "both")
    use_html = body.body_mode in ("html", "both")

    body_bytes = decode_image(body.body_image_b64)
    footer_bytes = decode_image(body.footer_image_b64) if body.footer_mode == "image" else None
    body_src = "cid:body_image" if body_bytes else None
    footer_src = "cid:footer_image" if footer_bytes else None
    footer_text = body.footer_text if body.footer_mode in ("text", "image") else ""

    try:
        server = smtp_connect(sender_email, body.sender_password)
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(400, "Gmail 인증 실패 (앱 비밀번호를 확인해 주세요)")
    except Exception as e:
        raise HTTPException(400, f"Gmail 접속 실패: {e}")

    sent = skipped = failed = 0
    errors: list[str] = []
    delay = max(0.5, min(float(body.delay_sec), 30.0))

    for t in body.targets:
        to_addr = t.이메일.strip().lower()
        if not EMAIL_RE.match(to_addr):
            failed += 1
            errors.append(f"{t.회사명} ({t.이메일}): 이메일 형식 오류")
            continue
        row = {
            "회사명": t.회사명, "대표자명": t.대표자명, "산업분류": t.산업분류,
            "AI_판정": t.AI_판정, "이메일": to_addr,
        }
        try:
            log_id = db.claim_send(body.topic_id, t.recipient_id, sender_email, sender_name)
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
                sender_name=sender_name,
                use_plain=use_plain, use_html=use_html,
                body_img_src=body_src, footer_img_src=footer_src,
                image_width_pct=body.image_width_pct, image_align=body.image_align,
                footer_text=footer_text,
                footer_image_width_pct=body.footer_image_width_pct,
                footer_image_align=body.footer_image_align,
                form_url=body.form_url, include_form=body.include_form,
            )
            # 본문에 직접 붙여 넣은 data:image 도 CID 첨부로 변환 (Gmail은 data: 이미지를 막음)
            html, inline_images = extract_data_uri_images(html)
            images = []
            if body_bytes and "cid:body_image" in html:
                images.append(("body_image", body_bytes, sniff_image_subtype(body_bytes)))
            if footer_bytes and "cid:footer_image" in html:
                images.append(("footer_image", footer_bytes, sniff_image_subtype(footer_bytes)))
            images.extend(inline_images)

            msg = build_mime(sender_name, sender_email, to_addr, subj, html, images)
            try:
                server.sendmail(sender_email, to_addr, msg.as_string())
            except smtplib.SMTPServerDisconnected:
                server = smtp_connect(sender_email, body.sender_password)
                server.sendmail(sender_email, to_addr, msg.as_string())
            # DB에는 이미지 바이트 없이 cid 참조 형태의 HTML만 저장 (용량 절약)
            db.mark_sent(log_id, subj, html)
            sent += 1
            time.sleep(delay)
        except Exception as e:
            failed += 1
            errors.append(f"{t.회사명} ({to_addr}): {e}")
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
