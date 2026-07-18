"""认证验证码接口测试."""

from __future__ import annotations

from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.v1 import auth
from app.exceptions import AppException
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services.captcha_service import create_captcha_challenge


def _make_test_client() -> TestClient:
    app = FastAPI()

    @app.exception_handler(AppException)
    async def handle_app_exception(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.error(
                code=exc.code,
                message=exc.message,
                detail=exc.detail,
            ).model_dump(),
        )

    app.include_router(auth.router, prefix="/api/v1")
    return TestClient(app)


def _make_user() -> User:
    return User(
        id=1,
        username="wangjh",
        email="wangjh@example.com",
        hashed_password="unused",
        role="user",
        is_active=1,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )


def test_get_captcha_returns_svg_challenge():
    client = _make_test_client()

    resp = client.get("/api/v1/auth/captcha")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "SUCCESS"
    assert body["data"]["captcha_token"]
    assert body["data"]["image_svg"].startswith("<svg")
    assert body["data"]["expires_in"] == 120


def test_login_rejects_missing_captcha():
    client = _make_test_client()

    resp = client.post(
        "/api/v1/auth/login",
        json={"username": "wangjh", "password": "secret123"},
    )

    assert resp.status_code == 422


def test_login_rejects_wrong_captcha(monkeypatch):
    client = _make_test_client()
    challenge = create_captcha_challenge(answer="0634")
    called = False

    def fake_authenticate_user(username: str, password: str) -> User:
        nonlocal called
        called = True
        return _make_user()

    monkeypatch.setattr(auth.auth_service, "authenticate_user", fake_authenticate_user)

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": "wangjh",
            "password": "secret123",
            "captcha_token": challenge.captcha_token,
            "captcha_answer": "9999",
        },
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "BAD_REQUEST"
    assert not called


def test_login_accepts_valid_captcha(monkeypatch):
    client = _make_test_client()
    challenge = create_captcha_challenge(answer="0634")

    monkeypatch.setattr(
        auth.auth_service,
        "authenticate_user",
        lambda username, password: _make_user(),
    )
    monkeypatch.setattr(auth, "create_access_token", lambda data: "test-token")

    resp = client.post(
        "/api/v1/auth/login",
        json={
            "username": "wangjh",
            "password": "secret123",
            "captcha_token": challenge.captcha_token,
            "captcha_answer": "0634",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == "SUCCESS"
    assert body["data"]["access_token"] == "test-token"
    assert body["data"]["user"]["username"] == "wangjh"
