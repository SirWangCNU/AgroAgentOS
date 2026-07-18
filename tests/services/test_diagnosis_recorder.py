from typing import Any

import pytest

from app.core.database import DatabaseManager
from app.services import diagnosis_recorder as recorder_module
from app.services.diagnosis_recorder import DiagnosisRecorder


@pytest.mark.asyncio
async def test_internal_diagnosis_write_defaults_to_farm_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved_records: list[dict[str, Any]] = []

    def save_history_record(**kwargs: Any) -> None:
        saved_records.append(kwargs)

    monkeypatch.setattr(
        recorder_module.sqlite_manager,
        "save_history_record",
        save_history_record,
    )

    record_id = await DiagnosisRecorder().record_diagnosis(question="检查农场风险")

    assert record_id is not None
    assert saved_records[0]["source"] == "farm_agent"


@pytest.mark.asyncio
@pytest.mark.parametrize("method_name", ["record_diagnosis", "record_conversation"])
async def test_recorder_rejects_legacy_aiops_source_before_persistence(
    monkeypatch: pytest.MonkeyPatch,
    method_name: str,
) -> None:
    def unexpected_write(**kwargs: Any) -> None:
        raise AssertionError(f"unexpected persistence call: {kwargs}")

    monkeypatch.setattr(
        recorder_module.sqlite_manager,
        "save_history_record",
        unexpected_write,
    )
    recorder = DiagnosisRecorder()

    with pytest.raises(ValueError, match="aiops"):
        if method_name == "record_diagnosis":
            await recorder.record_diagnosis(question="旧运维写入", source="aiops")
        else:
            await recorder.record_conversation(
                session_id="session-001",
                user_message="旧运维写入",
                assistant_response="",
                source="aiops",
            )


def test_database_manager_rejects_legacy_aiops_source_before_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = DatabaseManager()

    def unexpected_session() -> None:
        raise AssertionError("database session must not open for an invalid source")

    monkeypatch.setattr(manager, "session", unexpected_session)

    with pytest.raises(ValueError, match="aiops"):
        manager.save_history_record(
            record_id="record-aiops-001",
            question="旧运维写入",
            source="aiops",
        )
