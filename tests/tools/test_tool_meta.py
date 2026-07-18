"""Farm Agent tool metadata registration tests."""

from app.tools.meta import TOOL_META, warn_unregistered_tools


EXPECTED_FARM_TOOL_META = {
    "get_farm_snapshot": (True, True, "none", "low"),
    "inspect_farm_weather_risks": (True, True, "network", "medium"),
    "get_field_work_quality": (True, True, "none", "low"),
    "get_pending_farm_tasks": (True, True, "none", "low"),
    "get_task_evidence": (True, True, "none", "low"),
    "create_action_proposal": (False, False, "database", "medium"),
    "save_task_verification_draft": (False, False, "database", "medium"),
}


def test_farm_tool_metadata_matches_exact_safety_matrix() -> None:
    for name, expected in EXPECTED_FARM_TOOL_META.items():
        meta = TOOL_META[name]
        assert (
            meta.read_only,
            meta.concurrency_safe,
            meta.side_effect,
            meta.risk_level,
        ) == expected
        assert meta.destructive is False


def test_all_farm_tools_are_registered() -> None:
    assert warn_unregistered_tools(list(EXPECTED_FARM_TOOL_META)) == []
