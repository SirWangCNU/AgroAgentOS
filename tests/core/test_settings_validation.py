"""安全关键配置必须在启动前得到确定结果。"""

import pytest

from app.config import Settings


def test_agro_debug_overrides_invalid_ambient_debug_value(monkeypatch):
    """防止宿主环境的 DEBUG=release 让应用无法解析配置。"""
    monkeypatch.setenv("DEBUG", "release")
    monkeypatch.setenv("AGRO_DEBUG", "false")

    settings = Settings(_env_file=None)

    assert settings.debug is False


def test_runtime_rejects_short_jwt_secret_in_production(monkeypatch):
    """移除 JWT 长度检查会允许可伪造的生产登录令牌。"""
    monkeypatch.delenv("DEBUG", raising=False)
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        debug=False,
        jwt_secret_key="too-short",
        admin_default_password="a-unique-admin-password",
    )

    with pytest.raises(RuntimeError, match="JWT"):
        settings.validate_runtime()


def test_runtime_rejects_example_jwt_secret_in_production(monkeypatch):
    """示例密钥即使足够长也不能进入生产环境。"""
    monkeypatch.delenv("DEBUG", raising=False)
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        debug=False,
        jwt_secret_key="change-this-to-a-random-secret-key-before-production",
        admin_default_password="a-unique-admin-password",
    )

    with pytest.raises(RuntimeError, match="JWT"):
        settings.validate_runtime()


def test_runtime_rejects_default_admin_password_in_production(monkeypatch):
    """移除默认密码检查会让首次部署使用公开凭据。"""
    monkeypatch.delenv("DEBUG", raising=False)
    settings = Settings(
        _env_file=None,
        dashscope_api_key="test-key",
        debug=False,
        jwt_secret_key="a" * 32,
        admin_default_password="admin123",
    )

    with pytest.raises(RuntimeError, match="管理员"):
        settings.validate_runtime()
