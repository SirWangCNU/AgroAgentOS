"""使用确定性阈值生成农场风险及可追溯证据。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from app.exceptions import AppException
from app.models.farm import SensorReading
from app.schemas.farm_agent import FarmEvidence, Severity
from app.schemas.weather import (
    DailyForecastDetail,
    WeatherAlert,
    WeatherForecastResult,
)
from app.services import weather_service
from app.services.farm_snapshot_service import FarmSnapshot
from app.tools.weather_risk import classify_drainage_rainfall

_DEPTH_STD_THRESHOLD = 5.0
_MINIMUM_COVERAGE_RATIO = 0.8
# 逐日预报只能作为首个预报日代理，不能支撑滚动未来 24 小时的高置信度判断。
FIRST_FORECAST_DAY_PROXY_CONFIDENCE = 0.75
_FIRST_FORECAST_DAY_PROXY_BASIS = "first_calendar_day_proxy"

# ===== 感知风险规则阈值（确定性，不调用 LLM）=====
# 虫害爆发：诱虫灯单灯计数（头/灯）
_PEST_COUNT_HIGH_THRESHOLD = 30
_PEST_COUNT_MEDIUM_THRESHOLD = 15
_PEST_AFFECTED_RATE_HIGH_THRESHOLD = 0.15  # 田间被害率 ≥15% 加重证据

# 缺肥黄化：NDVI 与土壤速效氮
_NDVI_DEFICIENCY_MEDIUM_THRESHOLD = 0.5
_NDVI_DEFICIENCY_HIGH_THRESHOLD = 0.45
_SOIL_NITROGEN_LOW_THRESHOLD = 80.0  # mg/kg

# 干旱胁迫：土壤含水量 %
_SOIL_MOISTURE_MEDIUM_THRESHOLD = 30.0
_SOIL_MOISTURE_HIGH_THRESHOLD = 25.0

# 感知读数是 measured 证据，置信度高
_SENSOR_RISK_CONFIDENCE = 0.9


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


class _DemoWeatherSpec(BaseModel):
    rainfall_24h_mm: float = Field(..., ge=0)
    observed_at: datetime


class _DemoRainstormFixture(BaseModel):
    scenario_id: str
    label: str
    weather: _DemoWeatherSpec


@lru_cache(maxsize=1)
def _load_demo_rainstorm_fixture() -> _DemoRainstormFixture:
    fixture_path = Path(__file__).resolve().parents[1] / "data" / "demo_rainstorm_scenario.json"
    return _DemoRainstormFixture.model_validate_json(
        fixture_path.read_text(encoding="utf-8")
    )


class CompetitionDemoRainstormWeatherProvider:
    """只在显式比赛演示请求中读取版本化的确定性天气。"""

    async def get_forecast_with_alerts(
        self,
        location: str,
        days: int = 2,
    ) -> WeatherForecastResult:
        fixture = await asyncio.to_thread(_load_demo_rainstorm_fixture)
        observed_date = fixture.weather.observed_at.date().isoformat()
        return WeatherForecastResult(
            location=location,
            daily=[
                DailyForecastDetail(
                    date=observed_date,
                    min_temp=24.0,
                    max_temp=29.0,
                    precipitation_mm=fixture.weather.rainfall_24h_mm,
                    condition="暴雨",
                    wind_level=5,
                )
            ],
            alerts=[
                WeatherAlert(
                    alert_type="暴雨",
                    date=observed_date,
                    severity="高",
                    advice="检查排水沟并安排降雨期间巡查",
                )
            ],
            source=f"competition-demo:{fixture.scenario_id}",
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


def _is_mock_or_fallback_source(source: str) -> bool:
    normalized_source = source.strip().lower()
    return any(marker in normalized_source for marker in ("mock", "fallback"))


def _build_weather_risk(
    forecast: WeatherForecastResult,
    *,
    observed_at: datetime,
) -> FarmRisk | None:
    if not forecast.daily:
        return None

    first_forecast_day = forecast.daily[0]
    precipitation_proxy_mm = first_forecast_day.precipitation_mm
    severity = classify_drainage_rainfall(precipitation_proxy_mm)
    if severity is None:
        return None

    threshold_summary = "80mm critical" if severity == "critical" else "50mm high"
    return FarmRisk(
        risk_key="weather.rainstorm_drainage",
        severity=severity,
        confidence=FIRST_FORECAST_DAY_PROXY_CONFIDENCE,
        evidence=[
            FarmEvidence(
                source_type="weather_forecast",
                source_id=f"{forecast.source}:{first_forecast_day.date}",
                summary=(
                    f"首个预报日 {first_forecast_day.date}（日历日代理）预计降雨 "
                    f"{precipitation_proxy_mm:.1f}mm，"
                    f"达到排水风险阈值 {threshold_summary}"
                ),
                observed_at=observed_at,
                fact_kind="rule",
                payload={
                    "forecast_basis": _FIRST_FORECAST_DAY_PROXY_BASIS,
                    "precipitation_first_forecast_day_mm": precipitation_proxy_mm,
                    "rule": threshold_summary,
                    "forecast_date": first_forecast_day.date,
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
    field_id: int | None = None,
    limit: int | None = None,
) -> list[FarmRisk]:
    fields_by_id = {field.id: field for field in snapshot.fields}
    risks: list[FarmRisk] = []

    for trajectory in snapshot.recent_trajectory_files:
        if field_id is not None and trajectory.field_id != field_id:
            continue
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
        if limit is not None and len(risks) >= limit:
            break
    return risks


def _build_pest_risk(
    *,
    field,
    pest_reading: SensorReading | None,
    anomaly_reading: SensorReading | None,
    observed_at: datetime,
) -> FarmRisk | None:
    """草地贪夜蛾/稻纵卷叶螟等虫害爆发风险（确定性阈值）."""
    if pest_reading is None:
        return None
    pest_value = pest_reading.value or {}
    count_per_light = pest_value.get("count_per_light")
    if count_per_light is None:
        # 兼容 value_float 兜底
        count_per_light = pest_reading.value_float

    if count_per_light is None:
        return None

    severity: Severity | None = None
    threshold_used = 0
    if count_per_light >= _PEST_COUNT_HIGH_THRESHOLD:
        severity = "high"
        threshold_used = _PEST_COUNT_HIGH_THRESHOLD
    elif count_per_light >= _PEST_COUNT_MEDIUM_THRESHOLD:
        severity = "medium"
        threshold_used = _PEST_COUNT_MEDIUM_THRESHOLD
    else:
        return None

    # 辅助证据：田间被害率
    affected_rate: float | None = None
    if anomaly_reading is not None:
        anomaly_value = anomaly_reading.value or {}
        affected_rate = anomaly_value.get("affected_rate")
        if affected_rate is None and anomaly_reading.value_float is not None:
            # 兼容以 % 存储的被害率
            affected_rate = anomaly_reading.value_float / 100.0

    pest_name = pest_value.get("pest_name", "未识别害虫")
    evidence_summary = (
        f"地块 {field.name}（{field.current_crop or '未知作物'}）"
        f"诱虫灯计数 {count_per_light} 头/灯，"
        f"达到虫害爆发阈值（≥{threshold_used}，{severity}）"
    )
    if affected_rate is not None:
        evidence_summary += f"；田间被害率 {affected_rate * 100:.1f}%"

    payload = {
        "field_id": field.id,
        "field_name": field.name,
        "crop": field.current_crop,
        "pest_name": pest_name,
        "count_per_light": count_per_light,
        "threshold_high": _PEST_COUNT_HIGH_THRESHOLD,
        "threshold_medium": _PEST_COUNT_MEDIUM_THRESHOLD,
        "observed_at": pest_reading.observed_at.isoformat(),
        "rule": f"count_per_light >= {threshold_used}",
    }
    if affected_rate is not None:
        payload["affected_rate"] = affected_rate
        payload["affected_rate_high_threshold"] = _PEST_AFFECTED_RATE_HIGH_THRESHOLD

    suggested_actions = [
        f"在 {field.name} 启动 {pest_name} 防治，参考当地植保站推荐药剂与窗口期",
        "增加诱虫灯巡查频率，连续 3 天记录虫口密度变化趋势",
        "检查周边地块是否同步爆发，必要时联防联控",
    ]
    if affected_rate is not None and affected_rate >= _PEST_AFFECTED_RATE_HIGH_THRESHOLD:
        suggested_actions.insert(0, f"优先对 {field.name} 高被害区域进行补喷")

    return FarmRisk(
        risk_key=f"pest.outbreak:{field.id}",
        severity=severity,
        confidence=_SENSOR_RISK_CONFIDENCE,
        evidence=[
            FarmEvidence(
                source_type="sensor_reading",
                source_id=f"sensor:{pest_reading.id}",
                summary=evidence_summary,
                observed_at=pest_reading.observed_at,
                fact_kind="measured",
                payload=payload,
            )
        ],
        suggested_actions=suggested_actions,
    )


def _build_nutrient_risk(
    *,
    field,
    ndvi_reading: SensorReading | None,
    soil_n_reading: SensorReading | None,
    anomaly_reading: SensorReading | None,
    observed_at: datetime,
) -> FarmRisk | None:
    """缺肥黄化风险（NDVI + 土壤速效氮 + 叶片黄化率）."""
    if ndvi_reading is None or ndvi_reading.value_float is None:
        return None

    ndvi = ndvi_reading.value_float
    severity: Severity | None = None
    if ndvi < _NDVI_DEFICIENCY_HIGH_THRESHOLD:
        severity = "high"
    elif ndvi < _NDVI_DEFICIENCY_MEDIUM_THRESHOLD:
        severity = "medium"
    else:
        return None

    # 辅助证据：土壤速效氮
    soil_n: float | None = None
    if soil_n_reading is not None and soil_n_reading.value_float is not None:
        soil_n = soil_n_reading.value_float
        # 速效氮偏低加重严重度
        if soil_n < _SOIL_NITROGEN_LOW_THRESHOLD and severity == "medium":
            severity = "high"

    # 辅助证据：叶片黄化率
    yellow_rate: float | None = None
    if anomaly_reading is not None:
        anomaly_value = anomaly_reading.value or {}
        symptom = anomaly_value.get("symptom", "")
        if "黄化" in symptom and anomaly_reading.value_float is not None:
            yellow_rate = anomaly_reading.value_float  # 以 % 存储

    evidence_summary = (
        f"地块 {field.name}（{field.current_crop or '未知作物'}）"
        f"NDVI={ndvi:.2f}，低于缺肥阈值 "
        f"{_NDVI_DEFICIENCY_HIGH_THRESHOLD if severity == 'high' else _NDVI_DEFICIENCY_MEDIUM_THRESHOLD}"
    )
    if soil_n is not None:
        evidence_summary += f"；土壤速效氮 {soil_n:.0f} mg/kg"
        if soil_n < _SOIL_NITROGEN_LOW_THRESHOLD:
            evidence_summary += f"（低于 {_SOIL_NITROGEN_LOW_THRESHOLD:.0f} 阈值）"
    if yellow_rate is not None:
        evidence_summary += f"；叶片黄化率 {yellow_rate:.1f}%"

    payload = {
        "field_id": field.id,
        "field_name": field.name,
        "crop": field.current_crop,
        "ndvi": ndvi,
        "ndvi_high_threshold": _NDVI_DEFICIENCY_HIGH_THRESHOLD,
        "ndvi_medium_threshold": _NDVI_DEFICIENCY_MEDIUM_THRESHOLD,
        "soil_nitrogen_low_threshold": _SOIL_NITROGEN_LOW_THRESHOLD,
        "observed_at": ndvi_reading.observed_at.isoformat(),
        "rule": f"ndvi < {_NDVI_DEFICIENCY_HIGH_THRESHOLD if severity == 'high' else _NDVI_DEFICIENCY_MEDIUM_THRESHOLD}",
    }
    if soil_n is not None:
        payload["soil_nitrogen_mg_per_kg"] = soil_n
    if yellow_rate is not None:
        payload["leaf_yellow_rate_pct"] = yellow_rate

    suggested_actions = [
        f"对 {field.name} 紧急追施氮肥（参考 {field.current_crop or '该作物'} 当前生育期需肥量）",
        "5-7 天后复测 NDVI 与叶片状态，评估追肥效果",
        "结合土壤速效氮检测结果调整后续施肥方案",
    ]

    return FarmRisk(
        risk_key=f"nutrient.deficiency:{field.id}",
        severity=severity,
        confidence=_SENSOR_RISK_CONFIDENCE,
        evidence=[
            FarmEvidence(
                source_type="sensor_reading",
                source_id=f"sensor:{ndvi_reading.id}",
                summary=evidence_summary,
                observed_at=ndvi_reading.observed_at,
                fact_kind="measured",
                payload=payload,
            )
        ],
        suggested_actions=suggested_actions,
    )


def _build_drought_risk(
    *,
    field,
    soil_moisture_reading: SensorReading | None,
    observed_at: datetime,
) -> FarmRisk | None:
    """干旱胁迫风险（土壤含水量阈值）."""
    if soil_moisture_reading is None or soil_moisture_reading.value_float is None:
        return None

    moisture = soil_moisture_reading.value_float
    severity: Severity | None = None
    threshold_used = 0.0
    if moisture < _SOIL_MOISTURE_HIGH_THRESHOLD:
        severity = "high"
        threshold_used = _SOIL_MOISTURE_HIGH_THRESHOLD
    elif moisture < _SOIL_MOISTURE_MEDIUM_THRESHOLD:
        severity = "medium"
        threshold_used = _SOIL_MOISTURE_MEDIUM_THRESHOLD
    else:
        return None

    moisture_value = soil_moisture_reading.value or {}
    depth_cm = moisture_value.get("depth_cm", 20)
    water_layer_cm = moisture_value.get("water_layer_cm")

    evidence_summary = (
        f"地块 {field.name}（{field.current_crop or '未知作物'}）"
        f"土壤含水量 {moisture:.1f}%（深度 {depth_cm}cm），"
        f"低于干旱阈值 {threshold_used:.0f}%（{severity}）"
    )
    if water_layer_cm is not None:
        evidence_summary += f"；田面水层 {water_layer_cm:.1f} cm"

    payload = {
        "field_id": field.id,
        "field_name": field.name,
        "crop": field.current_crop,
        "growth_stage": field.growth_stage,
        "soil_moisture_pct": moisture,
        "depth_cm": depth_cm,
        "threshold_high": _SOIL_MOISTURE_HIGH_THRESHOLD,
        "threshold_medium": _SOIL_MOISTURE_MEDIUM_THRESHOLD,
        "observed_at": soil_moisture_reading.observed_at.isoformat(),
        "rule": f"soil_moisture < {threshold_used}",
    }
    if water_layer_cm is not None:
        payload["water_layer_cm"] = water_layer_cm

    suggested_actions = [
        f"对 {field.name} 启动灌溉，参考 {field.current_crop or '该作物'} {field.growth_stage or '当前'} 生育期需水量",
        "灌溉后 24-48 小时复测土壤含水量，确认水分下渗深度",
        "检查灌溉设备覆盖均匀性，避免局部持续干旱",
    ]

    return FarmRisk(
        risk_key=f"drought.stress:{field.id}",
        severity=severity,
        confidence=_SENSOR_RISK_CONFIDENCE,
        evidence=[
            FarmEvidence(
                source_type="sensor_reading",
                source_id=f"sensor:{soil_moisture_reading.id}",
                summary=evidence_summary,
                observed_at=soil_moisture_reading.observed_at,
                fact_kind="measured",
                payload=payload,
            )
        ],
        suggested_actions=suggested_actions,
    )


def _build_sensor_risks(
    snapshot: FarmSnapshot,
    *,
    observed_at: datetime,
) -> list[FarmRisk]:
    """基于 snapshot.sensor_readings 生成 pest/nutrient/drought 风险.

    B7 实现后 farm_snapshot_service.build_snapshot 总是聚合近 7 天 SensorReading 到
    snapshot.sensor_readings，所以这里只读 snapshot，不再回退到 DB。
    确定性阈值，不调用 LLM，保证比赛现场可复现。
    """
    if not snapshot.fields:
        return []

    fields_by_id = {field.id: field for field in snapshot.fields}

    # 用 snapshot 已聚合的 sensor_readings（B7 实现后总会带，可能为空列表）
    readings_by_field: dict[int, dict[str, object]] = {}
    snapshot_sensor_readings = getattr(snapshot, "sensor_readings", None) or []
    for reading in snapshot_sensor_readings:
        bucket = readings_by_field.setdefault(reading.field_id, {})
        if reading.sensor_type not in bucket:
            bucket[reading.sensor_type] = reading

    risks: list[FarmRisk] = []
    for field_id, field in fields_by_id.items():
        readings = readings_by_field.get(field_id, {})

        pest_risk = _build_pest_risk(
            field=field,
            pest_reading=readings.get("pest_count"),
            anomaly_reading=readings.get("anomaly_image"),
            observed_at=observed_at,
        )
        if pest_risk is not None:
            risks.append(pest_risk)

        nutrient_risk = _build_nutrient_risk(
            field=field,
            ndvi_reading=readings.get("ndvi"),
            soil_n_reading=readings.get("soil_nitrogen"),
            anomaly_reading=readings.get("anomaly_image"),
            observed_at=observed_at,
        )
        if nutrient_risk is not None:
            risks.append(nutrient_risk)

        drought_risk = _build_drought_risk(
            field=field,
            soil_moisture_reading=readings.get("soil_moisture"),
            observed_at=observed_at,
        )
        if drought_risk is not None:
            risks.append(drought_risk)

    return risks


def inspect_field_work_quality(
    snapshot: FarmSnapshot,
    *,
    field_id: int | None = None,
    limit: int = 20,
) -> FarmInspectionResult:
    """Return deterministic trajectory-quality findings without network access."""

    inspected_at = datetime.now(timezone.utc)
    return FarmInspectionResult(
        risks=_build_trajectory_risks(
            snapshot,
            observed_at=inspected_at,
            field_id=field_id,
            limit=limit,
        ),
        data_gaps=list(snapshot.data_gaps),
        inspected_at=inspected_at,
    )


async def inspect_farm(
    snapshot: FarmSnapshot,
    *,
    weather_provider: WeatherProvider,
    days: int = 2,
) -> FarmInspectionResult:
    """用确定性规则生成风险和证据，LLM 不参与阈值判定。"""

    inspected_at = datetime.now(timezone.utc)
    risks = _build_trajectory_risks(snapshot, observed_at=inspected_at)
    # 感知风险：pest/nutrient/drought（确定性阈值，从 SensorReading 表生成）
    risks.extend(_build_sensor_risks(snapshot, observed_at=inspected_at))
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
                days=days,
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
            if _is_mock_or_fallback_source(forecast.source):
                degraded = True
                _append_unique(data_gaps, "weather_forecast_mock_fallback")
                warnings.append(
                    f"天气预报来源 {forecast.source!r} 为 mock/fallback，"
                    "已跳过气象风险判断"
                )
                logger.warning(
                    "天气预报来源为 mock/fallback，风险巡检已降级: {}",
                    forecast.source,
                )
            elif not forecast.daily:
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
