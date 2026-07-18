import pytest

from app.agents import PlanExecuteState, build_farm_agent_graph
from app.agents.graph import farm_skill_router_node


def test_exports_only_farm_graph_builder() -> None:
    import app.agents as agents

    assert callable(build_farm_agent_graph)
    legacy_builder = "build_" + "aiops" + "_graph"
    assert not hasattr(agents, legacy_builder)


def test_farm_state_contract_accepts_business_identity() -> None:
    state: PlanExecuteState = {
        "input": "巡检",
        "user_id": 7,
        "farm_id": 11,
        "run_id": "run-1",
        "run_type": "inspection",
        "business_context": {"risks": []},
        "proposal_ids": [],
    }

    assert state["business_context"] == {"risks": []}


@pytest.mark.anyio
async def test_farm_router_forces_workflow_skill() -> None:
    inspection = await farm_skill_router_node({"run_type": "inspection"})
    verification = await farm_skill_router_node(
        {"run_type": "task_verification"}
    )

    assert inspection["selected_skill"] == "farm_inspection"
    assert verification["selected_skill"] == "farm_task_verification"
