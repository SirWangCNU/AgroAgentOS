import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { chatStream } from "../api/chat";
import { analyzeImage } from "../api/image";
import { consumeSSE } from "../api/client";
import { addSessionMessage } from "../api/sessions";
import { useConversationStore } from "../stores/conversation";
import { useUIStore } from "../stores/ui";
import WelcomeScreen from "../components/chat/WelcomeScreen";
import MessageBubble from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";
import ProgressSteps, {
  toProgressStep,
} from "../components/chat/ProgressSteps";

// 模块级 ref：跨组件卸载/重挂载保持状态，防止 navigate 导致 sendingRef 被重置
const _globalSendingRef = { current: false };

export default function Chat() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

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
      setLoadError(null);
      return;
    }

    // Always ensure activeId matches the URL
    if (sessionId !== activeId) {
      setActive(sessionId);
    }

    // Clear previous errors when navigating to a new conversation
    setLoadError(null);

    // Load messages if not already loaded
    // Skip if we're mid-send: createNew() + addMessage() already populated the conversation
    // 双重保护：模块级 ref + store 中的 isStreaming 状态
    if (_globalSendingRef.current) return;
    if (useConversationStore.getState().isStreaming) return;
    const conv = useConversationStore.getState().conversations.find((c) => c.id === sessionId);
    if (!conv || conv.messages.length === 0) {
      loadMessages(sessionId).catch((err) => {
        const message = err?.status === 404
          ? "对话不存在或已被删除"
          : `加载对话失败: ${err?.message || "未知错误"}`;
        setLoadError(message);
      });
    }
  }, [sessionId, activeId]);

  // Auto-scroll on new messages or progress updates
  const conversation = activeConversation();
  const messages = conversation?.messages || [];
  const lastMsg = messages[messages.length - 1];

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

    // Ensure we have an active conversation
    let convId = activeId;
    if (!convId) {
      convId = await createNew();
    }

    // Clear previous live state
    clearLiveState();

    // Image analysis
    if (image) {
      try {
        const result = await analyzeImage(image);
        if (result.success && result.detections.length > 0) {
          const detText = result.detections
            .map((d) => `${d.chinese_name}(${(d.confidence * 100).toFixed(0)}%)`)
            .join(", ");
          const userNote = text ? `\n用户补充说明: ${text}` : "";
          finalQuestion = `[图片分析] 识别到: ${detText}。\n${result.summary}${userNote}\n请根据识别结果给出详细的病虫害防治建议。`;
        } else {
          finalQuestion = `[图片分析] ${result.summary || "未识别到病虫害"}${text ? `\n用户说明: ${text}` : ""}`;
        }
        await addMessage({
          role: "user",
          content: text || "(图片分析)",
          type: "image",
        });
      } catch (err: any) {
        showToast(`图片分析失败: ${err.message}`, "error");
        return;
      }
    } else {
      await addMessage({ role: "user", content: text });
    }

    // Navigate AFTER addMessage — ensures user message is in the store before
    // the URL change triggers a component remount (different route = unmount/remount).
    // This prevents the "加载对话记录中..." flash where loadMessages overwrites
    // the user's first message.
    if (!activeId) {
      navigate(`/chat/${convId}`, { replace: true });
    }

    setStreaming(true);

    try {
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
          const stage = ev.stage as string;
          const data = (ev.data || ev) as Record<string, unknown>;

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
          thinkingContent += ev.content as string;
          setThinking(thinkingContent);
        } else if (ev.type === "token") {
          if (inProgressPhase) {
            // Buffer tokens until progress phase ends
            bufferedTokens += ev.content as string;
          } else {
            assistantContent += ev.content as string;
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
          const citations = ev.citations as any[];
          if (citations?.length) {
            setLiveCitations(
              citations.map((c) => ({
                source: c.source || "",
                chapter: c.chapter,
                category: c.category,
                preview: c.content || c.preview,
                score: c.relevance_score || c.score,
              }))
            );
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
    } catch (err: any) {
      showToast(`网络错误: ${err.message}`, "error");
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

  // Show loading state while fetching messages for a conversation
  if (sessionId && isLoadingMessages) {
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
  if (sessionId && loadError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4">
        <div className="text-red-400 text-sm">{loadError}</div>
        <button
          onClick={() => {
            setLoadError(null);
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
