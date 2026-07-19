"""比赛演示场景加载与感知数据注入服务.

职责:
  - load_scenario(scenario_id): 从 app/data/demo_<scenario>.json 加载并缓存 fixture
  - list_scenarios(): 列出可用场景元信息
  - inject_scenario_to_db(): 把 fixture 里的 seasons / sensor_readings 落库（幂等）

幂等保证:
  - SensorReading 按 (field_id, sensor_type, observed_at, scenario_id) 去重
  - CropSeason 按 (field_id, season_code, start_date) 去重，存在则更新 current_stage/status

联动效应:
  - 注入时会同步 Field.current_season_id 指针，让 AI 巡检 snapshot 能看到茬次
  - 注入的 sensor_readings 会被 farm_risk_service 用于生成虫害/缺肥/干旱风险
"""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field as PydanticField
from sqlalchemy.orm import Session

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException, ForbiddenError, NotFoundError
from app.models.farm import CropSeason, Farm, Field, SensorReading


# scenario_id → fixture 文件名映射
SCENARIO_FILE_MAP: dict[str, str] = {
    "rainstorm": "demo_rainstorm_scenario.json",
    "pest_outbreak": "demo_pest_outbreak_scenario.json",
    "nutrient_deficiency": "demo_nutrient_deficiency_scenario.json",
    "drought": "demo_drought_scenario.json",
}


# ==================== Pydantic 数据契约 ====================


class DemoScenarioSensorReading(BaseModel):
    field_name: str
    sensor_type: str
    value_float: float | None = None
    value_json: dict[str, Any] = PydanticField(default_factory=dict)
    unit: str = ""
    observed_at: datetime
    note: str = ""


class DemoScenarioSeason(BaseModel):
    field_name: str
    crop_name: str
    variety: str = ""
    season_code: str
    start_date: date
    expected_harvest: date | None = None
    current_stage: str = ""
    area_mu: float = 0.0
    target_yield: str = ""
    status: str = "growing"


class DemoScenarioField(BaseModel):
    name: str
    area_mu: float = 0.0
    soil_type: str = ""
    current_crop: str = ""
    planting_date: date | None = None
    expected_harvest: date | None = None
    growth_stage: str = ""
    status: str = ""
    latitude: float | None = None
    longitude: float | None = None
    notes: str = ""
    boundary: list[list[float]] = PydanticField(default_factory=list)


class DemoScenarioWeather(BaseModel):
    rainfall_24h_mm: float = 0.0
    observed_at: datetime
    condition: str = ""
    min_temp: float | None = None
    max_temp: float | None = None
    humidity: float | None = None
    wind_level: float | None = None
    consecutive_dry_days: int | None = None
    eto_mm_per_day: float | None = None


class DemoScenarioExpectedRisk(BaseModel):
    risk_key_prefix: str
    severity: str
    min_count: int = 1


class DemoScenario(BaseModel):
    scenario_id: str
    label: str
    farm: dict[str, Any]
    weather: DemoScenarioWeather
    fields: list[DemoScenarioField]
    trajectory_summaries: list[dict[str, Any]] = PydanticField(default_factory=list)
    seasons: list[DemoScenarioSeason] = PydanticField(default_factory=list)
    sensor_readings: list[DemoScenarioSensorReading] = PydanticField(default_factory=list)
    expected_risks: list[DemoScenarioExpectedRisk] = PydanticField(default_factory=list)


class ScenarioMeta(BaseModel):
    scenario_id: str
    label: str
    description: str
    weather_summary: str
    field_count: int
    sensor_count: int


class InjectionReport(BaseModel):
    scenario_id: str
    farm_id: int
    created_sensors: int
    skipped_sensors: int
    created_seasons: int
    updated_seasons: int
    fields_covered: list[str]


# ==================== 加载 / 列出场景 ====================


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


@lru_cache(maxsize=8)
def load_scenario(scenario_id: str) -> DemoScenario:
    """按 scenario_id 加载并缓存 fixture."""
    if scenario_id not in SCENARIO_FILE_MAP:
        raise NotFoundError(
            message=f"未知的比赛演示场景: {scenario_id}",
            code="DEMO_SCENARIO_NOT_FOUND",
        )
    fixture_path = _fixture_dir() / SCENARIO_FILE_MAP[scenario_id]
    if not fixture_path.exists():
        raise NotFoundError(
            message=f"场景 fixture 文件不存在: {fixture_path.name}",
            code="DEMO_SCENARIO_FILE_MISSING",
        )
    raw = fixture_path.read_text(encoding="utf-8")
    return DemoScenario.model_validate_json(raw)


def list_scenarios() -> list[ScenarioMeta]:
    """列出所有可用比赛场景的元信息（缺文件降级为跳过，不抛错）."""
    metas: list[ScenarioMeta] = []
    for scenario_id in SCENARIO_FILE_MAP:
        try:
            scenario = load_scenario(scenario_id)
        except Exception as exc:  # noqa: BLE001 - 列表场景不应因单个 fixture 缺失中断
            logger.warning("加载场景 {} 失败: {}", scenario_id, exc)
            continue
        metas.append(
            ScenarioMeta(
                scenario_id=scenario_id,
                label=scenario.label,
                description=scenario.farm.get("description", ""),
                weather_summary=(
                    f"{scenario.weather.condition or '未知'} / "
                    f"降雨 {scenario.weather.rainfall_24h_mm}mm"
                ),
                field_count=len(scenario.fields),
                sensor_count=len(scenario.sensor_readings),
            )
        )
    return metas


# ==================== 注入服务 ====================


def _require_owned_farm(
    session: Session, *, farm_id: int, user_id: int
) -> Farm:
    farm = (
        session.query(Farm)
        .filter(Farm.id == farm_id, Farm.user_id == user_id)
        .first()
    )
    if farm is None:
        raise ForbiddenError(message="无权访问目标农场")
    return farm


def _resolve_fields_by_name(
    session: Session, *, farm_id: int, scenario: DemoScenario
) -> dict[str, Field]:
    """按名称匹配 fixture 中的 fields 与数据库 Field 记录."""
    fields = session.query(Field).filter(Field.farm_id == farm_id).all()
    by_name: dict[str, Field] = {field.name: field for field in fields}
    missing = [
        fixture_field.name
        for fixture_field in scenario.fields
        if fixture_field.name not in by_name
    ]
    if missing:
        raise AppException(
            status_code=409,
            code="SCENARIO_FIELD_MISMATCH",
            message=(
                f"场景要求的地块在农场中不存在: {', '.join(missing)}。"
                "请先在农场管理中创建同名地块。"
            ),
        )
    return by_name


def _upsert_season(
    session: Session,
    *,
    field: Field,
    season_payload: DemoScenarioSeason,
) -> tuple[CropSeason, bool]:
    """插入或更新茬次记录，返回 (season, created)."""
    existing = (
        session.query(CropSeason)
        .filter(
            CropSeason.field_id == field.id,
            CropSeason.season_code == season_payload.season_code,
            CropSeason.start_date == season_payload.start_date,
        )
        .first()
    )
    if existing is not None:
        # 同步当前生育期 / 状态 / 面积（注入场景不同时间点会推进 stage）
        if existing.current_stage != season_payload.current_stage:
            existing.current_stage = season_payload.current_stage
        if existing.status != season_payload.status:
            existing.status = season_payload.status
        if existing.area_mu != season_payload.area_mu:
            existing.area_mu = season_payload.area_mu
        if existing.expected_harvest != season_payload.expected_harvest:
            existing.expected_harvest = season_payload.expected_harvest
        return existing, False

    season = CropSeason(
        field_id=field.id,
        crop_name=season_payload.crop_name,
        variety=season_payload.variety,
        season_code=season_payload.season_code,
        start_date=season_payload.start_date,
        expected_harvest=season_payload.expected_harvest,
        current_stage=season_payload.current_stage,
        area_mu=season_payload.area_mu,
        target_yield=season_payload.target_yield,
        status=season_payload.status,
    )
    session.add(season)
    session.flush()
    return season, True


def _upsert_sensor(
    session: Session,
    *,
    field: Field,
    sensor_payload: DemoScenarioSensorReading,
    scenario_id: str,
) -> bool:
    """插入或跳过感知读数，返回 True 表示新建、False 表示已存在跳过."""
    existing = (
        session.query(SensorReading)
        .filter(
            SensorReading.field_id == field.id,
            SensorReading.sensor_type == sensor_payload.sensor_type,
            SensorReading.observed_at == sensor_payload.observed_at,
            SensorReading.scenario_id == scenario_id,
        )
        .first()
    )
    if existing is not None:
        return False

    reading = SensorReading(
        field_id=field.id,
        sensor_type=sensor_payload.sensor_type,
        value_float=sensor_payload.value_float,
        unit=sensor_payload.unit,
        observed_at=sensor_payload.observed_at,
        source="demo_scenario",
        scenario_id=scenario_id,
        note=sensor_payload.note,
    )
    reading.set_value(sensor_payload.value_json)
    session.add(reading)
    return True


def _sync_field_from_season(field: Field, season: CropSeason) -> None:
    """同步 Field 表的冗余字段（兼容老代码读取 Field.current_crop/growth_stage）."""
    if field.current_crop != season.crop_name:
        field.current_crop = season.crop_name
    if field.growth_stage != season.current_stage:
        field.growth_stage = season.current_stage
    if field.planting_date != season.start_date:
        field.planting_date = season.start_date
    if season.expected_harvest and field.expected_harvest != season.expected_harvest:
        field.expected_harvest = season.expected_harvest
    if season.status == "growing" and field.status != "planting":
        field.status = "planting"
    if field.current_season_id != season.id:
        field.current_season_id = season.id


def inject_scenario_to_db(
    *,
    user_id: int,
    farm_id: int,
    scenario_id: str,
) -> InjectionReport:
    """把场景 fixture 中的 sensor_readings 和 seasons 落库.

    幂等：相同 (scenario_id, field, sensor_type, observed_at) 重复注入不会创建重复记录。
    同时维护 Field.current_season_id 指向当前茬次。
    """
    scenario = load_scenario(scenario_id)

    created_sensors = 0
    skipped_sensors = 0
    created_seasons = 0
    updated_seasons = 0
    fields_covered: set[str] = set()

    with sqlite_manager.session() as session:
        _require_owned_farm(session, farm_id=farm_id, user_id=user_id)
        fields_by_name = _resolve_fields_by_name(
            session, farm_id=farm_id, scenario=scenario
        )

        # 1) 注入或更新 seasons，并同步 Field 冗余字段
        for season_payload in scenario.seasons:
            field = fields_by_name.get(season_payload.field_name)
            if field is None:
                continue
            season, created = _upsert_season(
                session,
                field=field,
                season_payload=season_payload,
            )
            if created:
                created_seasons += 1
            else:
                updated_seasons += 1
            _sync_field_from_season(field, season)
            fields_covered.add(season_payload.field_name)

        # 2) 注入 sensor_readings（幂等去重）
        for sensor_payload in scenario.sensor_readings:
            field = fields_by_name.get(sensor_payload.field_name)
            if field is None:
                continue
            created = _upsert_sensor(
                session,
                field=field,
                sensor_payload=sensor_payload,
                scenario_id=scenario_id,
            )
            if created:
                created_sensors += 1
                fields_covered.add(sensor_payload.field_name)
            else:
                skipped_sensors += 1

    logger.info(
        "场景 {} 已注入农场 {}: 新增感知 {} 条 / 跳过 {} 条 / 茬次新建 {} 个 / 更新 {} 个",
        scenario_id,
        farm_id,
        created_sensors,
        skipped_sensors,
        created_seasons,
        updated_seasons,
    )

    return InjectionReport(
        scenario_id=scenario_id,
        farm_id=farm_id,
        created_sensors=created_sensors,
        skipped_sensors=skipped_sensors,
        created_seasons=created_seasons,
        updated_seasons=updated_seasons,
        fields_covered=sorted(fields_covered),
    )
