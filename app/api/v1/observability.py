"""Agent 可观测性接口.

GET /api/v1/observability/runs        - 查询 Agent 运行记录
GET /api/v1/observability/runs/{id}   - 获取单次运行详情
GET /api/v1/observability/stats       - 获取聚合统计信息
"""

from typing import Any

from fastapi import APIRouter

from app.schemas.common import ApiResponse
from app.core.sqlite import sqlite_manager, AgentRun

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/runs", summary="查询 Agent 运行记录（分页）")
async def list_runs(
    page: int = 1,
    page_size: int = 20,
    skill: str | None = None,
    status: str | None = None,
) -> ApiResponse:
    """分页查询 Agent 运行记录，默认按时间倒序."""
    if page < 1:
        return ApiResponse.error(code="INVALID_PARAM", message="page 必须 >= 1")
    if page_size < 1 or page_size > 100:
        return ApiResponse.error(code="INVALID_PARAM", message="page_size 必须在 1-100 之间")

    try:
        with sqlite_manager.session() as sess:
            query = sess.query(AgentRun)

            if skill:
                query = query.filter(AgentRun.selected_skill == skill)
            if status:
                query = query.filter(AgentRun.status == status)

            total = query.count()
            offset = (page - 1) * page_size
            runs = (
                query.order_by(AgentRun.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )

            return ApiResponse.success(data={
                "total": total,
                "page": page,
                "page_size": page_size,
                "runs": [_to_dict(r) for r in runs],
            })
    except Exception as e:
        from loguru import logger
        logger.warning(f"[observability] 查询失败: {type(e).__name__}: {e}")
        return ApiResponse.success(data={
            "total": 0,
            "page": page,
            "page_size": page_size,
            "runs": [],
        })


@router.get("/runs/{run_id}", summary="获取单次运行详情")
async def get_run(run_id: str) -> ApiResponse:
    """获取指定运行的详细信息，包含完整的 transitions 时间线."""
    try:
        with sqlite_manager.session() as sess:
            run = sess.query(AgentRun).filter(AgentRun.run_id == run_id).first()
            if run is None:
                return ApiResponse.error(
                    code="NOT_FOUND",
                    message=f"运行记录不存在: {run_id}",
                )

            result = _to_dict(run)
            result["transitions"] = run.transitions

            return ApiResponse.success(data=result)
    except Exception as e:
        from loguru import logger
        logger.warning(f"[observability] 读取运行记录失败: {type(e).__name__}: {e}")
        return ApiResponse.error(
            code="INTERNAL_ERROR",
            message=f"读取运行记录失败: {type(e).__name__}: {e}",
        )


@router.get("/stats", summary="获取 Agent 运行统计信息")
async def get_stats() -> ApiResponse:
    """获取 Agent 运行的聚合统计信息."""
    try:
        from sqlalchemy import func

        with sqlite_manager.session() as sess:
            # 总运行次数
            total_runs = sess.query(AgentRun).count()

            # 成功率
            completed_runs = sess.query(AgentRun).filter(
                AgentRun.status == "completed"
            ).count()
            success_rate = (completed_runs / total_runs * 100) if total_runs > 0 else 0

            # 平均 token 用量
            avg_tokens_result = sess.query(
                func.avg(AgentRun.total_tokens),
                func.avg(AgentRun.input_tokens),
                func.avg(AgentRun.output_tokens),
            ).first()
            avg_total_tokens = int(avg_tokens_result[0] or 0)
            avg_input_tokens = int(avg_tokens_result[1] or 0)
            avg_output_tokens = int(avg_tokens_result[2] or 0)

            # 平均耗时
            avg_ms_result = sess.query(func.avg(AgentRun.total_ms)).first()
            avg_ms = int(avg_ms_result[0] or 0)

            # 平均步骤数
            avg_steps_result = sess.query(func.avg(AgentRun.total_steps)).first()
            avg_steps = round(float(avg_steps_result[0] or 0), 1)

            # 按 Skill 统计
            skill_stats = {}
            for skill, count in sess.query(
                AgentRun.selected_skill, func.count(AgentRun.id)
            ).filter(AgentRun.selected_skill.isnot(None)).group_by(
                AgentRun.selected_skill
            ).order_by(func.count(AgentRun.id).desc()).all():
                skill_stats[skill] = count

            # 按状态统计
            status_stats = {}
            for status, count in sess.query(
                AgentRun.status, func.count(AgentRun.id)
            ).group_by(AgentRun.status).all():
                status_stats[status] = count

            # 最近 7 天的运行趋势
            from datetime import datetime, timedelta
            seven_days_ago = datetime.now() - timedelta(days=7)
            daily_trend = []
            for i in range(7):
                day_start = seven_days_ago + timedelta(days=i)
                day_end = day_start + timedelta(days=1)
                count = sess.query(AgentRun).filter(
                    AgentRun.created_at >= day_start,
                    AgentRun.created_at < day_end,
                ).count()
                daily_trend.append({
                    "date": day_start.strftime("%Y-%m-%d"),
                    "count": count,
                })

            return ApiResponse.success(data={
                "total_runs": total_runs,
                "success_rate": round(success_rate, 1),
                "avg_total_tokens": avg_total_tokens,
                "avg_input_tokens": avg_input_tokens,
                "avg_output_tokens": avg_output_tokens,
                "avg_ms": avg_ms,
                "avg_steps": avg_steps,
                "by_skill": skill_stats,
                "by_status": status_stats,
                "daily_trend": daily_trend,
            })
    except Exception as e:
        from loguru import logger
        logger.warning(f"[observability] 统计失败: {type(e).__name__}: {e}")
        return ApiResponse.success(data={
            "total_runs": 0,
            "success_rate": 0,
            "avg_total_tokens": 0,
            "avg_input_tokens": 0,
            "avg_output_tokens": 0,
            "avg_ms": 0,
            "avg_steps": 0,
            "by_skill": {},
            "by_status": {},
            "daily_trend": [],
        })


def _to_dict(run: AgentRun) -> dict[str, Any]:
    """将 AgentRun 模型转成前端可用的 dict."""
    return {
        "id": run.run_id,
        "session_id": run.session_id or "",
        "query": run.query or "",
        "skill": run.selected_skill or "",
        "status": run.status or "",
        "total_steps": run.total_steps or 0,
        "total_tool_calls": run.total_tool_calls or 0,
        "total_tokens": run.total_tokens or 0,
        "input_tokens": run.input_tokens or 0,
        "output_tokens": run.output_tokens or 0,
        "total_ms": run.total_ms or 0,
        "model_used": run.model_used or "",
        "reroute_count": run.reroute_count or 0,
        "report_preview": (run.report_preview or "")[:200],
        "ts": run.created_at.timestamp() if run.created_at else 0,
        "ts_iso": run.created_at.isoformat() if run.created_at else "",
    }
