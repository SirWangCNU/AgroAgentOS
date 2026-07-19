"""Farm Agent 巡检、运行时间线与行动提案接口。"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from loguru import logger
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.farm_agent import (
    AgentRunTimelineResponse,
    CropSeasonResponse,
    FarmEventResponse,
    FarmInspectionRequest,
    ProposalApprovalRequest,
    ProposalRejectRequest,
    ProposalResponse,
    ProposalStatus,
    SensorReadingResponse,
    TaskResponse,
)
from app.services import (
    farm_agent_service,
    farm_proposal_service,
    farm_query_service,
    farm_run_query_service,
)

router = APIRouter(prefix="/farm-agent", tags=["farm-agent"])


def _sse_stream(events: AsyncIterator[dict]) -> StreamingResponse:
    async def event_generator() -> AsyncIterator[str]:
        try:
            async for event in events:
                data = json.dumps(event, ensure_ascii=False, default=str)
                yield f"event: message\ndata: {data}\n\n"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Farm Agent SSE 输出失败: {}", exc)
            data = json.dumps(
                {
                    "type": "error",
                    "run_id": "",
                    "stage": "stream_failure",
                    "message": "Farm Agent 流式执行失败",
                    "data": {"error_type": type(exc).__name__},
                },
                ensure_ascii=False,
            )
            yield f"event: message\ndata: {data}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/inspections/stream", summary="启动 Farm Agent 综合巡检")
async def stream_inspection(
    request: FarmInspectionRequest,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    await farm_run_query_service.require_owned_farm(
        user_id=current_user.id,
        farm_id=request.farm_id,
    )
    return _sse_stream(
        farm_agent_service.stream_inspection(user_id=current_user.id, request=request)
    )


@router.get(
    "/runs/latest",
    response_model=ApiResponse[AgentRunTimelineResponse | None],
    summary="读取最近一次真实巡检运行",
)
async def get_latest_inspection_run(
    farm_id: int | None = Query(default=None, gt=0),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AgentRunTimelineResponse | None]:
    run = await farm_run_query_service.get_latest_inspection_run(
        user_id=current_user.id,
        farm_id=farm_id,
    )
    return ApiResponse.success(data=run)


@router.get(
    "/runs/{run_id}/timeline",
    response_model=ApiResponse[AgentRunTimelineResponse],
    summary="读取真实运行时间线",
)
async def get_run_timeline(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[AgentRunTimelineResponse]:
    timeline = await farm_run_query_service.get_run_timeline(
        user_id=current_user.id,
        run_id=run_id,
    )
    return ApiResponse.success(data=timeline)


@router.get(
    "/proposals",
    response_model=ApiResponse[list[ProposalResponse]],
    summary="列出当前用户的行动提案",
)
async def list_proposals(
    farm_id: int | None = Query(default=None, gt=0),
    status: ProposalStatus | None = None,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[ProposalResponse]]:
    proposals = await asyncio.to_thread(
        farm_proposal_service.list_proposals,
        user_id=current_user.id,
        farm_id=farm_id,
        status=status,
    )
    return ApiResponse.success(
        data=[ProposalResponse.model_validate(proposal) for proposal in proposals]
    )


@router.post("/proposals/{proposal_id}/approve", summary="人工批准行动提案")
async def approve_proposal(
    proposal_id: str,
    request: ProposalApprovalRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    proposal, tasks = await asyncio.to_thread(
        farm_proposal_service.approve,
        user_id=current_user.id,
        proposal_id=proposal_id,
        request=request,
    )
    proposal_response = ProposalResponse.model_validate(proposal)
    task_responses = [TaskResponse.model_validate(task) for task in tasks]
    return ApiResponse.success(
        data={
            "proposal": proposal_response.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in task_responses],
            "task_ids": [task.task_id for task in task_responses],
        }
    )


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=ApiResponse[ProposalResponse],
    summary="人工拒绝行动提案",
)
async def reject_proposal(
    proposal_id: str,
    request: ProposalRejectRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[ProposalResponse]:
    proposal = await asyncio.to_thread(
        farm_proposal_service.reject,
        user_id=current_user.id,
        proposal_id=proposal_id,
        request=request,
    )
    return ApiResponse.success(data=ProposalResponse.model_validate(proposal))


# ==================== B9 比赛演示场景/感知/事件/茬次查询接口 ====================


class ScenarioInjectRequest(BaseModel):
    """场景注入请求体."""

    farm_id: int


@router.get(
    "/scenarios",
    response_model=ApiResponse[list[dict]],
    summary="列出可用比赛演示场景",
)
async def list_scenarios(
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[dict]]:
    """返回 4 个比赛场景的元信息（label/字段数/感知数/天气摘要）."""
    metas = await asyncio.to_thread(farm_query_service.list_scenario_metas)
    return ApiResponse.success(
        data=[meta.model_dump(mode="json") for meta in metas]
    )


@router.post(
    "/scenarios/{scenario_id}/inject",
    response_model=ApiResponse[dict],
    summary="把比赛场景感知数据注入到指定农场",
)
async def inject_scenario(
    scenario_id: str,
    request: ScenarioInjectRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[dict]:
    """幂等注入：同一场景重复注入不会创建重复 sensor_readings.

    返回 InjectionReport（created_sensors / skipped_sensors / created_seasons 等）.
    """
    report = await asyncio.to_thread(
        farm_query_service.inject_scenario,
        user_id=current_user.id,
        farm_id=request.farm_id,
        scenario_id=scenario_id,
    )
    return ApiResponse.success(data=report.model_dump(mode="json"))


@router.get(
    "/sensors",
    response_model=ApiResponse[list[SensorReadingResponse]],
    summary="查询农场感知读数",
)
async def list_sensors(
    farm_id: int = Query(..., gt=0),
    field_id: int | None = Query(default=None, gt=0),
    sensor_type: str | None = Query(default=None),
    days: int | None = Query(default=7, ge=1, le=365),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[SensorReadingResponse]]:
    """按农场/地块/类型/天数查询感知读数，最近 N 天倒序."""
    rows = await asyncio.to_thread(
        farm_query_service.list_sensor_readings,
        user_id=current_user.id,
        farm_id=farm_id,
        field_id=field_id,
        sensor_type=sensor_type,
        days=days,
    )
    return ApiResponse.success(
        data=[SensorReadingResponse.model_validate(row) for row in rows]
    )


@router.get(
    "/events",
    response_model=ApiResponse[list[FarmEventResponse]],
    summary="查询农场事件流",
)
async def list_events(
    farm_id: int = Query(..., gt=0),
    field_id: int | None = Query(default=None, gt=0),
    days: int | None = Query(default=14, ge=1, le=365),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[FarmEventResponse]]:
    """按农场/地块/天数查询农场事件，最近 N 天倒序."""
    rows = await asyncio.to_thread(
        farm_query_service.list_farm_events,
        user_id=current_user.id,
        farm_id=farm_id,
        field_id=field_id,
        days=days,
    )
    return ApiResponse.success(
        data=[FarmEventResponse.model_validate(row) for row in rows]
    )


@router.get(
    "/seasons",
    response_model=ApiResponse[list[CropSeasonResponse]],
    summary="查询农场茬次",
)
async def list_seasons(
    farm_id: int = Query(..., gt=0),
    field_id: int | None = Query(default=None, gt=0),
    status: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[CropSeasonResponse]]:
    """按农场/地块/状态查询茬次，按 start_date 倒序."""
    rows = await asyncio.to_thread(
        farm_query_service.list_crop_seasons,
        user_id=current_user.id,
        farm_id=farm_id,
        field_id=field_id,
        status=status,
    )
    return ApiResponse.success(
        data=[CropSeasonResponse.model_validate(row) for row in rows]
    )
