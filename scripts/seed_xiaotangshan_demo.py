"""Seed Xiaotangshan farm demo data for an existing user."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.sqlite import sqlite_manager
from app.models.farm import CropSeason, Farm, Field, SensorReading
from app.models.farm_agent import FarmEvent
from app.models.trajectory import TrajectoryFile, TrajectoryPoint
from app.models.user import User
from app.services import trajectory_analysis

FARM_MARKER = "[xiaotangshan-demo:v1]"
FARM_CENTER = (40.155185, 116.433167)
TRAJECTORY_FILENAME = "xiaotangshan_A1_cultivation_20260720.xlsx"


class SeedError(RuntimeError):
    """Raised when demo data cannot be safely seeded."""


class SeedResult(NamedTuple):
    username: str
    farm_id: int
    field_ids: tuple[int, ...]
    season_ids: tuple[int, ...]
    event_count: int
    trajectory_file_id: int
    trajectory_point_count: int


def _polygon(coords: list[tuple[float, float]]) -> str:
    closed = [*coords, coords[0]]
    return json.dumps(
        {
            "type": "Polygon",
            "coordinates": [[[lon, lat] for lat, lon in closed]],
        },
        ensure_ascii=False,
    )


def _field_rows() -> list[dict[str, Any]]:
    return [
        {
            "name": "大田精准作业区A1",
            "area_mu": 42.6,
            "soil_type": "壤土",
            "current_crop": "春玉米",
            "planting_date": "2026-04-25",
            "expected_harvest": "2026-09-20",
            "growth_stage": "拔节期",
            "status": "planting",
            "latitude": 40.15555,
            "longitude": 116.43268,
            "notes": "小汤山精准农机作业演示地块。",
            "boundary_json": _polygon(
                [
                    (40.15605, 116.43185),
                    (40.15605, 116.43365),
                    (40.15505, 116.43365),
                    (40.15505, 116.43185),
                ]
            ),
        },
        {
            "name": "水肥试验区C3",
            "area_mu": 36.2,
            "soil_type": "壤土",
            "current_crop": "大豆",
            "planting_date": "2026-05-10",
            "expected_harvest": "2026-10-05",
            "growth_stage": "分枝期",
            "status": "planting",
            "latitude": 40.15435,
            "longitude": 116.43435,
            "notes": "水肥一体化与土壤墒情演示地块。",
            "boundary_json": _polygon(
                [
                    (40.15485, 116.43355),
                    (40.15485, 116.43510),
                    (40.15390, 116.43510),
                    (40.15390, 116.43355),
                ]
            ),
        },
        {
            "name": "设施番茄温室B2",
            "area_mu": 8.5,
            "soil_type": "基质栽培",
            "current_crop": "番茄",
            "planting_date": "2026-03-15",
            "expected_harvest": "2026-08-30",
            "growth_stage": "结果期",
            "status": "planting",
            "latitude": 40.15665,
            "longitude": 116.43455,
            "notes": "温室环境与病害风险演示区。",
            "boundary_json": _polygon(
                [
                    (40.15695, 116.43400),
                    (40.15695, 116.43510),
                    (40.15635, 116.43510),
                    (40.15635, 116.43400),
                ]
            ),
        },
    ]


def _season_rows() -> list[dict[str, Any]]:
    return [
        {
            "field_name": "大田精准作业区A1",
            "crop_name": "春玉米",
            "variety": "京科968",
            "season_code": "2026-S1",
            "start_date": "2026-04-25",
            "expected_harvest": "2026-09-20",
            "current_stage": "拔节期",
            "area_mu": 42.6,
            "target_yield": "650 kg/亩",
            "status": "growing",
            "note": "用于验证农机作业质量与暴雨前巡检。",
        },
        {
            "field_name": "水肥试验区C3",
            "crop_name": "大豆",
            "variety": "中黄13",
            "season_code": "2026-S1",
            "start_date": "2026-05-10",
            "expected_harvest": "2026-10-05",
            "current_stage": "分枝期",
            "area_mu": 36.2,
            "target_yield": "210 kg/亩",
            "status": "growing",
            "note": "用于验证水肥与墒情数据联动。",
        },
        {
            "field_name": "设施番茄温室B2",
            "crop_name": "番茄",
            "variety": "粉果番茄",
            "season_code": "2026-GH1",
            "start_date": "2026-03-15",
            "expected_harvest": "2026-08-30",
            "current_stage": "结果期",
            "area_mu": 8.5,
            "target_yield": "5200 kg/亩",
            "status": "growing",
            "note": "用于验证设施农业湿度与病害风险提示。",
        },
    ]


def _event_rows() -> list[dict[str, Any]]:
    base = datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc)
    return [
        {
            "field_name": "大田精准作业区A1",
            "event_type": "seeding",
            "event_time": datetime(2026, 4, 25, 9, 0, tzinfo=timezone.utc),
            "operator": "demo:播种机组",
            "inputs": [{"material": "春玉米种子", "rate_per_mu": "2.2 kg/亩"}],
            "note": "春玉米播种完成。",
        },
        {
            "field_name": "大田精准作业区A1",
            "event_type": "irrigating",
            "event_time": base - timedelta(days=4),
            "operator": "demo:水肥组",
            "inputs": [{"material": "滴灌补水", "rate_per_mu": "18 m³/亩"}],
            "note": "滴灌补水完成。",
        },
        {
            "field_name": "大田精准作业区A1",
            "event_type": "scouting",
            "event_time": base - timedelta(days=1),
            "operator": "demo:巡田员",
            "inputs": [],
            "note": "巡田发现局部低洼积水风险。",
        },
        {
            "field_name": "水肥试验区C3",
            "event_type": "fertilizing",
            "event_time": base - timedelta(days=3),
            "operator": "demo:水肥组",
            "inputs": [{"material": "复合肥", "rate_per_mu": "12 kg/亩"}],
            "note": "追施复合肥并记录水肥试验参数。",
        },
        {
            "field_name": "设施番茄温室B2",
            "event_type": "anomaly",
            "event_time": base - timedelta(hours=18),
            "operator": "demo:温室传感器",
            "inputs": [{"material": "humidity", "value": "88%"}],
            "note": "温室湿度偏高，需关注病害风险。",
        },
    ]


def _trajectory_points() -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    start = datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc)
    lat_rows = [40.15518, 40.15534, 40.15550, 40.15566, 40.15582]
    seq = 1
    for row_index, lat in enumerate(lat_rows):
        lon_values = [116.43202 + index * 0.00023 for index in range(8)]
        if row_index % 2 == 1:
            lon_values.reverse()
        for col_index, lon in enumerate(lon_values):
            depth = 8.5 if seq in {6, 21, 37} else 12.0 + ((seq % 7) * 0.8)
            points.append(
                {
                    "seq": seq,
                    "gps_time": start + timedelta(minutes=seq * 2),
                    "latitude": lat,
                    "longitude": lon,
                    "speed": 5.2 + ((seq + col_index) % 5) * 0.55,
                    "work_status": "working" if seq not in {1, 40} else "idle",
                    "depth": round(depth, 1),
                    "depth_std": 15.0,
                }
            )
            seq += 1
    return points


def _resolve_user(session, username: str | None) -> User:
    if username:
        user = session.query(User).filter(User.username == username).first()
        if user is None:
            raise SeedError(f"用户不存在: {username}")
        return user
    user = session.query(User).filter(User.is_active == 1).order_by(User.id.asc()).first()
    if user is None:
        raise SeedError("数据库中没有可用用户，请使用 --username 指定已有用户")
    return user


def _upsert_farm(session, user: User) -> Farm:
    farm = (
        session.query(Farm)
        .filter(Farm.user_id == user.id, Farm.description.like(f"{FARM_MARKER}%"))
        .first()
    )
    if farm is None:
        farm = Farm(user_id=user.id, name="北京小汤山农业实验基地")
        session.add(farm)
    farm.name = "北京小汤山农业实验基地"
    farm.location = "北京市昌平区小汤山镇国家精准农业研究示范基地"
    farm.latitude = FARM_CENTER[0]
    farm.longitude = FARM_CENTER[1]
    farm.area_mu = 2280
    farm.description = (
        f"{FARM_MARKER} 用于精准农业、农业物联网、农机作业质量与 AI 农场巡检演示的测试基地。"
    )
    session.flush()
    return farm


def _upsert_fields(session, farm: Farm) -> list[Field]:
    fields: list[Field] = []
    for row in _field_rows():
        field = (
            session.query(Field)
            .filter(Field.farm_id == farm.id, Field.name == row["name"])
            .first()
        )
        if field is None:
            field = Field(farm_id=farm.id, name=row["name"])
            session.add(field)
        for attr in (
            "area_mu",
            "soil_type",
            "current_crop",
            "growth_stage",
            "status",
            "latitude",
            "longitude",
            "notes",
            "boundary_json",
        ):
            setattr(field, attr, row[attr])
        field.planting_date = date.fromisoformat(row["planting_date"])
        field.expected_harvest = date.fromisoformat(row["expected_harvest"])
        session.flush()
        fields.append(field)
    return fields


def _upsert_seasons(session, fields: list[Field]) -> list[CropSeason]:
    fields_by_name = {field.name: field for field in fields}
    seasons: list[CropSeason] = []
    for row in _season_rows():
        field = fields_by_name[row["field_name"]]
        season = (
            session.query(CropSeason)
            .filter(CropSeason.field_id == field.id, CropSeason.season_code == row["season_code"])
            .first()
        )
        if season is None:
            season = CropSeason(field_id=field.id, season_code=row["season_code"], crop_name=row["crop_name"], start_date=date.fromisoformat(row["start_date"]))
            session.add(season)
        season.crop_name = row["crop_name"]
        season.variety = row["variety"]
        season.start_date = date.fromisoformat(row["start_date"])
        season.expected_harvest = date.fromisoformat(row["expected_harvest"])
        season.current_stage = row["current_stage"]
        season.area_mu = row["area_mu"]
        season.target_yield = row["target_yield"]
        season.status = row["status"]
        season.note = row["note"]
        session.flush()
        field.current_season_id = season.id
        seasons.append(season)
    session.flush()
    return seasons


def _upsert_events(session, fields: list[Field]) -> int:
    fields_by_name = {field.name: field for field in fields}
    count = 0
    for row in _event_rows():
        field = fields_by_name[row["field_name"]]
        event = (
            session.query(FarmEvent)
            .filter(
                FarmEvent.field_id == field.id,
                FarmEvent.source == "human_entry",
                FarmEvent.event_type == row["event_type"],
                FarmEvent.note == row["note"],
            )
            .first()
        )
        if event is None:
            event = FarmEvent(field_id=field.id, event_type=row["event_type"])
            session.add(event)
        event.season_id = field.current_season_id
        event.event_time = row["event_time"]
        event.operator = row["operator"]
        event.source = "human_entry"
        event.note = row["note"]
        event.set_inputs(row["inputs"])
        event.set_evidence([])
        event.set_geo_payload({})
        count += 1
    session.flush()
    return count


def _upsert_sensor_readings(session, fields: list[Field]) -> None:
    now = datetime(2026, 7, 20, 7, 30, tzinfo=timezone.utc)
    rows = [
        ("大田精准作业区A1", "soil_moisture", 31.5, "%", {"status": "normal"}),
        ("大田精准作业区A1", "ndvi", 0.73, "", {"status": "healthy"}),
        ("水肥试验区C3", "soil_moisture", 24.2, "%", {"status": "low"}),
        ("设施番茄温室B2", "humidity", 88.0, "%", {"status": "high"}),
    ]
    fields_by_name = {field.name: field for field in fields}
    for field_name, sensor_type, value, unit, payload in rows:
        field = fields_by_name[field_name]
        reading = (
            session.query(SensorReading)
            .filter(
                SensorReading.field_id == field.id,
                SensorReading.sensor_type == sensor_type,
                SensorReading.observed_at == now,
                SensorReading.scenario_id == "xiaotangshan-demo",
            )
            .first()
        )
        if reading is None:
            reading = SensorReading(
                field_id=field.id,
                sensor_type=sensor_type,
                observed_at=now,
                scenario_id="xiaotangshan-demo",
            )
            session.add(reading)
        reading.value_float = value
        reading.unit = unit
        reading.source = "manual"
        reading.note = "小汤山演示感知数据"
        reading.set_value(payload)
    session.flush()


def _upsert_trajectory(session, fields: list[Field]) -> tuple[TrajectoryFile, int]:
    field = next(item for item in fields if item.name == "大田精准作业区A1")
    points = _trajectory_points()
    stats = trajectory_analysis.calc_trajectory_stats(
        file_id=0,
        filename=TRAJECTORY_FILENAME,
        machine_id="XTSAI-TRACTOR-01",
        points=points,
        work_width=2.4,
    )
    coverage_rate = round(min(100.0, (stats.work_area_mu / field.area_mu) * 100), 1)
    quality_summary = {
        "depth_pass_rate": stats.depth_pass_rate,
        "work_efficiency_mu_per_hour": stats.work_efficiency_mu_per_hour,
        "coverage_rate": coverage_rate,
    }
    trajectory = (
        session.query(TrajectoryFile)
        .filter(
            TrajectoryFile.field_id == field.id,
            TrajectoryFile.filename == TRAJECTORY_FILENAME,
        )
        .first()
    )
    if trajectory is None:
        trajectory = TrajectoryFile(field_id=field.id, filename=TRAJECTORY_FILENAME)
        session.add(trajectory)
    trajectory.machine_id = "XTSAI-TRACTOR-01"
    trajectory.point_count = len(points)
    trajectory.start_time = stats.start_time
    trajectory.end_time = stats.end_time
    trajectory.total_distance_m = stats.total_distance_m
    trajectory.work_distance_m = stats.work_distance_m
    trajectory.work_area_mu = stats.work_area_mu
    trajectory.avg_depth = stats.avg_depth
    trajectory.avg_speed = stats.avg_speed
    trajectory.depth_std = stats.depth_std
    trajectory.work_width = 2.4
    trajectory.operation_type = "cultivation"
    trajectory.season_id = field.current_season_id
    trajectory.related_task_id = None
    trajectory.operator = "XTSAI-TRACTOR-01"
    trajectory.event_time = stats.end_time
    trajectory.coverage_rate = coverage_rate
    trajectory.set_quality_summary(quality_summary)
    session.flush()

    session.query(TrajectoryPoint).filter(TrajectoryPoint.file_id == trajectory.id).delete()
    for point in points:
        session.add(
            TrajectoryPoint(
                file_id=trajectory.id,
                seq=point["seq"],
                gps_time=point["gps_time"],
                latitude=point["latitude"],
                longitude=point["longitude"],
                speed=point["speed"],
                work_status=point["work_status"],
                depth=point["depth"],
                depth_std=point["depth_std"],
            )
        )

    event = (
        session.query(FarmEvent)
        .filter(
            FarmEvent.field_id == field.id,
            FarmEvent.source == "trajectory_upload",
            FarmEvent.event_type == "cultivation",
            FarmEvent.note == f"上传作业轨迹 {TRAJECTORY_FILENAME}",
        )
        .first()
    )
    if event is None:
        event = FarmEvent(field_id=field.id, event_type="cultivation")
        session.add(event)
    event.season_id = field.current_season_id
    event.event_time = stats.end_time or datetime(2026, 7, 20, 10, 20, tzinfo=timezone.utc)
    event.operator = "XTSAI-TRACTOR-01"
    event.source = "trajectory_upload"
    event.note = f"上传作业轨迹 {TRAJECTORY_FILENAME}"
    event.set_inputs([{"material": "trajectory", "file_id": trajectory.id, "filename": TRAJECTORY_FILENAME}])
    event.set_evidence([{"type": "trajectory_file", "file_id": trajectory.id, "summary": quality_summary}])
    session.flush()
    return trajectory, len(points)


def seed_xiaotangshan_demo(username: str | None = None) -> SeedResult:
    """Seed demo records for username, or the first active user when omitted."""
    with sqlite_manager.session() as session:
        user = _resolve_user(session, username)
        farm = _upsert_farm(session, user)
        fields = _upsert_fields(session, farm)
        seasons = _upsert_seasons(session, fields)
        event_count = _upsert_events(session, fields)
        _upsert_sensor_readings(session, fields)
        trajectory, point_count = _upsert_trajectory(session, fields)
        return SeedResult(
            username=user.username,
            farm_id=farm.id,
            field_ids=tuple(field.id for field in fields),
            season_ids=tuple(season.id for season in seasons),
            event_count=event_count + 1,
            trajectory_file_id=trajectory.id,
            trajectory_point_count=point_count,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="幂等写入北京小汤山农业实验基地演示数据")
    parser.add_argument("--username", help="接收演示数据的已有用户名；不传则使用第一个启用用户")
    args = parser.parse_args(argv)
    try:
        result = seed_xiaotangshan_demo(username=args.username)
    except SeedError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 2
    print(
        "seeded "
        f"username={result.username} "
        f"farm_id={result.farm_id} "
        f"fields={len(result.field_ids)} "
        f"seasons={len(result.season_ids)} "
        f"events={result.event_count} "
        f"trajectory_file_id={result.trajectory_file_id} "
        f"points={result.trajectory_point_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
