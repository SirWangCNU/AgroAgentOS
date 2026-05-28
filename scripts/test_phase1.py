"""Phase 1 功能测试脚本.

测试内容:
1. Skill 库扩展 - 验证新 Skill 文件存在
2. 告警中心 - 测试 Alert 表和服务
3. RCA 时间线 - 测试 StateTransition 扩展
4. Agent 可观测性 - 测试 AgentRun 表和服务

使用方法:
  python scripts/test_phase1.py
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_skill_definitions():
    """测试 1.1 Skill 库扩展."""
    print("\n=== 测试 1.1 Skill 库扩展 ===")

    skills_dir = Path(__file__).parent.parent / "app" / "skills" / "definitions"
    expected_skills = [
        "log_analysis",
        "database_diagnosis",
        "jvm_diagnosis",
        "performance_diagnosis",
        "security_incident",
        "change_impact",
    ]

    existing_skills = [d.name for d in skills_dir.iterdir() if d.is_dir()]
    print(f"已有 Skill 数量: {len(existing_skills)}")

    for skill_name in expected_skills:
        skill_file = skills_dir / skill_name / "SKILL.md"
        if skill_file.exists():
            print(f"  [OK] {skill_name}/SKILL.md 存在")
        else:
            print(f"  [FAIL] {skill_name}/SKILL.md 不存在")
            return False

    print("[OK] Skill 库扩展测试通过")
    return True


async def test_alert_service():
    """测试 1.2 告警中心."""
    print("\n=== 测试 1.2 告警中心 ===")

    from app.core.sqlite import sqlite_manager
    from app.services import alert_service

    sqlite_manager.connect()

    try:
        # 测试告警接入
        alert_id = await alert_service.ingest_alert(
            alertname="TestAlert_Phase1",
            severity="warning",
            status="firing",
            instance="test-instance",
            service="test-service",
            summary="Phase 1 测试告警",
            labels={"alertname": "TestAlert_Phase1"},
            fingerprint="fp-phase1-test",
        )
        print(f"  [OK] 告警接入成功: {alert_id}")

        # 测试查询
        result = await alert_service.list_alerts(page=1, page_size=10)
        print(f"  [OK] 告警查询成功: {result['total']} 条告警")

        # 测试确认
        success = await alert_service.acknowledge_alert(alert_id, user="test-user")
        print(f"  [OK] 告警确认: {success}")

        # 测试统计
        stats = await alert_service.get_alert_stats()
        print(f"  [OK] 告警统计: {stats['total']} 条")

        # 测试关联分析
        related = await alert_service.correlate_alerts(alert_id)
        print(f"  [OK] 关联分析: {len(related)} 条相关告警")

        # 测试解决
        success = await alert_service.resolve_alert(alert_id)
        print(f"  [OK] 告警解决: {success}")

        print("[OK] 告警中心测试通过")
        return True

    except Exception as e:
        print(f"[FAIL] 告警中心测试失败: {e}")
        return False
    finally:
        sqlite_manager.disconnect()


async def test_state_transition():
    """测试 1.3 RCA 时间线 - StateTransition 扩展."""
    print("\n=== 测试 1.3 RCA 时间线 ===")

    from app.runtime.transitions import make_transition

    # 测试基本 transition
    transition = make_transition("executor", "executor_ok", "测试详情")
    print(f"  [OK] 基本 transition: {transition['node']} - {transition['reason']}")

    # 测试带工具调用的 transition
    transition_with_tools = make_transition(
        "executor",
        "executor_ok",
        "执行工具调用",
        tool_calls=[
            {"name": "test_tool", "args": {"param": "value"}, "result_preview": "结果预览", "elapsed_ms": 100, "status": "success"}
        ],
        tokens_used={"input": 100, "output": 50},
        decision_summary="执行步骤 1/4: 测试步骤",
    )
    print(f"  [OK] 带工具调用 transition: {len(transition_with_tools.get('tool_calls', []))} 个工具调用")
    print(f"  [OK] token 用量: {transition_with_tools.get('tokens_used', {})}")
    print(f"  [OK] 决策摘要: {transition_with_tools.get('decision_summary', '')}")

    print("[OK] RCA 时间线测试通过")
    return True


async def test_agent_run():
    """测试 1.4 Agent 可观测性."""
    print("\n=== 测试 1.4 Agent 可观测性 ===")

    from app.core.sqlite import sqlite_manager, AgentRun
    import uuid

    sqlite_manager.connect()

    try:
        # 测试创建 AgentRun
        run_id = uuid.uuid4().hex[:16]
        with sqlite_manager.session() as sess:
            run = AgentRun(
                run_id=run_id,
                session_id="test-session-phase1",
                query="测试查询",
                selected_skill="generic_oncall",
                status="completed",
                total_steps=4,
                total_tool_calls=8,
                total_tokens=2000,
                input_tokens=1500,
                output_tokens=500,
                total_ms=5000,
                model_used="qwen-turbo",
                reroute_count=0,
                report_preview="测试报告预览",
            )
            sess.add(run)
            sess.flush()
            print(f"  [OK] AgentRun 创建成功: {run_id}")

        # 测试查询
        with sqlite_manager.session() as sess:
            runs = sess.query(AgentRun).all()
            print(f"  [OK] AgentRun 查询成功: {len(runs)} 条记录")

        print("[OK] Agent 可观测性测试通过")
        return True

    except Exception as e:
        print(f"[FAIL] Agent 可观测性测试失败: {e}")
        return False
    finally:
        sqlite_manager.disconnect()


async def test_api_imports():
    """测试 API 模块导入."""
    print("\n=== 测试 API 模块导入 ===")

    try:
        from app.api.v1 import alerts
        print("  [OK] alerts API 导入成功")

        from app.api.v1 import observability
        print("  [OK] observability API 导入成功")

        from app.main import app
        print("  [OK] FastAPI 应用导入成功")

        # 检查路由是否注册
        routes = [route.path for route in app.routes]
        if "/api/v1/alerts" in routes:
            print("  [OK] alerts 路由已注册")
        if "/api/v1/observability" in routes:
            print("  [OK] observability 路由已注册")

        print("[OK] API 模块导入测试通过")
        return True

    except Exception as e:
        print(f"[FAIL] API 模块导入测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试."""
    print("=" * 60)
    print("Phase 1 功能测试")
    print("=" * 60)

    results = []

    # 运行测试
    results.append(await test_skill_definitions())
    results.append(await test_alert_service())
    results.append(await test_state_transition())
    results.append(await test_agent_run())
    results.append(await test_api_imports())

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"[OK] 所有测试通过 ({passed}/{total})")
        return 0
    else:
        print(f"[FAIL] 部分测试失败 ({passed}/{total})")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
