"""验证码服务单元测试."""

from __future__ import annotations


class TestCaptchaService:
    def test_verify_accepts_matching_answer(self):
        """正确答案和未过期 token 应通过校验."""
        from app.services.captcha_service import (
            create_captcha_challenge,
            verify_captcha,
        )

        challenge = create_captcha_challenge(answer="0634", now=1_700_000_000)

        assert challenge.expires_in == 120
        assert challenge.captcha_token
        assert challenge.image_svg.startswith("<svg")
        assert verify_captcha(
            challenge.captcha_token,
            "0634",
            now=1_700_000_030,
        )

    def test_verify_rejects_wrong_answer(self):
        """错误答案应被拒绝."""
        from app.services.captcha_service import (
            create_captcha_challenge,
            verify_captcha,
        )

        challenge = create_captcha_challenge(answer="0634", now=1_700_000_000)

        assert not verify_captcha(
            challenge.captcha_token,
            "9999",
            now=1_700_000_030,
        )

    def test_verify_rejects_expired_token(self):
        """超过有效期的 token 应被拒绝."""
        from app.services.captcha_service import (
            create_captcha_challenge,
            verify_captcha,
        )

        challenge = create_captcha_challenge(answer="0634", now=1_700_000_000)

        assert not verify_captcha(
            challenge.captcha_token,
            "0634",
            now=1_700_000_121,
        )

    def test_verify_rejects_tampered_token(self):
        """被篡改的 token 应被拒绝."""
        from app.services.captcha_service import (
            create_captcha_challenge,
            verify_captcha,
        )

        challenge = create_captcha_challenge(answer="0634", now=1_700_000_000)
        tampered = challenge.captcha_token[:-1] + (
            "A" if challenge.captcha_token[-1] != "A" else "B"
        )

        assert not verify_captcha(tampered, "0634", now=1_700_000_030)
