export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  type?: "text" | "image";
  imageUrl?: string;
  imageResult?: ImageAnalysisResult;
  thinking?: string;
  citations?: Citation[];
  progress?: ProgressEvent[];
  /** 消息状态: success=正常 / error=AI 回复失败 / partial=流式中断 */
  status?: "success" | "error" | "partial";
  /** status=error 时的具体异常信息, 用于红色错误样式渲染 */
  errorMessage?: string;
}

export interface ChatRequest {
  session_id: string;
  question: string;
  top_k: number;
  web_search: boolean;
  mcp_tools: boolean;
}

export interface ProgressEvent {
  stage: string;
  label: string;
  detail: string;
  elapsed_ms: number;
}

export interface Citation {
  source: string;
  chapter?: string;
  category?: string;
  preview?: string;
  score?: number;
}

export interface DetectionItem {
  label: string;
  chinese_name: string;
  confidence: number;
  bbox: number[];
}

export interface ImageAnalysisResult {
  success: boolean;
  detections: DetectionItem[];
  summary: string;
  image_size: number[];
}
