import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chatStream } from "../api/chat";
import { analyzeImage } from "../api/image";
import { ApiError, consumeSSE, getErrorMessage } from "../api/client";
import { addSessionMessage } from "../api/sessions";
import { useConversationStore } from "../stores/conversation";
import { useUIStore } from "../stores/ui";
import WelcomeScreen from "../components/chat/WelcomeScreen";
import MessageBubble from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";
import ProgressSteps from "../components/chat/ProgressSteps";
import { toProgressStep } from "../lib/chat-progress";
import type { ChatMessage, Citation } from "../types/chat";

// 模块级 ref：跨组件卸载/重挂载保持状态，防止 navigate 导致 sendingRef 被重置
const _globalSendingRef = { current: false };
const EMPTY_MESSAGES: ChatMessage[] = [];

export default function Chat() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [loadError, setLoadError] = useState<{
    sessionId: string;
    message: string;
  } | null>(null);
  // Bug 修复: 记录已加载的 sessionId, 防止 useEffect 因 activeId 变化重复触发 loadMessages
  // 之前的问题: setActive(sessionId) 触发 store 更新 → 组件 re-render → useEffect 依赖 [sessionId, activeId]
  // 重跑, 但此时 conv.find 仍找不到 (loadMessages 还在进行中), 会再次调用 loadMessages.
  // 这浪费网络请求, 且 isLoadingMessages 反复被设为 true, UI 卡在 "加载对话记录中..." 状态.
  const loadedSessionRef = useRef<Set<string>>(new Set());

  const {
    activeId,
    setActive,
    loadMessages,
    addMessage,
    updateLastAssistant,
    setThinking,
    setStreaming,
    isStreaming,
    isLoadingMessages,
    activeConversation,
    createNew,
    refreshConversations,
    webSearch,
    mcpTools,
    setWebSearch,
    setMcpTools,
    liveProgress,
    liveCitations,
    progressPhase,
    addProgressStep,
    updateLastProgressStep,
    setLiveCitations,
    markAllProgressDone,
    clearLiveState,
  } = useConversationStore();
  const showToast = useUIStore((s) => s.showToast);

  // Sync URL param with store
  useEffect(() => {
    if (!sessionId) {
      // Navigated to /chat (no session) — clear active so welcome screen shows
      // Bug fix: 不要在发送过程中清除 activeId
      // createNew() 会在 navigate() 之前更新 store 中的 activeId，
      // 此时 sessionId 还是 undefined，如果不加保护就会清掉刚设置的 activeId，
      // 导致后续 addMessage 失败（addMessage 内部有 if (!activeId) return），
      // 用户消息不显示也不持久化，最终触发了 loadMessages 出现"加载对话记录"
      if (activeId && !_globalSendingRef.current) setActive(null);
      return;
    }

    // Always ensure activeId matches the URL
    if (sessionId !== activeId) {
      setActive(sessionId);
    }

    // Clear previous errors when navigating to a new conversation
    // Load messages if not already loaded
    // Skip if we're mid-send: createNew() + addMessage() already populated the conversation
    // 双重保护：模块级 ref + store 中的 isStreaming 状态
    if (_globalSendingRef.current) return;
    if (useConversationStore.getState().isStreaming) return;
    // Bug 修复: 已加载过该 sessionId 则跳过, 避免 setActive 触发的二次调用
    if (loadedSessionRef.current.has(sessionId)) return;
    const conv = useConversationStore.getState().conversations.find((c) => c.id === sessionId);
    if (!conv || conv.messages.length === 0) {
      loadedSessionRef.current.add(sessionId);
      // Bug 修复: 包装 loadMessages 带超时, 避免后端慢/挂起时永远卡在 "加载对话记录中..."
      // 之前如果 getSession 端点慢/超时, isLoadingMessages 一直 true, 用户卡在 loading 状态
      // Bug 修复: 超时从 8s 缩短到 4s. 后端有 TTL 缓存 + LEFT JOIN 优化, 正常请求 < 100ms,
      // 4s 内未返回基本可以判定为后端异常, 立即兜底让用户看到内容.
      const timeoutPromise = new Promise<"timeout">((resolve) =>
        setTimeout(() => resolve("timeout"), 4000)
      );
      Promise.race([
        loadMessages(sessionId).then(() => "ok" as const),
        timeoutPromise,
      ]).then((result) => {
        if (result === "timeout") {
          // 超时兜底: 强制结束 loading 状态, 让用户看到内容(可能是空对话的 welcome 页面)
          // 如果 store 中已有 stub (AppLayout 预加载的), 用户会看到空对话的 welcome 页面;
          // 如果 store 仍为空 (冷启动且 list 加载失败), 强制清空 isLoadingMessages 让 Chat 渲染欢迎页.
          loadedSessionRef.current.delete(sessionId);
          useConversationStore.setState({ isLoadingMessages: false });
        }
      }).catch((err) => {
        // 失败时清除标记, 允许重试
        loadedSessionRef.current.delete(sessionId);
        // 404 (会话不存在) 静默处理, 不弹错误 —— 用户可能刷新到一个旧链接,
        // 强制清空 loading 让 Chat 渲染 welcome 页面, 体验更平滑
        if (err instanceof ApiError && err.status === 404) {
          useConversationStore.setState({ isLoadingMessages: false });
          return;
        }
        setLoadError({
          sessionId,
          message: `加载对话失败: ${getErrorMessage(err, "未知错误")}`,
        });
      });
    } else {
      // store 已有消息也标记为已加载
      loadedSessionRef.current.add(sessionId);
    }
  }, [sessionId, activeId, loadMessages, setActive]);

  // 当前激活会话 (从 store 取, 避免组件渲染时再次 fetch)
  const conversation = activeConversation();
  const messages = conversation?.messages ?? EMPTY_MESSAGES;
  const lastMsg = messages[messages.length - 1];

  // Auto-scroll on new messages or progress updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveProgress]);

  const handleSend = async (text: string, image?: File) => {
    // Prevent double-send (e.g. rapid clicks or double Enter)
    if (_globalSendingRef.current) return;
    let finalQuestion = text;

    // Mark sending in progress BEFORE createNew() — createNew triggers a store
    // update that re-renders the component and runs the useEffect. If the flag
    // is set after createNew, the effect sees _globalSendingRef.current=false
    // and calls loadMessages, which overwrites the user's first message.
    _globalSendingRef.current = true;

    try {
      // Ensure we have an active conversation
      let convId = activeId;
      if (!convId) {
        convId = await createNew();
      }

      // Clear previous live state
      clearLiveState();

      if (image) {
        const imagePreviewUrl = await fileToDataUrl(image);
        await addMessage({
          role: "user",
          content: text || "(图片分析)",
          type: "image",
          imageUrl: imagePreviewUrl,
        });

        // Navigate as soon as the user's message is visible. Image analysis can
        // take seconds, so it should run after the chat view is already open.
        if (!activeId) {
          navigate(`/chat/${convId}`, { replace: true });
        }

        setStreaming(true);
        addProgressStep({
          id: `image-analysis-${Date.now()}`,
          stage: "image_analysis",
          label: "正在分析图片",
          detail: "多模态模型识别病虫害",
          status: "running",
        });

        try {
          const result = await analyzeImage(image);
          updateLastProgressStep({
            status: "done",
            detail: result.summary || "图片分析完成",
          });

          if (result.success && result.detections.length > 0) {
            const detText = result.detections
              .map((d) => `${d.chinese_name}(${(d.confidence * 100).toFixed(0)}%)`)
              .join(", ");
            const userNote = text ? `\n用户补充说明: ${text}` : "";
            const diagnosis = result.diagnosis ? `\n详细诊断: ${result.diagnosis}` : "";
            finalQuestion = `[图片分析] 识别到: ${detText}。\n${result.summary}${diagnosis}${userNote}\n请根据识别结果给出详细的病虫害防治建议。`;
          } else {
            const diagnosis = result.diagnosis ? `\n详细诊断: ${result.diagnosis}` : "";
            finalQuestion = `[图片分析] ${result.summary || "未识别到病虫害"}${diagnosis}${text ? `\n用户说明: ${text}` : ""}`;
          }
        } catch (err: unknown) {
          updateLastProgressStep({
            status: "error",
            detail: getErrorMessage(err, "未知错误"),
          });
          showToast(`图片分析失败: ${getErrorMessage(err, "未知错误")}`, "error");
          return;
        }
      } else {
        await addMessage({ role: "user", content: text });

        // Navigate AFTER addMessage — ensures user message is in the store before
        // the URL change triggers a component remount (different route = unmount/remount).
        // This prevents the "加载对话记录中..." flash where loadMessages overwrites
        // the user's first message.
        if (!activeId) {
          navigate(`/chat/${convId}`, { replace: true });
        }

        setStreaming(true);
      }

      const resp = await chatStream({
        session_id: convId!,
        question: finalQuestion,
        top_k: 3,
        web_search: webSearch,
        mcp_tools: mcpTools,
      });

      let assistantContent = "";
      let thinkingContent = "";
      let progressIndex = 0;
      let bufferedTokens = "";
      let inProgressPhase = true;

      for await (const event of consumeSSE(resp)) {
        const ev = event as Record<string, unknown>;

        if (ev.type === "progress") {
          const stage = typeof ev.stage === "string" ? ev.stage : "unknown";
          const data = isRecord(ev.data) ? ev.data : ev;

          // llm_start means retrieval/search phase is done, transition to answer phase
          if (stage === "llm_start") {
            // Flush buffered tokens
            if (bufferedTokens) {
              assistantContent = bufferedTokens;
              updateLastAssistant(assistantContent);
              bufferedTokens = "";
            }
            inProgressPhase = false;
            markAllProgressDone();

            // Add llm_start as a done step
            const step = toProgressStep(ev, progressIndex++);
            addProgressStep(step);
            continue;
          }

          // Mark the running version as done if this is a _done/_degraded event
          if (stage.endsWith("_done") || stage.endsWith("_degraded")) {
            updateLastProgressStep({
              status: "done",
              detail: getProgressDetail(stage, data),
              elapsed_ms: data.elapsed_ms as number | undefined,
            });
          }

          // Add new step
          const step = toProgressStep(ev, progressIndex++);
          addProgressStep(step);
        } else if (ev.type === "thinking") {
          thinkingContent += stringValue(ev.content);
          setThinking(thinkingContent);
        } else if (ev.type === "token") {
          if (inProgressPhase) {
            // Buffer tokens until progress phase ends
            bufferedTokens += stringValue(ev.content);
          } else {
            assistantContent += stringValue(ev.content);
            updateLastAssistant(assistantContent);
          }
        } else if (ev.type === "tool_call") {
          // Tool call events from MCP
          const step = toProgressStep(
            { type: "progress", stage: "tool_call", data: ev },
            progressIndex++
          );
          addProgressStep(step);
        } else if (ev.type === "citations") {
          const citations = toCitations(ev.citations);
          if (citations.length) {
            setLiveCitations(citations);
          }
        } else if (ev.type === "error") {
          showToast(`错误: ${ev.message}`, "error");
        }
      }

      // Flush any remaining buffered tokens (fallback if llm_start was missed)
      if (bufferedTokens && !assistantContent) {
        assistantContent = bufferedTokens;
        updateLastAssistant(assistantContent);
      }

      // Save assistant message to backend
      if (assistantContent) {
        addSessionMessage(convId!, "assistant", assistantContent).catch(() => {});
      }

      // Refresh conversation list so sidebar shows updated message_count
      refreshConversations().catch(() => {});
    } catch (err: unknown) {
      showToast(`网络错误: ${getErrorMessage(err, "未知错误")}`, "error");
    } finally {
      _globalSendingRef.current = false;
      setStreaming(false);
    }
  };

  const handleStop = () => {
    // AbortController could be added here in the future
    setStreaming(false);
  };

  const handleQuickAction = (text: string) => {
    handleSend(text);
  };

  // Show loading state only when fetching messages for a conversation that
  // isn't even in the store yet (e.g. cold start, list still loading).
  // If AppLayout eagerly preloaded conversations, we already have a stub
  // here — render the chat shell immediately and let loadMessages fill in
  // messages silently in the background. This avoids the "stuck on loading"
  // flash when the backend is slow on first hit.
  const hasStub = !!conversation;
  if (sessionId && isLoadingMessages && !hasStub) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-2 text-text-muted text-sm">
          <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
          加载对话记录中...
        </div>
      </div>
    );
  }

  // Show error state if loading failed
  const errorForCurrentSession =
    loadError && loadError.sessionId === sessionId ? loadError.message : null;
  if (sessionId && errorForCurrentSession) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <div className="text-red-400 text-sm">{errorForCurrentSession}</div>
        <button
          onClick={() => {
            navigate("/chat");
          }}
          className="px-4 py-2 text-sm bg-white/10 hover:bg-white/20 rounded-lg transition-colors"
        >
          返回首页
        </button>
      </div>
    );
  }

  // Show welcome screen if no messages
  if (!messages.length) {
    return (
      <>
        <WelcomeScreen onQuickAction={handleQuickAction} />
        <div className="pb-6">
          <ChatInput
            onSend={handleSend}
            streaming={isStreaming}
            disabled={isStreaming}
            webSearch={webSearch}
            onWebSearchChange={setWebSearch}
            mcpTools={mcpTools}
            onMcpToolsChange={setMcpTools}
          />
        </div>
      </>
    );
  }

  return (
    <>
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {messages.map((msg, i) => {
            // Skip last assistant message during streaming (rendered by live block below)
            const isLastMsg = i === messages.length - 1;
            if (isStreaming && isLastMsg && msg.role === "assistant") {
              return null;
            }
            return <MessageBubble key={i} msg={msg} />;
          })}

          {/* Streaming: progress + answer in one block */}
          {isStreaming && (
            <div className="flex justify-start mb-6">
              <div className="flex items-start gap-2 max-w-[85%]">
                <div className="w-8 h-8 rounded-full bg-accent-green/20 flex items-center justify-center flex-shrink-0">
                  <div className="w-2 h-2 bg-accent-green rounded-full animate-pulse" />
                </div>
                <div className="space-y-2 flex-1 min-w-0">
                  {/* Progress steps — always on top */}
                  {liveProgress.length > 0 ? (
                    <ProgressSteps steps={liveProgress} />
                  ) : progressPhase ? (
                    <div className="flex items-center gap-2 text-text-muted text-sm">
                      <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                      正在分析问题...
                    </div>
                  ) : null}

                  {/* Citations */}
                  {liveCitations.length > 0 && (
                    <div className="p-3 bg-bg-card border border-border rounded-xl">
                      <div className="text-xs font-medium text-text-secondary mb-2">
                        📚 引用来源
                      </div>
                      <div className="space-y-1.5">
                        {liveCitations.map((c, i) => (
                          <div key={i} className="text-xs text-text-muted">
                            <span className="text-text-secondary font-medium">
                              {c.source}
                            </span>
                            {c.chapter && (
                              <span className="text-text-muted"> · {c.chapter}</span>
                            )}
                            {c.score != null && (
                              <span className="text-accent-blue ml-1">
                                {(c.score * 100).toFixed(0)}%
                              </span>
                            )}
                            {c.preview && (
                              <div className="text-text-muted mt-0.5 line-clamp-1">
                                {c.preview}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Answer content — appears below progress */}
                  {!progressPhase && lastMsg?.role === "assistant" && (
                    <div className="px-4 py-3 bg-bg-card border border-border rounded-2xl rounded-bl-sm text-sm markdown-body">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {lastMsg.content || "..."}
                      </ReactMarkdown>
                      <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 animate-pulse rounded-sm align-middle" />
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="pb-6 pt-2">
        <ChatInput
          onSend={handleSend}
          onStop={handleStop}
          streaming={isStreaming}
          disabled={isStreaming}
          webSearch={webSearch}
          onWebSearchChange={setWebSearch}
          mcpTools={mcpTools}
          onMcpToolsChange={setMcpTools}
        />
      </div>
    </>
  );
}

/** Extract human-readable detail from progress event data */
function getProgressDetail(
  stage: string,
  data: Record<string, unknown>
): string | undefined {
  if (stage === "retrieve_done" && data.hits) {
    return `${(data.hits as unknown[]).length} 条结果`;
  }
  if (stage === "web_done" && data.results) {
    return `${(data.results as unknown[]).length} 条结果`;
  }
  if (stage === "user_context_done" && data.label) {
    return String(data.label);
  }
  return undefined;
}

function toCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => {
    if (!isRecord(item)) {
      return [];
    }
    return [{
      source: stringValue(item.source),
      chapter: optionalString(item.chapter),
      category: optionalString(item.category),
      preview: optionalString(item.content) ?? optionalString(item.preview),
      score: optionalNumber(item.relevance_score) ?? optionalNumber(item.score),
    }];
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function optionalString(value: unknown): string | undefined {
  const result = stringValue(value);
  return result || undefined;
}

function optionalNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("图片预览生成失败"));
      }
    };
    reader.onerror = () => reject(reader.error ?? new Error("图片预览生成失败"));
    reader.readAsDataURL(file);
  });
}
