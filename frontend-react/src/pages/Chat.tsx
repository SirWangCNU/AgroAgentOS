import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  ArrowUp,
  Camera,
  Globe,
  Loader2,
  PanelLeft,
  Square,
  Wrench,
  X,
  Sparkles,
  Leaf,
  Bot,
  CloudSun,
  Bug,
  Radar,
} from "lucide-react";
import { chatStream } from "../api/chat";
import { analyzeImage } from "../api/image";
import { consumeSSE } from "../api/client";
import { useConversationStore } from "../stores/conversation";
import { useUIStore } from "../stores/ui";
import { useAuthStore } from "../stores/auth";
import MessageBubble from "../components/chat/MessageBubble";
import ProgressSteps, { toProgressStep } from "../components/chat/ProgressSteps";
import { ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE } from "../lib/constants";

// 模块级 ref：跨组件卸载/重挂载保持状态，防止 navigate 导致 sendingRef 被重置
const _globalSendingRef = { current: false };

interface AgentMode {
  id: string;
  label: string;
  icon: typeof Sparkles;
  tagline: string;
}

const AGENT_MODES: AgentMode[] = [
  { id: "chat", label: "智农助手", icon: Sparkles, tagline: "问问农业问题" },
  { id: "farm", label: "农场巡检", icon: Radar, tagline: "综合风险研判" },
  { id: "pest", label: "病虫害诊断", icon: Bug, tagline: "看叶片识病害" },
  { id: "weather", label: "天气农事", icon: CloudSun, tagline: "明天能打药吗" },
];

const QUICK_PROMPTS = [
  "水稻分蘖期该怎么管理？",
  "帮我看看这片叶子是什么病",
  "明天天气适合施肥吗？",
  "玉米现在卖合算吗？",
  "A1地块最近有风险吗？",
];

export default function Chat() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const loadedSessionRef = useRef<Set<string>>(new Set());
  const initialHandledRef = useRef(false);

  const {
    activeId,
    setActive,
    loadMessages,
    loadMoreMessages,
    addMessage,
    updateLastAssistant,
    setThinking,
    setStreaming,
    isStreaming,
    streamingSessionId,
    isLoadingMessages,
    isLoadingMore,
    activeConversation,
    createNew,
    refreshConversations,
    webSearch,
    mcpTools,
    setWebSearch,
    setMcpTools,
    liveProgress,
    liveCitations,
    addProgressStep,
    updateLastProgressStep,
    setLiveCitations,
    markAllProgressDone,
    clearLiveState,
  } = useConversationStore();
  const showToast = useUIStore((s) => s.showToast);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const user = useAuthStore((s) => s.user);

  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [activeMode, setActiveMode] = useState("chat");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Sync URL param with store
  useEffect(() => {
    if (!sessionId) {
      if (activeId && !_globalSendingRef.current) setActive(null);
      setLoadError(null);
      return;
    }
    if (sessionId !== activeId) setActive(sessionId);
    setLoadError(null);
    if (_globalSendingRef.current) return;
    if (useConversationStore.getState().isStreaming) {
      const streamingId = useConversationStore.getState().streamingSessionId;
      if (streamingId === sessionId) return;
    }
    if (loadedSessionRef.current.has(sessionId)) return;
    const conv = useConversationStore.getState().conversations.find((c) => c.id === sessionId);
    if (conv && conv.messages.length > 0) {
      loadedSessionRef.current.add(sessionId);
      return;
    }
    const timeoutPromise = new Promise<"timeout">((resolve) =>
      setTimeout(() => resolve("timeout"), 4000)
    );
    Promise.race([
      loadMessages(sessionId).then(() => "ok" as const),
      timeoutPromise,
    ]).then((result) => {
      if (result === "timeout") {
        loadedSessionRef.current.delete(sessionId);
        useConversationStore.setState({ isLoadingMessages: false });
      } else {
        loadedSessionRef.current.add(sessionId);
      }
    }).catch((err: any) => {
      loadedSessionRef.current.delete(sessionId);
      if (err?.status === 404) {
        useConversationStore.setState({ isLoadingMessages: false });
        return;
      }
      setLoadError(err.message || "加载失败");
    });
  }, [sessionId, activeId, loadMessages, setActive]);

  // Auto-scroll on new messages or progress updates
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeConversation()?.messages, liveProgress, liveCitations]);

  // Textarea auto-resize
  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;
    element.style.height = "auto";
    element.style.height = `${Math.max(56, Math.min(element.scrollHeight, 200))}px`;
  }, [text]);

  // 支持能力中心「一键体验」：携带 initialMessage 进入 /chat 时自动创建会话并发送
  useEffect(() => {
    const initialMessage = (location.state as { initialMessage?: string } | null)?.initialMessage;
    if (!initialMessage) return;
    if (initialHandledRef.current) return;
    initialHandledRef.current = true;
    useConversationStore.getState().setActive(null);
    window.history.replaceState({}, document.title, window.location.pathname);
    handleSend(initialMessage);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state?.initialMessage, sessionId]);

  const handleSend = async (question: string, sendImage?: File) => {
    if (!question.trim() && !sendImage) return;

    const currentActiveId = useConversationStore.getState().activeId;
    const currentStreamingId = useConversationStore.getState().streamingSessionId;
    if (currentStreamingId && currentStreamingId === currentActiveId) return;

    let finalQuestion = question;
    _globalSendingRef.current = true;

    let convId = useConversationStore.getState().activeId;
    const hadActiveId = !!convId;
    if (!convId) {
      convId = await createNew();
    }
    const targetConvId = convId!;
    if (!targetConvId) {
      showToast("创建会话失败", "error");
      _globalSendingRef.current = false;
      return;
    }

    clearLiveState();

    if (sendImage) {
      try {
        const result = await analyzeImage(sendImage);
        if (result.success && result.detections.length > 0) {
          const detText = result.detections
            .map((d) => `${d.chinese_name}(${(d.confidence * 100).toFixed(0)}%)`)
            .join(", ");
          const userNote = question ? `\n用户补充说明: ${question}` : "";
          finalQuestion = `[图片分析] 识别到: ${detText}。\n${result.summary}${userNote}\n请根据识别结果给出详细的病虫害防治建议。`;
        } else {
          finalQuestion = `[图片分析] ${result.summary || "未识别到病虫害"}${question ? `\n用户说明: ${question}` : ""}`;
        }
        await addMessage({
          role: "user",
          content: question || "(图片分析)",
          type: "image",
        });
      } catch (err: any) {
        showToast(`图片分析失败: ${err.message}`, "error");
        _globalSendingRef.current = false;
        return;
      }
    } else {
      await addMessage({ role: "user", content: question });
    }

    if (!hadActiveId) {
      navigate(`/chat/${convId}`, { replace: true });
    }

    setStreaming(true, targetConvId);

    try {
      const resp = await chatStream({
        session_id: targetConvId,
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

          if (stage === "llm_start") {
            if (bufferedTokens) {
              assistantContent = bufferedTokens;
              updateLastAssistant(assistantContent, targetConvId);
              bufferedTokens = "";
            }
            inProgressPhase = false;
            markAllProgressDone(targetConvId);
            const step = toProgressStep(ev, progressIndex++);
            addProgressStep(step, targetConvId);
            continue;
          }

          if (stage.endsWith("_done") || stage.endsWith("_degraded")) {
            updateLastProgressStep(
              {
                status: "done",
                detail: getProgressDetail(stage, data),
                elapsed_ms: data.elapsed_ms as number | undefined,
              },
              targetConvId
            );
          }
          const step = toProgressStep(ev, progressIndex++);
          addProgressStep(step, targetConvId);
        } else if (ev.type === "thinking") {
          thinkingContent += ev.content as string;
          setThinking(thinkingContent, targetConvId);
        } else if (ev.type === "token") {
          if (inProgressPhase) {
            bufferedTokens += ev.content as string;
          } else {
            assistantContent += ev.content as string;
            updateLastAssistant(assistantContent, targetConvId);
          }
        } else if (ev.type === "tool_call") {
          const step = toProgressStep(
            { type: "progress", stage: "tool_call", data: ev },
            progressIndex++
          );
          addProgressStep(step, targetConvId);
        } else if (ev.type === "citations") {
          const citations = ev.citations as Array<{
            source?: string;
            chapter?: string;
            category?: string;
            content?: string;
            preview?: string;
            relevance_score?: number;
            score?: number;
          }>;
          if (citations?.length) {
            setLiveCitations(
              citations.map((c) => ({
                source: c.source || "",
                chapter: c.chapter,
                category: c.category,
                preview: c.content || c.preview,
                score: c.relevance_score ?? c.score,
              })),
              targetConvId
            );
          }
        } else if (ev.type === "error") {
          showToast(`错误: ${ev.message}`, "error");
        }
      }

      if (bufferedTokens && !assistantContent) {
        assistantContent = bufferedTokens;
        updateLastAssistant(assistantContent, targetConvId);
      }

      refreshConversations().catch(() => {});
    } catch (err: any) {
      showToast(`网络错误: ${err.message}`, "error");
    } finally {
      _globalSendingRef.current = false;
      setStreaming(false, targetConvId);
    }
  };

  const clearImage = () => {
    setImage(null);
    setImagePreview(null);
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      alert("请上传 JPEG/PNG/WebP 格式的图片");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      alert("图片文件过大，限制 10MB");
      return;
    }
    setImage(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
    event.target.value = "";
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (isCurrentStreaming) return;
      handleSend(text, image || undefined);
      setText("");
      clearImage();
    }
  };

  const activeConv = activeConversation();
  const messages = activeConv?.messages || [];
  const isCurrentStreaming = isStreaming && streamingSessionId === activeId;

  if (sessionId && loadError) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center">
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

  // ===== WELCOME SCREEN =====
  if (!messages.length) {
    return (
      <div className="flex flex-1 overflow-hidden relative">
        {/* 沉浸式背景 */}
        <div className="absolute inset-0 -z-10">
          <div className="absolute inset-0 bg-gradient-to-b from-[#eef5f1] via-[#f6f9f6] to-white" />
          <div className="absolute left-1/4 top-0 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-emerald-200/20 blur-[120px]" />
          <div className="absolute right-0 top-1/4 h-[500px] w-[500px] rounded-full bg-amber-200/20 blur-[100px]" />
          <div
            className="absolute inset-0 opacity-[0.35]"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
            }}
          />
        </div>

        <div className="mx-auto flex min-h-full w-full max-w-[880px] flex-col items-center justify-center px-6 pb-10 pt-16 sm:px-8">
          {/* 顶部导航栏（极简） */}
          <div className="absolute top-0 left-0 right-0 flex h-16 items-center justify-between px-6">
            <button
              onClick={toggleSidebar}
              className="flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition-all hover:bg-white/60 hover:text-slate-800"
            >
              <PanelLeft className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-3">
              <div className="hidden sm:flex items-center gap-2 rounded-full border border-white/60 bg-white/40 px-3 py-1.5 text-xs text-slate-600 backdrop-blur-sm">
                <Leaf className="w-3.5 h-3.5 text-emerald-600" />
                <span>AgroAgentOS</span>
              </div>
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center text-white text-xs font-medium">
                {user?.username?.[0]?.toUpperCase() || "U"}
              </div>
            </div>
          </div>

          {/* 主标题 */}
          <div className="text-center mb-8">
            <h1 className="text-[40px] font-semibold leading-[1.15] tracking-tight text-[#16271c] sm:text-[52px]">
              Hi {user?.username ? `${user.username.slice(0, 8)}...` : "农户"}，
            </h1>
            <h1 className="mt-2 text-[40px] font-semibold leading-[1.15] tracking-tight text-[#16271c] sm:text-[52px]">
              和智农助手聊聊农田事
            </h1>
          </div>

          {/* Agent 模式切换 */}
          <div className="mb-8 inline-flex items-center gap-1 rounded-full border border-white/70 bg-white/50 p-1 shadow-sm backdrop-blur-sm">
            {AGENT_MODES.map((mode) => {
              const Icon = mode.icon;
              const active = activeMode === mode.id;
              return (
                <button
                  key={mode.id}
                  onClick={() => setActiveMode(mode.id)}
                  className={`relative flex items-center gap-2 rounded-full px-4 py-2 text-sm font-medium transition-all ${
                    active
                      ? "bg-[#16271c] text-white shadow-md"
                      : "text-slate-600 hover:bg-white/60"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {mode.label}
                  {active && <Sparkles className="w-3 h-3 text-emerald-300" />}
                </button>
              );
            })}
          </div>

          {/* 输入区 */}
          <div className="w-full max-w-[720px]">
            <input
              type="file"
              ref={fileRef}
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handleFileChange}
            />

            {image && imagePreview && (
              <div className="mb-3 flex items-center gap-3 rounded-2xl border border-slate-200/60 bg-white/70 px-4 py-3 backdrop-blur-sm">
                <img src={imagePreview} alt="" className="h-12 w-12 rounded-lg object-cover" />
                <span className="min-w-0 flex-1 truncate text-sm text-slate-700">{image.name}</span>
                <button
                  onClick={clearImage}
                  className="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <div className="group relative overflow-hidden rounded-[28px] border border-white/80 bg-white/80 shadow-[0_12px_50px_rgba(22,39,28,0.10)] backdrop-blur-xl transition-all focus-within:shadow-[0_18px_60px_rgba(22,39,28,0.15)] focus-within:bg-white/95">
              <textarea
                ref={textareaRef}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={
                  activeMode === "chat"
                    ? "描述你要处理的农业问题，用 @ 引用农场/地块，用 / 使用技能..."
                    : activeMode === "farm"
                    ? "输入农场名称或地块编号，启动综合巡检..."
                    : activeMode === "pest"
                    ? "描述病虫害症状，或上传叶片照片..."
                    : "输入地点和日期，获取天气农事建议..."
                }
                rows={1}
                className="block max-h-[180px] min-h-[56px] w-full resize-none bg-transparent px-6 pt-5 pb-16 text-[16px] leading-6 text-slate-800 outline-none placeholder:text-slate-400"
              />

              <div className="absolute bottom-3 left-4 right-4 flex items-center justify-between">
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => fileRef.current?.click()}
                    className="flex h-9 w-9 items-center justify-center rounded-full text-slate-500 transition-all hover:bg-slate-100 hover:text-slate-800"
                    title="上传图片"
                  >
                    <Camera className="h-[18px] w-[18px]" />
                  </button>
                  <button
                    onClick={() => setWebSearch(!webSearch)}
                    className={`flex h-9 w-9 items-center justify-center rounded-full transition-all ${
                      webSearch
                        ? "bg-emerald-100 text-emerald-700"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                    }`}
                    title="联网搜索"
                  >
                    <Globe className="h-[18px] w-[18px]" />
                  </button>
                  <button
                    onClick={() => setMcpTools(!mcpTools)}
                    className={`flex h-9 w-9 items-center justify-center rounded-full transition-all ${
                      mcpTools
                        ? "bg-emerald-100 text-emerald-700"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
                    }`}
                    title="MCP 工具"
                  >
                    <Wrench className="h-[18px] w-[18px]" />
                  </button>
                </div>

                <button
                  onClick={() => {
                    handleSend(text, image || undefined);
                    setText("");
                    clearImage();
                  }}
                  disabled={isCurrentStreaming || (!text.trim() && !image)}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-[#16271c] text-white shadow-md transition-all hover:bg-[#2a3d2f] hover:scale-105 disabled:scale-100 disabled:bg-slate-200 disabled:text-slate-400"
                >
                  {isCurrentStreaming ? (
                    <Loader2 className="h-[18px] w-[18px] animate-spin" />
                  ) : (
                    <ArrowUp className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            {/* 快捷标签 */}
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              {QUICK_PROMPTS.map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => {
                    handleSend(prompt);
                    setText("");
                    clearImage();
                  }}
                  className="rounded-full border border-slate-200/70 bg-white/50 px-4 py-2 text-xs text-slate-600 backdrop-blur-sm transition-all hover:border-emerald-300 hover:bg-white hover:text-emerald-800"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ===== CHAT MESSAGES =====
  return (
    <>
      <div className="flex-1 overflow-y-auto bg-[#f8faf8]">
        <div className="max-w-3xl mx-auto px-4 py-6">
          {activeConversation()?.hasMoreMessages && (
            <div className="flex justify-center mb-4">
              <button
                onClick={() => activeId && loadMoreMessages(activeId)}
                disabled={isLoadingMore}
                className="px-4 py-1.5 text-sm text-emerald-700 hover:text-emerald-800 disabled:opacity-50 rounded-full border border-emerald-200 hover:border-emerald-400 transition-colors"
              >
                {isLoadingMore ? "加载中..." : "加载更多历史消息"}
              </button>
            </div>
          )}

          {messages.map((msg, index) => (
            <MessageBubble key={index} msg={msg} />
          ))}

          {(isCurrentStreaming || isLoadingMessages) && (
            <div className="flex items-start gap-3 py-3">
              <div className="w-8 h-8 rounded-full bg-emerald-600 flex items-center justify-center text-white">
                <Bot className="w-4 h-4" />
              </div>
              <div className="flex-1">
                {liveProgress.length > 0 ? (
                  <ProgressSteps steps={liveProgress} />
                ) : (
                  <div className="flex items-center gap-2 text-slate-500 text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{isLoadingMessages ? "加载中..." : "思考中..."}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {liveCitations.length > 0 && (
            <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 text-sm">
              <div className="font-medium text-slate-700 mb-2">参考来源</div>
              <ul className="space-y-2">
                {liveCitations.map((c, i) => (
                  <li key={i} className="text-slate-600 text-xs">
                    <span className="font-medium">[{i + 1}] {c.source}</span>
                    {c.chapter && <span className="text-slate-400"> · {c.chapter}</span>}
                    {c.preview && <p className="mt-0.5 text-slate-500 line-clamp-2">{c.preview}</p>}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* 底部输入 */}
      <div className="border-t border-slate-200/60 bg-white/90 backdrop-blur px-4 py-3">
        <div className="max-w-3xl mx-auto">
          <div className="relative flex items-end gap-2 rounded-2xl border border-slate-200 bg-white p-2 shadow-sm transition-all focus-within:border-emerald-400 focus-within:shadow-md">
            <input
              type="file"
              ref={fileRef}
              accept="image/jpeg,image/png,image/webp"
              className="hidden"
              onChange={handleFileChange}
            />
            <button
              onClick={() => fileRef.current?.click()}
              className="mb-1.5 flex h-9 w-9 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100"
            >
              <Camera className="h-[18px] w-[18px]" />
            </button>
            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="继续追问..."
              rows={1}
              className="max-h-[160px] min-h-[40px] flex-1 resize-none bg-transparent py-2.5 text-[15px] text-slate-800 outline-none placeholder:text-slate-400"
            />
            <div className="flex items-center gap-1 mb-1">
              <button
                onClick={() => setWebSearch(!webSearch)}
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm ${
                  webSearch ? "bg-emerald-100 text-emerald-700" : "text-slate-500 hover:bg-slate-100"
                }`}
              >
                <Globe className="h-4 w-4" />
              </button>
              <button
                onClick={() => setMcpTools(!mcpTools)}
                className={`flex h-8 w-8 items-center justify-center rounded-full text-sm ${
                  mcpTools ? "bg-emerald-100 text-emerald-700" : "text-slate-500 hover:bg-slate-100"
                }`}
              >
                <Wrench className="h-4 w-4" />
              </button>
            </div>
            {isCurrentStreaming ? (
              <button
                onClick={() => setStreaming(false)}
                className="mb-1 flex h-9 w-9 items-center justify-center rounded-full bg-slate-800 text-white"
              >
                <Square className="h-4 w-4 fill-current" />
              </button>
            ) : (
              <button
                onClick={() => {
                  handleSend(text, image || undefined);
                  setText("");
                  clearImage();
                }}
                disabled={!text.trim() && !image}
                className="mb-1 flex h-9 w-9 items-center justify-center rounded-full bg-[#16271c] text-white disabled:bg-slate-200"
              >
                <ArrowUp className="h-5 w-5" />
              </button>
            )}
          </div>
          {image && imagePreview && (
            <div className="mt-2 flex items-center gap-2">
              <img src={imagePreview} alt="" className="h-10 w-10 rounded-lg object-cover" />
              <span className="text-xs text-slate-500">{image.name}</span>
              <button onClick={clearImage} className="text-xs text-slate-400 hover:text-slate-700">
                移除
              </button>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function getProgressDetail(stage: string, data: Record<string, unknown>): string | undefined {
  if (stage === "rewrite_done") {
    return data.rewritten ? String(data.rewritten).slice(0, 30) : undefined;
  }
  if (stage === "retrieve_done") {
    return data.hits
      ? `${(data.hits as unknown[]).length} 条结果`
      : data.top_k
      ? `top-${data.top_k}`
      : undefined;
  }
  if (stage === "web_done") {
    return data.results
      ? `${(data.results as unknown[]).length} 条结果`
      : data.skip_reason
      ? String(data.skip_reason)
      : undefined;
  }
  if (stage === "user_context_done") {
    return data.label ? String(data.label) : undefined;
  }
  return undefined;
}
