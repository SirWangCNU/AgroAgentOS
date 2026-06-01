"""轨迹 API 路由.

提供轨迹文件的上传、查询、统计分析和删除功能。
"""

from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, Form, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.trajectory import (
    TrajectoryFileInfo,
    TrajectoryListResponse,
    TrajectoryPointsResponse,
    TrajectoryStatsResponse,
    TrajectoryUploadResponse,
)
from app.services import trajectory_service

router = APIRouter(tags=["轨迹管理"])


@router.post(
    "/fields/{field_id}/trajectories/upload",
    response_model=ApiResponse[TrajectoryUploadResponse],
)
async def upload_trajectory(
    field_id: int,
    file: UploadFile = File(..., description="轨迹 Excel 文件"),
    coord_system: str = Form("auto", description="坐标系: wgs84/gcj02/auto"),
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
