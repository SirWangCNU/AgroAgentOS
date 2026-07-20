"""轨迹相关 Pydantic Schema."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ==================== 数据分析 ====================


class WorkVolumeMetrics(BaseModel):
    """作业量指标."""

    work_duration_hours: float = Field(0.0, description="作业总时长（小时）")
    work_distance_km: float = Field(0.0, description="作业总行程（公里）")
    work_area_mu: float = Field(0.0, description="作业面积（亩）")
    avg_field_speed_kmh: float = Field(0.0, description="田间平均作业速度（km/h）")


class WorkEfficiencyMetrics(BaseModel):
    """作业效率指标."""

    compliance_rate: float = Field(0.0, description="综合作业达标率（%）")
    depth_compliance: float = Field(0.0, description="深度达标率（%）")
    speed_compliance: float = Field(0.0, description="速度达标率（%）")
    productivity_mu_per_hour: float = Field(0.0, description="生产率（亩/小时）")
    time_utilization_rate: float = Field(0.0, description="时间利用率（%）")
    total_points: int = Field(0, description="总作业点数")
    compliant_points: int = Field(0, description="达标点数")


class TrajectoryAnalysisResponse(BaseModel):
    """轨迹数据分析响应."""

    file_id: int
    filename: str
    machine_id: str = ""

    # 作业量指标
    work_volume: WorkVolumeMetrics

    # 作业效率指标
    work_efficiency: WorkEfficiencyMetrics

    # 图表（base64 编码）
    work_volume_chart: str = Field("", description="作业量指标图表（base64）")
    work_efficiency_chart: str = Field("", description="作业效率指标图表（base64）")


# ==================== 轨迹文件 ====================


class TrajectoryFileInfo(BaseModel):
    """轨迹文件元数据响应."""

    id: int
    field_id: int
    filename: str
    machine_id: str = ""
    point_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_distance_m: float = 0.0
    work_distance_m: float = 0.0
    work_area_mu: float = 0.0
    avg_depth: float = 0.0
    avg_speed: float = 0.0
    depth_std: float = 0.0
    work_width: float = 0.0
    operation_type: str = "unknown"
    season_id: Optional[int] = None
    related_task_id: Optional[str] = None
    operator: str = ""
    event_time: Optional[datetime] = None
    coverage_rate: Optional[float] = None
    quality_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class TrajectoryListResponse(BaseModel):
    """轨迹列表响应."""

    total: int
    trajectories: list[TrajectoryFileInfo]


class TrajectoryUploadResponse(BaseModel):
    """轨迹上传响应."""

    file_info: TrajectoryFileInfo
    message: str = "轨迹上传成功"


# ==================== 轨迹点 ====================


class TrajectoryPointData(BaseModel):
    """单个轨迹点."""

    id: int
    seq: int
    gps_time: Optional[datetime] = None
    latitude: float
    longitude: float
    speed: float = 0.0
    work_status: str = "idle"
    depth: float = 0.0
    depth_std: float = 0.0

    model_config = {"from_attributes": True}


class TrajectoryPointsResponse(BaseModel):
    """轨迹点列表响应."""

    file_id: int
    point_count: int
    points: list[TrajectoryPointData]


# ==================== 统计分析 ====================


class DepthDistribution(BaseModel):
    """深度分布."""

    range_label: str  # 如 "0-5cm", "5-10cm"
    count: int
    percentage: float


class TrajectoryStatsResponse(BaseModel):
    """轨迹统计分析响应."""

    file_id: int
    filename: str
    machine_id: str = ""

    # 基础统计
    point_count: int = 0
    total_distance_m: float = 0.0
    work_distance_m: float = 0.0
    work_area_mu: float = 0.0
    work_width: float = 0.0  # 幅宽（米）

    # 时间统计
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    work_duration_min: float = 0.0  # 作业时间(分钟)
    total_duration_min: float = 0.0  # 总时间(分钟)

    # 速度统计
    avg_speed: float = 0.0
    max_speed: float = 0.0

    # 深度统计
    avg_depth: float = 0.0
    depth_std: float = 0.0
    depth_pass_rate: float = 0.0  # 深度合格率(%)
    depth_distribution: list[DepthDistribution] = []

    # 效率指标
    work_efficiency_mu_per_hour: float = 0.0  # 作业效率(亩/小时)
