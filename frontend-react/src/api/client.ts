import { API_BASE, STORAGE_KEYS } from "../lib/constants";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
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

  // ✅ 检查返回类型是否是JSON，避免解析HTML导致Unexpected token '<'错误
  const contentType = resp.headers.get("content-type");
  if (contentType && !contentType.includes("application/json")) {
    const text = await resp.text().catch(() => "");
    console.error(`[authFetch] 接口返回非JSON内容: ${path}`, text.substring(0, 200));
    throw new ApiError(resp.status, `接口异常: ${path}`);
  }

  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new ApiError(resp.status, text || `HTTP ${resp.status}`);
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
