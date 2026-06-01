"""农机轨迹 ORM 模型.

轨迹数据结构:
  - TrajectoryFile: 轨迹文件元数据（一个 Excel 文件对应一条记录）
  - TrajectoryPoint: 轨迹点（GPS 采样点，一个文件可有数千条）
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func

from app.core.sqlite import Base


class TrajectoryFile(Base):
    """轨迹文件元数据表."""

    __tablename__ = "trajectory_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field_id = Column(Integer, ForeignKey("fields.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    machine_id = Column(String(64), default="")
    point_count = Column(Integer, default=0)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    total_distance_m = Column(Float, default=0.0)  # 总行驶距离(米)
    work_distance_m = Column(Float, default=0.0)   # 作业距离(米)
    work_area_mu = Column(Float, default=0.0)       # 作业面积(亩)
    avg_depth = Column(Float, default=0.0)          # 平均作业深度
    avg_speed = Column(Float, default=0.0)          # 平均速度
    depth_std = Column(Float, default=0.0)          # 深度标准差
    work_width = Column(Float, default=0.0)         # 幅宽(米)
    created_at = Column(DateTime, nullable=False, default=func.now())


class TrajectoryPoint(Base):
    """轨迹点表."""

    __tablename__ = "trajectory_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("trajectory_files.id", ondelete="CASCADE"), nullable=False, index=True)
    seq = Column(Integer, nullable=False)  # 序号
    gps_time = Column(DateTime, nullable=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    speed = Column(Float, default=0.0)
    work_status = Column(String(32), default="idle")  # working/idle/transporting
    depth = Column(Float, default=0.0)
    depth_std = Column(Float, default=0.0)
