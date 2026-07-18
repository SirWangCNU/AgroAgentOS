"""Agriculture-native prompt and subagent semantic tests."""

from __future__ import annotations

import re
from pathlib import Path

from app.agents.replanner import _force_summary
from app.agents.subagents import SUBAGENTS
from app.agents.subagents.runner import get_subagent_tools
from app.runtime.agent_harness import AgentHarness
from app.tools.meta import TOOL_META


PROJECT_ROOT = Path(__file__).parents[2]
PROMPT_BEARING_FILES = (
    PROJECT_ROOT / "app" / "runtime" / "agent_harness.py",
    PROJECT_ROOT / "app" / "runtime" / "tool_filter.py",
    PROJECT_ROOT / "app" / "agents" / "skill_router.py",
    PROJECT_ROOT / "app" / "agents" / "planner.py",
    PROJECT_ROOT / "app" / "agents" / "replanner.py",
    PROJECT_ROOT / "app" / "agents" / "subagents" / "__init__.py",
    PROJECT_ROOT / "app" / "agents" / "subagents" / "runner.py",
    PROJECT_ROOT / "app" / "skills" / "registry.py",
    PROJECT_ROOT / "app" / "skills" / "README.md",
    PROJECT_ROOT / "docs" / "skill_development_guide.md",
)
FORBIDDEN_PATTERNS = (
    r"aiops",
    r"sre",
    r"server root cause",
    r"generic_oncall",
    r"故障诊断报告",
)


def test_prompt_and_skill_surface_contains_no_legacy_operations_language() -> None:
    files = list(PROMPT_BEARING_FILES)
    files.extend(
        sorted((PROJECT_ROOT / "app" / "skills" / "definitions").glob("*/SKILL.md"))
    )

    violations: list[str] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                violations.append(f"{path.relative_to(PROJECT_ROOT)}: {pattern}")

    assert violations == []


def test_subagents_are_farm_native_and_delegate_names_are_registered() -> None:
    expected_names = {
        "farm_data_analyst",
        "agronomy_researcher",
        "farm_work_planner",
    }
    assert set(SUBAGENTS) == expected_names
    assert {tool.name for tool in get_subagent_tools()} == {
        f"delegate_to_{name}" for name in expected_names
    }
    assert {f"delegate_to_{name}" for name in expected_names} <= set(TOOL_META)

    assert "只收集" in SUBAGENTS["farm_data_analyst"].system_prompt
    assert "不确定性" in SUBAGENTS["agronomy_researcher"].system_prompt
    planner_prompt = SUBAGENTS["farm_work_planner"].system_prompt
    assert all(term in planner_prompt for term in ("行动", "截止时间", "验收条件"))
    assert "不做最终审批" in planner_prompt


def test_all_report_paths_use_agriculture_risk_report_title() -> None:
    harness = AgentHarness()
    report_messages = harness.build_report_messages(
        user_input="检查暴雨风险",
        past_steps=[("查询天气", "未来两天有强降雨")],
        current_time="2026-07-18 12:00:00 CST",
        draft="",
    )
    replanner_messages = harness.build_replanner_messages(
        user_input="检查暴雨风险",
        current_time="2026-07-18 12:00:00 CST",
        current_skill_line="farm_inspection",
        candidate_skills_text="(无)",
        tried_skills_text="(无)",
        reroute_count=0,
        reroute_quota_hint="不可 reroute",
        plan_text="1. 查询天气",
        past_steps_text="未来两天有强降雨",
    )
    force_summary = _force_summary(
        "检查暴雨风险",
        [],
        "2026-07-18 12:00:00 CST",
    )

    assert "农业风险分析报告" in "\n".join(
        message["content"] for message in report_messages + replanner_messages
    )
    assert force_summary.startswith("# 农业风险分析报告")
