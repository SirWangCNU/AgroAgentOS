import { authFetchRaw } from "./client";
import type { ChatRequest } from "../types/chat";

export async function chatStream(
  req: ChatRequest
): Promise<Response> {
  return authFetchRaw("/chat/stream", {
    method: "POST",
    body: JSON.stringify(req),
  });
}
