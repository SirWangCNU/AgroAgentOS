"""Farm Agent 运行记录的只读查询服务。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.sqlite import AgentRun, sqlite_manager
from app.exceptions import ForbiddenError
from app.models.farm import Farm
from app.schemas.farm_agent import AgentRunTimelineResponse, FarmAgentEvent


def _transition_event(run_id: str, index: int, transition: dict[str, Any]) -> FarmAgentEvent:
    node = str(transition.get("node") or "")
    event_type = {
        "skill_router": "skill_selected",
        "planner": "plan",
        "executor": "step_complete",
        "replanner": "replan",
        "fork_skill": "report",
    }.get(node, "step_complete")
    return FarmAgentEvent(
        event_id=f"{run_id}-transition-{index}",
        type=event_type,
        run_id=run_id,
        stage=str(transition.get("reason") or node),
        message=str(transition.get("detail") or ""),
        data=transition,
        ts=transition.get("ts"),
    )


def _timeline_response(run: AgentRun) -> AgentRunTimelineResponse:
    transitions = run.transitions
    outcome = run.outcome
    return AgentRunTimelineResponse(
        run_id=run.run_id,
        farm_id=run.farm_id,
        run_type=run.run_type,
        status=run.status,
        events=[
            _transition_event(run.run_id, index, transition)
            for index, transition in enumerate(transitions, start=1)
        ],
        total_steps=run.total_steps or 0,
        total_tool_calls=run.total_tool_calls or 0,
        total_tokens=run.total_tokens or 0,
        total_ms=run.total_ms or 0,
        context_snapshot=run.context_snapshot,
        outcome=outcome,
        proposal_ids=list(outcome.get("proposal_ids") or []),
        created_at=run.created_at,
    )


def _load_timeline(*, user_id: int, run_id: str) -> AgentRunTimelineResponse:
    with sqlite_manager.session() as session:
        run = (
            session.query(AgentRun)
            .filter(AgentRun.run_id == run_id, AgentRun.user_id == user_id)
            .first()
        )
        if run is None:
            # 不区分不存在和跨用户，避免泄露运行记录存在性。
            raise ForbiddenError(message="无权访问目标资源")
        return _timeline_response(run)


def _load_latest_inspection_run(
    *, user_id: int, farm_id: int | None = None
) -> AgentRunTimelineResponse | None:
    with sqlite_manager.session() as session:
        if farm_id is not None:
            owned = (
                session.query(Farm.id)
                .filter(Farm.id == farm_id, Farm.user_id == user_id)
                .first()
            )
            if owned is None:
                raise ForbiddenError(message="无权访问目标资源")

        query = session.query(AgentRun).filter(
            AgentRun.user_id == user_id,
            AgentRun.run_type == "inspection",
        )
        if farm_id is not None:
            query = query.filter(AgentRun.farm_id == farm_id)
        run = query.order_by(AgentRun.created_at.desc(), AgentRun.id.desc()).first()
        if run is None:
            return None
        return _timeline_response(run)


async def get_run_timeline(*, user_id: int, run_id: str) -> AgentRunTimelineResponse:
    """按当前用户读取真实持久化时间线。"""

    return await asyncio.to_thread(_load_timeline, user_id=user_id, run_id=run_id)


async def get_latest_inspection_run(
    *, user_id: int, farm_id: int | None = None
) -> AgentRunTimelineResponse | None:
    """读取当前用户最近一次已持久化的农场巡检运行。"""

    return await asyncio.to_thread(
        _load_latest_inspection_run,
        user_id=user_id,
        farm_id=farm_id,
    )


def _require_owned_farm(*, user_id: int, farm_id: int) -> None:
    with sqlite_manager.session() as session:
        owned = (
            session.query(Farm.id)
            .filter(Farm.id == farm_id, Farm.user_id == user_id)
            .first()
        )
        if owned is None:
            raise ForbiddenError(message="无权访问目标资源")


async def require_owned_farm(*, user_id: int, farm_id: int) -> None:
    """在建立 SSE 响应前完成农场所有权校验。"""

    await asyncio.to_thread(_require_owned_farm, user_id=user_id, farm_id=farm_id)
