import { useEffect, useRef, useState } from "react";
import {
  Camera,
  DatabaseZap,
  Globe,
  Loader2,
  Send,
  Square,
  Wrench,
} from "lucide-react";
import { ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE } from "../../lib/constants";

interface Props {
  onSend: (text: string, image?: File) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
  compact?: boolean;
  containerClassName?: string;
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
  containerClassName,
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

  const activeCapabilities = [
    webSearch ? "联网检索" : null,
    mcpTools ? "农场工具" : null,
    "知识库",
  ].filter(Boolean);

  return (
    <div
      className={
        containerClassName ??
        `w-full ${compact ? "max-w-2xl" : "max-w-3xl"} mx-auto px-4`
      }
    >
      {image && imagePreview && (
        <div className="mb-2 flex items-center gap-3 rounded-lg border border-border bg-bg-card px-3 py-2 shadow-sm">
          <img
            src={imagePreview}
            alt="待分析图片预览"
            className="h-10 w-10 rounded-md object-cover"
          />
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium text-text-primary">
              {image.name}
            </div>
            <div className="text-xs text-text-muted">将随问题一起提交给智能体处理</div>
          </div>
          <button
            onClick={() => {
              setImage(null);
              setImagePreview(null);
            }}
            className="rounded-md px-2 py-1 text-xs text-text-muted transition-colors hover:bg-bg-hover hover:text-accent-red"
          >
            移除
          </button>
        </div>
      )}

      <div className="rounded-lg border border-border bg-bg-card shadow-[0_10px_30px_rgba(47,83,64,0.08)]">
        <div className="flex items-end gap-2 px-3 py-3">
          <input
            type="file"
            ref={fileRef}
            accept="image/jpeg,image/png,image/webp"
            className="hidden"
            onChange={handleFileChange}
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-text-muted transition-colors hover:bg-primary/10 hover:text-primary"
            title="上传作物或田间图片"
          >
            <Camera className="h-5 w-5" />
          </button>

          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="描述作物、地块、症状，提交给智能体处理..."
            rows={1}
            className="max-h-[200px] min-h-9 flex-1 resize-none bg-transparent py-2 text-sm leading-5 text-text-primary outline-none placeholder:text-text-muted"
            disabled={disabled}
          />

          <div className="flex shrink-0 items-center gap-1">
            <button
              onClick={() => onWebSearchChange?.(!webSearch)}
              className={`flex h-8 w-8 items-center justify-center rounded-md transition-all ${
                webSearch
                  ? "bg-accent-amber/10 text-accent-amber"
                  : "text-text-muted hover:bg-bg-hover hover:text-text-secondary"
              }`}
              title={webSearch ? "联网检索已开启" : "联网检索已关闭"}
            >
              <Globe className="h-4 w-4" />
            </button>

            <button
              onClick={() => onMcpToolsChange?.(!mcpTools)}
              className={`flex h-8 w-8 items-center justify-center rounded-md transition-all ${
                mcpTools
                  ? "bg-primary/10 text-primary"
                  : "text-text-muted hover:bg-bg-hover hover:text-text-secondary"
              }`}
              title={mcpTools ? "农场工具已连接" : "农场工具已关闭"}
            >
              <Wrench className="h-4 w-4" />
            </button>
          </div>

          <div className="mx-0.5 h-6 w-px bg-border" />

          {streaming ? (
            <button
              onClick={onStop}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent-red text-white transition-opacity hover:opacity-90"
              title="停止生成"
            >
              <Square className="h-5 w-5" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={disabled || (!text.trim() && !image)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary text-white transition-all hover:bg-primary-hover disabled:opacity-30"
              title="发送任务"
            >
              {disabled ? (
                <Loader2 className="h-5 w-5 spinner" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-3 py-2">
          <div className="flex items-center gap-1.5 text-xs text-text-muted">
            <DatabaseZap className="h-3.5 w-3.5 text-primary" />
            <span>任务上下文会随对话持续整理</span>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {activeCapabilities.map((item) => (
              <span
                key={item}
                className="rounded-md bg-bg-hover px-2 py-0.5 text-[11px] font-medium text-text-secondary"
              >
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
