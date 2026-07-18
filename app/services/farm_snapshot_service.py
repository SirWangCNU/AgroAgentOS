"""聚合经所有权校验的只读农场业务快照。"""

from __future__ import annotations

from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field as PydanticField

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException, ForbiddenError
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmTask
from app.models.trajectory import TrajectoryFile
from app.schemas.trajectory import TrajectoryFileInfo
from app.services import farm_service

_TERMINAL_TASK_STATUSES = ("completed", "cancelled")
_TRAJECTORY_LIMIT_PER_FIELD = 3


class FarmSnapshotFarm(BaseModel):
    """不依赖 ORM 会话的农场基础字段。"""

    id: int
    user_id: int
    name: str
    location: str
    latitude: float | None
    longitude: float | None
    area_mu: float
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FarmSnapshotField(BaseModel):
    """不依赖 ORM 会话的地块、作物和边界字段。"""

    id: int
    farm_id: int
    name: str
    area_mu: float
    soil_type: str
    current_crop: str
    planting_date: date | None
    expected_harvest: date | None
    growth_stage: str
    status: str
    latitude: float | None
    longitude: float | None
    notes: str
    boundary_json: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FarmSnapshot(BaseModel):
    """供 Farm Agent 使用的有界、可序列化业务上下文。"""

    farm: FarmSnapshotFarm
    fields: list[FarmSnapshotField] = PydanticField(default_factory=list)
    recent_trajectory_files: list[TrajectoryFileInfo] = PydanticField(
        default_factory=list
    )
    pending_task_count: int = PydanticField(default=0, ge=0)
    captured_at: datetime
    data_gaps: list[str] = PydanticField(default_factory=list)


def _raise_forbidden_if_farm_exists(farm_id: int, original: AppException) -> None:
    """区分不存在与越权，同时避免在错误中暴露农场业务字段。"""

    with sqlite_manager.session() as session:
        farm_exists = session.query(Farm.id).filter(Farm.id == farm_id).first()
    if farm_exists:
        raise ForbiddenError(message="无权访问目标农场") from original
    raise original


def _build_data_gaps(
    farm: FarmSnapshotFarm,
    fields: list[FarmSnapshotField],
    trajectories: list[TrajectoryFileInfo],
) -> list[str]:
    gaps: list[str] = []
    if not farm.location.strip():
        gaps.append("farm_location_missing")
    if not fields:
        gaps.append("farm_fields_missing")
        return gaps

    trajectory_field_ids = {item.field_id for item in trajectories}
    for field in fields:
        if not field.current_crop.strip():
            gaps.append(f"field:{field.id}:current_crop_missing")
        if not field.growth_stage.strip():
            gaps.append(f"field:{field.id}:growth_stage_missing")
        if not field.boundary_json.strip():
            gaps.append(f"field:{field.id}:boundary_missing")
        if field.id not in trajectory_field_ids:
            gaps.append(f"field:{field.id}:trajectory_missing")
    return gaps


def get_snapshot(farm_id: int, user_id: int) -> FarmSnapshot:
    """校验农场所有权并在单次只读会话中聚合快照。"""

    try:
        farm_service.get_farm(farm_id=farm_id, user_id=user_id)
    except AppException as exc:
        if exc.status_code == 404:
            _raise_forbidden_if_farm_exists(farm_id, exc)
        raise

    with sqlite_manager.session() as session:
        farm_row = (
            session.query(Farm)
            .filter(Farm.id == farm_id, Farm.user_id == user_id)
            .one()
        )
        field_rows = (
            session.query(Field)
            .filter(Field.farm_id == farm_id)
            .order_by(Field.created_at.asc(), Field.id.asc())
            .all()
        )
        field_ids = [field.id for field in field_rows]

        trajectory_rows: list[TrajectoryFile] = []
        if field_ids:
            all_trajectory_rows = (
                session.query(TrajectoryFile)
                .filter(TrajectoryFile.field_id.in_(field_ids))
                .order_by(
                    TrajectoryFile.created_at.desc(),
                    TrajectoryFile.id.desc(),
                )
                .all()
            )
            count_by_field: dict[int, int] = {}
            for trajectory in all_trajectory_rows:
                current_count = count_by_field.get(trajectory.field_id, 0)
                if current_count >= _TRAJECTORY_LIMIT_PER_FIELD:
                    continue
                trajectory_rows.append(trajectory)
                count_by_field[trajectory.field_id] = current_count + 1

        pending_task_count = (
            session.query(FarmTask)
            .filter(
                FarmTask.farm_id == farm_id,
                FarmTask.status.notin_(_TERMINAL_TASK_STATUSES),
            )
            .count()
        )

        farm = FarmSnapshotFarm.model_validate(farm_row)
        fields = [FarmSnapshotField.model_validate(field) for field in field_rows]
        trajectories = [
            TrajectoryFileInfo.model_validate(trajectory)
            for trajectory in trajectory_rows
        ]

    return FarmSnapshot(
        farm=farm,
        fields=fields,
        recent_trajectory_files=trajectories,
        pending_task_count=pending_task_count,
        captured_at=datetime.now(timezone.utc),
        data_gaps=_build_data_gaps(farm, fields, trajectories),
    )
