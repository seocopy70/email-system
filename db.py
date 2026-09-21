"""공유 발송이력 DB 계층 (Turso / libSQL, HTTP API 사용).

별도 드라이버 없이 `requests`만으로 Turso의 HTTP 파이프라인 API(/v2/pipeline)를 호출합니다.
테이블은 앱 시작 시 자동 생성되므로 Turso에서 SQL을 따로 실행할 필요가 없습니다.
"""
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import streamlit as st

KST = ZoneInfo("Asia/Seoul")
STALE_PENDING_MIN = 30  # 이 시간 넘게 '발송중'이면 다시 선점 가능 (앱이 중간에 종료된 경우 대비)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now() -> str:
    return _iso(datetime.now(timezone.utc))


# ---------------------------------------------------------------- 연결 설정
def _cfg() -> dict:
    return st.secrets["turso"]


def secrets_ok() -> bool:
    try:
        cfg = _cfg()
        return bool(cfg.get("url") and cfg.get("auth_token"))
    except Exception:
        return False


def _base_url() -> str:
    url = str(_cfg()["url"]).strip().rstrip("/")
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    return url


# ---------------------------------------------------------------- HTTP 전송
def _enc(v) -> dict:
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "integer", "value": str(int(v))}
    if isinstance(v, int):
        return {"type": "integer", "value": str(v)}
    if isinstance(v, float):
        return {"type": "float", "value": v}
    return {"type": "text", "value": str(v)}


def _dec(v: dict):
    t = v.get("type")
    if t == "null":
        return None
    if t == "integer":
        return int(v["value"])
    if t == "float":
        return float(v["value"])
    return v.get("value")


def _pipeline(stmts: list) -> list:
    """[(sql, args), ...]를 한 번의 HTTP 요청으로 순서대로 실행하고 결과 리스트를 반환."""
    reqs = [{"type": "execute", "stmt": {"sql": sql, "args": [_enc(a) for a in args]}}
            for sql, args in stmts]
    reqs.append({"type": "close"})
    headers = {"Authorization": f"Bearer {_cfg()['auth_token']}"}

    last = None
    resp = None
    for attempt in range(3):
        try:  # 요청이 서버에 닿기 전의 연결 오류만 재시도 (중복 실행 방지)
            resp = requests.post(_base_url() + "/v2/pipeline", json={"requests": reqs},
                                 headers=headers, timeout=30)
            break
        except requests.ConnectionError as e:
            last = e
            time.sleep(1 + attempt)
        except requests.RequestException as e:
            raise RuntimeError(f"Turso 요청 실패: {e}")
    if resp is None:
        raise RuntimeError(f"Turso 연결 실패: {last}")
    if resp.status_code != 200:
        raise RuntimeError(f"Turso HTTP {resp.status_code}: {resp.text[:300]}")

    out = []
    for item in resp.json().get("results", [])[:len(stmts)]:
        if item.get("type") == "error":
            raise RuntimeError(item.get("error", {}).get("message", "Turso 쿼리 오류"))
        out.append(item["response"]["result"])
    return out


def _rows(sql: str, args: list = ()) -> list:
    res = _pipeline([(sql, list(args))])[0]
    names = [c["name"] for c in res.get("cols", [])]
    return [dict(zip(names, [_dec(v) for v in row])) for row in res.get("rows", [])]


def _exec(sql: str, args: list = ()):
    return _pipeline([(sql, list(args))])[0]


# ---------------------------------------------------------------- 스키마
_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS senders (
        email        TEXT PRIMARY KEY,
        display_name TEXT,
        is_active    INTEGER NOT NULL DEFAULT 1,
        is_admin     INTEGER NOT NULL DEFAULT 0,
        created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )""",
    """CREATE TABLE IF NOT EXISTS topics (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        name           TEXT NOT NULL UNIQUE,
        created_by     TEXT,
        default_preset TEXT,
        created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )""",
    """CREATE TABLE IF NOT EXISTS recipients (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT NOT NULL UNIQUE,
        company    TEXT,
        ceo        TEXT,
        industry   TEXT,
        rating     TEXT,
        updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )""",
    """CREATE TABLE IF NOT EXISTS send_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id     INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
        recipient_id INTEGER NOT NULL REFERENCES recipients(id) ON DELETE CASCADE,
        sender_email TEXT NOT NULL,
        sender_name  TEXT,
        status       TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','sent','failed')),
        subject      TEXT,
        body_html    TEXT,
        error        TEXT,
        claimed_at   TEXT NOT NULL,
        sent_at      TEXT,
        UNIQUE (topic_id, recipient_id)
    )""",
    """CREATE TABLE IF NOT EXISTS sender_prefs (
        email              TEXT PRIMARY KEY,
        body_mode          TEXT DEFAULT 'html',
        footer_mode        TEXT DEFAULT 'text',
        footer_text        TEXT,
        footer_html        TEXT,
        footer_image_b64   TEXT,
        footer_image_name  TEXT,
        footer_image_width INTEGER DEFAULT 60,
        footer_image_align TEXT DEFAULT '가운데',
        use_footer_image   INTEGER DEFAULT 0,
        updated_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
    )""",
    """CREATE TABLE IF NOT EXISTS mail_templates (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_email  TEXT NOT NULL,
        name         TEXT NOT NULL,
        subject      TEXT,
        body_mode    TEXT DEFAULT 'html',
        plain_body   TEXT,
        html_body    TEXT,
        image_insert_mode TEXT,
        image_width_pct   INTEGER DEFAULT 80,
        image_align       TEXT DEFAULT '가운데',
        created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now')),
        UNIQUE (owner_email, name)
    )""",
    "CREATE INDEX IF NOT EXISTS send_log_topic_idx  ON send_log (topic_id, status)",
    "CREATE INDEX IF NOT EXISTS send_log_sender_idx ON send_log (sender_email, sent_at)",
]

# 기존 DB에 컬럼이 없을 때 추가 (이미 있으면 무시)
_MIGRATIONS = [
    "ALTER TABLE topics ADD COLUMN default_preset TEXT",
]


@st.cache_resource
def init() -> bool:
    """테이블 생성 + secrets의 admin_email을 관리자 발신 계정으로 등록(없을 때만)."""
    _pipeline([(sql, []) for sql in _SCHEMA])
    for mig in _MIGRATIONS:
        try:
            _exec(mig)
        except Exception:
            pass  # 컬럼이 이미 있으면 오류 → 무시
    admin = str(_cfg().get("admin_email", "") or "").strip().lower()
    if admin:
        _exec("INSERT OR IGNORE INTO senders (email, display_name, is_active, is_admin) "
              "VALUES (?, ?, 1, 1)", [admin, admin])
    return True


# ---------------------------------------------------------------- 발신 계정
def get_sender(email: str):
    rows = _rows("SELECT email, display_name, is_active, is_admin FROM senders WHERE email = ?",
                 [email.strip().lower()])
    if not rows:
        return None
    r = rows[0]
    r["is_active"] = bool(r["is_active"])
    r["is_admin"] = bool(r["is_admin"])
    return r


def count_senders() -> int:
    return _rows("SELECT COUNT(*) AS n FROM senders")[0]["n"]


def list_senders() -> list:
    rows = _rows("SELECT email, display_name, is_active, is_admin FROM senders ORDER BY email")
    for r in rows:
        r["is_active"] = bool(r["is_active"])
        r["is_admin"] = bool(r["is_admin"])
    return rows


def upsert_sender(email: str, display_name: str, is_admin: bool, is_active: bool):
    _exec("""INSERT INTO senders (email, display_name, is_active, is_admin) VALUES (?, ?, ?, ?)
             ON CONFLICT(email) DO UPDATE SET
               display_name = excluded.display_name,
               is_active    = excluded.is_active,
               is_admin     = excluded.is_admin""",
          [email.strip().lower(), display_name.strip() or None, int(is_active), int(is_admin)])


# ---------------------------------------------------------------- 주제
def list_topics() -> list:
    return _rows("SELECT id, name, default_preset, created_at FROM topics ORDER BY created_at DESC, id DESC")


def create_topic(name: str, created_by: str, default_preset: str = None) -> int:
    name = name.strip()
    _exec("INSERT OR IGNORE INTO topics (name, created_by, default_preset, created_at) VALUES (?, ?, ?, ?)",
          [name, created_by, default_preset, _now()])
    return _rows("SELECT id FROM topics WHERE name = ?", [name])[0]["id"]


def set_topic_preset(topic_id: int, default_preset: str):
    _exec("UPDATE topics SET default_preset = ? WHERE id = ?",
          [default_preset or None, topic_id])


# ---------------------------------------------------------------- 발신자 기본 설정
def get_sender_prefs(email: str) -> dict:
    rows = _rows("SELECT * FROM sender_prefs WHERE email = ?", [email.strip().lower()])
    if not rows:
        return {}
    r = rows[0]
    r["use_footer_image"] = bool(r.get("use_footer_image"))
    return r


def save_sender_prefs(email: str, prefs: dict):
    email = email.strip().lower()
    _exec("""INSERT INTO sender_prefs (
                email, body_mode, footer_mode, footer_text, footer_html,
                footer_image_b64, footer_image_name, footer_image_width,
                footer_image_align, use_footer_image, updated_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(email) DO UPDATE SET
                body_mode = excluded.body_mode,
                footer_mode = excluded.footer_mode,
                footer_text = excluded.footer_text,
                footer_html = excluded.footer_html,
                footer_image_b64 = excluded.footer_image_b64,
                footer_image_name = excluded.footer_image_name,
                footer_image_width = excluded.footer_image_width,
                footer_image_align = excluded.footer_image_align,
                use_footer_image = excluded.use_footer_image,
                updated_at = excluded.updated_at""",
          [email,
           prefs.get("body_mode", "html"),
           prefs.get("footer_mode", "html"),
           prefs.get("footer_text"),
           prefs.get("footer_html"),
           prefs.get("footer_image_b64"),
           prefs.get("footer_image_name"),
           int(prefs.get("footer_image_width") or 60),
           prefs.get("footer_image_align") or "가운데",
           int(bool(prefs.get("use_footer_image"))),
           _now()])


# ---------------------------------------------------------------- 수신자
_UPSERT_RECIPIENT = """INSERT INTO recipients (email, company, ceo, industry, rating, updated_at)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(email) DO UPDATE SET
      company = excluded.company, ceo = excluded.ceo, industry = excluded.industry,
      rating = excluded.rating, updated_at = excluded.updated_at
    RETURNING id, email"""


def upsert_recipients(df) -> dict:
    """엑셀 명단을 recipients에 반영하고 {이메일: id}를 돌려줍니다."""
    now = _now()
    stmts = [(_UPSERT_RECIPIENT, [r["이메일"], str(r["회사명"]), str(r["대표자명"]),
                                   str(r["산업분류"]), str(r["AI_판정"]), now])
             for _, r in df.iterrows()]
    id_map = {}
    for i in range(0, len(stmts), 100):
        for res in _pipeline(stmts[i:i + 100]):
            for row in res.get("rows", []):
                id_map[_dec(row[1])] = _dec(row[0])
    return id_map


def count_recipients() -> int:
    return _rows("SELECT COUNT(*) AS n FROM recipients")[0]["n"]


# ---------------------------------------------------------------- 발송 기록
def topic_status(topic_id: int) -> dict:
    """{recipient_id: 로그행} — 상태 표시용(본문 제외)."""
    rows = _rows("""SELECT id, recipient_id, status, sender_email, sender_name, sent_at, claimed_at
                    FROM send_log WHERE topic_id = ?""", [topic_id])
    return {r["recipient_id"]: r for r in rows}


def claim_send(topic_id: int, recipient_id: int, sender_email: str, sender_name: str):
    """발송 권한 선점(단일 SQL문이라 원자적).

    성공 시 log id, 이미 발송됐거나 다른 계정이 진행 중이면 None.
    실패(failed) 건과 오래된 발송중(pending) 건은 다시 선점할 수 있습니다.
    """
    now = datetime.now(timezone.utc)
    rows = _rows("""INSERT INTO send_log
                      (topic_id, recipient_id, sender_email, sender_name, status, claimed_at)
                    VALUES (?, ?, ?, ?, 'pending', ?)
                    ON CONFLICT (topic_id, recipient_id) DO UPDATE SET
                      sender_email = excluded.sender_email,
                      sender_name  = excluded.sender_name,
                      status       = 'pending',
                      error        = NULL,
                      claimed_at   = excluded.claimed_at
                    WHERE send_log.status = 'failed'
                       OR (send_log.status = 'pending' AND send_log.claimed_at < ?)
                    RETURNING id""",
                 [topic_id, recipient_id, sender_email, sender_name, _iso(now),
                  _iso(now - timedelta(minutes=STALE_PENDING_MIN))])
    return rows[0]["id"] if rows else None


def _update_with_retry(sql: str, args: list, tries: int = 3):
    last = None
    for n in range(tries):
        try:
            _exec(sql, args)
            return
        except Exception as e:  # 네트워크 일시 오류 대비
            last = e
            time.sleep(1 + n)
    raise last


def mark_sent(log_id: int, subject: str, body_html: str):
    _update_with_retry(
        "UPDATE send_log SET status='sent', subject=?, body_html=?, sent_at=?, error=NULL WHERE id=?",
        [subject, body_html, _now(), log_id])


def mark_failed(log_id: int, error: str):
    _update_with_retry("UPDATE send_log SET status='failed', error=? WHERE id=?",
                       [error[:500], log_id])


def all_log_lite() -> list:
    return _rows("SELECT id, topic_id, status, sender_email FROM send_log")


def sent_today_by_sender() -> Counter:
    start_kst = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _rows("""SELECT sender_email, COUNT(*) AS n FROM send_log
                    WHERE status = 'sent' AND sent_at >= ? GROUP BY sender_email""",
                 [_iso(start_kst)])
    return Counter({r["sender_email"]: r["n"] for r in rows})


def log_detail(topic_id: int, sender_email: str = None, limit: int = 200) -> list:
    sql = """SELECT l.id, l.status, l.subject, l.sender_email, l.sender_name, l.sent_at,
                    l.claimed_at, l.error,
                    r.email AS r_email, r.company AS r_company, r.ceo AS r_ceo
             FROM send_log l JOIN recipients r ON r.id = l.recipient_id
             WHERE l.topic_id = ?"""
    args = [topic_id]
    if sender_email:
        sql += " AND l.sender_email = ?"
        args.append(sender_email)
    sql += " ORDER BY l.claimed_at DESC, l.id DESC LIMIT ?"
    args.append(limit)
    out = []
    for r in _rows(sql, args):
        r["recipients"] = {"email": r.pop("r_email"), "company": r.pop("r_company"),
                           "ceo": r.pop("r_ceo")}
        out.append(r)
    return out


def get_body(log_id: int) -> str:
    rows = _rows("SELECT body_html FROM send_log WHERE id = ?", [log_id])
    return (rows[0]["body_html"] if rows else "") or ""


# ---------------------------------------------------------------- 사용자 메일 템플릿
def list_mail_templates(owner_email: str) -> list:
    return _rows(
        "SELECT id, name, subject, body_mode, plain_body, html_body, "
        "image_insert_mode, image_width_pct, image_align, created_at "
        "FROM mail_templates WHERE owner_email = ? ORDER BY name",
        [owner_email.strip().lower()])


def save_mail_template(owner_email: str, name: str, data: dict) -> int:
    name = name.strip()
    owner = owner_email.strip().lower()
    _exec("""INSERT INTO mail_templates (
                owner_email, name, subject, body_mode, plain_body, html_body,
                image_insert_mode, image_width_pct, image_align, created_at
             ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
             ON CONFLICT(owner_email, name) DO UPDATE SET
                subject = excluded.subject,
                body_mode = excluded.body_mode,
                plain_body = excluded.plain_body,
                html_body = excluded.html_body,
                image_insert_mode = excluded.image_insert_mode,
                image_width_pct = excluded.image_width_pct,
                image_align = excluded.image_align""",
          [owner, name, data.get("subject"), data.get("body_mode", "html"),
           data.get("plain_body"), data.get("html_body"),
           data.get("image_insert_mode"), int(data.get("image_width_pct") or 80),
           data.get("image_align") or "가운데", _now()])
    return _rows("SELECT id FROM mail_templates WHERE owner_email = ? AND name = ?",
                 [owner, name])[0]["id"]


def get_mail_template(owner_email: str, name: str) -> dict:
    rows = _rows(
        "SELECT * FROM mail_templates WHERE owner_email = ? AND name = ?",
        [owner_email.strip().lower(), name.strip()])
    return rows[0] if rows else {}


def delete_mail_template(owner_email: str, name: str):
    _exec("DELETE FROM mail_templates WHERE owner_email = ? AND name = ?",
          [owner_email.strip().lower(), name.strip()])
