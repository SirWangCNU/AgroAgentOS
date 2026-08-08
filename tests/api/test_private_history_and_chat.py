"""聊天与历史接口必须要求已登录用户。"""

from fastapi.testclient import TestClient

from app.main import app


def test_chat_stream_rejects_anonymous_requests():
    """移除聊天认证依赖会让匿名请求读取任意会话上下文。"""
    client = TestClient(app)

    response = client.post(
        "/api/v1/chat/stream",
        json={"session_id": "any-session", "question": "水稻怎么施肥？"},
    )

    assert response.status_code == 401


def test_history_listing_rejects_anonymous_requests():
    """移除历史认证依赖会暴露所有用户的农业问答。"""
    client = TestClient(app)

    response = client.get("/api/v1/history")

    assert response.status_code == 401
