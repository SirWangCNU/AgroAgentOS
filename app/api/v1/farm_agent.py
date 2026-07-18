"""Farm Agent 巡检、运行时间线与行动提案接口。"""

from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Query
from loguru import logger
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.farm_agent import (
    AgentRunTimelineResponse,
    FarmInspectionRequest,
    ProposalApprovalRequest,
    ProposalRejectRequest,
    ProposalResponse,
    ProposalStatus,
    TaskResponse,
)
from app.services import farm_agent_service, farm_proposal_service, farm_run_query_service

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
