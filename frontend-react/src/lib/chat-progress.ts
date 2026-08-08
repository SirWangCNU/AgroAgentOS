import type { ProgressStep } from "../types/chat";

/** Convert a raw SSE progress event into the presentation model. */
export function toProgressStep(
  event: Record<string, unknown>,
  index: number
): ProgressStep {
  const stage = typeof event.stage === "string" ? event.stage : "unknown";
  const data = isRecord(event.data) ? event.data : event;

  const statusMap: Record<string, ProgressStep["status"]> = {
    rewrite: "running",
    rewrite_done: "done",
    retrieve: "running",
    retrieve_done: "done",
    retrieve_degraded: "skipped",
    web: "running",
    web_done: "done",
    web_degraded: "skipped",
    user_context: "running",
    user_context_done: "done",
    llm_start: "done",
    tool_call: "done",
    stats: "done",
  };

  const labelMap: Record<string, string> = {
    rewrite: "理解问题",
    rewrite_done: "理解完成",
    retrieve: "检索知识库",
    retrieve_done: "知识库命中",
    retrieve_degraded: "知识库跳过",
    web: "联网搜索",
    web_done: "搜索完成",
    web_degraded: "搜索跳过",
    user_context: "加载农场数据",
    user_context_done: "农场数据就绪",
    llm_start: "生成回答",
    tool_call: `调用 ${stringValue(data.name) ?? "工具"}`,
    stats: "统计",
  };

  return {
    id: `${stage}-${index}`,
    stage,
    label: labelMap[stage] ?? stage,
    detail: getDetail(stage, data),
    status: statusMap[stage] ?? "done",
    elapsed_ms: numberValue(data.elapsed_ms),
    data,
  };
}

function getDetail(
  stage: string,
  data: Record<string, unknown>
): string | undefined {
  if (stage === "rewrite_done") {
    return stringValue(data.rewritten)?.slice(0, 30);
  }
  if (stage === "retrieve_done") {
    return Array.isArray(data.hits)
      ? `${data.hits.length} 条结果`
      : data.top_k !== undefined
        ? `top-${String(data.top_k)}`
        : undefined;
  }
  if (stage === "web_done") {
    return Array.isArray(data.results)
      ? `${data.results.length} 条结果`
      : stringValue(data.skip_reason);
  }
  if (stage === "user_context_done") {
    return stringValue(data.label);
  }
  if (stage === "tool_call") {
    return data.elapsed_ms !== undefined
      ? `${String(data.elapsed_ms)}ms`
      : stringValue(data.status);
  }
  return undefined;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" && value ? value : undefined;
}

function numberValue(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}
