"""세션 토큰(HMAC 서명) 발급/검증과 로그인 시도 제한.

- 로그인(허용 목록 + Gmail SMTP 확인)에 성공하면 서명된 토큰을 발급하고,
  이후 모든 API 호출은 `Authorization: Bearer <토큰>` 헤더로 인증합니다.
- 운영에서는 환경변수 SESSION_SECRET(긴 무작위 문자열)을 반드시 설정하세요.
  없으면 서버가 켜질 때마다 임시 키를 만들어 재시작 시 모두 로그아웃됩니다.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets as _secrets
import time
from typing import Optional

_env_secret = os.environ.get("SESSION_SECRET", "").strip()
SECRET_IS_EPHEMERAL = not _env_secret
_SECRET = _env_secret.encode() if _env_secret else _secrets.token_bytes(32)
TTL_SECONDS = int(float(os.environ.get("SESSION_TTL_HOURS", "12")) * 3600)


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())


def issue(email: str) -> str:
    payload = _b64(json.dumps({"e": email, "exp": int(time.time()) + TTL_SECONDS},
                              separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def verify(token: str) -> Optional[str]:
    """유효하면 이메일, 아니면 None."""
    try:
        payload, sig = token.split(".")
        if not hmac.compare_digest(sig, _sign(payload)):
            return None
        data = json.loads(_unb64(payload))
        if float(data["exp"]) < time.time():
            return None
        return str(data["e"])
    except Exception:
        return None


# ---- 로그인 실패 횟수 제한 (계정별, 메모리) ----
_FAIL_LIMIT = 8
_FAIL_WINDOW = 600
_fails: dict = {}


def _recent(key: str) -> list:
    now = time.time()
    lst = [t for t in _fails.get(key, []) if now - t < _FAIL_WINDOW]
    _fails[key] = lst
    return lst


def too_many_failures(key: str) -> bool:
    return len(_recent(key)) >= _FAIL_LIMIT


def record_failure(key: str) -> None:
    _recent(key).append(time.time())


def clear_failures(key: str) -> None:
    _fails.pop(key, None)
