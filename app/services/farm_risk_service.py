"""使用确定性阈值生成农场风险及可追溯证据。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import AppException
from app.schemas.farm_agent import FarmEvidence, Severity
from app.schemas.weather import WeatherForecastResult
from app.services import weather_service
from app.services.farm_snapshot_service import FarmSnapshot
from app.tools.weather_risk import classify_drainage_rainfall

_DEPTH_STD_THRESHOLD = 5.0
_MINIMUM_COVERAGE_RATIO = 0.8


class WeatherProvider(Protocol):
    """Farm 风险巡检所需的最小天气提供方契约。"""

    async def get_forecast_with_alerts(
        self,
        location: str,
        days: int = 2,
    ) -> WeatherForecastResult:
        """返回指定地点的短期天气预报。"""


class WeatherServiceProvider:
    """连接现有天气服务的生产适配器。"""

    async def get_forecast_with_alerts(
        self,
        location: str,
        days: int = 2,
    ) -> WeatherForecastResult:
        return await weather_service.get_weather_service().get_forecast_with_alerts(
            location,
            days=days,
        )


class FarmRisk(BaseModel):
    """确定性规则产生的单项风险。"""

    risk_key: str = Field(..., min_length=1, max_length=256)
    severity: Severity
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[FarmEvidence] = Field(..., min_length=1)
    suggested_actions: list[str] = Field(..., min_length=1)


class FarmInspectionResult(BaseModel):
    """农场风险巡检结果。"""

    risks: list[FarmRisk] = Field(default_factory=list)
    degraded: bool = False
    data_gaps: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    inspected_at: datetime


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _build_weather_risk(
    forecast: WeatherForecastResult,
    *,
    observed_at: datetime,
) -> FarmRisk | None:
    if not forecast.daily:
        return None

    precipitation_24h_mm = forecast.daily[0].precipitation_mm
    severity = classify_drainage_rainfall(precipitation_24h_mm)
    if severity is None:
        return None

    threshold_summary = "80mm critical" if severity == "critical" else "50mm high"
    return FarmRisk(
        risk_key="weather.rainstorm_drainage",
        severity=severity,
        confidence=0.95,
        evidence=[
            FarmEvidence(
                source_type="weather_forecast",
                source_id=f"{forecast.source}:{forecast.daily[0].date}",
                summary=(
                    f"未来 24 小时预计降雨 {precipitation_24h_mm:.1f}mm，"
                    f"达到排水风险阈值 {threshold_summary}"
                ),
                observed_at=observed_at,
                fact_kind="rule",
                payload={
                    "precipitation_24h_mm": precipitation_24h_mm,
                    "rule": threshold_summary,
                    "forecast_date": forecast.daily[0].date,
                },
            )
        ],
        suggested_actions=[
            "检查并清理地块排水沟和低洼积水点",
            "确认排水设备可用并安排降雨期间巡查",
        ],
    )


def _build_trajectory_risks(
    snapshot: FarmSnapshot,
    *,
    observed_at: datetime,
) -> list[FarmRisk]:
    fields_by_id = {field.id: field for field in snapshot.fields}
    risks: list[FarmRisk] = []

    for trajectory in snapshot.recent_trajectory_files:
        field = fields_by_id.get(trajectory.field_id)
        if field is None:
            continue

        triggered_rules: list[str] = []
        coverage_ratio: float | None = None
        if trajectory.depth_std > _DEPTH_STD_THRESHOLD:
            triggered_rules.append("depth_variability")
        if field.area_mu > 0:
            coverage_ratio = trajectory.work_area_mu / field.area_mu
            if coverage_ratio < _MINIMUM_COVERAGE_RATIO:
                triggered_rules.append("insufficient_coverage")
        if not triggered_rules:
            continue

        suggested_actions: list[str] = []
        if "depth_variability" in triggered_rules:
            suggested_actions.append("检查农机耕深标定和作业速度，复核深度波动区段")
        if "insufficient_coverage" in triggered_rules:
            suggested_actions.append("核对未覆盖区域并判断是否需要补作业")

        risks.append(
            FarmRisk(
                risk_key=(
                    f"trajectory.work_quality:{trajectory.field_id}:{trajectory.id}"
                ),
                severity="medium",
                confidence=0.9,
                evidence=[
                    FarmEvidence(
                        source_type="trajectory_file",
                        source_id=str(trajectory.id),
                        summary=f"轨迹 {trajectory.filename} 触发作业质量规则",
                        observed_at=trajectory.created_at or observed_at,
                        fact_kind="measured",
                        payload={
                            "field_id": field.id,
                            "trajectory_file_id": trajectory.id,
                            "depth_std": trajectory.depth_std,
                            "depth_std_threshold": _DEPTH_STD_THRESHOLD,
                            "work_area_mu": trajectory.work_area_mu,
                            "field_area_mu": field.area_mu,
                            "coverage_ratio": coverage_ratio,
                            "minimum_coverage_ratio": _MINIMUM_COVERAGE_RATIO,
                            "triggered_rules": triggered_rules,
                        },
                    )
                ],
                suggested_actions=suggested_actions,
            )
        )
    return risks


async def inspect_farm(
    snapshot: FarmSnapshot,
    *,
    weather_provider: WeatherProvider,
) -> FarmInspectionResult:
    """用确定性规则生成风险和证据，LLM 不参与阈值判定。"""

    inspected_at = datetime.now(timezone.utc)
    risks = _build_trajectory_risks(snapshot, observed_at=inspected_at)
    data_gaps = list(snapshot.data_gaps)
    warnings: list[str] = []
    degraded = False

    if not snapshot.farm.location.strip():
        degraded = True
        _append_unique(data_gaps, "weather_forecast_unavailable")
        warnings.append("农场位置缺失，无法获取天气预报")
    else:
        try:
            forecast = await weather_provider.get_forecast_with_alerts(
                snapshot.farm.location,
                days=2,
            )
        except SQLAlchemyError:
            raise
        except AppException as exc:
            if exc.status_code in {401, 403}:
                raise
            degraded = True
            _append_unique(data_gaps, "weather_forecast_unavailable")
            warnings.append("天气预报不可用，已跳过气象风险判断")
            logger.warning(
                "农场天气服务返回错误，风险巡检已降级: {}",
                exc.code,
            )
        except Exception as exc:
            degraded = True
            _append_unique(data_gaps, "weather_forecast_unavailable")
            warnings.append("天气预报不可用，已跳过气象风险判断")
            logger.warning("农场天气预报不可用，风险巡检已降级: {}", type(exc).__name__)
        else:
            if not forecast.daily:
                degraded = True
                _append_unique(data_gaps, "weather_forecast_unavailable")
                warnings.append("天气预报为空，已跳过气象风险判断")
                logger.warning("农场天气预报为空，风险巡检已降级")
            else:
                weather_risk = _build_weather_risk(
                    forecast,
                    observed_at=inspected_at,
                )
                if weather_risk is not None:
                    risks.insert(0, weather_risk)

    return FarmInspectionResult(
        risks=risks,
        degraded=degraded,
        data_gaps=data_gaps,
        warnings=warnings,
        inspected_at=inspected_at,
    )
