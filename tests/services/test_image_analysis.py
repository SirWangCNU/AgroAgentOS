"""Tests for multimodal crop image analysis."""

from __future__ import annotations

import io
from typing import Any

from PIL import Image

from app.services.image_analysis import ImageAnalysisService


def _make_image_bytes(width: int = 64, height: int = 48) -> bytes:
    img = Image.new("RGB", (width, height), color=(80, 120, 58))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeClient:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> _FakeResponse:
        self.payload = {"url": url, "headers": headers, "json": json}
        return _FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"summary":"疑似叶斑病，需补充作物种类确认。",'
                                '"detections":[{"label":"leaf_spot","chinese_name":"叶斑病",'
                                '"confidence":0.72,"bbox":[]}],'
                                '"diagnosis":"叶片可见斑点，应结合湿度和发病部位进一步确认。"}'
                            )
                        }
                    }
                ]
            }
        )


def test_analyze_builds_openai_compatible_vision_request(monkeypatch):
    fake_client = _FakeClient()
    monkeypatch.setattr(
        "app.services.image_analysis.httpx.Client",
        lambda **_: fake_client,
    )
    monkeypatch.setattr("app.services.image_analysis.settings.dashscope_api_key", "sk-test")
    monkeypatch.setattr(
        "app.services.image_analysis.settings.dashscope_base_url",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    monkeypatch.setattr("app.services.image_analysis.settings.dashscope_vision_model", "qwen-vl-plus")

    service = ImageAnalysisService()
    result = service.analyze(_make_image_bytes(), content_type="image/png")

    assert result.success is True
    assert result.summary == "疑似叶斑病，需补充作物种类确认。"
    assert result.image_size == [64, 48]
    assert result.detections[0].label == "leaf_spot"

    assert fake_client.payload is not None
    body = fake_client.payload["json"]
    assert body["model"] == "qwen-vl-plus"
    content = body["messages"][1]["content"]
    assert content[0]["type"] == "image_url"
    assert content[0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert content[1]["type"] == "text"
    assert "病虫害" in content[1]["text"]
