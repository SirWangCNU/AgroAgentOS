"""视频生成服务 — Seedance 2.0 via 火山引擎 Ark API.

支持:
  - 文本生成视频 (text-to-video)
  - 图文混合生成视频 (image+text-to-video)
  - Mock 模式 (无 API Key 时)

设计:
  - 异步 HTTP 调用 (httpx)
  - 提交任务 + 轮询结果的异步模式
  - .env 可配置 API Key / Base URL / Model, 动态切换 provider
"""

from __future__ import annotations

import base64
import uuid
from typing import Any, Optional

import httpx
from loguru import logger

from app.config import settings
from app.exceptions import VideoGenerationError


class VideoGenService:
    """异步视频生成服务."""

    def __init__(self, api_key: str, base_url: str, model: str, timeout: int) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout, connect=10.0),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @property
    def is_mock(self) -> bool:
        return not self._api_key

    async def submit_task(
        self, prompt: str, image_bytes: Optional[bytes] = None, model: Optional[str] = None
    ) -> dict[str, Any]:
        """提交视频生成任务.

        Returns:
            {"task_id": str, "status": str}
        """
        if self.is_mock:
            return self._mock_submit(prompt)

        use_model = model or self._model
        client = await self._get_client()

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if image_bytes:
            b64_image = base64.b64encode(image_bytes).decode()
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
            })

        body = {"model": use_model, "content": content}

        try:
            resp = await client.post(f"{self._base_url}/contents/generations/tasks", json=body)
            resp.raise_for_status()
            data = resp.json()
            task_id = data.get("id") or data.get("task_id", "")
            logger.info(f"[video_gen] 任务已提交: {task_id}")
            return {"task_id": task_id, "status": "pending"}
        except httpx.TimeoutException:
            raise VideoGenerationError(message="视频生成服务请求超时")
        except httpx.HTTPStatusError as e:
            logger.error(f"[video_gen] API error: {e.response.status_code} {e.response.text}")
            raise VideoGenerationError(message=f"视频生成 API 错误: {e.response.status_code}")
        except Exception as e:
            logger.error(f"[video_gen] submit failed: {e}")
            raise VideoGenerationError(message=f"视频生成任务提交失败: {e}")

    async def query_task(self, task_id: str) -> dict[str, Any]:
        """查询任务状态.

        Returns:
            {"task_id": str, "status": str, "video_url": str|None, "error": str|None, "extra": dict}
        """
        if self.is_mock:
            return self._mock_query(task_id)

        client = await self._get_client()
        try:
            resp = await client.get(f"{self._base_url}/contents/generations/tasks/{task_id}")
            resp.raise_for_status()
            data = resp.json()

            api_status = data.get("status", "")
            status_map = {
                "submitted": "pending",
                "running": "processing",
                "succeeded": "completed",
                "failed": "failed",
            }
            status = status_map.get(api_status, "processing")

            video_url = None
            error_msg = None
            if status == "completed":
                outputs = data.get("output", {}).get("contents", [])
                if outputs:
                    video_url = outputs[0].get("url")
            elif status == "failed":
                error_msg = data.get("error", {}).get("message", "未知错误")

            return {
                "task_id": task_id,
                "status": status,
                "video_url": video_url,
                "error": error_msg,
                "extra": data,
            }
        except httpx.TimeoutException:
            raise VideoGenerationError(message="查询视频任务超时")
        except Exception as e:
            logger.error(f"[video_gen] query failed: {e}")
            raise VideoGenerationError(message=f"查询视频任务失败: {e}")

    def _mock_submit(self, prompt: str) -> dict[str, Any]:
        mock_id = f"mock-{uuid.uuid4().hex[:12]}"
        logger.info(f"[video_gen][MOCK] 任务已提交: {mock_id}")
        return {"task_id": mock_id, "status": "pending"}

    def _mock_query(self, task_id: str) -> dict[str, Any]:
        logger.info(f"[video_gen][MOCK] 查询任务: {task_id}")
        return {
            "task_id": task_id,
            "status": "completed",
            "video_url": "https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4",
            "error": None,
            "extra": {"mock": True},
        }


_video_gen_service: Optional[VideoGenService] = None


def get_video_gen_service() -> VideoGenService:
    """获取视频生成服务单例."""
    global _video_gen_service
    if _video_gen_service is None:
        _video_gen_service = VideoGenService(
            api_key=settings.video_gen_api_key,
            base_url=settings.video_gen_base_url,
            model=settings.video_gen_model,
            timeout=settings.video_gen_timeout,
        )
    return _video_gen_service


def reset_video_gen_service() -> None:
    """重置视频生成服务 (测试用)."""
    global _video_gen_service
    if _video_gen_service and _video_gen_service._client and not _video_gen_service._client.is_closed:
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_video_gen_service.close())
        except RuntimeError:
            pass
    _video_gen_service = None
