"""Farm-agent Skill registry and playbook contract tests."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from app.runtime.tool_filter import filter_tools_for_skill
from app.schemas.farm_agent import VerificationVerdict
from app.skills.registry import GENERIC_SKILL_NAME, get_skill_registry
from app.tools.mcp_loader import get_local_tools


DEFINITIONS_DIR = Path(__file__).parents[2] / "app" / "skills" / "definitions"
SKILL_GUIDE = Path(__file__).parents[2] / "docs" / "skill_development_guide.md"
VERIFICATION_VERDICTS = {"pass", "needs_evidence", "rework", "manual_review"}
FORBIDDEN_VERDICTS = {"fail", "needs_review"}


def test_agriculture_qa_is_the_hard_fallback() -> None:
    registry = get_skill_registry()

    assert GENERIC_SKILL_NAME == "agriculture_qa"
    assert registry.get_or_generic("missing").name == "agriculture_qa"
    assert not (DEFINITIONS_DIR / "generic_oncall").exists()


def test_farm_inspection_has_exact_tool_allowlist() -> None:
    skill = get_skill_registry().get("farm_inspection")

    assert skill is not None
    assert set(skill.allowed_tools) == {
        "get_farm_snapshot",
        "inspect_farm_weather_risks",
        "get_field_work_quality",
        "get_pending_farm_tasks",
        "search_knowledge_base",
        "create_action_proposal",
    }


def test_farm_task_verification_has_exact_tool_allowlist() -> None:
    skill = get_skill_registry().get("farm_task_verification")

    assert skill is not None
    assert set(skill.allowed_tools) == {
        "get_task_evidence",
        "get_field_work_quality",
        "search_knowledge_base",
        "save_task_verification_draft",
    }


@pytest.mark.parametrize(
    ("skill_name", "expected_tools"),
    [
        (
            "farm_inspection",
            {
                "get_farm_snapshot",
                "inspect_farm_weather_risks",
                "get_field_work_quality",
                "get_pending_farm_tasks",
                "search_knowledge_base",
                "create_action_proposal",
            },
        ),
        (
            "farm_task_verification",
            {
                "get_task_evidence",
                "get_field_work_quality",
                "search_knowledge_base",
                "save_task_verification_draft",
            },
        ),
    ],
)
def test_controlled_farm_skills_enforce_exact_runtime_allowlists(
    skill_name: str,
    expected_tools: set[str],
) -> None:
    visible_tools, _ = filter_tools_for_skill(skill_name, get_local_tools())

    assert {tool.name for tool in visible_tools} == expected_tools


def test_farm_inspection_playbook_enforces_evidence_first_proposals() -> None:
    skill = get_skill_registry().get("farm_inspection")
    assert skill is not None
    playbook = skill.playbook

    evidence_steps = [
        "get_farm_snapshot",
        "inspect_farm_weather_risks",
        "get_field_work_quality",
        "get_pending_farm_tasks",
        "search_knowledge_base",
        "create_action_proposal",
    ]
    positions = [playbook.index(tool_name) for tool_name in evidence_steps]
    assert positions == sorted(positions)
    assert all(label in playbook for label in ("实测事实", "规则依据", "分析推断"))
    assert all(f"`{kind}`" in playbook for kind in ("measured", "rule", "inference"))
    assert "没有证据不得生成高置信度提案" in playbook
    assert "pending" in playbook
    assert "needs_review" not in playbook
    assert "仅创建待人工确认的提案" in playbook
    assert "结构化提案" in playbook
    assert "人工确认" in playbook


def test_task_verification_playbook_is_draft_only() -> None:
    skill = get_skill_registry().get("farm_task_verification")
    assert skill is not None
    playbook = skill.playbook

    evidence_steps = [
        "get_task_evidence",
        "get_field_work_quality",
        "search_knowledge_base",
        "save_task_verification_draft",
    ]
    positions = [playbook.index(tool_name) for tool_name in evidence_steps]
    assert positions == sorted(positions)
    assert all(label in playbook for label in ("实测事实", "规则依据", "分析推断"))
    assert all(f"`{kind}`" in playbook for kind in ("measured", "rule", "inference"))
    assert "verdict" in playbook
    documented_verdicts = set(
        re.findall(r"^- `([^`]+)`：", playbook, flags=re.MULTILINE)
    )
    assert documented_verdicts == VERIFICATION_VERDICTS
    assert set(get_args(VerificationVerdict)) == VERIFICATION_VERDICTS
    assert all(value not in playbook for value in FORBIDDEN_VERDICTS)
    assert "没有证据不得给出高置信度结论" in playbook
    assert "保存草稿不改变任务状态" in playbook
    assert "最终审核" in playbook


def test_skill_guide_documents_exact_task_verification_verdicts() -> None:
    guide = SKILL_GUIDE.read_text(encoding="utf-8")
    verification_section = guide.split("### `farm_task_verification`", maxsplit=1)[1]
    verification_section = verification_section.split("## Playbook", maxsplit=1)[0]

    documented_verdicts = set(
        re.findall(r"^- `([^`]+)`：", verification_section, flags=re.MULTILINE)
    )
    assert documented_verdicts == VERIFICATION_VERDICTS
    assert all(value not in verification_section for value in FORBIDDEN_VERDICTS)
