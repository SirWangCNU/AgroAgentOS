import os

os.environ["DEBUG"] = "false"

import app.agents as agents
from app.skills.registry import get_skill_registry


def test_unknown_skill_uses_agriculture_default():
    registry = get_skill_registry()

    assert registry.get_or_default("missing-skill").name == "agriculture_qa"


def test_agent_package_exports_agriculture_graph():
    assert callable(agents.build_agriculture_graph)
    assert not hasattr(agents, "build_aiops_graph")
