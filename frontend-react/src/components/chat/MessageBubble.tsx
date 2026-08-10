import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Brain,
  ChevronDown,
  ChevronUp,
  Leaf,
  User,
  BookOpen,
} from "lucide-react";
import type { ChatMessage } from "../../types/chat";

export default function MessageBubble({ msg }: { msg: ChatMessage }) {
  const [thinkingOpen, setThinkingOpen] = useState(false);
  const [citationsOpen, setCitationsOpen] = useState(false);

  if (msg.role === "user") {
    return (
      <div className="flex justify-end mb-6">
        <div className="flex items-start gap-2 max-w-[80%]">
          <div className="overflow-hidden rounded-2xl rounded-br-sm bg-primary text-white shadow-sm">
            {msg.imageUrl && (
              <img
                src={msg.imageUrl}
                alt="用户上传的作物图片"
                className="max-h-72 w-full max-w-sm object-cover"
              />
            )}
            <div className="px-4 py-3 text-sm whitespace-pre-wrap">
              {msg.content}
            </div>
          </div>
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
            <User className="w-4 h-4 text-primary" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-6">
      <div className="flex items-start gap-2 max-w-[85%]">
        <div className="w-8 h-8 rounded-full bg-accent-green/20 flex items-center justify-center flex-shrink-0">
          <Leaf className="w-4 h-4 text-accent-green" />
        </div>
        <div className="space-y-2 flex-1 min-w-0">
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
          <div className="px-4 py-3 bg-bg-card border border-border rounded-2xl rounded-bl-sm text-sm markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {msg.content || "..."}
            </ReactMarkdown>
          </div>

          {/* Citations */}
          {msg.citations && msg.citations.length > 0 && (
            <div className="border border-border rounded-lg overflow-hidden">
              <button
                onClick={() => setCitationsOpen(!citationsOpen)}
                className="flex items-center gap-2 w-full px-3 py-2 text-xs text-text-muted hover:bg-bg-hover transition-colors"
              >
                <BookOpen className="w-3 h-3 text-accent-blue" />
                <span>
                  引用来源 ({msg.citations.length})
                </span>
                {citationsOpen ? (
                  <ChevronUp className="w-3 h-3 ml-auto" />
                ) : (
                  <ChevronDown className="w-3 h-3 ml-auto" />
                )}
              </button>
              {citationsOpen && (
                <div className="px-3 pb-3 space-y-2 max-h-60 overflow-y-auto">
                  {msg.citations.map((c, i) => (
                    <div
                      key={i}
                      className="text-xs border-l-2 border-accent-blue/30 pl-2"
                    >
                      <div className="font-medium text-text-secondary">
                        {c.source}
                        {c.chapter && (
                          <span className="text-text-muted">
                            {" "}
                            · {c.chapter}
                          </span>
                        )}
                        {c.score != null && (
                          <span className="text-accent-blue ml-1">
                            {(c.score * 100).toFixed(0)}%
                          </span>
                        )}
                      </div>
                      {c.preview && (
                        <div className="text-text-muted mt-0.5 line-clamp-2">
                          {c.preview}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
