import asyncio
from types import SimpleNamespace

import pytest

from app.schemas.farm_agent import FarmInspectionRequest
from app.services import farm_agent_service


class _FakeGraph:
    async def astream(self, state, config):
        assert state["user_id"] == 7
        assert state["farm_id"] == 11
        assert state["run_type"] == "inspection"
        assert state["selected_skill"] == "farm_inspection"
        yield {"skill_router": {"selected_skill": "farm_inspection"}}
        yield {"planner": {"plan": ["检查风险"]}}
        yield {"replanner": {"response": "巡检报告", "proposal_ids": ["p-1"]}}


@pytest.mark.asyncio
async def test_inspection_stream_has_business_lifecycle(monkeypatch) -> None:
    snapshot = SimpleNamespace(model_dump=lambda mode: {"farm": {"id": 11}})
    risks = SimpleNamespace(model_dump=lambda mode: {"risks": []})
    persisted = []
    histories = []

    monkeypatch.setattr(farm_agent_service, "_get_graph", lambda: _FakeGraph())
    monkeypatch.setattr(
        farm_agent_service.farm_snapshot_service,
        "get_snapshot",
        lambda farm_id, user_id: snapshot,
    )

    async def inspect_farm(*args, **kwargs):
        return risks

    async def add_record(**kwargs):
        histories.append(kwargs)

    monkeypatch.setattr(farm_agent_service.farm_risk_service, "inspect_farm", inspect_farm)
    monkeypatch.setattr(farm_agent_service, "_add_history_record", add_record)
    monkeypatch.setattr(farm_agent_service, "_persist_run_start", lambda **kwargs: persisted.append(("start", kwargs)))
    monkeypatch.setattr(farm_agent_service, "_persist_run_finish", lambda **kwargs: persisted.append(("finish", kwargs)))

    events = [
        event
        async for event in farm_agent_service.stream_inspection(
            user_id=7,
            request=FarmInspectionRequest(farm_id=11),
        )
    ]

    types = [event["type"] for event in events]
    assert types[:4] == ["start", "context_loaded", "skill_selected", "plan"]
    assert types[-2:] == ["report", "complete"]
    assert histories[0]["source"] == "farm_agent"
    assert persisted[0][0] == "start"
    assert persisted[-1][1]["status"] == "completed"
    assert persisted[-1][1]["outcome"]["proposal_ids"] == ["p-1"]


@pytest.mark.asyncio
async def test_cancellation_is_persisted_and_sink_is_closed(monkeypatch) -> None:
    class CancelGraph:
        async def astream(self, state, config):
            raise asyncio.CancelledError
            yield

    snapshot = SimpleNamespace(model_dump=lambda mode: {"farm": {"id": 11}})
    risks = SimpleNamespace(model_dump=lambda mode: {"risks": []})
    finished = []
    monkeypatch.setattr(farm_agent_service, "_get_graph", lambda: CancelGraph())
    monkeypatch.setattr(farm_agent_service.farm_snapshot_service, "get_snapshot", lambda **kwargs: snapshot)
    monkeypatch.setattr(farm_agent_service.farm_risk_service, "inspect_farm", lambda *args, **kwargs: asyncio.sleep(0, result=risks))
    monkeypatch.setattr(farm_agent_service, "_persist_run_start", lambda **kwargs: None)
    monkeypatch.setattr(farm_agent_service, "_persist_run_finish", lambda **kwargs: finished.append(kwargs))

    with pytest.raises(asyncio.CancelledError):
        async for _ in farm_agent_service.stream_inspection(
            user_id=7, request=FarmInspectionRequest(farm_id=11)
        ):
            pass

    assert finished[-1]["status"] == "cancelled"
    assert farm_agent_service.get_sink() is None
