"""Redis 会话记忆必须按用户和会话双重隔离。"""

from app.services import chat_memory


def test_same_session_id_has_distinct_memory_keys_for_different_users():
    """防止只按 session_id 缓存时串入另一位用户的上下文。"""
    first_key = chat_memory._messages_key(user_id=101, session_id="shared-session")
    second_key = chat_memory._messages_key(user_id=202, session_id="shared-session")

    assert first_key != second_key
    assert "shared-session" not in first_key
