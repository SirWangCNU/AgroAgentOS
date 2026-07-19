"""B6 新增的 pest/nutrient/drought 感知风险规则测试.

规则来自 farm_risk_service 中的确定性阈值（不调用 LLM）：
  - pest.outbreak: 诱虫灯计数 ≥30 high, ≥15 medium
  - nutrient.deficiency: NDVI <0.45 high, <0.5 medium；速效氮 <80 mg/kg 加重升级
  - drought.stress: 土壤含水量 <25% high, <30% medium
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.farm import Field, SensorReading
from app.services.farm_risk_service import (
    FarmRisk,
    _build_drought_risk,
    _build_nutrient_risk,
    _build_pest_risk,
    _build_sensor_risks,
    inspect_farm,
)
from app.services.farm_snapshot_service import FarmSnapshot


_OBSERVED_AT = datetime(2026, 7, 25, 8, 0, 0, tzinfo=timezone.utc)


def _make_field(
    *,
    id: int = 11,
    name: str = "A1",
    crop: str = "玉米",
    stage: str = "大喇叭口期",
) -> Field:
    field = Field(
        farm_id=1,
        name=name,
        area_mu=10.0,
        current_crop=crop,
        growth_stage=stage,
    )
    field.id = id
    return field


def _make_reading(
    *,
    id: int,
    sensor_type: str,
    value_float: float | None = None,
    value: dict | None = None,
    observed_at: datetime = _OBSERVED_AT,
    field_id: int = 11,
) -> SensorReading:
    reading = SensorReading(
        field_id=field_id,
        sensor_type=sensor_type,
        value_float=value_float,
        observed_at=observed_at,
        source="demo_scenario",
        scenario_id="test",
        note="",
        unit="",
    )
    reading.id = id
    if value is not None:
        reading.set_value(value)
    return reading


# ==================== pest.outbreak ====================


def test_pest_outbreak_high_risk_with_affected_rate() -> None:
    """35 头/灯 + 被害率 18% → pest.outbreak high，含'优先补喷'建议."""
    field = _make_field()
    pest = _make_reading(
        id=1,
        sensor_type="pest_count",
        value_float=35.0,
        value={"pest_name": "草地贪夜蛾", "count_per_light": 35},
    )
    anomaly = _make_reading(
        id=2,
        sensor_type="anomaly_image",
        value_float=18.0,
        value={"symptom": "叶片缺刻", "affected_rate": 0.18},
    )

    risk = _build_pest_risk(
        field=field,
        pest_reading=pest,
        anomaly_reading=anomaly,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.risk_key == f"pest.outbreak:{field.id}"
    assert risk.severity == "high"
    assert risk.confidence == 0.9
    evidence_payload = risk.evidence[0].payload
    assert evidence_payload["count_per_light"] == 35
    assert evidence_payload["affected_rate"] == 0.18
    # affected_rate ≥15% → 应该在最前面插入"优先补喷"
    assert "优先" in risk.suggested_actions[0]


def test_pest_outbreak_medium_risk_without_anomaly() -> None:
    """20 头/灯，无田间被害率证据 → pest.outbreak medium."""
    field = _make_field()
    pest = _make_reading(
        id=1,
        sensor_type="pest_count",
        value_float=20.0,
        value={"pest_name": "稻纵卷叶螟", "count_per_light": 20},
    )

    risk = _build_pest_risk(
        field=field,
        pest_reading=pest,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"
    assert "affected_rate" not in risk.evidence[0].payload


@pytest.mark.parametrize("count_per_light", [0, 5, 14.9])
def test_pest_below_threshold_no_risk(count_per_light: float) -> None:
    """虫量 <15 → 不触发风险."""
    field = _make_field()
    pest = _make_reading(
        id=1,
        sensor_type="pest_count",
        value_float=count_per_light,
        value={"pest_name": "草地贪夜蛾", "count_per_light": count_per_light},
    )

    risk = _build_pest_risk(
        field=field,
        pest_reading=pest,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is None


def test_pest_threshold_boundary_30_is_high() -> None:
    """30 头/灯（边界值，含等号）→ high."""
    field = _make_field()
    pest = _make_reading(
        id=1,
        sensor_type="pest_count",
        value_float=30.0,
        value={"pest_name": "草地贪夜蛾", "count_per_light": 30},
    )

    risk = _build_pest_risk(
        field=field,
        pest_reading=pest,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "high"


def test_pest_threshold_boundary_15_is_medium() -> None:
    """15 头/灯（边界值，含等号）→ medium."""
    field = _make_field()
    pest = _make_reading(
        id=1,
        sensor_type="pest_count",
        value_float=15.0,
        value={"pest_name": "草地贪夜蛾", "count_per_light": 15},
    )

    risk = _build_pest_risk(
        field=field,
        pest_reading=pest,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"


def test_pest_reading_falls_back_to_value_float_when_json_missing() -> None:
    """value_json 没有 count_per_light 时，回退到 value_float."""
    field = _make_field()
    pest = _make_reading(
        id=1,
        sensor_type="pest_count",
        value_float=35.0,
        value={},  # 没有 count_per_light
    )

    risk = _build_pest_risk(
        field=field,
        pest_reading=pest,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "high"
    assert risk.evidence[0].payload["count_per_light"] == 35


def test_pest_no_risk_when_reading_is_none() -> None:
    """pest_reading 为 None → 不触发风险."""
    field = _make_field()
    risk = _build_pest_risk(
        field=field,
        pest_reading=None,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )
    assert risk is None


# ==================== nutrient.deficiency ====================


def test_nutrient_deficiency_high_risk_with_low_soil_n() -> None:
    """NDVI 0.42 + 速效氮 65 → nutrient.deficiency high."""
    field = _make_field()
    ndvi = _make_reading(id=10, sensor_type="ndvi", value_float=0.42)
    soil_n = _make_reading(id=11, sensor_type="soil_nitrogen", value_float=65.0)

    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=ndvi,
        soil_n_reading=soil_n,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.risk_key == f"nutrient.deficiency:{field.id}"
    assert risk.severity == "high"
    assert risk.evidence[0].payload["soil_nitrogen_mg_per_kg"] == 65.0


def test_nutrient_deficiency_medium_upgraded_to_high_by_low_soil_n() -> None:
    """NDVI 0.48（medium 区间）+ 速效氮 65（<80）→ 升级为 high."""
    field = _make_field()
    ndvi = _make_reading(id=10, sensor_type="ndvi", value_float=0.48)
    soil_n = _make_reading(id=11, sensor_type="soil_nitrogen", value_float=65.0)

    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=ndvi,
        soil_n_reading=soil_n,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "high"  # 速效氮偏低导致升级


def test_nutrient_deficiency_medium_keeps_medium_when_soil_n_normal() -> None:
    """NDVI 0.48 + 速效氮 100（≥80）→ 保持 medium."""
    field = _make_field()
    ndvi = _make_reading(id=10, sensor_type="ndvi", value_float=0.48)
    soil_n = _make_reading(id=11, sensor_type="soil_nitrogen", value_float=100.0)

    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=ndvi,
        soil_n_reading=soil_n,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"


def test_nutrient_deficiency_medium_without_soil_n() -> None:
    """NDVI 0.48 + 无速效氮 → medium."""
    field = _make_field()
    ndvi = _make_reading(id=10, sensor_type="ndvi", value_float=0.48)

    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=ndvi,
        soil_n_reading=None,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"


@pytest.mark.parametrize("ndvi", [0.5, 0.55, 0.9])
def test_nutrient_no_risk_when_ndvi_normal(ndvi: float) -> None:
    """NDVI ≥0.5 → 不触发风险."""
    field = _make_field()
    ndvi_reading = _make_reading(id=10, sensor_type="ndvi", value_float=ndvi)

    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=ndvi_reading,
        soil_n_reading=None,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is None


def test_nutrient_boundary_0_45_is_medium_not_high() -> None:
    """NDVI 0.45 不满足 <0.45，走 medium 路径（<0.5）."""
    field = _make_field()
    ndvi = _make_reading(id=10, sensor_type="ndvi", value_float=0.45)

    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=ndvi,
        soil_n_reading=None,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"


def test_nutrient_no_risk_when_ndvi_reading_none() -> None:
    """ndvi_reading 为 None → 不触发风险."""
    field = _make_field()
    risk = _build_nutrient_risk(
        field=field,
        ndvi_reading=None,
        soil_n_reading=None,
        anomaly_reading=None,
        observed_at=_OBSERVED_AT,
    )
    assert risk is None


# ==================== drought.stress ====================


def test_drought_stress_high_risk() -> None:
    """土壤含水量 22% → drought.stress high."""
    field = _make_field(crop="水稻", stage="分蘖期")
    moisture = _make_reading(
        id=20,
        sensor_type="soil_moisture",
        value_float=22.0,
        value={"depth_cm": 20},
    )

    risk = _build_drought_risk(
        field=field,
        soil_moisture_reading=moisture,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.risk_key == f"drought.stress:{field.id}"
    assert risk.severity == "high"
    assert risk.evidence[0].payload["soil_moisture_pct"] == 22.0
    assert risk.evidence[0].payload["depth_cm"] == 20


def test_drought_stress_medium_risk() -> None:
    """土壤含水量 28% → drought.stress medium."""
    field = _make_field()
    moisture = _make_reading(
        id=20,
        sensor_type="soil_moisture",
        value_float=28.0,
        value={"depth_cm": 20},
    )

    risk = _build_drought_risk(
        field=field,
        soil_moisture_reading=moisture,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"


@pytest.mark.parametrize("moisture", [30.0, 35.0, 60.0])
def test_drought_no_risk_when_moisture_normal(moisture: float) -> None:
    """土壤含水量 ≥30% → 不触发风险."""
    field = _make_field()
    moisture_reading = _make_reading(
        id=20,
        sensor_type="soil_moisture",
        value_float=moisture,
        value={"depth_cm": 20},
    )

    risk = _build_drought_risk(
        field=field,
        soil_moisture_reading=moisture_reading,
        observed_at=_OBSERVED_AT,
    )

    assert risk is None


def test_drought_boundary_25_is_high() -> None:
    """25% 不满足 <25，走 medium 路径（<30）."""
    field = _make_field()
    moisture = _make_reading(
        id=20,
        sensor_type="soil_moisture",
        value_float=25.0,
        value={"depth_cm": 20},
    )

    risk = _build_drought_risk(
        field=field,
        soil_moisture_reading=moisture,
        observed_at=_OBSERVED_AT,
    )

    assert risk is not None
    assert risk.severity == "medium"


def test_drought_no_risk_when_reading_none() -> None:
    """soil_moisture_reading 为 None → 不触发风险."""
    field = _make_field()
    risk = _build_drought_risk(
        field=field,
        soil_moisture_reading=None,
        observed_at=_OBSERVED_AT,
    )
    assert risk is None


# ==================== _build_sensor_risks 集成（snapshot 路径） ====================


def _make_snapshot(
    *,
    field_id: int = 11,
    crop: str = "玉米",
    stage: str = "大喇叭口期",
    sensor_readings: list[dict] | None = None,
) -> FarmSnapshot:
    """构造带感知读数的 FarmSnapshot（B7 路径：直接从 snapshot.sensor_readings 取）."""
    observed_at = _OBSERVED_AT
    farm_dict = {
        "id": 1,
        "user_id": 7,
        "name": "示范农场",
        "location": "",  # 空位置让 inspect_farm 跳过天气查询
        "latitude": None,
        "longitude": None,
        "area_mu": 10.0,
        "description": "",
        "created_at": observed_at,
        "updated_at": observed_at,
    }
    field_dict = {
        "id": field_id,
        "farm_id": 1,
        "name": "A1",
        "area_mu": 10.0,
        "soil_type": "壤土",
        "current_crop": crop,
        "planting_date": None,
        "expected_harvest": None,
        "growth_stage": stage,
        "status": "planting",
        "latitude": None,
        "longitude": None,
        "notes": "",
        "boundary_json": "",
        "current_season_id": None,
        "created_at": observed_at,
        "updated_at": observed_at,
    }
    readings = []
    for index, item in enumerate(sensor_readings or [], start=1):
        readings.append(
            {
                "id": index,
                "field_id": field_id,
                "sensor_type": item["sensor_type"],
                "value_float": item.get("value_float"),
                "value": item.get("value", {}),
                "unit": item.get("unit", ""),
                "observed_at": item.get("observed_at", observed_at),
                "source": "demo_scenario",
                "scenario_id": "test",
                "note": item.get("note", ""),
            }
        )
    return FarmSnapshot.model_validate(
        {
            "farm": farm_dict,
            "fields": [field_dict],
            "recent_trajectory_files": [],
            "sensor_readings": readings,
            "recent_events": [],
            "pending_task_count": 0,
            "captured_at": observed_at,
            "data_gaps": [],
        }
    )


def test_build_sensor_risks_aggregates_pest_nutrient_drought() -> None:
    """snapshot 携带 3 类感知读数 → _build_sensor_risks 同时生成 3 条风险."""
    snapshot = _make_snapshot(
        sensor_readings=[
            {
                "sensor_type": "pest_count",
                "value_float": 35.0,
                "value": {"pest_name": "草地贪夜蛾", "count_per_light": 35},
            },
            {
                "sensor_type": "ndvi",
                "value_float": 0.42,
            },
            {
                "sensor_type": "soil_moisture",
                "value_float": 22.0,
                "value": {"depth_cm": 20},
            },
        ]
    )

    risks = _build_sensor_risks(snapshot, observed_at=_OBSERVED_AT)

    risk_keys = {risk.risk_key for risk in risks}
    assert f"pest.outbreak:11" in risk_keys
    assert f"nutrient.deficiency:11" in risk_keys
    assert f"drought.stress:11" in risk_keys
    assert all(risk.confidence == 0.9 for risk in risks)


def test_build_sensor_risks_returns_empty_when_no_readings() -> None:
    """snapshot 没有感知读数 → 返回空列表."""
    snapshot = _make_snapshot(sensor_readings=[])

    risks = _build_sensor_risks(snapshot, observed_at=_OBSERVED_AT)

    assert risks == []


def test_build_sensor_risks_returns_empty_when_no_fields() -> None:
    """snapshot 没有地块 → 返回空列表."""
    snapshot = FarmSnapshot.model_validate(
        {
            "farm": {
                "id": 1,
                "user_id": 7,
                "name": "示范农场",
                "location": "",
                "latitude": None,
                "longitude": None,
                "area_mu": 10.0,
                "description": "",
                "created_at": _OBSERVED_AT,
                "updated_at": _OBSERVED_AT,
            },
            "fields": [],
            "recent_trajectory_files": [],
            "sensor_readings": [],
            "recent_events": [],
            "pending_task_count": 0,
            "captured_at": _OBSERVED_AT,
            "data_gaps": [],
        }
    )

    risks = _build_sensor_risks(snapshot, observed_at=_OBSERVED_AT)

    assert risks == []


# ==================== inspect_farm 端到端（snapshot 路径） ====================


async def _noop_weather_provider() -> None:
    """inspect_farm 在 farm.location 为空时不会调用 weather provider."""


class NoCallWeatherProvider:
    """占位 weather provider，被调用即代表测试失败."""

    calls: list[tuple[str, int]] = []

    async def get_forecast_with_alerts(self, location: str, days: int = 2) -> None:
        self.calls.append((location, days))
        raise AssertionError("farm.location 为空时不应该调用 weather provider")


@pytest.mark.asyncio
async def test_inspect_farm_returns_no_sensor_risk_when_snapshot_has_no_readings() -> None:
    """snapshot.sensor_readings 为空时，_build_sensor_risks 直接返回空（不再回退到 DB）.

    B7 实现后 build_snapshot 总是聚合近 7 天 SensorReading 到 snapshot.sensor_readings，
    所以 _build_sensor_risks 只读 snapshot，不查 DB。snapshot 为空说明 DB 也没有近 7 天
    读数，直接返回空即可。
    """
    snapshot = _make_snapshot(sensor_readings=[])

    result = await inspect_farm(
        snapshot,
        weather_provider=NoCallWeatherProvider(),
    )

    sensor_risks = [
        r for r in result.risks
        if r.risk_key.startswith(("pest.outbreak", "nutrient.deficiency", "drought.stress"))
    ]
    assert sensor_risks == []
    assert NoCallWeatherProvider.calls == []


@pytest.mark.asyncio
async def test_inspect_farm_prefers_snapshot_readings_over_db() -> None:
    """snapshot 携带 sensor_readings 时，直接走 snapshot 路径生成风险."""
    snapshot = _make_snapshot(
        sensor_readings=[
            {
                "sensor_type": "pest_count",
                "value_float": 35.0,
                "value": {"pest_name": "草地贪夜蛾", "count_per_light": 35},
            }
        ]
    )

    result = await inspect_farm(
        snapshot,
        weather_provider=NoCallWeatherProvider(),
    )

    pest_risks = [r for r in result.risks if r.risk_key.startswith("pest.outbreak")]
    assert len(pest_risks) == 1
    assert pest_risks[0].severity == "high"
