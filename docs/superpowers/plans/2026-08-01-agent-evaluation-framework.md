# AgroAgentOS Agent Evaluation Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible evaluation framework that measures AgroAgentOS routing, retrieval, end-to-end task completion, answer quality, fault recovery, latency, and token cost, then produces evidence suitable for regression gates and resume claims.

**Architecture:** Add a standalone `evals/` package with versioned JSONL datasets, pure metric functions, adapters around the existing Router/LangGraph/RAG entry points, and one CLI orchestrator. Evaluation runs are divided into deterministic offline tests, local integration tests, and explicitly enabled online benchmarks; all tiers write the same case-result schema and are aggregated into JSON plus Markdown reports.

**Tech Stack:** Python 3.11, Pydantic 2, pytest, LangGraph, FastAPI service modules, Milvus, DashScope/DeepSeek-compatible LLMs, standard-library `argparse`, `json`, `statistics`, and `time`.

## Global Constraints

- Never report a metric unless its dataset version, git commit, model name, configuration snapshot, run count, and timestamp are recorded with it.
- Treat current comments such as the MRR values in `app/utils/splitter.py` as unverified until reproduced by this framework.
- Keep deterministic unit tests independent of Milvus, Redis, MCP servers, and paid LLM APIs.
- Require `--online` for any command that can call a paid model or an external service.
- Use a fixed temperature of `0` for evaluation-capable model configurations and run nondeterministic online cases three times.
- Do not use the model under test as the sole judge of its own answer; final answer quality requires two human ratings or an independent judge plus human audit.
- Store datasets and aggregate baselines in git; store raw model answers under `output/evals/`, which remains untracked.
- Redact API keys, authorization headers, Redis URLs containing credentials, and user data from every result artifact.
- Do not change production Agent behavior merely to improve the benchmark; behavior changes and dataset changes must be reviewed separately.
- Proposed release gates are targets, not existing results: Router exact accuracy >= 0.90, out-of-scope F1 >= 0.95, RAG Recall@20 >= 0.90, NDCG@3 >= 0.80, end-to-end task success >= 0.85, bounded termination = 1.00, graceful degradation >= 0.95, and forbidden-tool-call rate = 0.

## Evaluation Matrix

| Suite | Versioned sample count | Primary metrics | Execution tier |
| --- | ---: | --- | --- |
| Router | 300 | exact accuracy, Macro-F1, OOS F1, collaboration micro-F1, three-run stability | offline mock + online |
| Retrieval | 100 | Recall@20, Precision@3, MRR@3, NDCG@3, citation coverage | local integration + online rerank |
| End-to-end Agent | 100 | task success, required-tool recall, tool precision, forbidden-call rate, completion rate, steps, reroutes | offline mock + online |
| Answer quality | 50 sampled from end-to-end | correctness, groundedness, actionability, completeness, safety, inter-rater agreement | human review |
| Reliability | 50 | graceful-degradation rate, unhandled-exception rate, bounded termination | deterministic fault injection |
| Performance | 30 representative tasks x 3 runs | TTFT P50/P95, total latency P50/P95, token/request, tool time, parallel speedup | online and controlled local |

---

### Task 1: Define Evaluation Schemas and Pure Metrics

**Files:**
- Create: `evals/__init__.py`
- Create: `evals/schemas.py`
- Create: `evals/metrics.py`
- Create: `tests/evals/__init__.py`
- Create: `tests/evals/test_metrics.py`
- Create: `tests/evals/test_schemas.py`

**Interfaces:**
- Produces `RouterCase`, `RetrievalCase`, `AgentCase`, `FaultCase`, `CaseResult`, and `RunMetadata` Pydantic models.
- Produces `classification_metrics()`, `set_metrics()`, `recall_at_k()`, `precision_at_k()`, `mrr_at_k()`, `ndcg_at_k()`, `percentile()`, `bootstrap_delta_ci()`, and `quadratic_weighted_kappa()`.
- All later evaluators consume these types and metric functions.

- [ ] **Step 1: Write failing schema and metric tests**

```python
from evals.metrics import mrr_at_k, ndcg_at_k, recall_at_k, set_metrics
from evals.schemas import RouterCase


def test_router_case_rejects_unknown_skill():
    try:
        RouterCase(
            id="router-001",
            query="水稻叶片发黄怎么办",
            expected_skill="unknown",
            expected_collaboration=[],
            is_agriculture=True,
            tags=["single-skill"],
        )
    except ValueError:
        return
    raise AssertionError("unknown skills must be rejected")


def test_rank_metrics_use_canonical_document_ids():
    ranked = ["planting/rice.md#施肥", "soil/fertilizer.md#氮肥", "weather/rain.md#暴雨"]
    relevant = {"soil/fertilizer.md#氮肥", "planting/rice.md#施肥"}
    assert recall_at_k(ranked, relevant, 2) == 1.0
    assert mrr_at_k(ranked, relevant, 3) == 1.0
    assert 0.0 <= ndcg_at_k(ranked, relevant, 3) <= 1.0


def test_set_metrics_penalize_extra_collaboration_skills():
    values = set_metrics({"weather_advice"}, {"weather_advice", "pest_diagnosis"})
    assert values == {"precision": 0.5, "recall": 1.0, "f1": 2 / 3}
```

- [ ] **Step 2: Run tests and verify missing-module failures**

Run: `pytest tests/evals/test_metrics.py tests/evals/test_schemas.py -q`

Expected: collection fails because `evals.schemas` and `evals.metrics` do not exist.

- [ ] **Step 3: Implement the shared schemas**

Use these exact fields in `evals/schemas.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


SKILL_NAMES = {
    "agriculture_qa",
    "crop_advisory",
    "knowledge_retrieval",
    "marketing_generator",
    "market_intelligence",
    "pest_diagnosis",
    "weather_advice",
}


class RouterCase(BaseModel):
    id: str
    query: str
    expected_skill: str
    expected_collaboration: list[str] = Field(default_factory=list)
    is_agriculture: bool
    tags: list[str] = Field(default_factory=list)

    @field_validator("expected_skill")
    @classmethod
    def validate_skill(cls, value: str) -> str:
        if value not in SKILL_NAMES:
            raise ValueError(f"unknown skill: {value}")
        return value


class RetrievalCase(BaseModel):
    id: str
    query: str
    relevant_doc_ids: list[str] = Field(min_length=1)
    category: Literal["planting", "pest_control", "soil", "weather"]
    tags: list[str] = Field(default_factory=list)


class AgentCase(BaseModel):
    id: str
    query: str
    required_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    required_answer_terms: list[str] = Field(default_factory=list)
    expected_skill: str
    max_steps: int = Field(default=5, ge=1, le=10)
    tags: list[str] = Field(default_factory=list)


class FaultCase(BaseModel):
    id: str
    query: str
    fault: Literal[
        "router_llm_error", "planner_llm_error", "tool_error", "milvus_error",
        "reranker_timeout", "mcp_unavailable", "redis_unavailable"
    ]
    expected_reason: str | None = None
    requires_response: bool = True
    max_steps: int = 5


class RunMetadata(BaseModel):
    suite: str
    dataset_version: str
    git_commit: str
    started_at: datetime
    model: str
    config: dict[str, Any]
    online: bool
    repeat: int


class CaseResult(BaseModel):
    case_id: str
    passed: bool
    latency_ms: int
    metrics: dict[str, float] = Field(default_factory=dict)
    actual: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Implement pure metric functions with empty-input behavior**

`recall_at_k([], relevant, k)` and `precision_at_k([], relevant, k)` return `0.0`; dataset validation prevents an empty relevant set. `percentile(values, 95)` sorts values and uses nearest-rank indexing. `bootstrap_delta_ci()` uses `random.Random(seed)` so report deltas are reproducible. `quadratic_weighted_kappa()` accepts two equal-length integer rating lists in the closed range 1-5 and rejects empty or mismatched inputs.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/evals/test_metrics.py tests/evals/test_schemas.py -q`

Expected: PASS.

Commit: `git commit -m "test: add agent evaluation schemas and metrics"`

---

### Task 2: Create Versioned Evaluation Datasets and Validation

**Files:**
- Create: `evals/datasets/router_v1.jsonl`
- Create: `evals/datasets/retrieval_v1.jsonl`
- Create: `evals/datasets/agent_v1.jsonl`
- Create: `evals/datasets/fault_v1.jsonl`
- Create: `evals/datasets/manifest.json`
- Create: `evals/dataset_io.py`
- Create: `tests/evals/test_datasets.py`

**Interfaces:**
- Produces `load_jsonl(path: Path, model_type: type[BaseModel]) -> list[BaseModel]`.
- Produces `validate_manifest(root: Path) -> dict[str, int]`.
- Dataset document IDs use `source#chapter`, matching `Document.metadata["source"]` and `Document.metadata["chapter"]`.

- [ ] **Step 1: Write failing dataset quota tests**

```python
from pathlib import Path

from evals.dataset_io import load_jsonl, validate_manifest
from evals.schemas import RouterCase


DATASET_ROOT = Path("evals/datasets")


def test_router_v1_has_balanced_300_cases():
    cases = load_jsonl(DATASET_ROOT / "router_v1.jsonl", RouterCase)
    assert len(cases) == 300
    assert sum("single-skill" in case.tags for case in cases) == 210
    assert sum("collaboration" in case.tags for case in cases) == 50
    assert sum("out-of-scope" in case.tags for case in cases) == 40


def test_all_dataset_ids_are_unique_and_manifest_hashes_match():
    counts = validate_manifest(DATASET_ROOT)
    assert counts == {"router": 300, "retrieval": 100, "agent": 100, "fault": 50}
```

- [ ] **Step 2: Run the tests and verify missing-data failures**

Run: `pytest tests/evals/test_datasets.py -q`

Expected: FAIL because the dataset files do not exist.

- [ ] **Step 3: Implement JSONL loading and manifest validation**

Each JSONL line is UTF-8 JSON. Reject blank IDs, duplicate IDs, malformed lines, counts that disagree with the manifest, and SHA-256 mismatches. The manifest contains `version`, `created_at`, per-file `count`, `sha256`, and a one-sentence annotation policy.

- [ ] **Step 4: Author the Router dataset using fixed quotas**

Create exactly 210 single-Skill cases: 30 per Skill. Add exactly 50 collaboration cases distributed across weather+pest, weather+crop, market+marketing, and knowledge+crop combinations. Add exactly 40 out-of-scope cases spanning programming, entertainment, finance, general chat, and adversarial agriculture-keyword stuffing.

Representative records:

```json
{"id":"router-001","query":"水稻分蘖期应该怎样追肥","expected_skill":"crop_advisory","expected_collaboration":[],"is_agriculture":true,"tags":["single-skill","crop"]}
{"id":"router-211","query":"明天有大风，还适合给苹果树喷药吗","expected_skill":"weather_advice","expected_collaboration":["pest_diagnosis"],"is_agriculture":true,"tags":["collaboration","weather+pest"]}
{"id":"router-261","query":"帮我写一个 React 登录页面","expected_skill":"agriculture_qa","expected_collaboration":[],"is_agriculture":false,"tags":["out-of-scope","programming"]}
```

- [ ] **Step 5: Author the Retrieval, Agent, and Fault datasets**

Retrieval: exactly 25 questions for each of the four knowledge categories. Every record must be independently checked against the current 164 chunks and contain at least one canonical relevant document ID.

Agent: exactly 100 cases distributed as 30 planting/pest/weather, 20 market, 20 cross-Skill, 15 farm-context/memory, and 15 safety/out-of-scope tasks.

Fault: exactly 50 cases distributed as 8 Router failures, 7 Planner failures, 8 tool failures, 8 Milvus failures, 7 Reranker timeouts, 6 MCP outages, and 6 Redis outages.

- [ ] **Step 6: Review labels independently and freeze v1**

Have a second reviewer inspect all 550 labels without seeing model predictions. Resolve disagreements before generating `manifest.json`; never edit a frozen v1 file in place—create `*_v2.jsonl` instead.

- [ ] **Step 7: Run tests and commit**

Run: `pytest tests/evals/test_datasets.py -q`

Expected: PASS with exact dataset counts and hashes.

Commit: `git commit -m "test: add versioned agriculture evaluation datasets"`

---

### Task 3: Implement Skill Router Evaluation

**Files:**
- Create: `evals/adapters.py`
- Create: `evals/evaluators/__init__.py`
- Create: `evals/evaluators/router.py`
- Create: `tests/evals/test_router_evaluator.py`

**Interfaces:**
- Produces `async run_router_case(case: RouterCase) -> CaseResult`.
- Produces `aggregate_router(results: list[CaseResult]) -> dict[str, float]`.
- Wraps `app.agents.skill_router.skill_router_node()` without modifying production routing logic.

- [ ] **Step 1: Write a failing evaluator test with a patched Router response**

```python
import asyncio
from unittest.mock import AsyncMock, patch

from evals.evaluators.router import run_router_case
from evals.schemas import RouterCase


def test_router_case_scores_main_and_collaboration_skills():
    case = RouterCase(
        id="router-test",
        query="明天适合给水稻喷药吗",
        expected_skill="weather_advice",
        expected_collaboration=["pest_diagnosis"],
        is_agriculture=True,
        tags=["collaboration"],
    )
    predicted = {
        "selected_skill": "weather_advice",
        "collaboration_skills": ["pest_diagnosis"],
        "response": "",
        "transition_history": [],
    }
    with patch("evals.adapters.skill_router_node", new=AsyncMock(return_value=predicted)):
        result = asyncio.run(run_router_case(case))
    assert result.passed
    assert result.metrics["main_exact"] == 1.0
    assert result.metrics["collaboration_f1"] == 1.0
```

- [ ] **Step 2: Implement the production adapter and case scoring**

Call `skill_router_node({"input": case.query})`, measure wall time with `time.perf_counter()`, and store selected Skill, collaboration Skills, response presence, transition reason, and confidence when available. An out-of-scope case passes only when the Router produces a non-empty response and the transition reason is `router_out_of_scope`.

- [ ] **Step 3: Aggregate classification and stability metrics**

Aggregate exact accuracy, per-Skill precision/recall/F1, Macro-F1, OOS precision/recall/F1, collaboration micro precision/recall/F1, fallback rate, mean latency, and three-run stability. Stability is the fraction of cases whose selected Skill and collaboration set are identical across all three online repeats.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/evals/test_router_evaluator.py -q`

Expected: PASS without calling an external model.

Commit: `git commit -m "feat: add skill router evaluation"`

---

### Task 4: Implement Three-Variant RAG Evaluation

**Files:**
- Create: `evals/evaluators/retrieval.py`
- Create: `tests/evals/test_retrieval_evaluator.py`
- Modify: `evals/adapters.py`

**Interfaces:**
- Produces `canonical_doc_id(document: Document) -> str`.
- Produces `async run_retrieval_case(case: RetrievalCase, variant: str) -> CaseResult`.
- Supported variants are `vector`, `hybrid`, and `hybrid_rerank`.

- [ ] **Step 1: Write failing tests for canonical IDs and ranking metrics**

```python
import asyncio
from unittest.mock import AsyncMock, patch

from langchain_core.documents import Document

from evals.evaluators.retrieval import canonical_doc_id, run_retrieval_case
from evals.schemas import RetrievalCase


def test_canonical_doc_id_uses_source_and_chapter():
    doc = Document(page_content="内容", metadata={"source": "soil/肥料.md", "chapter": "氮肥"})
    assert canonical_doc_id(doc) == "soil/肥料.md#氮肥"


def test_full_pipeline_scores_gold_document_at_rank_two():
    case = RetrievalCase(
        id="rag-test",
        query="水稻缺氮怎么办",
        relevant_doc_ids=["soil/肥料.md#氮肥"],
        category="soil",
    )
    docs = [
        Document(page_content="a", metadata={"source": "soil/检测.md", "chapter": "采样"}),
        Document(page_content="b", metadata={"source": "soil/肥料.md", "chapter": "氮肥"}),
    ]
    with patch("evals.adapters.advanced_search", new=AsyncMock(return_value=docs)):
        result = asyncio.run(run_retrieval_case(case, "hybrid_rerank"))
    assert result.metrics["mrr@3"] == 0.5
```

- [ ] **Step 2: Map variants to existing retrieval flags**

Use the existing `app.core.vector_store.advanced_search()` entry point:

```python
VARIANTS = {
    "vector": {"k": 20, "use_hybrid": False, "use_rerank": False},
    "hybrid": {"k": 20, "use_hybrid": True, "use_rerank": False},
    "hybrid_rerank": {"k": 3, "use_hybrid": True, "use_rerank": True},
}
```

Record Recall@20 for `vector` and `hybrid`; record Precision@3, MRR@3, and NDCG@3 for `hybrid_rerank`. Persist ranked canonical IDs, source, chapter, and score for audit.

- [ ] **Step 3: Report paired improvements, not unrelated averages**

Join variants by `case_id` and calculate paired deltas for Hybrid minus Vector and Hybrid+Rerank minus Hybrid. Report a seeded 95% bootstrap confidence interval and the fraction of cases improved, tied, and regressed.

- [ ] **Step 4: Add citation coverage**

For the final Top-3, citation coverage is `1.0` when at least one returned citation is a gold document ID. Keep it separate from answer citation correctness, which belongs to Task 5.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/evals/test_retrieval_evaluator.py -q`

Expected: PASS with no Milvus connection because `advanced_search` is patched.

Commit: `git commit -m "feat: add comparative RAG evaluation"`

---

### Task 5: Implement End-to-End Agent and Human Answer Evaluation

**Files:**
- Create: `evals/evaluators/agent.py`
- Create: `evals/answer_review.py`
- Create: `evals/rubrics/answer_quality_v1.md`
- Create: `tests/evals/test_agent_evaluator.py`
- Modify: `evals/adapters.py`

**Interfaces:**
- Produces `async run_agent_case(case: AgentCase) -> CaseResult`.
- Produces `export_review_sheet(results, path) -> None` and `import_review_sheet(path) -> dict[str, float]`.
- Invokes `build_agriculture_graph().ainvoke(initial_state, config={"recursion_limit": 32})`.

- [ ] **Step 1: Write a failing trace-scoring test**

```python
from evals.evaluators.agent import score_agent_result
from evals.schemas import AgentCase


def test_agent_result_requires_completion_and_required_tool():
    case = AgentCase(
        id="agent-test",
        query="查询北京天气后给水稻灌溉建议",
        required_tools=["get_weather"],
        forbidden_tools=["mcp_execute_tool"],
        required_answer_terms=["灌溉"],
        expected_skill="weather_advice",
    )
    state = {
        "selected_skill": "weather_advice",
        "response": "根据降雨情况调整灌溉。",
        "iteration": 2,
        "reroute_count": 0,
        "transition_history": [
            {"node": "executor", "reason": "executor_ok", "tool_calls": [{"name": "get_weather"}]},
            {"node": "replanner", "reason": "replanner_finished_ok"},
        ],
    }
    result = score_agent_result(case, state, latency_ms=100)
    assert result.passed
    assert result.metrics["required_tool_recall"] == 1.0
    assert result.metrics["bounded_termination"] == 1.0
```

- [ ] **Step 2: Build the exact initial state and capture traces**

```python
initial_state = {
    "input": case.query,
    "past_steps": [],
    "plan": [],
    "response": "",
    "iteration": 0,
    "reroute_count": 0,
    "tried_skills": [],
    "pending_reroute": False,
    "transition_history": [],
    "permission_mode": "normal",
    "inside_fork": False,
}
```

Extract tool names from `transition_history[*].tool_calls`, token counts from `tokens_used`, selected Skill, iterations, reroutes, terminal reason, and final response. Mark bounded termination false if the graph raises `GraphRecursionError`, exceeds the case limit, or produces neither a response nor an accepted out-of-scope result.

- [ ] **Step 3: Define deterministic task success**

A case passes automatic checks when the selected Skill matches, every required tool appears, no forbidden tool appears, every required answer term appears, a terminal response exists, and the workflow stays within `max_steps`. Report each component separately so failures remain diagnosable.

- [ ] **Step 4: Define the human answer rubric**

The Markdown rubric scores correctness, groundedness, actionability, completeness, and safety from 1 to 5. Review 50 stratified end-to-end cases with two independent reviewers; hide model/config labels during review. A quality pass requires correctness >= 4, groundedness >= 4, actionability >= 4, safety = 5, and no fabricated citation. Report means, pass rate, and quadratic weighted kappa; adjudicate cases with a score gap greater than one.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/evals/test_agent_evaluator.py -q`

Expected: PASS using a synthetic final state.

Commit: `git commit -m "feat: evaluate end-to-end agent execution"`

---

### Task 6: Implement Deterministic Fault-Injection Evaluation

**Files:**
- Create: `evals/evaluators/reliability.py`
- Create: `tests/evals/test_reliability_evaluator.py`

**Interfaces:**
- Produces `async run_fault_case(case: FaultCase) -> CaseResult`.
- Produces `FAULT_PATCHES`, a mapping from dataset fault name to a scoped `unittest.mock.patch` factory.

- [ ] **Step 1: Write failing tests for Milvus and tool failures**

```python
import asyncio

from evals.evaluators.reliability import run_fault_case
from evals.schemas import FaultCase


def test_milvus_failure_is_reported_as_graceful_degradation():
    case = FaultCase(
        id="fault-test",
        query="水稻叶片发黄怎么办",
        fault="milvus_error",
        requires_response=True,
        max_steps=5,
    )
    result = asyncio.run(run_fault_case(case))
    assert result.metrics["unhandled_exception"] == 0.0
    assert result.metrics["graceful_degradation"] == 1.0
```

- [ ] **Step 2: Patch failures at system boundaries**

Patch Router/Planner structured LLM calls, `_safe_invoke_tool`, `advanced_search`, `rerank_docs`, MCP tool loading, and Redis connection creation. Raise typed `RuntimeError`, `TimeoutError`, or connection errors at those boundaries; do not patch evaluator code or fallback code.

- [ ] **Step 3: Define reliability pass conditions**

`graceful_degradation=1` requires no exception escaping the public entry point, a non-empty user-facing response when `requires_response` is true, a matching fallback transition or progress stage, and bounded termination. Report fault-specific rates as well as the 50-case aggregate.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/evals/test_reliability_evaluator.py -q`

Expected: PASS without live infrastructure.

Commit: `git commit -m "test: add agent fault-injection evaluation"`

---

### Task 7: Implement Performance, Token, and Parallelism Benchmarks

**Files:**
- Create: `evals/evaluators/performance.py`
- Create: `tests/evals/test_performance_evaluator.py`
- Modify: `evals/adapters.py`

**Interfaces:**
- Produces `async benchmark_stream_chat(case, repeat: int) -> CaseResult`.
- Produces `async benchmark_parallel_tools(max_parallel: int) -> CaseResult`.
- Consumes existing `stats`, `tool_call`, `usage`, and token events from `app.services.rag_service.stream_chat()`.

- [ ] **Step 1: Write a failing event-timing test**

```python
import asyncio

from evals.evaluators.performance import consume_timed_events


async def fake_stream():
    yield {"type": "progress", "stage": "retrieve"}
    yield {"type": "token", "content": "答"}
    yield {"type": "progress", "stage": "stats", "data": {"total_tokens": 42, "total_ms": 120}}


def test_timing_extracts_first_token_and_usage():
    values = asyncio.run(consume_timed_events(fake_stream()))
    assert values["ttft_ms"] >= 0
    assert values["total_tokens"] == 42
    assert values["reported_total_ms"] == 120
```

- [ ] **Step 2: Collect online latency and cost inputs**

For 30 representative Agent cases, execute three repeats after one warm-up. Record TTFT, end-to-end latency, LLM time, tool time, input/output/total tokens, tool-call count, answer length, model name, and failures. Report P50 and P95; never average percentiles across separate runs.

- [ ] **Step 3: Build a controlled parallelism benchmark**

Use six deterministic async fake tools that each wait 100 ms. Run `run_parallel_agent` with a scripted fake chat model under `max_parallel=1` and `max_parallel=6`. Assert both modes return identical tool results and calculate `speedup = serial_ms / parallel_ms` plus `latency_reduction = 1 - parallel_ms / serial_ms`.

- [ ] **Step 4: Run tests and commit**

Run: `pytest tests/evals/test_performance_evaluator.py -q`

Expected: PASS; the parallel run is materially faster while producing identical results.

Commit: `git commit -m "perf: add agent latency and parallelism benchmarks"`

---

### Task 8: Add the Evaluation CLI, Reports, and Regression Gates

**Files:**
- Create: `scripts/run_agent_eval.py`
- Create: `evals/runner.py`
- Create: `evals/report.py`
- Create: `evals/gates.py`
- Create: `docs/evaluation/README.md`
- Create: `tests/evals/test_report.py`
- Modify: `.gitignore`

**Interfaces:**
- CLI suites: `router`, `retrieval`, `agent`, `reliability`, `performance`, and `all`.
- CLI options: `--dataset-version`, `--output`, `--online`, `--repeat`, `--seed`, and `--fail-on-gate`.
- Produces `metadata.json`, `case-results.jsonl`, `summary.json`, and `report.md` under one run directory.

- [ ] **Step 1: Write a failing report test**

```python
from pathlib import Path

from evals.report import write_report


def test_report_contains_dataset_model_and_primary_metrics(tmp_path: Path):
    summary = {
        "suite": "router",
        "dataset_version": "v1",
        "model": "test-model",
        "metrics": {"exact_accuracy": 0.91, "macro_f1": 0.90},
        "gates": {"exact_accuracy": {"threshold": 0.90, "passed": True}},
    }
    path = write_report(summary, tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "v1" in text
    assert "test-model" in text
    assert "0.9100" in text
```

- [ ] **Step 2: Implement CLI safety and metadata capture**

Without `--online`, Router and Agent evaluators must use injected deterministic adapters, Retrieval may use local Milvus only when explicitly selected, and no paid model can be called. Capture `git rev-parse HEAD`, dirty-worktree status, Python version, model names, non-secret RAG settings, dataset hashes, seed, and repeat count.

- [ ] **Step 3: Implement commands**

```powershell
# Deterministic regression suite
python scripts\run_agent_eval.py reliability --dataset-version v1 --fail-on-gate

# Local retrieval comparison with Milvus running
python scripts\run_agent_eval.py retrieval --dataset-version v1 --output output\evals\retrieval-v1

# Paid/online Router benchmark, repeated three times
python scripts\run_agent_eval.py router --dataset-version v1 --online --repeat 3 --output output\evals\router-v1

# Full online baseline
python scripts\run_agent_eval.py all --dataset-version v1 --online --repeat 3 --output output\evals\baseline-v1
```

- [ ] **Step 4: Implement gates without hiding raw values**

Gate failures make the CLI exit with status 1 only when `--fail-on-gate` is supplied. Reports always include the raw metric, threshold, sample count, and confidence interval. Performance metrics are informational in v1 except controlled parallelism latency reduction, whose target is >= 0.30.

- [ ] **Step 5: Ignore raw outputs and document operation**

Add `output/evals/` to `.gitignore`. Document required services, expected cost-bearing commands, dataset annotation rules, baseline update policy, and how to compare two summaries.

- [ ] **Step 6: Run tests and commit**

Run: `pytest tests/evals -q`

Expected: all evaluator unit tests pass without external services.

Commit: `git commit -m "feat: add agent evaluation CLI and reports"`

---

### Task 9: Establish the First Reproducible Baseline and Resume Metrics

**Files:**
- Create: `evals/baselines/v1-summary.json`
- Create: `docs/evaluation/baseline-v1.md`
- Test: `tests/evals/test_baseline.py`

**Interfaces:**
- Produces the first reviewed aggregate baseline tied to one git commit and one model/config snapshot.
- Produces a resume-ready metrics block derived only from `summary.json`.

- [ ] **Step 1: Verify infrastructure and run the deterministic suites**

Run:

```powershell
pytest tests/evals -q
python scripts\run_agent_eval.py reliability --dataset-version v1 --fail-on-gate
```

Expected: deterministic tests and bounded-termination/fallback gates pass before spending API quota.

- [ ] **Step 2: Run Retrieval with all three variants**

Start Milvus and ingest the frozen knowledge base, then run the retrieval suite. Save the collection entity count and knowledge-base file hashes in the report so a future corpus change cannot be compared silently against v1.

- [ ] **Step 3: Run online Router, Agent, and Performance suites**

Use one pinned model/configuration, temperature 0, three repeats, and a clean or explicitly recorded dirty worktree. If any run is interrupted, discard the partial aggregate and rerun that suite.

- [ ] **Step 4: Complete blind human review**

Export 50 stratified answers, collect two independent rubric files, import both, resolve gaps greater than one point, and append adjudicated metrics to the baseline.

- [ ] **Step 5: Write and validate the baseline report**

The report must include sample counts, confidence intervals, per-category breakdowns, failure examples, and limitations. Add a test that loads `v1-summary.json`, checks the git/model/dataset metadata, and verifies every resume metric exists as a numeric value with `sample_count > 0`.

- [ ] **Step 6: Derive the resume sentence mechanically**

Generate this shape from the report, substituting measured values only:

```text
构建覆盖 300 条路由问题、100 条 RAG 标注问题、100 条端到端任务和 50 条故障注入用例的评测集；
Skill 路由准确率达到 {router_exact_accuracy:.1%}，端到端任务成功率达到 {task_success:.1%}；
混合检索 Recall@20 达到 {recall_at_20:.1%}、NDCG@3 达到 {ndcg_at_3:.3f}；
外部依赖异常时降级成功率达到 {graceful_degradation:.1%}，P95 首 Token 延迟为 {ttft_p95_ms/1000:.2f}s。
```

- [ ] **Step 7: Commit the reviewed aggregate baseline**

Do not commit raw prompts or answers containing user data. Commit the aggregate summary, methodology, and anonymized representative failures.

Commit: `git commit -m "docs: publish agent evaluation baseline v1"`

## Recommended Execution Order

1. Complete Tasks 1-3 to obtain Router metrics first; this is the fastest useful resume signal.
2. Complete Task 4 after freezing the 164-chunk knowledge corpus.
3. Complete Tasks 5-6 to establish end-to-end correctness and reliability.
4. Complete Tasks 7-8 for performance reporting and one-command reproducibility.
5. Complete Task 9 only after all datasets and gates have been reviewed.

## Definition of Done

- `pytest tests/evals -q` passes without network access.
- Every dataset is versioned, hashed, quota-validated, and independently reviewed.
- One command produces case-level JSONL, aggregate JSON, and a readable Markdown report.
- Router, RAG, Agent, reliability, performance, and human answer-quality metrics all include sample counts and reproducibility metadata.
- The report distinguishes measured results, proposed gates, and external limitations.
- Every number used in the resume can be traced to a field in the committed aggregate baseline.
