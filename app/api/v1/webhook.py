"""外部告警 webhook 的安全接收边界。

当前项目尚未配置 webhook 签名密钥，因此告警只会被确认接收，不会猜测
用户/农场，也不会越过认证边界启动 Farm Agent。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/webhook", tags=["webhook"])


class AlertmanagerAlert(BaseModel):
    status: str = "firing"
    labels: dict[str, Any] = Field(default_factory=dict)
    annotations: dict[str, Any] = Field(default_factory=dict)
    startsAt: str = ""
    endsAt: str = ""
    generatorURL: str = ""
    fingerprint: str = ""


class AlertmanagerPayload(BaseModel):
    version: str = "4"
    status: str = "firing"
    alerts: list[AlertmanagerAlert] = Field(default_factory=list)


HISTORY_FILE = Path(__file__).resolve().parents[3] / "data" / "alert_history.jsonl"


@router.post("/alertmanager", summary="接收外部农场告警")
async def alertmanager_webhook(payload: AlertmanagerPayload) -> dict[str, Any]:
    """安全确认告警；无签名校验能力时绝不启动有身份的 Agent 运行。"""

    firing = [
        alert.labels.get("alertname", f"alert_{index}")
        for index, alert in enumerate(payload.alerts)
        if alert.status == "firing"
    ]
    if firing:
        logger.warning(
            "webhook 未配置签名与农场 owner 绑定，已接收但未启动 Farm Agent: {}",
            firing,
        )
    return {
        "status": "accepted",
        "received": len(payload.alerts),
        "triggered": [],
        "skipped": firing,
    }


@router.get("/history", summary="查看旧 webhook 接收历史")
async def get_history(limit: int = 20) -> dict[str, Any]:
    if not HISTORY_FILE.exists():
        return {"count": 0, "items": []}
    records: list[dict[str, Any]] = []
    with HISTORY_FILE.open("r", encoding="utf-8") as history_file:
        for line in history_file:
            try:
                records.append(json.loads(line))
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.warning("跳过无法解析的 webhook 历史行")
    items = list(reversed(records))[:limit]
    return {"count": len(items), "items": items}
