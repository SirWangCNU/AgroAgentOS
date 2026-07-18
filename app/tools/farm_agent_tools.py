"""Trusted-context adapters exposing controlled Farm Agent capabilities."""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.exceptions import AppException
from app.runtime.farm_run_context import FarmRunContext, require_farm_run_context
from app.schemas.farm_agent import (
    ProposalDraft,
    ProposalResponse,
    TaskResponse,
    TaskVerificationDraft,
)
from app.services import (
    farm_proposal_service,
    farm_risk_service,
    farm_snapshot_service,
    farm_task_service,
)


class PendingFarmTasksResult(BaseModel):
    """Bounded pending-task query result for an owned farm."""

    tasks: list[TaskResponse] = Field(default_factory=list)
    total: int = Field(default=0, ge=0)


def _require_task_id(context: FarmRunContext) -> str:
    if context.task_id is None:
        raise AppException(
            status_code=500,
            code="FARM_TASK_CONTEXT_MISSING",
            message="Farm Agent task context is missing",
        )
    return context.task_id


@tool
def get_farm_snapshot() -> dict[str, object]:
    """Return the trusted current farm snapshot with fields and recent evidence."""

    context = require_farm_run_context()
    snapshot = farm_snapshot_service.get_snapshot(
        farm_id=context.farm_id,
        user_id=context.user_id,
    )
    return snapshot.model_dump(mode="json")


@tool
async def inspect_farm_weather_risks(
    days: Annotated[int, Field(ge=1, le=7)] = 2,
) -> dict[str, object]:
    """Inspect deterministic weather risks for the trusted farm over 1 to 7 days."""

    context = require_farm_run_context()
    snapshot = farm_snapshot_service.get_snapshot(
        farm_id=context.farm_id,
        user_id=context.user_id,
    )
    inspection = await farm_risk_service.inspect_farm(
        snapshot,
        weather_provider=farm_risk_service.WeatherServiceProvider(),
        days=days,
    )
    weather_inspection = inspection.model_copy(
        update={
            "risks": [
                risk for risk in inspection.risks if risk.risk_key.startswith("weather.")
            ]
        }
    )
    return weather_inspection.model_dump(mode="json")


@tool
def get_field_work_quality(
    field_id: Annotated[int | None, Field(gt=0)] = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> dict[str, object]:
    """Return deterministic recent trajectory-quality findings for the trusted farm."""

    context = require_farm_run_context()
    snapshot = farm_snapshot_service.get_snapshot(
        farm_id=context.farm_id,
        user_id=context.user_id,
    )
    result = farm_risk_service.inspect_field_work_quality(
        snapshot,
        field_id=field_id,
        limit=limit,
    )
    return result.model_dump(mode="json")


@tool
def get_pending_farm_tasks(
    field_id: Annotated[int | None, Field(gt=0)] = None,
    task_type: Annotated[str | None, Field(min_length=1, max_length=64)] = None,
    limit: Annotated[int, Field(ge=1, le=50)] = 20,
) -> dict[str, object]:
    """Return bounded pending tasks for the trusted farm and optional business filters."""

    context = require_farm_run_context()
    tasks = farm_task_service.list_tasks(
        user_id=context.user_id,
        farm_id=context.farm_id,
        status="pending",
    )
    filtered = [
        task
        for task in tasks
        if (field_id is None or task.field_id == field_id)
        and (task_type is None or task.task_type == task_type)
    ][:limit]
    result = PendingFarmTasksResult(
        tasks=[TaskResponse.model_validate(task) for task in filtered],
        total=len(filtered),
    )
    return result.model_dump(mode="json")


@tool
def get_task_evidence() -> dict[str, object]:
    """Return evidence for the task bound to the trusted verification context."""

    context = require_farm_run_context()
    result = farm_task_service.get_task_evidence(
        user_id=context.user_id,
        task_id=_require_task_id(context),
    )
    return result.model_dump(mode="json")


@tool
def create_action_proposal(draft: ProposalDraft) -> dict[str, object]:
    """Create only a pending action proposal for the trusted farm run."""

    context = require_farm_run_context()
    proposal = farm_proposal_service.create_pending_proposal(
        user_id=context.user_id,
        farm_id=context.farm_id,
        run_id=context.run_id,
        draft=draft,
    )
    return ProposalResponse.model_validate(proposal).model_dump(mode="json")


@tool
def save_task_verification_draft(
    verdict: TaskVerificationDraft,
) -> dict[str, object]:
    """Save an AI verification draft without transitioning the trusted task."""

    context = require_farm_run_context()
    task = farm_task_service.save_verification_draft(
        user_id=context.user_id,
        task_id=_require_task_id(context),
        verdict=verdict,
    )
    return TaskResponse.model_validate(task).model_dump(mode="json")
