import { API_BASE, STORAGE_KEYS } from "../lib/constants";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(status: number, message: string, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function getErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function extractErrorMessage(text: string): { message: string; code?: string } {
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === "object") {
      // 优先使用后端统一响应格式的外层 message
      if (typeof parsed.message === "string" && parsed.message) {
        return { message: parsed.message, code: parsed.code };
      }
      // 兼容嵌套 data.message
      if (parsed.data && typeof parsed.data.message === "string" && parsed.data.message) {
        return { message: parsed.data.message, code: parsed.data.code };
      }
      // 兼容 { error: "..." }
      if (typeof parsed.error === "string" && parsed.error) {
        return { message: parsed.error };
      }
    }
  } catch {
    // 非 JSON 时直接返回原文
  }
  return { message: text };
}

export async function authFetch<T = unknown>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem(STORAGE_KEYS.TOKEN);
  const headers = new Headers(options.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401) {
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
    window.location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    const { message, code } = extractErrorMessage(text);
    throw new ApiError(resp.status, message || `HTTP ${resp.status}`, code);
  }

  return resp.json();
}

export async function authFetchRaw(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const token = localStorage.getItem(STORAGE_KEYS.TOKEN);
  const headers = new Headers(options.headers);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const resp = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (resp.status === 401) {
    localStorage.removeItem(STORAGE_KEYS.TOKEN);
    localStorage.removeItem(STORAGE_KEYS.USER);
    window.location.href = "/login";
    throw new ApiError(401, "Unauthorized");
  }

  return resp;
}

/** SSE consumer: yields parsed JSON events from a streaming response */
export async function* consumeSSE(
  resp: Response
): AsyncGenerator<Record<string, unknown>, void, unknown> {
  const reader = resp.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split(/\r?\n\r?\n|\n\n/);
    buffer = parts.pop()!;

    for (const part of parts) {
      const dataLine = part
        .split("\n")
        .find((l) => l.startsWith("data:"));
      if (dataLine) {
        const json = dataLine.slice(5).trim();
        if (json) {
          try {
            yield JSON.parse(json);
          } catch {
            // skip malformed events
          }
        }
      }
    }
  }
}
