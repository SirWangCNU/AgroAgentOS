import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.diagnosis import DiagnosisRecordRequest, RecordResponse
from app.schemas.farm_agent import (
    FarmEvidence,
    ProposalDraft,
    ProposalStatus,
    ProposedAction,
)


@pytest.fixture
def measured_evidence() -> FarmEvidence:
    return FarmEvidence(
        source_type="weather_forecast",
        source_id="demo-rainstorm-24h",
        summary="未来 24 小时累计降雨 82mm",
        observed_at="2026-07-18T08:00:00+08:00",
        fact_kind="measured",
        payload={"rainfall_mm": 82.0, "threshold_mm": 50.0},
    )


@pytest.fixture
def proposed_action() -> ProposedAction:
    return ProposedAction(
        action_key="drainage-check-a1",
        title="检查 A1 地块排水沟",
        task_type="drainage",
        instructions="清理堵塞点并提交轨迹或文字记录",
        priority="urgent",
        field_id=1,
        assignee_name="现场作业员",
        due_at="2026-07-18T18:00:00+08:00",
        acceptance_criteria=["排水沟无明显堵塞", "提交执行说明"],
    )


def test_proposal_draft_accepts_measured_evidence_and_structured_action(
    measured_evidence: FarmEvidence,
    proposed_action: ProposedAction,
) -> None:
    draft = ProposalDraft(
        risk_key="rainstorm-drainage",
        title="暴雨前检查排水系统",
        severity="high",
        summary="强降雨可能造成田间积水",
        confidence=0.92,
        evidence=[measured_evidence],
        actions=[proposed_action],
    )

    assert draft.evidence[0].payload["rainfall_mm"] == 82.0
    assert draft.actions[0].priority == "urgent"


@pytest.mark.parametrize("severity", ["", "warning", "extreme"])
def test_proposal_draft_rejects_invalid_severity(
    severity: str,
    measured_evidence: FarmEvidence,
    proposed_action: ProposedAction,
) -> None:
    with pytest.raises(ValidationError):
        ProposalDraft(
            risk_key="rainstorm-drainage",
            title="暴雨前检查排水系统",
            severity=severity,
            summary="强降雨可能造成田间积水",
            confidence=0.5,
            evidence=[measured_evidence],
            actions=[proposed_action],
        )


def test_proposed_action_rejects_invalid_priority() -> None:
    with pytest.raises(ValidationError):
        ProposedAction(
            action_key="drainage-check-a1",
            title="检查 A1 地块排水沟",
            task_type="drainage",
            instructions="清理堵塞点",
            priority="critical",
            acceptance_criteria=["排水沟无明显堵塞"],
        )


def test_proposal_status_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(ProposalStatus).validate_python("archived")


def test_proposal_draft_rejects_empty_evidence(
    proposed_action: ProposedAction,
) -> None:
    with pytest.raises(ValidationError):
        ProposalDraft(
            risk_key="rainstorm-drainage",
            title="暴雨前检查排水系统",
            severity="high",
            summary="强降雨可能造成田间积水",
            confidence=0.5,
            evidence=[],
            actions=[proposed_action],
        )


def test_high_confidence_proposal_requires_non_inference_evidence(
    proposed_action: ProposedAction,
) -> None:
    inferred_evidence = FarmEvidence(
        source_type="agent_reasoning",
        source_id="inference-001",
        summary="根据季节推测可能有积水",
        observed_at="2026-07-18T08:00:00+08:00",
        fact_kind="inference",
        payload={},
    )

    with pytest.raises(ValidationError):
        ProposalDraft(
            risk_key="rainstorm-drainage",
            title="暴雨前检查排水系统",
            severity="high",
            summary="可能存在田间积水",
            confidence=0.9,
            evidence=[inferred_evidence],
            actions=[proposed_action],
        )


def test_diagnosis_write_source_excludes_legacy_aiops_value() -> None:
    assert DiagnosisRecordRequest(question="巡检农场").source == "farm_agent"
    assert DiagnosisRecordRequest(question="对话", source="chat").source == "chat"
    assert DiagnosisRecordRequest(question="监测", source="monitoring").source == "monitoring"

    with pytest.raises(ValidationError):
        DiagnosisRecordRequest(question="旧运维写入", source="aiops")

    historical_record = RecordResponse(
        id="record-aiops-001",
        question="历史运维记录",
        source="aiops",
    )
    assert historical_record.source == "aiops"
