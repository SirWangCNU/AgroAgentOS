"""农场和地块 ORM 模型."""

import json

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, func

from app.core.sqlite import Base


class Farm(Base):
    """农场表."""

    __tablename__ = "farms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    location = Column(String(256), default="")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    area_mu = Column(Float, default=0.0)  # 面积/亩
    description = Column(Text, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())


class Field(Base):
    """地块表."""

    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, autoincrement=True)
    farm_id = Column(Integer, ForeignKey("farms.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(128), nullable=False)
    area_mu = Column(Float, default=0.0)
    soil_type = Column(String(64), default="")  # 沙土/黏土/壤土
    current_crop = Column(String(64), default="")
    planting_date = Column(Date, nullable=True)
    expected_harvest = Column(Date, nullable=True)
    growth_stage = Column(String(64), default="")  # 生长阶段
    status = Column(String(32), default="idle")  # idle/planting/fallow
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    notes = Column(Text, default="")
    boundary_json = Column(Text, default="")  # 地块边界 GeoJSON
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    @property
    def boundary(self):
        """Return the stored GeoJSON boundary, if present."""
        if not self.boundary_json:
            return None
        try:
            return json.loads(self.boundary_json)
        except (TypeError, ValueError):
            return None
