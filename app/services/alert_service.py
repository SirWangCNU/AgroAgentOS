"""告警管理服务 (SQLite-based).

提供告警的结构化存储、查询、状态管理和关联分析功能。
替代原有的 JSONL 存储方式，支持更强大的查询和聚合能力。

主要功能:
  - 告警接入: 解析 Alertmanager payload，按 fingerprint 去重
  - 状态管理: firing/resolved/acknowledged
  - 查询过滤: 按 severity/status/service/时间范围
  - 聚合统计: 按维度统计告警数量
  - 关联分析: 按 service/instance/时间窗口关联告警
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import func

from app.core.sqlite import sqlite_manager, Alert


async def ingest_alert(
    *,
    alertname: str,
    severity: str,
    status: str = "firing",
    instance: str = "",
    service: str = "",
    summary: str = "",
    description: str = "",
    labels: dict[str, Any] | None = None,
    annotations: dict[str, Any] | None = None,
    fingerprint: str = "",
    source: str = "alertmanager",
    starts_at: str = "",
) -> str | None:
    """接入一条告警，按 fingerprint 去重。

    如果 fingerprint 已存在且状态为 firing，则更新告警信息。
    如果 fingerprint 已存在且状态为 resolved，则创建新告警。

    Returns:
        alert_id if successful, None otherwise.
    """
    if not alertname:
        return None

    try:
        with sqlite_manager.session() as sess:
            # 按 fingerprint 去重
            if fingerprint:
                existing = sess.query(Alert).filter(
                    Alert.fingerprint == fingerprint,
                    Alert.status == "firing",
                ).first()

                if existing:
                    # 更新已有告警
                    existing.summary = summary or existing.summary
                    existing.description = description or existing.description
                    if labels:
                        existing.set_labels(labels)
                    if annotations:
                        existing.set_annotations(annotations)
                    logger.info(f"[alert] 更新已有告警 id={existing.alert_id} fingerprint={fingerprint}")
                    sess.flush()
                    sess.expunge(existing)
                    return existing.alert_id

            # 创建新告警
            alert_id = uuid.uuid4().hex[:16]
            alert = Alert(
                alert_id=alert_id,
                alertname=alertname[:256],
                severity=severity[:32],
                status=status[:32],
                instance=instance[:256] if instance else None,
                service=service[:128] if service else None,
                summary=summary[:2000] if summary else None,
                description=description[:5000] if description else None,
                fingerprint=fingerprint[:64] if fingerprint else None,
                source=source[:64],
            )
            if labels:
                alert.set_labels(labels)
            if annotations:
                alert.set_annotations(annotations)

            sess.add(alert)
            sess.flush()
            logger.info(f"[alert] 新增告警 id={alert_id} alertname={alertname} severity={severity}")
            return alert_id

    except Exception as e:
        logger.warning(f"[alert] 告警接入失败: {type(e).__name__}: {e}")
        return None


async def list_alerts(
    *,
    page: int = 1,
    page_size: int = 20,
    severity: str | None = None,
    status: str | None = None,
    service: str | None = None,
    alertname: str | None = None,
) -> dict[str, Any]:
    """分页查询告警列表 (时间倒序)."""
    try:
        with sqlite_manager.session() as sess:
            query = sess.query(Alert)

            if severity:
                query = query.filter(Alert.severity == severity)
            if status:
                query = query.filter(Alert.status == status)
            if service:
                query = query.filter(Alert.service == service)
            if alertname:
                query = query.filter(Alert.alertname.ilike(f"%{alertname}%"))

            total = query.count()
            offset = (page - 1) * page_size
            alerts = (
                query.order_by(Alert.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "alerts": [_to_dict(a) for a in alerts],
            }
    except Exception as e:
        logger.warning(f"[alert] 查询失败: {type(e).__name__}: {e}")
        return {"total": 0, "page": page, "page_size": page_size, "alerts": []}


async def get_alert(alert_id: str) -> dict[str, Any] | None:
    """获取单条告警详情."""
    try:
        with sqlite_manager.session() as sess:
            alert = sess.query(Alert).filter(Alert.alert_id == alert_id).first()
            if alert is None:
                return None
            result = _to_dict(alert)
            sess.expunge(alert)
            return result
    except Exception as e:
        logger.warning(f"[alert] 读取告警失败: {type(e).__name__}: {e}")
        return None


async def acknowledge_alert(alert_id: str, user: str = "system") -> bool:
    """确认告警."""
    try:
        with sqlite_manager.session() as sess:
            alert = sess.query(Alert).filter(Alert.alert_id == alert_id).first()
            if alert is None:
                return False

            alert.status = "acknowledged"
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = user[:128]
            sess.flush()
            logger.info(f"[alert] 告警已确认 id={alert_id} by={user}")
            return True
    except Exception as e:
        logger.warning(f"[alert] 确认告警失败: {type(e).__name__}: {e}")
        return False


async def resolve_alert(alert_id: str) -> bool:
    """解决告警."""
    try:
        with sqlite_manager.session() as sess:
            alert = sess.query(Alert).filter(Alert.alert_id == alert_id).first()
            if alert is None:
                return False

            alert.status = "resolved"
            alert.resolved_at = datetime.now(timezone.utc)
            sess.flush()
            logger.info(f"[alert] 告警已解决 id={alert_id}")
            return True
    except Exception as e:
        logger.warning(f"[alert] 解决告警失败: {type(e).__name__}: {e}")
        return False


async def update_diagnosis(
    alert_id: str,
    *,
    session_id: str,
    status: str = "completed",
    report: str = "",
) -> bool:
    """更新告警的诊断信息."""
    try:
        with sqlite_manager.session() as sess:
            alert = sess.query(Alert).filter(Alert.alert_id == alert_id).first()
            if alert is None:
                return False

            alert.diagnosis_session_id = session_id[:128]
            alert.diagnosis_status = status[:32]
            if report:
                alert.diagnosis_report = report[:50000]
            sess.flush()
            logger.info(f"[alert] 诊断信息已更新 id={alert_id} status={status}")
            return True
    except Exception as e:
        logger.warning(f"[alert] 更新诊断信息失败: {type(e).__name__}: {e}")
        return False


async def get_alert_stats() -> dict[str, Any]:
    """获取告警统计信息."""
    try:
        with sqlite_manager.session() as sess:
            # 总数
            total = sess.query(Alert).count()

            # 按 severity 统计
            severity_stats = {}
            for severity, count in sess.query(
                Alert.severity, func.count(Alert.id)
            ).group_by(Alert.severity).all():
                severity_stats[severity] = count

            # 按 status 统计
            status_stats = {}
            for status, count in sess.query(
                Alert.status, func.count(Alert.id)
            ).group_by(Alert.status).all():
                status_stats[status] = count

            # 按 service 统计 (Top 10)
            service_stats = {}
            for service, count in sess.query(
                Alert.service, func.count(Alert.id)
            ).filter(Alert.service.isnot(None)).group_by(Alert.service).order_by(
                func.count(Alert.id).desc()
            ).limit(10).all():
                service_stats[service] = count

            return {
                "total": total,
                "by_severity": severity_stats,
                "by_status": status_stats,
                "by_service": service_stats,
            }
    except Exception as e:
        logger.warning(f"[alert] 统计失败: {type(e).__name__}: {e}")
        return {"total": 0, "by_severity": {}, "by_status": {}, "by_service": {}}


async def correlate_alerts(alert_id: str, time_window_minutes: int = 30) -> list[dict[str, Any]]:
    """关联分析：查找与指定告警相关的告警。

    关联条件:
    - 同一 service
    - 同一 instance
    - 时间窗口内 (默认 30 分钟)
    """
    try:
        with sqlite_manager.session() as sess:
            target = sess.query(Alert).filter(Alert.alert_id == alert_id).first()
            if target is None:
                return []

            # 计算时间窗口
            from datetime import timedelta
            time_start = target.created_at - timedelta(minutes=time_window_minutes)
            time_end = target.created_at + timedelta(minutes=time_window_minutes)

            # 查询相关告警
            query = sess.query(Alert).filter(
                Alert.alert_id != alert_id,
                Alert.created_at.between(time_start, time_end),
            )

            # 按 service 或 instance 关联
            conditions = []
            if target.service:
                conditions.append(Alert.service == target.service)
            if target.instance:
                conditions.append(Alert.instance == target.instance)

            if conditions:
                from sqlalchemy import or_
                query = query.filter(or_(*conditions))

            related = query.order_by(Alert.created_at.desc()).limit(20).all()

            return [_to_dict(a) for a in related]
    except Exception as e:
        logger.warning(f"[alert] 关联分析失败: {type(e).__name__}: {e}")
        return []


async def clear_alerts() -> int:
    """清空所有告警."""
    try:
        with sqlite_manager.session() as sess:
            count = sess.query(Alert).delete()
            sess.flush()
            logger.info(f"[alert] 已清空 {count} 条告警")
            return count
    except Exception as e:
        logger.warning(f"[alert] 清空告警失败: {type(e).__name__}: {e}")
        return 0


def _to_dict(alert: Alert) -> dict[str, Any]:
    """将 Alert 模型转成前端可用的 dict."""
    return {
        "id": alert.alert_id,
        "alertname": alert.alertname,
        "severity": alert.severity,
        "status": alert.status,
        "instance": alert.instance or "",
        "service": alert.service or "",
        "summary": alert.summary or "",
        "description": alert.description or "",
        "labels": alert.labels,
        "annotations": alert.annotations,
        "fingerprint": alert.fingerprint or "",
        "source": alert.source,
        "diagnosis_session_id": alert.diagnosis_session_id or "",
        "diagnosis_status": alert.diagnosis_status or "",
        "diagnosis_report": alert.diagnosis_report or "",
        "ts": alert.created_at.timestamp() if alert.created_at else 0,
        "ts_iso": alert.created_at.isoformat() if alert.created_at else "",
        "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else "",
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else "",
        "acknowledged_by": alert.acknowledged_by or "",
    }
