import { useState, useRef, useEffect } from "react";
import { Send, Camera, Loader2, Square, Globe, Wrench } from "lucide-react";
import { ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE } from "../../lib/constants";

interface Props {
  onSend: (text: string, image?: File) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
  compact?: boolean;
  webSearch?: boolean;
  onWebSearchChange?: (v: boolean) => void;
  mcpTools?: boolean;
  onMcpToolsChange?: (v: boolean) => void;
}

export default function ChatInput({
  onSend,
  onStop,
  disabled,
  streaming,
  compact,
  webSearch = false,
  onWebSearchChange,
  mcpTools = true,
  onMcpToolsChange,
}: Props) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 200) + "px";
    }
  }, [text]);

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && !image) return;
    onSend(trimmed, image || undefined);
    setText("");
    setImage(null);
    setImagePreview(null);
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (streaming) return;
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
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
    e.target.value = "";
  };

  return (
    <div className={`w-full ${compact ? "max-w-2xl" : "max-w-3xl"} mx-auto px-4`}>
      {/* Image preview */}
      {image && imagePreview && (
        <div className="flex items-center gap-2 mb-2 px-3 py-2 bg-bg-hover rounded-lg">
          <img
            src={imagePreview}
            alt="preview"
            className="w-10 h-10 object-cover rounded"
          />
          <span className="text-sm truncate flex-1">{image.name}</span>
          <button
            onClick={() => {
              setImage(null);
              setImagePreview(null);
            }}
            className="text-text-muted hover:text-accent-red text-xs"
          >
            移除
          </button>
        </div>
      )}

      {/* Input bar */}
      <div className="flex items-end gap-2 p-3 bg-bg-card border border-border rounded-2xl shadow-sm">
        <input
          type="file"
          ref={fileRef}
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="p-2 text-text-muted hover:text-accent-green rounded-lg transition-colors flex-shrink-0"
          title="上传图片"
        >
          <Camera className="w-5 h-5" />
        </button>
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题或上传图片..."
          rows={1}
          className="flex-1 bg-transparent outline-none text-sm resize-none max-h-[200px] py-2"
          disabled={disabled}
        />

        {/* Toggle buttons */}
        <div className="flex items-center gap-1 flex-shrink-0">
          {/* Web search toggle */}
          <button
            onClick={() => onWebSearchChange?.(!webSearch)}
            className={`p-1.5 rounded-lg transition-all ${
              webSearch
                ? "text-accent-amber bg-accent-amber/10"
                : "text-text-muted hover:text-text-secondary"
            }`}
            title={webSearch ? "联网搜索：已开启" : "联网搜索：已关闭"}
          >
            <Globe className="w-4 h-4" />
          </button>

          {/* MCP tools toggle */}
          <button
            onClick={() => onMcpToolsChange?.(!mcpTools)}
            className={`p-1.5 rounded-lg transition-all ${
              mcpTools
                ? "text-primary bg-primary/10"
                : "text-text-muted hover:text-text-secondary"
            }`}
            title={mcpTools ? "MCP 工具：已开启" : "MCP 工具：已关闭"}
          >
            <Wrench className="w-4 h-4" />
          </button>
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-border mx-0.5" />

        {streaming ? (
          <button
            onClick={onStop}
            className="p-2 bg-accent-red text-white rounded-lg hover:opacity-90 transition-opacity flex-shrink-0"
            title="停止生成"
          >
            <Square className="w-5 h-5" />
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={disabled || (!text.trim() && !image)}
            className="p-2 bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-30 transition-all flex-shrink-0"
          >
            {disabled ? (
              <Loader2 className="w-5 h-5 spinner" />
            ) : (
              <Send className="w-5 h-5" />
            )}
          </button>
        )}
      </div>

      {/* Status indicators */}
      <div className="flex items-center justify-center gap-3 mt-2">
        {webSearch && (
          <span className="inline-flex items-center gap-1 text-[11px] text-accent-amber">
            <Globe className="w-3 h-3" />
            联网搜索
          </span>
        )}
        {mcpTools && (
          <span className="inline-flex items-center gap-1 text-[11px] text-primary">
            <Wrench className="w-3 h-3" />
            MCP 工具
          </span>
        )}
        {!webSearch && !mcpTools && (
          <span className="text-[11px] text-text-muted">
            AgroAgentOS · 基于 RAG + 多智能体的农业 AI 助手
          </span>
        )}
      </div>
    </div>
  );
}
