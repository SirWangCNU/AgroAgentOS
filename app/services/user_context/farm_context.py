"""农场/地块数据摘要构建.

从 SQLite 查询用户的农场和地块信息, 格式化为 LLM 可理解的结构化文本.
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.models.farm import Farm, Field


# ── 状态显示映射 ──────────────────────────────────────────────

_STATUS_DISPLAY = {
    "planting": "种植中",
    "idle": "空闲",
    "fallow": "休耕",
}


def build_farm_summary(db: Session, user_id: int) -> str:
    """构建用户农场概况摘要.

    查询所有农场及其地块, 格式化为结构化文本.
    数据量通常 <20 条, 全量注入.

    Args:
        db: SQLAlchemy Session
        user_id: 用户 ID

    Returns:
        格式化的农场概况文本, 无数据时返回空字符串
    """
    farms = (
        db.query(Farm)
        .filter(Farm.user_id == user_id)
        .order_by(Farm.created_at.desc())
        .all()
    )

    if not farms:
        return ""

    lines = [f"【用户农场概况】共 {len(farms)} 个农场"]
    total_mu = 0.0

    for farm in farms:
        total_mu += farm.area_mu or 0
        loc = f"（{farm.location}）" if farm.location else ""
        area_str = f"{farm.area_mu:.0f}亩" if farm.area_mu else "面积未设置"
        lines.append(f"- {farm.name}{loc}，{area_str}")

        # 查询该农场的地块
        fields = (
            db.query(Field)
            .filter(Field.farm_id == farm.id)
            .order_by(Field.name)
            .all()
        )

        if fields:
            lines.append(f"  共 {len(fields)} 个地块：")
            for field in fields:
                parts = []
                if field.current_crop:
                    parts.append(field.current_crop)
                if field.growth_stage:
                    parts.append(field.growth_stage)
                if field.area_mu:
                    parts.append(f"{field.area_mu:.0f}亩")
                if field.soil_type:
                    parts.append(field.soil_type)
                status = _STATUS_DISPLAY.get(field.status, field.status)
                if status and status != "空闲":
                    parts.append(status)

                detail = "，".join(parts) if parts else "暂无详细信息"
                lines.append(f"  · {field.name}：{detail}")
        else:
            lines.append("  暂无地块")

    if total_mu > 0:
        lines.insert(1, f"总耕地面积：{total_mu:.0f}亩")

    return "\n".join(lines)
