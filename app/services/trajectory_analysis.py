"""轨迹统计分析服务.

提供轨迹数据的统计计算功能:
  - 总距离（Haversine 公式）
  - 作业面积（幅宽 × 作业距离）
  - 深度统计（均值、合格率、分布）
  - 作业效率（作业时间/总面积）
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from loguru import logger

from app.schemas.trajectory import DepthDistribution, TrajectoryStatsResponse


# ==================== 距离计算 ====================


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """使用 Haversine 公式计算两点间的距离（米）.

    Args:
        lat1, lon1: 第一个点的经纬度
        lat2, lon2: 第二个点的经纬度

    Returns:
        距离（米）
    """
    R = 6371000  # 地球半径（米）

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = (math.sin(delta_lat / 2) ** 2 +
         math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def calc_total_distance(points: list[dict[str, Any]]) -> float:
    """计算轨迹总距离（米）.

    Args:
        points: 轨迹点列表，每个点包含 latitude, longitude

    Returns:
        总距离（米）
    """
    if len(points) < 2:
        return 0.0

    total_distance = 0.0
    for i in range(1, len(points)):
        dist = haversine_distance(
            points[i - 1]["latitude"],
            points[i - 1]["longitude"],
            points[i]["latitude"],
            points[i]["longitude"],
        )
        total_distance += dist

    return total_distance


# ==================== 作业面积计算 ====================


def calc_work_distance(points: list[dict[str, Any]]) -> float:
    """计算作业距离（仅统计 work_status=working 的段落）.

    Returns:
        作业距离（米）
    """
    if len(points) < 2:
        return 0.0

    work_distance = 0.0
    for i in range(1, len(points)):
        if points[i].get("work_status") == "working":
            dist = haversine_distance(
                points[i - 1]["latitude"],
                points[i - 1]["longitude"],
                points[i]["latitude"],
                points[i]["longitude"],
            )
            work_distance += dist

    return work_distance


def calc_work_area(work_distance_m: float, work_width_m: float) -> float:
    """计算作业面积（亩）.

    Args:
        work_distance_m: 作业距离（米）
        work_width_m: 幅宽（米）

    Returns:
        作业面积（亩），1亩 ≈ 666.67平方米
    """
    area_sqm = work_distance_m * work_width_m
    return area_sqm / 666.67


# ==================== 深度统计 ====================


def calc_depth_stats(
    points: list[dict[str, Any]],
    target_depth: float = 15.0,
    tolerance: float = 5.0,
) -> dict[str, Any]:
    """计算深度统计.

    Args:
        points: 轨迹点列表
        target_depth: 目标深度（厘米），默认 15cm
        tolerance: 允许误差（厘米），默认 ±5cm

    Returns:
        包含 avg_depth, depth_std, depth_pass_rate, depth_distribution
    """
    depths = [p.get("depth", 0.0) for p in points if p.get("depth", 0.0) > 0]

    if not depths:
        return {
            "avg_depth": 0.0,
            "depth_std": 0.0,
            "depth_pass_rate": 0.0,
            "depth_distribution": [],
        }

    # 平均深度
    avg_depth = sum(depths) / len(depths)

    # 深度标准差
    variance = sum((d - avg_depth) ** 2 for d in depths) / len(depths)
    depth_std = math.sqrt(variance)

    # 合格率（在目标深度 ± 容差范围内）
    min_depth = target_depth - tolerance
    max_depth = target_depth + tolerance
    pass_count = sum(1 for d in depths if min_depth <= d <= max_depth)
    depth_pass_rate = (pass_count / len(depths)) * 100

    # 深度分布（按 5cm 分段）
    distribution = _calc_depth_distribution(depths)

    return {
        "avg_depth": round(avg_depth, 2),
        "depth_std": round(depth_std, 2),
        "depth_pass_rate": round(depth_pass_rate, 1),
        "depth_distribution": distribution,
    }


def _calc_depth_distribution(depths: list[float]) -> list[DepthDistribution]:
    """计算深度分布."""
    if not depths:
        return []

    # 按 5cm 分段
    step = 5
    min_d = int(min(depths) // step * step)
    max_d = int((max(depths) // step + 1) * step)

    buckets: dict[str, int] = {}
    for d in depths:
        bucket_start = int(d // step * step)
        bucket_end = bucket_start + step
        label = f"{bucket_start}-{bucket_end}cm"
        buckets[label] = buckets.get(label, 0) + 1

    total = len(depths)
    result = []
    for label in sorted(buckets.keys()):
        count = buckets[label]
        result.append(DepthDistribution(
            range_label=label,
            count=count,
            percentage=round(count / total * 100, 1),
        ))

    return result


# ==================== 速度统计 ====================


def calc_speed_stats(points: list[dict[str, Any]]) -> dict[str, float]:
    """计算速度统计.

    Returns:
        avg_speed, max_speed
    """
    speeds = [p.get("speed", 0.0) for p in points if p.get("speed", 0.0) > 0]

    if not speeds:
        return {"avg_speed": 0.0, "max_speed": 0.0}

    return {
        "avg_speed": round(sum(speeds) / len(speeds), 2),
        "max_speed": round(max(speeds), 2),
    }


# ==================== 时间统计 ====================


def calc_time_stats(points: list[dict[str, Any]]) -> dict[str, Any]:
    """计算时间统计.

    Returns:
        start_time, end_time, work_duration_min, total_duration_min
    """
    if not points:
        return {
            "start_time": None,
            "end_time": None,
            "work_duration_min": 0.0,
            "total_duration_min": 0.0,
        }

    # 获取有效时间点
    times = []
    work_times = []
    for p in points:
        gps_time = p.get("gps_time")
        if gps_time:
            if isinstance(gps_time, str):
                try:
                    gps_time = datetime.fromisoformat(gps_time.replace("Z", "+00:00"))
                except ValueError:
                    continue
            times.append(gps_time)
            if p.get("work_status") == "working":
                work_times.append(gps_time)

    if not times:
        return {
            "start_time": None,
            "end_time": None,
            "work_duration_min": 0.0,
            "total_duration_min": 0.0,
        }

    start_time = min(times)
    end_time = max(times)
    total_duration = (end_time - start_time).total_seconds() / 60

    work_duration = 0.0
    if len(work_times) >= 2:
        work_duration = (max(work_times) - min(work_times)).total_seconds() / 60

    return {
        "start_time": start_time,
        "end_time": end_time,
        "work_duration_min": round(work_duration, 1),
        "total_duration_min": round(total_duration, 1),
    }


# ==================== 综合统计 ====================


def calc_trajectory_stats(
    file_id: int,
    filename: str,
    machine_id: str,
    points: list[dict[str, Any]],
    work_width: float = 0.0,
    target_depth: float = 15.0,
) -> TrajectoryStatsResponse:
    """计算轨迹综合统计.

    Args:
        file_id: 轨迹文件 ID
        filename: 文件名
        machine_id: 农机编号
        points: 轨迹点列表
        work_width: 幅宽（米）
        target_depth: 目标深度（厘米）

    Returns:
        TrajectoryStatsResponse
    """
    # 距离统计
    total_distance = calc_total_distance(points)
    work_distance = calc_work_distance(points)
    work_area = calc_work_area(work_distance, work_width)

    # 深度统计
    depth_stats = calc_depth_stats(points, target_depth)

    # 速度统计
    speed_stats = calc_speed_stats(points)

    # 时间统计
    time_stats = calc_time_stats(points)

    # 作业效率（亩/小时）
    work_efficiency = 0.0
    if time_stats["work_duration_min"] > 0 and work_area > 0:
        work_hours = time_stats["work_duration_min"] / 60
        work_efficiency = work_area / work_hours

    return TrajectoryStatsResponse(
        file_id=file_id,
        filename=filename,
        machine_id=machine_id,
        point_count=len(points),
        total_distance_m=round(total_distance, 1),
        work_distance_m=round(work_distance, 1),
        work_area_mu=round(work_area, 2),
        start_time=time_stats["start_time"],
        end_time=time_stats["end_time"],
        work_duration_min=time_stats["work_duration_min"],
        total_duration_min=time_stats["total_duration_min"],
        avg_speed=speed_stats["avg_speed"],
        max_speed=speed_stats["max_speed"],
        avg_depth=depth_stats["avg_depth"],
        depth_std=depth_stats["depth_std"],
        depth_pass_rate=depth_stats["depth_pass_rate"],
        depth_distribution=depth_stats["depth_distribution"],
        work_efficiency_mu_per_hour=round(work_efficiency, 2),
    )
