"""轨迹功能测试脚本.

测试内容:
1. Redis 连接
2. 轨迹分析计算
3. Excel 解析（模拟数据）

使用方式:
  python scripts/test_trajectory.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_redis_connection():
    """测试 Redis 连接."""
    print("=" * 50)
    print("测试 Redis 连接...")
    print("=" * 50)

    try:
        from app.core.redis import redis_manager
        redis_manager.connect()

        if redis_manager.is_alive():
            print("[OK] Redis 连接成功")

            # 测试基本操作
            test_key = "test:trajectory:demo"
            test_value = {"name": "测试轨迹", "points": 100}

            # SET
            redis_manager.set(test_key, test_value, expire=60)
            print(f"[OK] SET {test_key}")

            # GET
            result = redis_manager.get(test_key)
            assert result == test_value, f"GET 结果不匹配: {result}"
            print(f"[OK] GET {test_key} = {result}")

            # DELETE
            redis_manager.delete(test_key)
            assert redis_manager.get(test_key) is None
            print(f"[OK] DELETE {test_key}")

            # 测试缓存键生成
            print(f"[OK] 轨迹列表键: {redis_manager.trajectory_list_key(1)}")
            print(f"[OK] 轨迹点键: {redis_manager.trajectory_points_key(1)}")
            print(f"[OK] 轨迹统计键: {redis_manager.trajectory_stats_key(1)}")
        else:
            print("[SKIP] Redis 不可用，将使用数据库直查模式")

    except Exception as e:
        print(f"[ERROR] Redis 测试失败: {e}")
        return False

    return True


def test_trajectory_analysis():
    """测试轨迹分析计算."""
    print("\n" + "=" * 50)
    print("测试轨迹分析计算...")
    print("=" * 50)

    try:
        from app.services.trajectory_analysis import (
            haversine_distance,
            calc_total_distance,
            calc_work_distance,
            calc_work_area,
            calc_depth_stats,
            calc_speed_stats,
            calc_time_stats,
            calc_compliance_rate,
            calc_productivity,
            calc_time_utilization,
            calc_work_volume_metrics,
            calc_work_efficiency_metrics,
        )

        # 测试 Haversine 距离计算
        # 北京天安门到故宫的距离约 1km
        dist = haversine_distance(39.9042, 116.4074, 39.9163, 116.3972)
        print(f"[OK] Haversine 距离: {dist:.1f} 米 (预期约 1400 米)")
        assert 1000 < dist < 2000, f"距离计算异常: {dist}"

        # 模拟轨迹点
        points = [
            {"seq": 1, "latitude": 39.9042, "longitude": 116.4074, "speed": 5.0, "work_status": "working", "depth": 15.0},
            {"seq": 2, "latitude": 39.9043, "longitude": 116.4075, "speed": 5.5, "work_status": "working", "depth": 14.5},
            {"seq": 3, "latitude": 39.9044, "longitude": 116.4076, "speed": 4.8, "work_status": "working", "depth": 16.0},
            {"seq": 4, "latitude": 39.9045, "longitude": 116.4077, "speed": 5.2, "work_status": "idle", "depth": 0.0},
            {"seq": 5, "latitude": 39.9046, "longitude": 116.4078, "speed": 6.0, "work_status": "working", "depth": 15.5},
        ]

        # 测试总距离
        total_dist = calc_total_distance(points)
        print(f"[OK] 总距离: {total_dist:.1f} 米")
        assert total_dist > 0, "总距离应大于 0"

        # 测试作业距离
        work_dist = calc_work_distance(points)
        print(f"[OK] 作业距离: {work_dist:.1f} 米")
        assert work_dist > 0, "作业距离应大于 0"
        assert work_dist <= total_dist, "作业距离不应大于总距离"

        # 测试作业面积
        area = calc_work_area(work_dist, 3.0)  # 幅宽 3 米
        print(f"[OK] 作业面积: {area:.2f} 亩")
        assert area > 0, "作业面积应大于 0"

        # 测试深度统计
        depth_stats = calc_depth_stats(points, target_depth=15.0, tolerance=2.0)
        print(f"[OK] 平均深度: {depth_stats['avg_depth']} cm")
        print(f"[OK] 深度标准差: {depth_stats['depth_std']} cm")
        print(f"[OK] 深度合格率: {depth_stats['depth_pass_rate']}%")
        print(f"[OK] 深度分布: {len(depth_stats['depth_distribution'])} 个区间")

        # 测试速度统计
        speed_stats = calc_speed_stats(points)
        print(f"[OK] 平均速度: {speed_stats['avg_speed']} km/h")
        print(f"[OK] 最大速度: {speed_stats['max_speed']} km/h")

        # 测试时间统计
        points_with_time = [
            {**p, "gps_time": datetime(2026, 6, 1, 10, i * 5)}
            for i, p in enumerate(points)
        ]
        time_stats = calc_time_stats(points_with_time)
        print(f"[OK] 总时间: {time_stats['total_duration_min']} 分钟")

        # 测试作业量指标
        work_volume = calc_work_volume_metrics(points_with_time, work_width=3.0)
        print(f"[OK] 作业总时长: {work_volume['work_duration_hours']} 小时")
        print(f"[OK] 作业总行程: {work_volume['work_distance_km']} 公里")
        print(f"[OK] 作业面积: {work_volume['work_area_mu']} 亩")
        print(f"[OK] 田间平均速度: {work_volume['avg_field_speed_kmh']} km/h")

        # 测试达标率
        compliance = calc_compliance_rate(points_with_time, target_depth=15.0, depth_tolerance=2.0)
        print(f"[OK] 综合达标率: {compliance['compliance_rate']}%")
        print(f"[OK] 深度达标率: {compliance['depth_compliance']}%")
        print(f"[OK] 速度达标率: {compliance['speed_compliance']}%")

        # 测试生产率
        productivity = calc_productivity(work_volume['work_area_mu'], time_stats['total_duration_min'])
        print(f"[OK] 生产率: {productivity} 亩/小时")

        # 测试时间利用率
        time_util = calc_time_utilization(time_stats['work_duration_min'], time_stats['total_duration_min'])
        print(f"[OK] 时间利用率: {time_util}%")

        # 测试作业效率指标
        efficiency = calc_work_efficiency_metrics(points_with_time, work_volume['work_area_mu'])
        print(f"[OK] 作业效率指标: {efficiency}")

    except Exception as e:
        print(f"[ERROR] 轨迹分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_excel_parser():
    """测试 Excel 解析（使用 openpyxl 创建测试文件）."""
    print("\n" + "=" * 50)
    print("测试 Excel 解析...")
    print("=" * 50)

    try:
        from app.services.trajectory_service import parse_excel

        # 尝试导入 openpyxl
        try:
            import openpyxl
        except ImportError:
            print("[SKIP] openpyxl 未安装，跳过 Excel 解析测试")
            return True

        # 创建测试 Excel
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "轨迹数据"

        # 写入表头
        headers = ["GPS时间", "纬度", "经度", "速度", "工作状态", "作业深度", "幅宽", "农机编号"]
        ws.append(headers)

        # 写入测试数据
        base_time = datetime(2026, 6, 1, 10, 0, 0)
        for i in range(10):
            row = [
                base_time.replace(minute=i * 5),
                39.9042 + i * 0.0001,
                116.4074 + i * 0.0001,
                5.0 + i * 0.1,
                "working" if i % 3 != 0 else "idle",
                15.0 + (i % 3 - 1) * 0.5,
                3.0,
                "T001",
            ]
            ws.append(row)

        # 保存到内存
        from io import BytesIO
        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        # 解析
        result = parse_excel(content, "test.xlsx")

        print(f"[OK] 解析成功: {len(result['points'])} 个轨迹点")
        print(f"[OK] 农机编号: {result['machine_id']}")
        print(f"[OK] 幅宽: {result['work_width']} 米")

        # 验证数据
        assert len(result["points"]) == 10, f"预期 10 个点，实际 {len(result['points'])}"
        assert result["machine_id"] == "T001", f"农机编号不匹配: {result['machine_id']}"
        assert result["work_width"] == 3.0, f"幅宽不匹配: {result['work_width']}"

        # 打印第一个点
        p = result["points"][0]
        print(f"[OK] 第一个点: lat={p['latitude']}, lon={p['longitude']}, speed={p['speed']}")

    except Exception as e:
        print(f"[ERROR] Excel 解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_schema_validation():
    """测试 Schema 验证."""
    print("\n" + "=" * 50)
    print("测试 Schema 验证...")
    print("=" * 50)

    try:
        from app.schemas.trajectory import (
            TrajectoryFileInfo,
            TrajectoryPointData,
            TrajectoryStatsResponse,
            DepthDistribution,
            WorkVolumeMetrics,
            WorkEfficiencyMetrics,
            TrajectoryAnalysisResponse,
        )

        # 测试 TrajectoryPointData
        point = TrajectoryPointData(
            id=1,
            seq=1,
            latitude=39.9042,
            longitude=116.4074,
            speed=5.0,
            work_status="working",
            depth=15.0,
        )
        print(f"[OK] TrajectoryPointData: {point.model_dump()}")

        # 测试 DepthDistribution
        dist = DepthDistribution(
            range_label="10-15cm",
            count=50,
            percentage=33.3,
        )
        print(f"[OK] DepthDistribution: {dist.model_dump()}")

        # 测试 TrajectoryStatsResponse
        stats = TrajectoryStatsResponse(
            file_id=1,
            filename="test.xlsx",
            machine_id="T001",
            point_count=100,
            total_distance_m=5000.0,
            work_distance_m=4000.0,
            work_area_mu=20.0,
            work_width=3.0,
            avg_speed=5.5,
            max_speed=8.0,
            avg_depth=15.2,
            depth_std=1.5,
            depth_pass_rate=85.0,
            depth_distribution=[dist],
            work_efficiency_mu_per_hour=10.0,
        )
        print(f"[OK] TrajectoryStatsResponse 创建成功")

        # 测试 WorkVolumeMetrics
        volume = WorkVolumeMetrics(
            work_duration_hours=2.5,
            work_distance_km=12.5,
            work_area_mu=18.0,
            avg_field_speed_kmh=5.0,
        )
        print(f"[OK] WorkVolumeMetrics: {volume.model_dump()}")

        # 测试 WorkEfficiencyMetrics
        efficiency = WorkEfficiencyMetrics(
            compliance_rate=85.0,
            depth_compliance=90.0,
            speed_compliance=88.0,
            productivity_mu_per_hour=7.2,
            time_utilization_rate=75.0,
            total_points=100,
            compliant_points=85,
        )
        print(f"[OK] WorkEfficiencyMetrics: {efficiency.model_dump()}")

        # 测试 TrajectoryAnalysisResponse
        analysis = TrajectoryAnalysisResponse(
            file_id=1,
            filename="test.xlsx",
            machine_id="T001",
            work_volume=volume,
            work_efficiency=efficiency,
            work_volume_chart="base64_encoded_chart_data",
            work_efficiency_chart="base64_encoded_chart_data",
        )
        print(f"[OK] TrajectoryAnalysisResponse 创建成功")

    except Exception as e:
        print(f"[ERROR] Schema 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_chart_generation():
    """测试图表生成."""
    print("\n" + "=" * 50)
    print("测试图表生成...")
    print("=" * 50)

    try:
        from app.services.trajectory_charts import (
            generate_work_volume_chart,
            generate_work_efficiency_chart,
            generate_combined_analysis_chart,
            HAS_MATPLOTLIB,
        )

        if not HAS_MATPLOTLIB:
            print("[SKIP] matplotlib 未安装，跳过图表生成测试")
            return True

        # 测试数据
        work_volume = {
            "work_duration_hours": 2.5,
            "work_distance_km": 12.5,
            "work_area_mu": 18.0,
            "avg_field_speed_kmh": 5.0,
        }

        work_efficiency = {
            "compliance_rate": 85.0,
            "depth_compliance": 90.0,
            "speed_compliance": 88.0,
            "productivity_mu_per_hour": 7.2,
            "time_utilization_rate": 75.0,
            "total_points": 100,
            "compliant_points": 85,
        }

        # 测试作业量图表
        volume_chart = generate_work_volume_chart(work_volume)
        if volume_chart:
            print(f"[OK] 作业量图表生成成功，长度: {len(volume_chart)} 字符")
        else:
            print("[SKIP] 作业量图表生成返回空（matplotlib 可能不可用）")

        # 测试作业效率图表
        efficiency_chart = generate_work_efficiency_chart(work_efficiency)
        if efficiency_chart:
            print(f"[OK] 作业效率图表生成成功，长度: {len(efficiency_chart)} 字符")
        else:
            print("[SKIP] 作业效率图表生成返回空（matplotlib 可能不可用）")

        # 测试综合图表生成
        volume_chart, efficiency_chart = generate_combined_analysis_chart(work_volume, work_efficiency)
        print(f"[OK] 综合图表生成完成")

    except Exception as e:
        print(f"[ERROR] 图表生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    """运行所有测试."""
    print("\n" + "=" * 60)
    print("  轨迹功能测试")
    print("=" * 60 + "\n")

    results = []
    results.append(("Redis 连接", test_redis_connection()))
    results.append(("轨迹分析", test_trajectory_analysis()))
    results.append(("Excel 解析", test_excel_parser()))
    results.append(("Schema 验证", test_schema_validation()))
    results.append(("图表生成", test_chart_generation()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name}: {status}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("  所有测试通过!")
    else:
        print("  部分测试失败!")
    print("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
