import { useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import { chatStream } from "../api/chat";
import { analyzeImage } from "../api/image";
import { consumeSSE } from "../api/client";
import { addSessionMessage } from "../api/sessions";
import { useConversationStore } from "../stores/conversation";
import { useUIStore } from "../stores/ui";
import WelcomeScreen from "../components/chat/WelcomeScreen";
import MessageBubble from "../components/chat/MessageBubble";
import ChatInput from "../components/chat/ChatInput";

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
  } = useConversationStore();
  const showToast = useUIStore((s) => s.showToast);

  // Sync URL param with store
  useEffect(() => {
    if (sessionId && sessionId !== activeId) {
      setActive(sessionId);
      loadMessages(sessionId);
    }
  }, [sessionId, activeId, setActive, loadMessages]);

  // Auto-scroll on new messages
  const conversation = activeConversation();
  const messages = conversation?.messages || [];

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (text: string, image?: File) => {
    let finalQuestion = text;

    // Ensure we have an active conversation
    let convId = activeId;
    if (!convId) {
      convId = await createNew();
    }

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
        // Show image in chat
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
        web_search: false,
        mcp_tools: true,
      });

      let assistantContent = "";
      let thinkingContent = "";

      for await (const event of consumeSSE(resp)) {
        const ev = event as Record<string, unknown>;
        if (ev.type === "thinking") {
          thinkingContent += ev.content as string;
          setThinking(thinkingContent);
        } else if (ev.type === "token") {
          assistantContent += ev.content as string;
          updateLastAssistant(assistantContent);
        } else if (ev.type === "error") {
          showToast(`错误: ${ev.message}`, "error");
        }
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
          {messages.map((msg, i) => (
            <MessageBubble key={i} msg={msg} />
          ))}
          {isStreaming && (
            <div className="flex items-center gap-2 text-text-muted text-sm mb-4">
              <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
              正在思考...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div className="pb-6 pt-2">
        <ChatInput
          onSend={handleSend}
          streaming={isStreaming}
          disabled={isStreaming}
        />
      </div>
    </>
  );
}
