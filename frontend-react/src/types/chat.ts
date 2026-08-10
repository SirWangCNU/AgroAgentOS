export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  type?: "text" | "image";
  imageUrl?: string;
  imageResult?: ImageAnalysisResult;
  thinking?: string;
  citations?: Citation[];
  progress?: ProgressEvent[];
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

export interface ProgressStep {
  id: string;
  stage: string;
  label: string;
  detail?: string;
  status: "running" | "done" | "error" | "skipped";
  elapsed_ms?: number;
  data?: Record<string, unknown>;
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
  diagnosis?: string;
  model?: string;
  image_size: number[];
}
