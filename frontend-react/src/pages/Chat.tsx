import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Send,
  Globe,
  Wrench,
  Camera,
  X,
  Brain,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Loader2,
} from "lucide-react";
import { chatStream } from "../api/chat";
import { analyzeImage } from "../api/image";
import { consumeSSE } from "../api/client";
import { useChatStore } from "../stores/chat";
import { useUIStore } from "../stores/ui";
import type { ChatMessage, ImageAnalysisResult } from "../types/chat";
import { ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE } from "../lib/constants";

export default function Chat() {
  const store = useChatStore();
  const showToast = useUIStore((s) => s.showToast);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [store.messages]);

  const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
      showToast("请上传 JPEG/PNG/WebP 格式的图片", "error");
      return;
    }
    if (file.size > MAX_IMAGE_SIZE) {
      showToast("图片文件过大，限制 10MB", "error");
      return;
    }
    setSelectedImage(file);
    const reader = new FileReader();
    reader.onload = () => setImagePreview(reader.result as string);
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const handleSend = async () => {
    const question = input.trim();
    if (!question && !selectedImage) return;

    setInput("");
    let finalQuestion = question;
    let imageResult: ImageAnalysisResult | undefined;

    // Image analysis
    if (selectedImage) {
      const file = selectedImage;
      setSelectedImage(null);
      setImagePreview(null);

      try {
        imageResult = await analyzeImage(file);
        if (imageResult.success && imageResult.detections.length > 0) {
          const detText = imageResult.detections
            .map((d) => `${d.chinese_name}(${(d.confidence * 100).toFixed(0)}%)`)
            .join(", ");
          const userNote = question ? `\n用户补充说明: ${question}` : "";
          finalQuestion = `[图片分析] 识别到: ${detText}。\n${imageResult.summary}${userNote}\n请根据识别结果给出详细的病虫害防治建议。`;
        } else {
          finalQuestion = `[图片分析] ${imageResult.summary || "未识别到病虫害"}${question ? `\n用户说明: ${question}` : ""}`;
        }
      } catch (err: any) {
        showToast(`图片分析失败: ${err.message}`, "error");
        return;
      }
    }

    // Add user message
    store.addMessage({
      role: "user",
      content: question || "(图片分析)",
      type: selectedImage ? "image" : "text",
    });

    // Reset progress
    store.citations.forEach(() => {});
    setStreaming(true);

    try {
      const resp = await chatStream({
        session_id: "web-chat",
        question: finalQuestion,
        top_k: 3,
        web_search: store.webEnabled,
        mcp_tools: store.mcpEnabled,
      });

      let assistantContent = "";
      let thinkingContent = "";

      for await (const event of consumeSSE(resp)) {
        const ev = event as Record<string, unknown>;
        if (ev.type === "progress") {
          store.addProgress({
            stage: ev.stage as string,
            label: ev.label as string,
            detail: ev.detail as string,
            elapsed_ms: ev.elapsed_ms as number,
          });
        } else if (ev.type === "thinking") {
          thinkingContent += ev.content as string;
          store.setThinking(thinkingContent);
        } else if (ev.type === "token") {
          assistantContent += ev.content as string;
          store.updateLastAssistant(assistantContent);
        } else if (ev.type === "citations") {
          store.setCitations(ev.citations as any[]);
        } else if (ev.type === "error") {
          showToast(`错误: ${ev.message}`, "error");
        }
      }
    } catch (err: any) {
      showToast(`网络错误: ${err.message}`, "error");
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex h-full gap-4">
      {/* Chat Panel */}
      <div className="flex-1 flex flex-col bg-bg-card rounded-xl border border-border overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {store.messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-text-muted text-sm">
              输入问题开始对话，或上传图片识别病虫害
            </div>
          )}
          {store.messages.map((msg, i) => (
            <ChatBubble key={i} msg={msg} />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Image preview */}
        {selectedImage && imagePreview && (
          <div className="flex items-center gap-3 px-4 py-2 border-t border-border bg-bg-hover">
            <img
              src={imagePreview}
              alt="preview"
              className="w-12 h-12 object-cover rounded-lg"
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm truncate">{selectedImage.name}</div>
              <div className="text-xs text-text-muted">待识别</div>
            </div>
            <button
              onClick={() => {
                setSelectedImage(null);
                setImagePreview(null);
              }}
              className="p-1 text-text-muted hover:text-accent-red"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Input bar */}
        <div className="flex items-center gap-2 px-4 py-3 border-t border-border">
          <input
            type="file"
            ref={fileInputRef}
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleImageSelect}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="p-2 text-accent-green hover:bg-primary-light rounded-lg transition-colors"
            title="上传图片识别病虫害"
          >
            <Camera className="w-5 h-5" />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入问题或上传图片..."
            className="flex-1 px-3 py-2 text-sm bg-bg-hover rounded-lg outline-none focus:ring-1 focus:ring-primary transition-shadow"
            disabled={streaming}
          />
          <button
            onClick={() => store.toggleWeb()}
            className={`p-2 rounded-lg transition-colors text-xs flex items-center gap-1 ${
              store.webEnabled
                ? "bg-accent-blue/10 text-accent-blue"
                : "text-text-muted hover:bg-bg-hover"
            }`}
          >
            <Globe className="w-4 h-4" />
            <span>联网</span>
          </button>
          <button
            onClick={() => store.toggleMcp()}
            className={`p-2 rounded-lg transition-colors text-xs flex items-center gap-1 ${
              store.mcpEnabled
                ? "bg-accent-amber/10 text-accent-amber"
                : "text-text-muted hover:bg-bg-hover"
            }`}
          >
            <Wrench className="w-4 h-4" />
            <span>工具</span>
          </button>
          <button
            onClick={handleSend}
            disabled={streaming || (!input.trim() && !selectedImage)}
            className="p-2 bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
          >
            {streaming ? (
              <Loader2 className="w-5 h-5 spinner" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        </div>
      </div>

      {/* Context Panel */}
      <div className="w-72 hidden lg:flex flex-col bg-bg-card rounded-xl border border-border overflow-hidden">
        <div className="flex border-b border-border">
          {(["detail", "tools", "stats"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => store.setCtxTab(tab)}
              className={`flex-1 py-2 text-xs font-medium transition-colors ${
                store.activeCtxTab === tab
                  ? "text-primary border-b-2 border-primary"
                  : "text-text-muted"
              }`}
            >
              {tab === "detail" ? "知识来源" : tab === "tools" ? "工具调用" : "统计"}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-3 text-sm">
          {store.activeCtxTab === "detail" && (
            <div className="space-y-3">
              {store.citations.length > 0 ? (
                store.citations.map((c, i) => (
                  <div key={i} className="p-2 bg-bg-hover rounded-lg">
                    <div className="flex items-center gap-1 text-xs font-medium">
                      <BookOpen className="w-3 h-3" />
                      {c.source}
                    </div>
                    {c.preview && (
                      <div className="text-xs text-text-muted mt-1 line-clamp-3">
                        {c.preview}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="text-text-muted text-xs">暂无知识来源</div>
              )}
            </div>
          )}
          {store.activeCtxTab === "tools" && (
            <div className="text-text-muted text-xs">暂无工具调用</div>
          )}
          {store.activeCtxTab === "stats" && (
            <div className="text-text-muted text-xs">暂无统计数据</div>
          )}
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ msg }: { msg: ChatMessage }) {
  const [thinkingOpen, setThinkingOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[70%] bg-primary text-white px-4 py-2 rounded-2xl rounded-br-sm text-sm">
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[80%] space-y-2">
        {/* Thinking bubble */}
        {msg.thinking && (
          <div className="border border-border rounded-lg overflow-hidden">
            <button
              onClick={() => setThinkingOpen(!thinkingOpen)}
              className="flex items-center gap-2 w-full px-3 py-2 text-xs text-text-muted hover:bg-bg-hover transition-colors"
            >
              <Brain className="w-3 h-3 text-accent-purple" />
              <span>思考过程</span>
              {thinkingOpen ? (
                <ChevronUp className="w-3 h-3 ml-auto" />
              ) : (
                <ChevronDown className="w-3 h-3 ml-auto" />
              )}
            </button>
            {thinkingOpen && (
              <div className="px-3 pb-3 text-xs text-text-secondary max-h-48 overflow-y-auto">
                {msg.thinking}
              </div>
            )}
          </div>
        )}

        {/* Main content */}
        <div className="bg-bg-hover px-4 py-3 rounded-2xl rounded-bl-sm text-sm markdown-body">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {msg.content || "..."}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
