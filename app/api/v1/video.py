"""视频生成接口.

POST   /api/v1/video/generate        — 提交生成任务 (text + optional image)
GET    /api/v1/video/tasks            — 获取当前用户的任务列表
GET    /api/v1/video/tasks/{task_id}  — 查询单个任务状态/结果
"""

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_current_user
from app.core.database import database_manager
from app.core.sqlite import VideoTask
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.video import (
    VideoGenResponse,
    VideoTaskDetail,
    VideoTaskListResponse,
    VideoTaskStatus,
)
from app.services.video_gen_service import get_video_gen_service

router = APIRouter(prefix="/video", tags=["video"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post(
    "/generate",
    response_model=ApiResponse[VideoGenResponse],
    summary="提交视频生成任务",
    description="输入文本描述和可选图片, 异步生成短视频. 返回 task_id 用于轮询结果.",
)
async def generate_video(
    prompt: str = Form(..., min_length=1, max_length=2000, description="视频描述文本"),
    model: str = Form(None, description="模型名称 (可选)"),
    image: UploadFile = File(None, description="参考图片 (可选, JPEG/PNG/WebP)"),
    current_user: User = Depends(get_current_user),
):
    image_bytes = None
    if image:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            return ApiResponse.error("BAD_REQUEST", f"不支持的图片格式: {image.content_type}")
        image_bytes = await image.read()
        if len(image_bytes) > MAX_IMAGE_SIZE:
            return ApiResponse.error("BAD_REQUEST", "图片文件过大, 最大 10MB")

    service = get_video_gen_service()
    result = await service.submit_task(prompt=prompt, image_bytes=image_bytes, model=model)

    with database_manager.session() as sess:
        task = VideoTask(
            task_id=result["task_id"],
            user_id=current_user.id,
            prompt=prompt,
            model=model,
            status="pending",
        )
        sess.add(task)

    return ApiResponse.success(
        data=VideoGenResponse(task_id=result["task_id"], status=VideoTaskStatus.PENDING),
        message="视频生成任务已提交",
    )


@router.get(
    "/tasks",
    response_model=ApiResponse[VideoTaskListResponse],
    summary="获取视频生成任务列表",
    description="获取当前用户的所有视频生成任务, 按创建时间倒序.",
)
async def list_tasks(
    current_user: User = Depends(get_current_user),
    page: int = 1,
    page_size: int = 20,
):
    with database_manager.session() as sess:
        query = sess.query(VideoTask).filter(VideoTask.user_id == current_user.id)
        total = query.count()
        tasks = (
            query.order_by(VideoTask.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        task_list = [
            VideoTaskDetail(
                task_id=t.task_id,
                prompt=t.prompt,
                image_url=t.image_url,
                status=VideoTaskStatus(t.status),
                video_url=t.video_url,
                error_message=t.error_message,
                duration=t.duration,
                model=t.model,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in tasks
        ]

    return ApiResponse.success(data=VideoTaskListResponse(total=total, tasks=task_list))


@router.get(
    "/tasks/{task_id}",
    response_model=ApiResponse[VideoTaskDetail],
    summary="查询视频生成任务状态",
    description="查询指定任务的当前状态, 如已完成则返回视频 URL.",
)
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    with database_manager.session() as sess:
        task = (
            sess.query(VideoTask)
            .filter(VideoTask.task_id == task_id, VideoTask.user_id == current_user.id)
            .first()
        )
        if not task:
            return ApiResponse.error("NOT_FOUND", "任务不存在")

        if task.status in ("pending", "processing"):
            service = get_video_gen_service()
            result = await service.query_task(task_id)
            task.status = result["status"]
            if result.get("video_url"):
                task.video_url = result["video_url"]
            if result.get("error"):
                task.error_message = result["error"]
            if result.get("extra"):
                task.set_extra(result["extra"])

        detail = VideoTaskDetail(
            task_id=task.task_id,
            prompt=task.prompt,
            image_url=task.image_url,
            status=VideoTaskStatus(task.status),
            video_url=task.video_url,
            error_message=task.error_message,
            duration=task.duration,
            model=task.model,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    return ApiResponse.success(data=detail)
