"""Farm Agent 图执行、SSE 合并与运行审计服务。"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Callable, TypeVar

from loguru import logger

from app.agents import build_farm_agent_graph
from app.config import settings
from app.agents.stream_sink import get_sink, reset_sink, set_sink
from app.core.sqlite import AgentRun, sqlite_manager
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.runtime.agent_harness import HarnessUsageStats, get_agent_harness
from app.runtime.farm_run_context import (
    FarmRunContext,
    bind_farm_run_context,
)
from app.schemas.farm_agent import FarmInspectionRequest
from app.exceptions import AppException
from app.services import (
    farm_risk_service,
    farm_snapshot_service,
    farm_task_service,
)

_T = TypeVar("_T")
_graph = None
_agent_semaphore = asyncio.Semaphore(get_agent_harness().agent_max_concurrency())


def _select_inspection_weather_provider(
    request: FarmInspectionRequest,
) -> farm_risk_service.WeatherProvider:
    if request.demo_scenario is None:
        return farm_risk_service.WeatherServiceProvider()
    if not settings.competition_demo_enabled:
        raise AppException(
            status_code=403,
            code="COMPETITION_DEMO_DISABLED",
            message="比赛演示场景未启用",
        )
    return farm_risk_service.CompetitionDemoRainstormWeatherProvider()


def _get_graph():
    global _graph
    if _graph is None:
        _graph = build_farm_agent_graph()
    return _graph


def _event(run_id: str, event_type: str, stage: str, message: str = "", **data: Any) -> dict[str, Any]:
    return {
        "event_id": uuid.uuid4().hex,
        "type": event_type,
        "run_id": run_id,
        "stage": stage,
        "message": message,
        "data": data,
        "ts": datetime.now(timezone.utc).isoformat(),
    }


async def _offload(function: Callable[..., _T], /, **kwargs: Any) -> _T:
    return await asyncio.to_thread(function, **kwargs)


async def _add_history_record(**kwargs: Any) -> str | None:
    # history_service 的知识库依赖较重，运行结束且确有报告时再加载。
    from app.services import history_service

    return await history_service.add_record(**kwargs)


def _persist_run_start(
    *,
    run_id: str,
    user_id: int,
    farm_id: int,
    run_type: str,
    query: str,
    context_snapshot: dict[str, Any],
) -> None:
    with sqlite_manager.session() as session:
        run = AgentRun(
            run_id=run_id,
            user_id=user_id,
            farm_id=farm_id,
            run_type=run_type,
            session_id=run_id,
            query=query[:2000],
            status="running",
        )
        run.set_context_snapshot(context_snapshot)
        session.add(run)


def _persist_run_finish(
    *,
    run_id: str,
    status: str,
    selected_skill: str,
    transitions: list[dict[str, Any]],
    outcome: dict[str, Any],
    report: str,
    total_steps: int,
    tool_calls: int,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    total_ms: int,
) -> None:
    with sqlite_manager.session() as session:
        run = session.query(AgentRun).filter(AgentRun.run_id == run_id).one()
        run.status = status
        run.selected_skill = selected_skill[:128] or None
        run.set_transitions(transitions)
        run.set_outcome(outcome)
        run.report_preview = report[:500] or None
        run.total_steps = total_steps
        run.total_tool_calls = tool_calls
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.total_tokens = total_tokens
        run.total_ms = total_ms
        run.model_used = get_agent_harness().executor_model() or ""


def _load_proposal_ids(run_id: str) -> list[str]:
    with sqlite_manager.session() as session:
        rows = (
            session.query(FarmActionProposal.proposal_id)
            .filter(FarmActionProposal.run_id == run_id)
            .order_by(FarmActionProposal.id.asc())
            .all()
        )
    return [proposal_id for proposal_id, in rows]


def _load_task_verdict(task_id: str) -> dict[str, Any]:
    with sqlite_manager.session() as session:
        task = session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
        return task.agent_verdict


async def _convert_node_event(
    run_id: str,
    node_name: str,
    node_output: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    if node_name == "skill_router":
        skill = node_output.get("selected_skill", "")
        yield _event(
            run_id,
            "skill_selected",
            "skill_selected",
            f"已进入 {skill} 工作流",
            skill=skill,
            reason=node_output.get("skill_reason", ""),
        )
    elif node_name == "planner":
        plan = node_output.get("plan", [])
        yield _event(run_id, "plan", "plan_created", "已生成执行计划", plan=plan)
    elif node_name == "executor":
        past_steps = node_output.get("past_steps", [])
        if past_steps:
            step, result = past_steps[-1]
            yield _event(
                run_id,
                "step_complete",
                "step_executed",
                "执行步骤已完成",
                step=step,
                result_preview=str(result)[:200],
                iteration=node_output.get("iteration", 0),
            )
    elif node_name == "replanner":
        response = node_output.get("response", "")
        if response:
            yield _event(run_id, "report", "report_generated", "Farm Agent 报告已生成", report=response)
        elif node_output.get("plan"):
            yield _event(run_id, "replan", "plan_updated", "执行计划已调整", plan=node_output["plan"])
    elif node_name == "fork_skill" and node_output.get("response"):
        yield _event(run_id, "report", "report_generated", "Farm Agent 报告已生成", report=node_output["response"])


async def _stream_run(
    *,
    context: FarmRunContext,
    query: str,
    business_context: dict[str, Any],
) -> AsyncIterator[dict[str, Any]]:
    harness = get_agent_harness()
    run_id = context.run_id
    run_started = time.perf_counter()
    selected_skill = {
        "inspection": "farm_inspection",
        "task_verification": "farm_task_verification",
    }[context.run_type]
    final_report = ""
    proposal_ids: list[str] = []
    transitions: list[dict[str, Any]] = []
    input_tokens = output_tokens = total_tokens = 0
    tool_calls = total_steps = 0
    runner_task: asyncio.Task[None] | None = None
    sink_token = None
    status = "failed"
    outcome: dict[str, Any] = {}

    await _offload(
        _persist_run_start,
        run_id=run_id,
        user_id=context.user_id,
        farm_id=context.farm_id,
        run_type=context.run_type,
        query=query,
        context_snapshot=business_context,
    )
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=2048)
    sentinel: dict[str, Any] = {"__done__": True}

    async def run_graph() -> None:
        state = {
            "input": query,
            "user_id": context.user_id,
            "farm_id": context.farm_id,
            "run_id": run_id,
            "run_type": context.run_type,
            "business_context": business_context,
            "proposal_ids": [],
            "selected_skill": selected_skill,
        }
        try:
            async for graph_event in _get_graph().astream(
                state,
                config={"recursion_limit": harness.graph_recursion_limit()},
            ):
                await queue.put({"__node__": graph_event})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await queue.put({"__error__": exc})
        finally:
            await queue.put(sentinel)

    try:
        sink_token = set_sink(queue)
        yield _event(run_id, "start", "run_started", "Farm Agent 已启动", run_type=context.run_type)
        yield _event(
            run_id,
            "context_loaded",
            "context_loaded",
            "业务上下文已加载",
            farm_id=context.farm_id,
            inspection=business_context.get("inspection", {}),
        )

        with bind_farm_run_context(context):
            runner_task = asyncio.create_task(run_graph())
            graph_failed = False
            while True:
                item = await queue.get()
                if item is sentinel:
                    # graph runner 自身被取消时不能把 sentinel 误判为成功结束。
                    if runner_task is not None:
                        await runner_task
                    break
                if "__error__" in item:
                    graph_failed = True
                    exc = item["__error__"]
                    logger.error("Farm Agent graph 执行失败: {}", type(exc).__name__)
                    outcome = {"error_type": type(exc).__name__, "proposal_ids": proposal_ids}
                    yield _event(run_id, "error", "run_failed", "Farm Agent 执行失败", error_type=type(exc).__name__)
                    continue
                if "__node__" in item:
                    for node_name, raw_output in item["__node__"].items():
                        node_output = raw_output or {}
                        selected_skill = node_output.get("selected_skill", selected_skill)
                        new_proposal_ids = [
                            proposal_id
                            for proposal_id in node_output.get("proposal_ids", [])
                            if proposal_id not in proposal_ids
                        ]
                        proposal_ids.extend(new_proposal_ids)
                        for proposal_id in new_proposal_ids:
                            yield _event(
                                run_id,
                                "proposal_created",
                                "proposal_created",
                                "行动提案已生成，等待人工审批",
                                proposal_id=proposal_id,
                            )
                        node_transitions = node_output.get("transition_history", [])
                        transitions.extend(node_transitions)
                        if node_name == "executor" and node_output.get("past_steps"):
                            total_steps += 1
                        async for event in _convert_node_event(run_id, node_name, node_output):
                            if event["type"] == "report":
                                final_report = event["data"].get("report", "")
                            yield event
                    continue

                event_type = item.get("type", "step_token")
                payload = {key: value for key, value in item.items() if key != "type"}
                if event_type == "usage":
                    input_tokens += int(payload.get("input_tokens") or 0)
                    output_tokens += int(payload.get("output_tokens") or 0)
                    total_tokens += int(payload.get("total_tokens") or 0)
                elif event_type == "tool_call":
                    tool_calls += 1
                    payload["duration_ms"] = int(payload.pop("elapsed_ms", 0) or 0)
                yield _event(run_id, event_type, event_type, **payload)

            if not graph_failed:
                if context.run_type == "inspection" and not proposal_ids:
                    proposal_ids = await _offload(_load_proposal_ids, run_id=run_id)
                outcome = {"proposal_ids": proposal_ids}
                if context.task_id:
                    outcome["task_id"] = context.task_id
                    evidence = await _offload(
                        farm_task_service.get_task_evidence,
                        user_id=context.user_id,
                        task_id=context.task_id,
                    )
                    outcome["task_status"] = evidence.status
                    outcome["task_verdict"] = await _offload(
                        _load_task_verdict,
                        task_id=context.task_id,
                    )

                stats = HarnessUsageStats(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens or input_tokens + output_tokens,
                    total_ms=int((time.perf_counter() - run_started) * 1000),
                    tool_calls=tool_calls,
                    tool_ms=0,
                    run_kind=f"farm_agent_{context.run_type}",
                )
                budget_event = harness.build_budget_event(harness.evaluate_budget(stats))
                if budget_event:
                    yield _event(run_id, budget_event["type"], budget_event["stage"], budget_event.get("detail", ""), **(budget_event.get("data") or {}))
                if final_report:
                    await _add_history_record(
                        question=query,
                        answer=final_report,
                        source="farm_agent",
                        session_id=run_id,
                        skill=selected_skill,
                    )
                status = "completed"
                yield _event(run_id, "complete", "run_completed", "Farm Agent 流程完成", outcome=outcome)
    except (asyncio.CancelledError, GeneratorExit):
        if status != "completed":
            status = "cancelled"
            outcome = {"cancelled": True, "proposal_ids": proposal_ids}
        if runner_task is not None and not runner_task.done():
            runner_task.cancel()
        raise
    except Exception as exc:
        status = "failed"
        outcome = {
            "error_type": type(exc).__name__,
            "proposal_ids": proposal_ids,
        }
        logger.error("Farm Agent 后处理失败: {}", type(exc).__name__)
        yield _event(
            run_id,
            "error",
            "run_failed",
            "Farm Agent 执行失败",
            error_type=type(exc).__name__,
        )
    finally:
        if runner_task is not None and not runner_task.done():
            runner_task.cancel()
            try:
                await runner_task
            except (asyncio.CancelledError, Exception):
                pass
        if sink_token is not None:
            reset_sink(sink_token)
        elapsed_ms = int((time.perf_counter() - run_started) * 1000)
        await _offload(
            _persist_run_finish,
            run_id=run_id,
            status=status,
            selected_skill=selected_skill,
            transitions=transitions,
            outcome=outcome,
            report=final_report,
            total_steps=total_steps,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens or input_tokens + output_tokens,
            total_ms=elapsed_ms,
        )


async def stream_inspection(
    *,
    user_id: int,
    request: FarmInspectionRequest,
) -> AsyncIterator[dict[str, Any]]:
    """校验农场所有权并流式执行综合巡检。"""

    if _agent_semaphore.locked():
        yield _event("", "error", "concurrency_limited", "当前 Farm Agent 任务较多，请稍后重试")
        return
    async with _agent_semaphore:
        snapshot = await _offload(
            farm_snapshot_service.get_snapshot,
            farm_id=request.farm_id,
            user_id=user_id,
        )
        inspection = await farm_risk_service.inspect_farm(
            snapshot,
            weather_provider=_select_inspection_weather_provider(request),
        )
        business_context = {
            "snapshot": snapshot.model_dump(mode="json"),
            "inspection": inspection.model_dump(mode="json"),
            "objective": request.objective,
        }
        run_id = uuid.uuid4().hex
        context = FarmRunContext(
            user_id=user_id,
            farm_id=request.farm_id,
            run_id=run_id,
            run_type="inspection",
            demo_scenario=request.demo_scenario,
        )
        async for event in _stream_run(
            context=context,
            query=request.objective,
            business_context=business_context,
        ):
            yield event


async def stream_task_verification(
    *,
    user_id: int,
    task_id: str,
) -> AsyncIterator[dict[str, Any]]:
    """校验任务所有权并流式生成复核草稿，永不直接完成任务。"""

    if _agent_semaphore.locked():
        yield _event("", "error", "concurrency_limited", "当前 Farm Agent 任务较多，请稍后重试")
        return
    async with _agent_semaphore:
        evidence = await _offload(
            farm_task_service.get_task_evidence,
            user_id=user_id,
            task_id=task_id,
        )
        run_id = uuid.uuid4().hex
        context = FarmRunContext(
            user_id=user_id,
            farm_id=evidence.farm_id,
            run_id=run_id,
            run_type="task_verification",
            task_id=task_id,
        )
        async for event in _stream_run(
            context=context,
            query=f"复核农场任务 {task_id}",
            business_context={"task_evidence": evidence.model_dump(mode="json")},
        ):
            yield event


__all__ = [
    "get_sink",
    "stream_inspection",
    "stream_task_verification",
]
