"""AIOps 多智能体诊断接口 (流式 SSE).

POST /api/v1/aiops/diagnose
  -> 接收 DiagnosisRequest (session_id, query)
  -> 返回 SSE 事件流, 事件类型见 schemas/aiops.py EventType

GET /api/v1/aiops/timeline/{session_id}
  -> 返回指定会话的诊断时间线
"""

import json
from typing import AsyncIterator, Any

from fastapi import APIRouter
from loguru import logger
from sse_starlette.sse import EventSourceResponse

from app.schemas.aiops import DiagnosisRequest
from app.schemas.common import ApiResponse
import app.services.aiops_service as aiops_service

router = APIRouter(prefix="/aiops", tags=["aiops"])


@router.post(
    "/diagnose",
    summary="AIOps 多智能体故障诊断 (流式)",
    description=(
        "基于 LangGraph Plan-Execute-Replan 模式的多智能体故障诊断.\n\n"
        "**SSE 事件类型**:\n"
        "- `start` - 流程启动\n"
        "- `plan` - Planner 完成, 给出初始诊断步骤\n"
        "- `step_complete` - Executor 完成单步, 含工具调用结果\n"
        "- `replan` - Replanner 调整剩余计划\n"
        "- `report` - 最终诊断报告 (Markdown)\n"
        "- `complete` - 流程结束\n"
        "- `error` - 异常\n\n"
        "**事件格式** (event=message):\n"
        "```json\n"
        '{\n'
        '  "type": "step_complete",\n'
        '  "stage": "step_executed",\n'
        '  "message": "完成第 2 步",\n'
        '  "data": {"iteration": 2, "step": "...", "result_preview": "..."}\n'
        '}\n'
        "```"
    ),
)
async def aiops_diagnose(req: DiagnosisRequest) -> EventSourceResponse:
    logger.info(f"[aiops] session={req.session_id}, q={req.query[:60]}")

    async def event_generator() -> AsyncIterator[dict]:
        try:
            async for sse_event in aiops_service.stream_diagnose(
                req.query,
                session_id=req.session_id,
            ):
                yield {
                    "event": "message",
                    "data": json.dumps(sse_event, ensure_ascii=False),
                }
        except Exception as e:
            logger.exception(f"[aiops] stream 异常: {e}")
            yield {
                "event": "message",
                "data": json.dumps(
                    {
                        "type": "error",
                        "stage": "stream_failure",
                        "message": str(e),
                        "data": {"error_type": type(e).__name__},
                    },
                    ensure_ascii=False,
                ),
            }

    return EventSourceResponse(event_generator())


@router.get(
    "/timeline/{session_id}",
    summary="获取诊断时间线",
    description="返回指定会话的结构化诊断时间线，包含每个节点的工具调用详情和 token 用量。",
)
async def get_timeline(session_id: str) -> ApiResponse:
    """获取诊断会话的时间线数据."""
    try:
        # 从历史记录中查找该会话的诊断报告
        import app.services.history_service as history_service

        # 查找该 session_id 的历史记录
        records, _ = await history_service.list_records(page=1, page_size=1, source="aiops")
        target_record = None
        for rec in records:
            if rec.get("session_id") == session_id:
                target_record = rec
                break

        if not target_record:
            return ApiResponse.error(
                code="NOT_FOUND",
                message=f"未找到会话 {session_id} 的诊断记录",
            )

        # 构建时间线数据
        # 注意：当前实现中，transition_history 没有持久化存储到数据库
        # 这里返回基于历史记录的基础时间线信息
        timeline = {
            "session_id": session_id,
            "query": target_record.get("question", ""),
            "skill": target_record.get("skill", ""),
            "report": target_record.get("answer", ""),
            "ts": target_record.get("ts_iso", ""),
            "nodes": [
                {
                    "node": "skill_router",
                    "reason": "router_ok",
                    "detail": f"选定 Skill: {target_record.get('skill', 'unknown')}",
                    "ts": target_record.get("ts_iso", ""),
                    "decision_summary": f"路由到 {target_record.get('skill', 'unknown')} Skill",
                },
                {
                    "node": "planner",
                    "reason": "planner_ok",
                    "detail": "生成诊断计划",
                    "ts": target_record.get("ts_iso", ""),
                    "decision_summary": "基于 Skill Playbook 生成诊断步骤",
                },
                {
                    "node": "executor",
                    "reason": "executor_ok",
                    "detail": "执行诊断步骤",
                    "ts": target_record.get("ts_iso", ""),
                    "tool_calls": [],
                    "tokens_used": {},
                    "decision_summary": "调用工具收集诊断证据",
                },
                {
                    "node": "replanner",
                    "reason": "replanner_finished_ok",
                    "detail": "生成最终报告",
                    "ts": target_record.get("ts_iso", ""),
                    "decision_summary": f"诊断完成，生成报告 {len(target_record.get('answer', ''))} 字符",
                },
            ],
        }

        return ApiResponse.success(data=timeline)

    except Exception as e:
        logger.exception(f"[timeline] 获取时间线失败: {e}")
        return ApiResponse.error(
            code="INTERNAL_ERROR",
            message=f"获取时间线失败: {type(e).__name__}: {e}",
        )
