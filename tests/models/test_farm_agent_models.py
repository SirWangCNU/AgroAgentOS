import json

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from app.core.sqlite import AgentRun, Base
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.models.user import User


def _unique_column_sets(engine, table_name: str) -> set[tuple[str, ...]]:
    constraints = {
        tuple(constraint["column_names"])
        for constraint in inspect(engine).get_unique_constraints(table_name)
    }
    indexes = {
        tuple(index["column_names"])
        for index in inspect(engine).get_indexes(table_name)
        if index["unique"]
    }
    return constraints | indexes


def test_farm_workflow_models_apply_defaults_and_keep_json_types_stable() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(username="owner", email="owner@example.com", hashed_password="hash")
        session.add(user)
        session.flush()
        farm = Farm(user_id=user.id, name="示范农场")
        session.add(farm)
        session.flush()
        field = Field(farm_id=farm.id, name="A1")
        run = AgentRun(run_id="run-001", user_id=user.id, farm_id=farm.id)
        session.add_all([field, run])
        session.flush()

        proposal = FarmActionProposal(
            proposal_id="proposal-001",
            farm_id=farm.id,
            created_by=user.id,
            run_id=run.run_id,
            risk_fingerprint="risk-001",
            title="暴雨排水风险",
            severity="high",
            summary="预计强降雨",
        )
        task = FarmTask(
            task_id="task-001",
            proposal_id=proposal.proposal_id,
            action_key="drainage-check-a1",
            farm_id=farm.id,
            field_id=field.id,
            title="检查排水沟",
            task_type="drainage",
            instructions="清理堵塞点",
        )
        session.add_all([proposal, task])
        session.flush()

        assert proposal.status == "pending"
        assert task.status == "pending"
        assert proposal.evidence == []
        assert proposal.actions == []
        assert task.execution == {}
        assert task.agent_verdict == {}
        assert run.context_snapshot == {}
        assert run.outcome == {}


def test_farm_workflow_json_setters_preserve_chinese_text() -> None:
    proposal = FarmActionProposal()
    task = FarmTask()
    run = AgentRun()

    proposal.set_evidence([{"summary": "未来 24 小时有暴雨"}])
    proposal.set_actions([{"title": "检查排水沟"}])
    task.set_execution({"note": "已清理堵塞点"})
    task.set_agent_verdict({"note": "证据充分"})
    run.set_context_snapshot({"farm_name": "示范农场"})
    run.set_outcome({"report": "巡检完成"})

    assert "未来 24 小时有暴雨" in proposal.evidence_json
    assert "检查排水沟" in proposal.actions_json
    assert "已清理堵塞点" in task.execution_json
    assert "证据充分" in task.agent_verdict_json
    assert "示范农场" in run.context_snapshot_json
    assert "巡检完成" in run.outcome_json
    assert proposal.evidence == [{"summary": "未来 24 小时有暴雨"}]
    assert proposal.actions == [{"title": "检查排水沟"}]
    assert task.execution == {"note": "已清理堵塞点"}
    assert task.agent_verdict == {"note": "证据充分"}
    assert run.context_snapshot == {"farm_name": "示范农场"}
    assert run.outcome == {"report": "巡检完成"}
    assert all(
        "\\u" not in value
        for value in (
            proposal.evidence_json,
            proposal.actions_json,
            task.execution_json,
            task.agent_verdict_json,
            run.context_snapshot_json,
            run.outcome_json,
        )
    )
    json.loads(proposal.evidence_json)


def test_external_workflow_identifiers_are_unique() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    assert ("proposal_id",) in _unique_column_sets(engine, "farm_action_proposals")
    assert ("task_id",) in _unique_column_sets(engine, "farm_tasks")
    assert ("run_id",) in _unique_column_sets(engine, "agent_runs")
