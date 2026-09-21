"""공유 발송이력 DB 계층 (Supabase / Postgres)."""
import time
from collections import Counter
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import streamlit as st
from supabase import Client, create_client

KST = ZoneInfo("Asia/Seoul")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def secrets_ok() -> bool:
    try:
        cfg = st.secrets["supabase"]
        return bool(cfg.get("url") and cfg.get("service_key"))
    except Exception:
        return False


@st.cache_resource
def client() -> Client:
    cfg = st.secrets["supabase"]
    return create_client(cfg["url"], cfg["service_key"])


def _fetch_all(build, page: int = 1000) -> list:
    """PostgREST 기본 1000행 제한을 넘어도 전부 가져오는 페이지네이션."""
    rows, start = [], 0
    while True:
        data = build().range(start, start + page - 1).execute().data or []
        rows.extend(data)
        if len(data) < page:
            return rows
        start += page


# ---------- 발신 계정 ----------
def get_sender(email: str):
    res = (client().table("senders").select("*")
           .eq("email", email.strip().lower()).limit(1).execute())
    return res.data[0] if res.data else None


def list_senders() -> list:
    return client().table("senders").select("*").order("email").execute().data or []


def upsert_sender(email: str, display_name: str, is_admin: bool, is_active: bool):
    client().table("senders").upsert({
        "email": email.strip().lower(),
        "display_name": display_name.strip() or None,
        "is_admin": is_admin,
        "is_active": is_active,
    }, on_conflict="email").execute()


# ---------- 주제 ----------
def list_topics() -> list:
    return (client().table("topics").select("id,name,created_at")
            .order("created_at", desc=True).execute().data or [])


def create_topic(name: str, created_by: str) -> int:
    name = name.strip()
    client().table("topics").upsert(
        {"name": name, "created_by": created_by},
        on_conflict="name", ignore_duplicates=True).execute()
    got = client().table("topics").select("id").eq("name", name).limit(1).execute()
    return got.data[0]["id"]


# ---------- 수신자 ----------
def upsert_recipients(df) -> dict:
    """엑셀 명단을 recipients에 반영하고 {이메일: id}를 돌려줍니다."""
    recs = [{
        "email": r["이메일"],
        "company": str(r["회사명"]),
        "ceo": str(r["대표자명"]),
        "industry": str(r["산업분류"]),
        "rating": str(r["AI_판정"]),
        "updated_at": _now_iso(),
    } for _, r in df.iterrows()]

    id_map = {}
    for i in range(0, len(recs), 500):
        res = client().table("recipients").upsert(
            recs[i:i + 500], on_conflict="email").execute()
        for row in res.data or []:
            id_map[row["email"]] = row["id"]

    missing = [r["email"] for r in recs if r["email"] not in id_map]
    for i in range(0, len(missing), 100):
        res = (client().table("recipients").select("id,email")
               .in_("email", missing[i:i + 100]).execute())
        for row in res.data or []:
            id_map[row["email"]] = row["id"]
    return id_map


def count_recipients() -> int:
    res = client().table("recipients").select("id", count="exact").limit(1).execute()
    return res.count or 0


# ---------- 발송 기록 ----------
def topic_status(topic_id: int) -> dict:
    """{recipient_id: 로그행} — 상태 표시용(본문 제외)."""
    rows = _fetch_all(lambda: (
        client().table("send_log")
        .select("id,recipient_id,status,sender_email,sender_name,sent_at,claimed_at")
        .eq("topic_id", topic_id).order("id")))
    return {r["recipient_id"]: r for r in rows}


def claim_send(topic_id: int, recipient_id: int, sender_email: str, sender_name: str):
    """발송 권한 선점. 성공 시 log id, 이미 처리됐거나 진행 중이면 None."""
    res = client().rpc("claim_send", {
        "p_topic": topic_id, "p_recipient": recipient_id,
        "p_sender": sender_email, "p_sender_name": sender_name,
    }).execute()
    data = res.data
    if isinstance(data, list):
        data = data[0] if data else None
    return data


def _update_with_retry(log_id: int, values: dict, tries: int = 3):
    last = None
    for n in range(tries):
        try:
            client().table("send_log").update(values).eq("id", log_id).execute()
            return
        except Exception as e:  # 네트워크 일시 오류 대비
            last = e
            time.sleep(1 + n)
    raise last


def mark_sent(log_id: int, subject: str, body_html: str):
    _update_with_retry(log_id, {
        "status": "sent", "subject": subject, "body_html": body_html,
        "sent_at": _now_iso(), "error": None})


def mark_failed(log_id: int, error: str):
    _update_with_retry(log_id, {"status": "failed", "error": error[:500]})


def all_log_lite() -> list:
    return _fetch_all(lambda: (
        client().table("send_log").select("id,topic_id,status,sender_email").order("id")))


def sent_today_by_sender() -> Counter:
    start_kst = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = start_kst.astimezone(timezone.utc).isoformat()
    rows = _fetch_all(lambda: (
        client().table("send_log").select("id,sender_email")
        .eq("status", "sent").gte("sent_at", start_utc).order("id")))
    return Counter(r["sender_email"] for r in rows)


def log_detail(topic_id: int, sender_email: str = None, limit: int = 200) -> list:
    q = (client().table("send_log")
         .select("id,status,subject,sender_email,sender_name,sent_at,claimed_at,error,"
                 "recipients(email,company,ceo)")
         .eq("topic_id", topic_id))
    if sender_email:
        q = q.eq("sender_email", sender_email)
    return q.order("claimed_at", desc=True).limit(limit).execute().data or []


def get_body(log_id: int) -> str:
    res = (client().table("send_log").select("body_html")
           .eq("id", log_id).limit(1).execute())
    return (res.data[0]["body_html"] if res.data else "") or ""
