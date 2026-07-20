"""Trajectory ORM models."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func

from app.core.sqlite import Base


class TrajectoryFile(Base):
    """Metadata for an uploaded trajectory file."""

    __tablename__ = "trajectory_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    machine_id = Column(String(64), default="")
    point_count = Column(Integer, default=0)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_distance_m = Column(Float, default=0.0)
    work_distance_m = Column(Float, default=0.0)
    work_area_mu = Column(Float, default=0.0)
    avg_depth = Column(Float, default=0.0)
    avg_speed = Column(Float, default=0.0)
    depth_std = Column(Float, default=0.0)
    work_width = Column(Float, default=0.0)
    operation_type = Column(String(64), nullable=False, default="unknown", index=True)
    season_id = Column(Integer, ForeignKey("crop_seasons.id", ondelete="SET NULL"), nullable=True, index=True)
    related_task_id = Column(String(64), nullable=True, index=True)
    operator = Column(String(128), nullable=False, default="")
    event_time = Column(DateTime, nullable=True)
    coverage_rate = Column(Float, nullable=True)
    quality_summary_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=func.now())

    @property
    def quality_summary(self) -> dict[str, Any]:
        if not self.quality_summary_json:
            return {}
        try:
            parsed = json.loads(self.quality_summary_json)
            if not isinstance(parsed, dict):
                raise ValueError("JSON value is not an object")
            return parsed
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse trajectory quality_summary_json: {}", exc)
            return {}

    def set_quality_summary(self, data: dict[str, Any]) -> None:
        self.quality_summary_json = json.dumps(data, ensure_ascii=False)


class TrajectoryPoint(Base):
    """GPS sampling point in a trajectory file."""

    __tablename__ = "trajectory_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("trajectory_files.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)
    gps_time = Column(DateTime, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, default=0.0)
    work_status = Column(String(32), default="idle")
    depth = Column(Float, default=0.0)
    depth_std = Column(Float, default=0.0)
