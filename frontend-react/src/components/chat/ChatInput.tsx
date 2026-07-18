import { useEffect, useRef, useState } from "react";
import {
  ArrowUp,
  Camera,
  Globe,
  Loader2,
  Square,
  Wrench,
  X,
} from "lucide-react";
import { ALLOWED_IMAGE_TYPES, MAX_IMAGE_SIZE } from "../../lib/constants";

interface Props {
  onSend: (text: string, image?: File) => void;
  onStop?: () => void;
  disabled?: boolean;
  streaming?: boolean;
  compact?: boolean;
  webSearch?: boolean;
  onWebSearchChange?: (value: boolean) => void;
  mcpTools?: boolean;
  onMcpToolsChange?: (value: boolean) => void;
  mode?: "chat" | "welcome";
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
  mode = "chat",
}: Props) {
  const [text, setText] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const isWelcomeMode = mode === "welcome";

  useEffect(() => {
    const element = textareaRef.current;
    if (!element) return;

    element.style.height = "auto";
    const minimumHeight = isWelcomeMode ? 76 : 44;
    element.style.height = `${Math.max(
      minimumHeight,
      Math.min(element.scrollHeight, 200),
    )}px`;
  }, [isWelcomeMode, text]);

  const clearImage = () => {
    setImage(null);
    setImagePreview(null);
  };

  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed && !image) return;

    onSend(trimmed, image || undefined);
    setText("");
    clearImage();
    textareaRef.current?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (streaming) return;
      handleSend();
    }
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

  const containerWidth = compact ? "max-w-2xl" : "max-w-3xl";
  const toolButtonClass =
    "flex h-10 w-10 items-center justify-center rounded-[8px] text-slate-500 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600/25";

  return (
    <div
      className={`mx-auto w-full ${containerWidth} ${
        isWelcomeMode ? "px-0" : "px-4"
      }`}
    >
      <div
        className={`overflow-hidden border bg-white transition-[border-color,box-shadow] focus-within:border-[#9aafa1] ${
          isWelcomeMode
            ? "rounded-[16px] border-slate-200 shadow-[0_18px_50px_rgba(32,45,38,0.10)] focus-within:shadow-[0_22px_58px_rgba(32,45,38,0.13)]"
            : "rounded-[10px] border-slate-200 shadow-[0_10px_30px_rgba(15,23,42,0.08)]"
        }`}
      >
        <input
          type="file"
          ref={fileRef}
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={handleFileChange}
        />

        {image && imagePreview && (
          <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
            <img
              src={imagePreview}
              alt="已选择的图片"
              className="h-11 w-11 rounded-[6px] object-cover"
            />
            <span className="min-w-0 flex-1 truncate text-sm text-slate-600">
              {image.name}
            </span>
            <button
              type="button"
              onClick={clearImage}
              className="flex h-9 w-9 items-center justify-center rounded-[6px] text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600/25"
              title="移除图片"
              aria-label="移除图片"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            isWelcomeMode
              ? "描述你要处理的农业问题"
              : "输入问题或上传图片..."
          }
          rows={isWelcomeMode ? 3 : 1}
          className={`block max-h-[200px] w-full resize-none bg-transparent px-5 text-[15px] leading-6 text-slate-800 outline-none placeholder:text-slate-400 disabled:cursor-not-allowed disabled:opacity-60 ${
            isWelcomeMode ? "min-h-[76px] pt-5" : "min-h-11 py-3"
          }`}
          disabled={disabled}
        />

        <div className="flex min-h-14 items-center justify-between gap-3 px-3 pb-3">
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className={`${toolButtonClass} hover:bg-slate-100 hover:text-slate-800`}
              title="上传图片"
              aria-label="上传图片"
            >
              <Camera className="h-[18px] w-[18px]" />
            </button>
            <button
              type="button"
              onClick={() => onWebSearchChange?.(!webSearch)}
              className={`${toolButtonClass} ${
                webSearch
                  ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                  : "hover:bg-slate-100 hover:text-slate-800"
              }`}
              title={webSearch ? "关闭联网搜索" : "开启联网搜索"}
              aria-label={webSearch ? "关闭联网搜索" : "开启联网搜索"}
              aria-pressed={webSearch}
            >
              <Globe className="h-[18px] w-[18px]" />
            </button>
            <button
              type="button"
              onClick={() => onMcpToolsChange?.(!mcpTools)}
              className={`${toolButtonClass} ${
                mcpTools
                  ? "bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                  : "hover:bg-slate-100 hover:text-slate-800"
              }`}
              title={mcpTools ? "关闭 MCP 工具" : "开启 MCP 工具"}
              aria-label={mcpTools ? "关闭 MCP 工具" : "开启 MCP 工具"}
              aria-pressed={mcpTools}
            >
              <Wrench className="h-[18px] w-[18px]" />
            </button>
          </div>

          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="flex h-10 w-10 items-center justify-center rounded-[8px] bg-[#17201b] text-white transition-colors hover:bg-[#2b3730] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/25"
              title="停止生成"
              aria-label="停止生成"
            >
              <Square className="h-4 w-4 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleSend}
              disabled={disabled || (!text.trim() && !image)}
              className="flex h-10 w-10 items-center justify-center rounded-[8px] bg-[#17201b] text-white transition-colors hover:bg-[#2b3730] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900/25 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
              title="发送"
              aria-label="发送"
            >
              {disabled ? (
                <Loader2 className="h-[18px] w-[18px] animate-spin" />
              ) : (
                <ArrowUp className="h-5 w-5" />
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
