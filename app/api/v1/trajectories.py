"""轨迹 API 路由.

提供轨迹文件的上传、查询、统计分析和删除功能。
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.trajectory import (
    TrajectoryAnalysisResponse,
    TrajectoryFileInfo,
    TrajectoryListResponse,
    TrajectoryPointsResponse,
    TrajectoryStatsResponse,
    TrajectoryUploadResponse,
    WorkEfficiencyMetrics,
    WorkVolumeMetrics,
)
from app.services import trajectory_service
from app.services.trajectory_analysis import (
    calc_work_efficiency_metrics,
    calc_work_volume_metrics,
)
from app.services.trajectory_charts import generate_combined_analysis_chart

router = APIRouter(tags=["轨迹管理"])


@router.post(
    "/fields/{field_id}/trajectories/upload",
    response_model=ApiResponse[TrajectoryUploadResponse],
)
async def upload_trajectory(
    field_id: int,
    file: UploadFile = File(..., description="轨迹 Excel 文件"),
    coord_system: str = Form("auto", description="坐标系: wgs84/gcj02/auto"),
    operation_type: str = Form("unknown", description="作业类型"),
    season_id: int | None = Form(None, description="关联茬次 ID"),
    related_task_id: str | None = Form(None, description="关联任务 ID"),
    operator: str = Form("", description="操作人"),
    event_time: datetime | None = Form(None, description="作业事件时间"),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """上传轨迹 Excel 文件.

    支持的 Excel 列名（中英文均可）:
    - GPS时间 / gps_time / time
    - 纬度 / latitude / lat (WGS-84 坐标)
    - 经度 / longitude / lng / lon (WGS-84 坐标)
    - 纬度_gcj02 / lat_gcj02 (GCJ-02 坐标，会自动转换)
    - 经度_gcj02 / lon_gcj02 (GCJ-02 坐标，会自动转换)
    - 速度 / speed
    - 工作状态 / work_status / status
    - 作业深度 / depth
    - 深度标准值 / depth_std
    - 幅宽 / work_width / width
    - 农机编号 / machine_id
    """
    # 读取文件内容
    content = await file.read()

    if not file.filename:
        return ApiResponse.error(message="文件名不能为空")

    # 验证文件类型
    if not file.filename.endswith((".xlsx", ".xls")):
        return ApiResponse.error(message="仅支持 .xlsx / .xls 格式的 Excel 文件")

    # 验证坐标系参数
    if coord_system not in ("wgs84", "gcj02", "auto"):
        return ApiResponse.error(message="坐标系参数无效，可选值: wgs84/gcj02/auto")

    result = trajectory_service.upload_trajectory(
        field_id=field_id,
        user_id=current_user.id,
        file_content=content,
        filename=file.filename,
        coord_system=coord_system,
        operation_type=operation_type,
        season_id=season_id,
        related_task_id=related_task_id,
        operator=operator,
        event_time=event_time,
    )

    return ApiResponse.success(data=result, message=result.message)


@router.get(
    "/fields/{field_id}/trajectories",
    response_model=ApiResponse[TrajectoryListResponse],
)
def list_trajectories(
    field_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取地块的轨迹列表."""
    trajectories = trajectory_service.get_trajectories(field_id, current_user.id)
    return ApiResponse.success(
        data=TrajectoryListResponse(
            total=len(trajectories),
            trajectories=trajectories,
        )
    )


@router.get(
    "/trajectories/{file_id}/points",
    response_model=ApiResponse[TrajectoryPointsResponse],
)
def get_trajectory_points(
    file_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取轨迹点数据（用于地图渲染）."""
    result = trajectory_service.get_trajectory_points(file_id, current_user.id)
    return ApiResponse.success(data=result)


@router.get(
    "/trajectories/{file_id}/stats",
    response_model=ApiResponse[TrajectoryStatsResponse],
)
def get_trajectory_stats(
    file_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取轨迹统计分析.

    返回:
    - 总距离、作业距离、作业面积
    - 时间统计（作业时间、总时间）
    - 速度统计（平均速度、最大速度）
    - 深度统计（平均深度、标准差、合格率、分布）
    - 作业效率（亩/小时）
    """
    result = trajectory_service.get_trajectory_stats(file_id, current_user.id)
    return ApiResponse.success(data=result)


@router.get(
    "/trajectories/{file_id}/analysis",
    response_model=ApiResponse[TrajectoryAnalysisResponse],
)
def get_trajectory_analysis(
    file_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取轨迹数据分析.

    返回:
    - 作业量指标（时长、行程、面积、速度）
    - 作业效率指标（达标率、生产率、时间利用率）
    - 可视化图表（base64编码）
    """
    # 获取轨迹统计数据（包含文件信息）
    stats = trajectory_service.get_trajectory_stats(file_id, current_user.id)

    # 获取轨迹点数据
    points_data = trajectory_service.get_trajectory_points(file_id, current_user.id)

    # 转换轨迹点为字典格式
    points = [
        {
            "latitude": p.latitude,
            "longitude": p.longitude,
            "speed": p.speed,
            "work_status": p.work_status,
            "depth": p.depth,
            "gps_time": p.gps_time.isoformat() if p.gps_time else None,
        }
        for p in points_data.points
    ]

    # 计算作业量指标
    work_volume = calc_work_volume_metrics(points, stats.work_width)

    # 计算作业效率指标
    work_efficiency = calc_work_efficiency_metrics(
        points, work_volume["work_area_mu"]
    )

    # 生成图表
    volume_chart, efficiency_chart = generate_combined_analysis_chart(
        work_volume, work_efficiency
    )

    # 构建响应
    result = TrajectoryAnalysisResponse(
        file_id=file_id,
        filename=stats.filename,
        machine_id=stats.machine_id,
        work_volume=WorkVolumeMetrics(**work_volume),
        work_efficiency=WorkEfficiencyMetrics(**work_efficiency),
        work_volume_chart=volume_chart,
        work_efficiency_chart=efficiency_chart,
    )

    return ApiResponse.success(data=result)


@router.delete(
    "/trajectories/{file_id}",
    response_model=ApiResponse,
)
def delete_trajectory(
    file_id: int,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """删除轨迹文件及其所有轨迹点."""
    trajectory_service.delete_trajectory(file_id, current_user.id)
    return ApiResponse.success(message="轨迹已删除")
