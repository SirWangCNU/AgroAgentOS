"""告警管理接口.

GET  /api/v1/alerts              - 分页查询告警列表
GET  /api/v1/alerts/stats        - 获取告警统计信息
GET  /api/v1/alerts/{id}         - 获取单条告警详情
POST /api/v1/alerts/{id}/acknowledge - 确认告警
POST /api/v1/alerts/{id}/resolve     - 解决告警
POST /api/v1/alerts/{id}/diagnose    - 触发告警诊断
DELETE /api/v1/alerts            - 清空所有告警
"""

from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks

from app.schemas.common import ApiResponse
import app.services.alert_service as alert_service
import app.services.aiops_service as aiops_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", summary="查询告警列表（分页）")
async def list_alerts(
    page: int = 1,
    page_size: int = 20,
    severity: str | None = None,
    status: str | None = None,
    service: str | None = None,
    alertname: str | None = None,
) -> ApiResponse:
    """分页查询告警列表，默认按时间倒序."""
    if page < 1:
        return ApiResponse.error(code="INVALID_PARAM", message="page 必须 >= 1")
    if page_size < 1 or page_size > 100:
        return ApiResponse.error(code="INVALID_PARAM", message="page_size 必须在 1-100 之间")

    data = await alert_service.list_alerts(
        page=page,
        page_size=page_size,
        severity=severity,
        status=status,
        service=service,
        alertname=alertname,
    )
    return ApiResponse.success(data=data)


@router.get("/stats", summary="获取告警统计信息")
async def get_alert_stats() -> ApiResponse:
    """获取告警的聚合统计信息，按 severity/status/service 维度."""
    stats = await alert_service.get_alert_stats()
    return ApiResponse.success(data=stats)


@router.get("/{alert_id}", summary="获取单条告警详情")
async def get_alert(alert_id: str) -> ApiResponse:
    """获取指定 ID 的告警详情，包含诊断报告."""
    alert = await alert_service.get_alert(alert_id)
    if alert is None:
        return ApiResponse.error(code="NOT_FOUND", message=f"告警不存在: {alert_id}")
    return ApiResponse.success(data=alert)


@router.post("/{alert_id}/acknowledge", summary="确认告警")
async def acknowledge_alert(alert_id: str, user: str = "system") -> ApiResponse:
    """确认告警，标记为 acknowledged 状态."""
    success = await alert_service.acknowledge_alert(alert_id, user=user)
    if not success:
        return ApiResponse.error(code="NOT_FOUND", message=f"告警不存在: {alert_id}")
    return ApiResponse.success(data={"alert_id": alert_id}, message="告警已确认")


@router.post("/{alert_id}/resolve", summary="解决告警")
async def resolve_alert(alert_id: str) -> ApiResponse:
    """解决告警，标记为 resolved 状态."""
    success = await alert_service.resolve_alert(alert_id)
    if not success:
        return ApiResponse.error(code="NOT_FOUND", message=f"告警不存在: {alert_id}")
    return ApiResponse.success(data={"alert_id": alert_id}, message="告警已解决")


@router.post("/{alert_id}/diagnose", summary="触发告警诊断")
async def diagnose_alert(
    alert_id: str,
    background: BackgroundTasks,
) -> ApiResponse:
    """为指定告警触发 AI 诊断."""
    alert = await alert_service.get_alert(alert_id)
    if alert is None:
        return ApiResponse.error(code="NOT_FOUND", message=f"告警不存在: {alert_id}")

    # 构建诊断查询
    query_parts = [
        f"[{alert['severity'].upper()}] {alert['alertname']} 告警触发",
    ]
    if alert['instance']:
        query_parts.append(f"实例: {alert['instance']}")
    if alert['service']:
        query_parts.append(f"服务: {alert['service']}")
    if alert['summary']:
        query_parts.append(f"摘要: {alert['summary']}")
    if alert['description']:
        query_parts.append(f"描述: {alert['description']}")
    query_parts.append("请你作为 OnCall 工程师，诊断上述告警根因并给出处置建议。")

    query = "\n".join(query_parts)
    session_id = f"alert-{alert_id[:12]}"

    # 后台异步执行诊断
    async def _run_diagnosis():
        try:
            # 更新诊断状态
            await alert_service.update_diagnosis(
                alert_id,
                session_id=session_id,
                status="running",
            )

            # 执行诊断
            final_report = ""
            async for event in aiops_service.stream_diagnose(query, session_id=session_id):
                if event.get("type") == "report":
                    final_report = event.get("data", {}).get("report", "")

            # 更新诊断结果
            await alert_service.update_diagnosis(
                alert_id,
                session_id=session_id,
                status="completed",
                report=final_report,
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).exception(f"[alert] 诊断失败: {e}")
            await alert_service.update_diagnosis(
                alert_id,
                session_id=session_id,
                status="failed",
            )

    background.add_task(_run_diagnosis)

    return ApiResponse.success(
        data={
            "alert_id": alert_id,
            "session_id": session_id,
        },
        message="诊断任务已提交，正在后台执行",
    )


@router.delete("", summary="清空所有告警")
async def clear_alerts() -> ApiResponse:
    """清空所有告警记录."""
    count = await alert_service.clear_alerts()
    return ApiResponse.success(data={"deleted_count": count})
