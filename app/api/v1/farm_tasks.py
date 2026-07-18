"""农场执行任务的人工门控和 AI 复核接口。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query
from starlette.responses import StreamingResponse

from app.api.deps import get_current_user
from app.api.v1.farm_agent import _sse_stream
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.farm_agent import TaskDecisionRequest, TaskResponse, TaskStatus, TaskSubmitRequest
from app.services import farm_agent_service, farm_task_service

router = APIRouter(prefix="/farm-tasks", tags=["farm-tasks"])


def _task_response(task: object) -> TaskResponse:
    return TaskResponse.model_validate(task)


@router.get("/", response_model=ApiResponse[list[TaskResponse]], summary="列出农场任务")
async def list_tasks(
    farm_id: int | None = Query(default=None, gt=0),
    status: TaskStatus | None = None,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[list[TaskResponse]]:
    tasks = await asyncio.to_thread(
        farm_task_service.list_tasks,
        user_id=current_user.id,
        farm_id=farm_id,
        status=status,
    )
    return ApiResponse.success(data=[_task_response(task) for task in tasks])


@router.post("/{task_id}/start", response_model=ApiResponse[TaskResponse])
async def start_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskResponse]:
    task = await asyncio.to_thread(farm_task_service.start, user_id=current_user.id, task_id=task_id)
    return ApiResponse.success(data=_task_response(task))


@router.post("/{task_id}/submit", response_model=ApiResponse[TaskResponse])
async def submit_task(
    task_id: str,
    request: TaskSubmitRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskResponse]:
    task = await asyncio.to_thread(
        farm_task_service.submit,
        user_id=current_user.id,
        task_id=task_id,
        request=request,
    )
    return ApiResponse.success(data=_task_response(task))


@router.post("/{task_id}/verify/stream", summary="生成 AI 复核草稿")
async def verify_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    return _sse_stream(
        farm_agent_service.stream_task_verification(
            user_id=current_user.id,
            task_id=task_id,
        )
    )


@router.post("/{task_id}/complete", response_model=ApiResponse[TaskResponse])
async def complete_task(
    task_id: str,
    request: TaskDecisionRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskResponse]:
    task = await asyncio.to_thread(
        farm_task_service.complete,
        user_id=current_user.id,
        task_id=task_id,
        note=request.note,
    )
    return ApiResponse.success(data=_task_response(task))


@router.post("/{task_id}/return", response_model=ApiResponse[TaskResponse])
async def return_task(
    task_id: str,
    request: TaskDecisionRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse[TaskResponse]:
    task = await asyncio.to_thread(
        farm_task_service.return_task,
        user_id=current_user.id,
        task_id=task_id,
        note=request.note,
    )
    return ApiResponse.success(data=_task_response(task))
