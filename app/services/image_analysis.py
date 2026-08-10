"""Multimodal crop image analysis service.

This module uses DashScope's OpenAI-compatible Qwen-VL endpoint instead of a
local YOLO model. The service keeps the old API response shape compatible with
the frontend while returning richer diagnosis text from the vision model.
"""

from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger
from PIL import Image

from app.config import settings


@dataclass
class DetectionResult:
    label: str
    chinese_name: str
    confidence: float
    bbox: list[float] = field(default_factory=list)


@dataclass
class ImageAnalysisResult:
    success: bool
    summary: str
    image_size: list[int]
    detections: list[DetectionResult] = field(default_factory=list)
    diagnosis: str = ""
    model: str = ""


class ImageAnalysisService:
    """Analyze crop images with a multimodal model."""

    def __init__(self, timeout_sec: float | None = None) -> None:
        self._timeout_sec = timeout_sec or settings.dashscope_vision_timeout_sec

    def analyze(
        self,
        image_bytes: bytes,
        *,
        content_type: str = "image/jpeg",
        user_note: str = "",
    ) -> ImageAnalysisResult:
        image_size = _read_image_size(image_bytes)
        model = settings.dashscope_vision_model
        payload = _build_vision_payload(
            image_bytes=image_bytes,
            content_type=content_type,
            model=model,
            user_note=user_note,
        )

        try:
            raw_text = self._call_dashscope(payload)
            parsed = _parse_model_content(raw_text)
            detections = [_to_detection(item) for item in parsed.get("detections", [])]
            summary = str(parsed.get("summary") or "").strip()
            diagnosis = str(parsed.get("diagnosis") or raw_text or "").strip()
            if not summary:
                summary = diagnosis[:180] or "图片分析完成，但模型未返回摘要"

            return ImageAnalysisResult(
                success=True,
                detections=detections,
                summary=summary,
                diagnosis=diagnosis,
                image_size=image_size,
                model=model,
            )
        except Exception as exc:
            logger.exception(f"[image] multimodal analysis failed: {type(exc).__name__}: {exc}")
            return ImageAnalysisResult(
                success=False,
                detections=[],
                summary=f"图片分析失败: {type(exc).__name__}: {exc}",
                diagnosis="",
                image_size=image_size,
                model=model,
            )

    def _call_dashscope(self, payload: dict[str, Any]) -> str:
        api_key = (settings.dashscope_api_key or "").strip()
        if not api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未配置")

        url = f"{settings.dashscope_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout_sec) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise RuntimeError("多模态模型未返回 choices")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        return str(content)

    @classmethod
    def get_instance(cls) -> "ImageAnalysisService":
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        return None


def _read_image_size(image_bytes: bytes) -> list[int]:
    img = Image.open(io.BytesIO(image_bytes))
    return [img.width, img.height]


def _build_vision_payload(
    *,
    image_bytes: bytes,
    content_type: str,
    model: str,
    user_note: str,
) -> dict[str, Any]:
    data_url = _to_data_url(image_bytes, content_type)
    prompt = (
        "请作为植物保护专家分析这张农作物图片，判断是否存在病虫害或生理性问题。"
        "请只返回 JSON，不要使用 Markdown。JSON 字段为："
        "summary(string, 一句话摘要), "
        "detections(array, 每项含 label/chinese_name/confidence/bbox), "
        "diagnosis(string, 详细观察、疑似原因、补充问题和防治建议)。"
        "如果无法确认，请明确说明不确定性和需要补拍/补充的信息。"
    )
    if user_note.strip():
        prompt += f"\n用户补充说明：{user_note.strip()}"

    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是严谨的农业病虫害图像诊断助手，避免夸大确定性。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            },
        ],
        "temperature": 0.1,
    }


def _to_data_url(image_bytes: bytes, content_type: str) -> str:
    mime = content_type if content_type.startswith("image/") else "image/jpeg"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _parse_model_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            parsed = json.loads(text[start : end + 1])
        else:
            parsed = {"summary": text[:180], "diagnosis": text, "detections": []}

    if not isinstance(parsed, dict):
        return {"summary": str(parsed)[:180], "diagnosis": str(parsed), "detections": []}
    parsed.setdefault("detections", [])
    return parsed


def _to_detection(value: Any) -> DetectionResult:
    if not isinstance(value, dict):
        return DetectionResult(
            label="unknown",
            chinese_name="疑似病虫害",
            confidence=0.0,
            bbox=[],
        )

    confidence = value.get("confidence", 0.0)
    try:
        confidence_float = float(confidence)
    except (TypeError, ValueError):
        confidence_float = 0.0

    bbox = value.get("bbox") or []
    if not isinstance(bbox, list):
        bbox = []

    return DetectionResult(
        label=str(value.get("label") or "unknown"),
        chinese_name=str(value.get("chinese_name") or value.get("name") or "疑似病虫害"),
        confidence=max(0.0, min(1.0, confidence_float)),
        bbox=[float(x) for x in bbox if isinstance(x, int | float)],
    )
