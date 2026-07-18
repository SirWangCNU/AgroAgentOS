"""登录验证码服务."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from html import escape

from app.config import settings

CAPTCHA_EXPIRES_IN = 120


@dataclass(frozen=True)
class CaptchaChallenge:
    """验证码挑战响应数据."""

    captcha_token: str
    image_svg: str
    expires_in: int


def create_captcha_challenge(
    answer: str | None = None,
    *,
    now: int | None = None,
) -> CaptchaChallenge:
    """创建验证码挑战.

    answer 和 now 仅用于测试构造可预测场景；生产调用不传。
    """
    issued_at = _current_time(now)
    captcha_answer = answer or f"{secrets.randbelow(10_000):04d}"
    nonce = secrets.token_urlsafe(16)
    expires_at = issued_at + CAPTCHA_EXPIRES_IN
    token = _encode_token(nonce, captcha_answer, expires_at)
    return CaptchaChallenge(
        captcha_token=token,
        image_svg=_render_svg(captcha_answer),
        expires_in=CAPTCHA_EXPIRES_IN,
    )


def verify_captcha(
    captcha_token: str,
    captcha_answer: str,
    *,
    now: int | None = None,
) -> bool:
    """校验验证码 token 与用户输入."""
    try:
        payload_b64, signature_b64 = captcha_token.split(".", 1)
        expected_signature = _sign_payload(payload_b64)
        if not hmac.compare_digest(signature_b64, expected_signature):
            return False

        payload = json.loads(_base64url_decode(payload_b64).decode("utf-8"))
        expires_at = int(payload["exp"])
        if _current_time(now) > expires_at:
            return False

        expected_digest = str(payload["answer_digest"])
        actual_digest = _answer_digest(str(payload["nonce"]), captcha_answer.strip())
        return hmac.compare_digest(expected_digest, actual_digest)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _encode_token(nonce: str, answer: str, expires_at: int) -> str:
    payload = {
        "nonce": nonce,
        "exp": expires_at,
        "answer_digest": _answer_digest(nonce, answer),
    }
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    payload_b64 = _base64url_encode(payload_json)
    signature_b64 = _sign_payload(payload_b64)
    return f"{payload_b64}.{signature_b64}"


def _answer_digest(nonce: str, answer: str) -> str:
    message = f"{nonce}:{answer}".encode("utf-8")
    return hmac.new(_answer_key(), message, hashlib.sha256).hexdigest()


def _sign_payload(payload_b64: str) -> str:
    signature = hmac.new(
        _signing_key(),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _base64url_encode(signature)


def _signing_key() -> bytes:
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        b"agroagentos:captcha:sign",
        hashlib.sha256,
    ).digest()


def _answer_key() -> bytes:
    return hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        b"agroagentos:captcha:answer",
        hashlib.sha256,
    ).digest()


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")


def _current_time(now: int | None) -> int:
    return int(time.time()) if now is None else now


def _render_svg(answer: str) -> str:
    digits = escape(answer)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="132" height="48" '
        'viewBox="0 0 132 48" role="img" aria-label="验证码">'
        '<rect width="132" height="48" rx="10" fill="#f8fbff"/>'
        '<path d="M7 36 C28 16, 48 46, 68 24 S105 10, 126 31" '
        'fill="none" stroke="#ef4444" stroke-width="2.2" opacity=".65"/>'
        '<path d="M10 14 C34 32, 55 4, 78 22 S108 40, 124 13" '
        'fill="none" stroke="#f59e0b" stroke-width="2" opacity=".7"/>'
        '<path d="M16 40 L116 8" stroke="#0ea5e9" stroke-width="1.6" '
        'opacity=".45"/>'
        '<text x="66" y="33" text-anchor="middle" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace" '
        'font-size="26" font-weight="800" letter-spacing="8" fill="#0f4c81" '
        f'transform="rotate(-5 66 24)">{digits}</text>'
        '<circle cx="21" cy="12" r="2" fill="#38bdf8" opacity=".8"/>'
        '<circle cx="109" cy="35" r="2.5" fill="#22c55e" opacity=".75"/>'
        "</svg>"
    )
