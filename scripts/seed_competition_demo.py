"""为已有用户幂等写入比赛演示农场数据。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, NamedTuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.sqlite import sqlite_manager
from app.models.farm import Farm, Field
from app.models.trajectory import TrajectoryFile
from app.models.user import User

DEFAULT_FIXTURE_PATH = PROJECT_ROOT / "app" / "data" / "demo_rainstorm_scenario.json"
_MARKER_TEMPLATE = "[competition-demo:{external_key}]"


class DemoSeedError(RuntimeError):
    """演示数据无法安全写入。"""


class SeedResult(NamedTuple):
    farm_id: int
    field_ids: tuple[int, ...]
    trajectory_file_ids: tuple[int, ...]


def _load_fixture(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if fixture.get("scenario_id") != "rainstorm-v1":
        raise DemoSeedError("不支持的比赛演示场景版本")
    if fixture.get("label") != "比赛演示数据":
        raise DemoSeedError("演示 fixture 缺少明确标识")
    return fixture


def _upsert_farm(session, *, user_id: int, data: dict[str, Any]) -> Farm:
    marker = _MARKER_TEMPLATE.format(external_key=data["external_key"])
    farm = (
        session.query(Farm)
        .filter(Farm.user_id == user_id, Farm.description.like(f"{marker}%"))
        .first()
    )
    if farm is None:
        farm = Farm(user_id=user_id, name=data["name"])
        session.add(farm)
    farm.name = data["name"]
    farm.location = data.get("location", "")
    farm.area_mu = float(data.get("area_mu", 0.0))
    farm.description = f"{marker} {data.get('description', '')}".strip()
    session.flush()
    return farm


def _upsert_fields(session, *, farm: Farm, rows: list[dict[str, Any]]) -> list[Field]:
    fields: list[Field] = []
    for row in rows:
        field = session.query(Field).filter(
            Field.farm_id == farm.id,
            Field.name == row["name"],
        ).first()
        if field is None:
            field = Field(farm_id=farm.id, name=row["name"])
            session.add(field)
        for attribute in (
            "area_mu", "soil_type", "current_crop", "growth_stage", "status",
            "latitude", "longitude", "notes",
        ):
            setattr(field, attribute, row.get(attribute))
        field.planting_date = date.fromisoformat(row["planting_date"])
        field.expected_harvest = date.fromisoformat(row["expected_harvest"])
        field.boundary_json = json.dumps(row.get("boundary", []), ensure_ascii=False)
        session.flush()
        fields.append(field)
    return fields


def _upsert_trajectories(
    session,
    *,
    fields: list[Field],
    rows: list[dict[str, Any]],
) -> list[TrajectoryFile]:
    fields_by_name = {field.name: field for field in fields}
    trajectories: list[TrajectoryFile] = []
    for row in rows:
        field = fields_by_name.get(row["field_name"])
        if field is None:
            raise DemoSeedError(f"轨迹引用了不存在的地块: {row['field_name']}")
        trajectory = session.query(TrajectoryFile).filter(
            TrajectoryFile.field_id == field.id,
            TrajectoryFile.filename == row["filename"],
        ).first()
        if trajectory is None:
            trajectory = TrajectoryFile(field_id=field.id, filename=row["filename"])
            session.add(trajectory)
        for attribute in (
            "machine_id", "point_count", "total_distance_m", "work_distance_m",
            "work_area_mu", "avg_depth", "avg_speed", "depth_std", "work_width",
        ):
            setattr(trajectory, attribute, row.get(attribute))
        trajectory.start_time = datetime.fromisoformat(row["start_time"])
        trajectory.end_time = datetime.fromisoformat(row["end_time"])
        session.flush()
        trajectories.append(trajectory)
    return trajectories


def seed_competition_demo(
    *,
    username: str,
    fixture_path: Path | None = None,
) -> SeedResult:
    """只为指定的已有用户写入稳定演示资源，不创建账号或凭据。"""

    fixture = _load_fixture(fixture_path or DEFAULT_FIXTURE_PATH)
    with sqlite_manager.session() as session:
        user = session.query(User).filter(User.username == username).first()
        if user is None:
            raise DemoSeedError(f"用户不存在: {username}")
        farm = _upsert_farm(session, user_id=user.id, data=fixture["farm"])
        fields = _upsert_fields(session, farm=farm, rows=fixture["fields"])
        trajectories = _upsert_trajectories(
            session,
            fields=fields,
            rows=fixture["trajectory_summaries"],
        )
        return SeedResult(
            farm_id=farm.id,
            field_ids=tuple(field.id for field in fields),
            trajectory_file_ids=tuple(item.id for item in trajectories),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="幂等写入 AgroAgentOS 比赛演示数据")
    parser.add_argument("--username", required=True, help="接收演示农场的已有用户名")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
        help="版本化演示 fixture 路径",
    )
    args = parser.parse_args(argv)
    try:
        result = seed_competition_demo(username=args.username, fixture_path=args.fixture)
    except DemoSeedError as exc:
        print(f"seed failed: {exc}", file=sys.stderr)
        return 2
    print(
        f"seeded farm_id={result.farm_id} fields={len(result.field_ids)} "
        f"trajectories={len(result.trajectory_file_ids)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
