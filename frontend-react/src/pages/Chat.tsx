import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
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

export default function Chat() {
  const { sessionId } = useParams();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const {
    activeId,
    setActive,
    loadMessages,
    addMessage,
    updateLastAssistant,
    setThinking,
    setStreaming,
    isStreaming,
    activeConversation,
    createNew,
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
    if (sessionId && sessionId !== activeId) {
      setActive(sessionId);
      loadMessages(sessionId);
    }
  }, [sessionId, activeId, setActive, loadMessages]);

  // Auto-scroll on new messages or progress updates
  const conversation = activeConversation();
  const messages = conversation?.messages || [];
  const lastMsg = messages[messages.length - 1];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, liveProgress]);

  const handleSend = async (text: string, image?: File) => {
    let finalQuestion = text;

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
        addMessage({
          role: "user",
          content: text || "(图片分析)",
          type: "image",
        });
      } catch (err: any) {
        showToast(`图片分析失败: ${err.message}`, "error");
        return;
      }
    } else {
      addMessage({ role: "user", content: text });
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
    } catch (err: any) {
      showToast(`网络错误: ${err.message}`, "error");
    } finally {
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
