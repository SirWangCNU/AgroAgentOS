"""轨迹作业数据摘要构建.

从 SQLite 查询用户的轨迹文件统计, 格式化为 LLM 可理解的结构化文本.
只查 TrajectoryFile 的聚合统计字段, 不查 TrajectoryPoint (数万条 GPS 点).
"""

from __future__ import annotations

from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.farm import Farm, Field
from app.models.trajectory import TrajectoryFile


def build_trajectory_context(
    db: Session,
    user_id: int,
    *,
    time_range: str = "",
    limit: int = 5,
) -> str:
    """构建用户近期作业数据摘要.

    Args:
        db: SQLAlchemy Session
        user_id: 用户 ID
        time_range: 时间范围 ("recent" 最近7天 / "month" 最近30天 / "" 最近N条)
        limit: 最大返回条数

    Returns:
        格式化的作业数据文本, 无数据时返回空字符串
    """
    query = (
        db.query(TrajectoryFile, Field, Farm)
        .join(Field, TrajectoryFile.field_id == Field.id)
        .join(Farm, Field.farm_id == Farm.id)
        .filter(Farm.user_id == user_id)
    )

    # 时间过滤
    if time_range == "recent":
        cutoff = datetime.now() - timedelta(days=7)
        query = query.filter(TrajectoryFile.start_time >= cutoff)
    elif time_range == "month":
        cutoff = datetime.now() - timedelta(days=30)
        query = query.filter(TrajectoryFile.start_time >= cutoff)

    records = (
        query.order_by(desc(TrajectoryFile.start_time))
        .limit(limit)
        .all()
    )

    if not records:
        return ""

    lines = ["【近期作业数据】"]
    for tf, field, farm in records:
        date_str = tf.start_time.strftime("%Y-%m-%d") if tf.start_time else "日期未知"
        machine = tf.machine_id or "未知"

        line_parts = [f"- {farm.name}/{field.name} {date_str} 作业记录："]
        line_parts.append(f"  文件：{tf.filename}，机具编号：{machine}")

        stats = []
        if tf.work_area_mu and tf.work_area_mu > 0:
            stats.append(f"面积 {tf.work_area_mu:.1f}亩")
        if tf.avg_depth and tf.avg_depth > 0:
            depth_part = f"平均耕深 {tf.avg_depth:.1f}cm"
            if tf.depth_std and tf.depth_std > 0:
                depth_part += f"（标准差 {tf.depth_std:.1f}cm）"
            stats.append(depth_part)
        if tf.avg_speed and tf.avg_speed > 0:
            stats.append(f"平均速度 {tf.avg_speed:.1f}km/h")
        if tf.work_distance_m and tf.work_distance_m > 0:
            dist_km = tf.work_distance_m / 1000
            stats.append(f"作业距离 {dist_km:.1f}km")
        if tf.total_distance_m and tf.total_distance_m > 0:
            total_km = tf.total_distance_m / 1000
            stats.append(f"总行驶 {total_km:.1f}km")

        if stats:
            line_parts.append("  " + "，".join(stats))

        lines.append("\n".join(line_parts))

    return "\n".join(lines)
