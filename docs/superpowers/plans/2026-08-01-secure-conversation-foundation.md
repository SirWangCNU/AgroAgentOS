# Secure Conversation Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make agricultural chat sessions and history private to their owning account, remove duplicate session ORM registration, and restore a reliable backend test baseline.

**Architecture:** A session is created through the authenticated SessionService and owned by one user. Chat memory and persisted HistoryRecord writes use that owner; every read, delete and knowledge-base upload checks ownership. `app.core.sqlite` becomes the canonical session ORM location, while `app.models.session` only re-exports those models.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic Settings, pytest.

## Global Constraints

- Do not expose one user's chat context, history, or generated answers to another user.
- Do not alter or delete historical database rows without an explicit migration.
- Preserve the React flow: it creates an authenticated session before opening the SSE chat stream.
- Add regression tests before every production behavior change.

---

### Task 1: Add user-owned history persistence

**Files:**
- Modify: `app/core/sqlite.py`, `app/core/database.py`, `app/services/history_service.py`, `app/api/v1/history.py`
- Create: `alembic/versions/008_add_history_record_owner.py`
- Test: `tests/services/test_history_ownership.py`

**Interfaces:**
- Produces `HistoryRecord.user_id: int | None`.
- Produces `history_service.list_records(user_id=...)`, `get_record(record_id, user_id=...)`, `delete_record(record_id, user_id=...)`, and `clear_records(user_id=...)`.

- [ ] Write a failing test showing two user IDs cannot retrieve or delete each other's record.
- [ ] Run `pytest tests/services/test_history_ownership.py -q` and confirm the cross-user assertion fails.
- [ ] Add the owner column, owner-scoped SQL queries, authenticated router dependencies, and an Alembic migration that backfills owner IDs from matching sessions where possible.
- [ ] Run the same test and confirm it passes.

### Task 2: Make chat memory session ownership mandatory

**Files:**
- Modify: `app/api/v1/chat.py`, `app/services/chat_memory.py`, `app/services/rag_service.py`, `app/services/session_service.py`
- Test: `tests/api/test_chat_session_access.py`, `tests/services/test_chat_memory_keys.py`

**Interfaces:**
- Chat stream, read-memory and clear-memory routes consume `current_user: User`.
- `session_service.assert_session_owner(session_id, user_id)` returns the owned session or raises a not-found error.
- Redis key derivation consumes both `user_id` and `session_id`.

- [ ] Write failing tests for an unauthenticated chat stream and for two users receiving distinct Redis key material for the same session ID.
- [ ] Run the targeted tests and confirm they fail because the stream is optional-auth and memory keys omit the owner.
- [ ] Require authentication, validate session ownership before streaming or accessing memory, and scope Redis keys by account plus session.
- [ ] Run targeted tests and confirm they pass.

### Task 3: Consolidate the session ORM and fix test discovery

**Files:**
- Modify: `app/core/sqlite.py`, `app/models/session.py`, `requirements.txt`
- Create: `pytest.ini`, `tests/core/test_session_schema.py`

**Interfaces:**
- `app.models.session.ChatSession` and `ChatSessionMessage` re-export the canonical models from `app.core.sqlite`.
- `Base.metadata.create_all()` creates each index once.

- [ ] Write a failing schema test that imports SessionService and creates all metadata in a fresh in-memory SQLite engine.
- [ ] Run it and confirm it fails with duplicate `ix_chat_sessions_session_id`.
- [ ] Move the canonical session-message model to `app.core.sqlite`, replace duplicate ORM definitions with re-exports, and configure pytest to only collect `tests/` with asyncio support.
- [ ] Run the schema test and the complete `tests/` suite.

### Task 4: Validate security-critical configuration

**Files:**
- Modify: `app/config.py`, `.env.example`
- Test: `tests/core/test_settings_validation.py`

**Interfaces:**
- Runtime configuration reads application-scoped `AGRO_DEBUG` while retaining existing `DEBUG` compatibility only when valid.
- `validate_runtime()` rejects weak JWT secrets and the default administrator password outside debug mode.

- [ ] Write failing tests for `DEBUG=release`, an empty production JWT secret, and the production default admin password.
- [ ] Run the settings test and confirm the current configuration accepts or misparses these values.
- [ ] Add deterministic validation and documented `AGRO_` configuration names.
- [ ] Run the settings test and confirm it passes.

### Task 5: Verify the hardened foundation

**Files:**
- Test: `tests/`

- [ ] Run `python -m compileall -q app alembic scripts`.
- [ ] Run `pytest tests -q`.
- [ ] Run `npm run build` in `frontend-react/`.
- [ ] Run `git diff --check` and scan for unscoped history/session access.
