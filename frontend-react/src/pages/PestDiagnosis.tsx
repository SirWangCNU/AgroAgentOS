import { useState } from "react";
import {
  Bug,
  Send,
  Loader2,
  Leaf,
  TreePine,
  TreeDeciduous,
  Apple,
  Flower2,
  Upload,
  X,
  ScanLine,
} from "lucide-react";
import { chatStream } from "../api/chat";
import { analyzeImage } from "../api/image";
import { consumeSSE } from "../api/client";
import type { ImageAnalysisResult } from "../types/chat";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";

const AFFECTED_PARTS = [
  { value: "leaf", label: "叶片", icon: Leaf, color: "text-accent-green" },
  { value: "stem", label: "茎部", icon: TreePine, color: "text-accent-amber" },
  { value: "root", label: "根部", icon: TreeDeciduous, color: "text-accent-amber" },
  { value: "fruit", label: "果实", icon: Apple, color: "text-accent-red" },
  { value: "flower", label: "花朵", icon: Flower2, color: "text-accent-purple" },
];

export default function PestDiagnosis() {
  const [cropType, setCropType] = useState("");
  const [symptoms, setSymptoms] = useState("");
  const [affectedPart, setAffectedPart] = useState("leaf");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(false);

  // Image upload state
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [imageResult, setImageResult] = useState<ImageAnalysisResult | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setImage(file);
    setImageResult(null);
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    } else {
      setImagePreview(null);
    }
  };

  const handleAnalyzeImage = async () => {
    if (!image) return;
    setAnalyzing(true);
    try {
      const resp = await analyzeImage(image);
      setImageResult(resp);
      // Auto-fill crop type and symptoms from detection if empty
      if (resp.success && resp.detections.length > 0) {
        if (!cropType) {
          setCropType("（请补充作物种类）");
        }
        const detectionSummary = resp.detections
          .slice(0, 3)
          .map((d) => `${d.chinese_name}（置信度 ${(d.confidence * 100).toFixed(0)}%）`)
          .join("、");
        setSymptoms(
          (prev) =>
            prev
              ? `${prev}\n\n[图片识别结果] ${detectionSummary}`
              : `[图片识别结果] ${detectionSummary}`
        );
      }
    } catch (err: any) {
      setImageResult({
        success: false,
        detections: [],
        summary: `图片识别失败: ${err.message}`,
        image_size: [],
      });
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDiagnose = async () => {
    if (!cropType || !symptoms) return;

    setLoading(true);
    setResult("");

    // Compose question with image recognition context
    const imageContext = imageResult?.success && imageResult.detections.length > 0
      ? `\n\n[图片识别参考] ${imageResult.detections
          .map((d) => `${d.chinese_name}(${(d.confidence * 100).toFixed(0)}%)`)
          .join(", ")}`
      : "";

    const question = `请诊断以下病虫害：\n作物：${cropType}\n症状：${symptoms}\n发病部位：${affectedPart}${imageContext}\n请给出详细的诊断和防治方案。`;

    try {
      const resp = await chatStream({
        session_id: "pest-diagnosis",
        question,
        top_k: 3,
        web_search: false,
        mcp_tools: false,
      });

      let content = "";
      for await (const event of consumeSSE(resp)) {
        if (event.type === "token") {
          content += event.content;
          setResult(content);
        }
      }
    } catch (err: any) {
      setResult(`诊断失败: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <WorkspaceLayout
      title="病虫害诊断"
      icon={Bug}
      iconColor="text-accent-red"
      description="支持图片识别 + 文字描述，AI 智能诊断病虫害并给出防治方案"
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-bg-card rounded-xl border border-border p-6 space-y-5">
          {/* Image upload */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              上传病叶图片（可选）
            </label>
            {imagePreview ? (
              <div className="relative">
                <img
                  src={imagePreview}
                  alt="preview"
                  className="w-full h-40 object-cover rounded-lg border border-border"
                />
                <button
                  onClick={() => {
                    setImage(null);
                    setImagePreview(null);
                    setImageResult(null);
                  }}
                  className="absolute top-2 right-2 p-1 bg-black/50 rounded-full text-white hover:bg-black/70 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
                <button
                  onClick={handleAnalyzeImage}
                  disabled={analyzing}
                  className="absolute bottom-2 right-2 flex items-center gap-1 px-3 py-1.5 bg-accent-blue/90 text-white text-xs font-medium rounded-lg hover:bg-accent-blue transition-colors disabled:opacity-50"
                >
                  {analyzing ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <ScanLine className="w-3.5 h-3.5" />
                  )}
                  {analyzing ? "识别中..." : "AI 识别"}
                </button>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-primary/50 transition-colors">
                <Upload className="w-6 h-6 text-text-muted mb-1" />
                <span className="text-xs text-text-muted">
                  点击上传图片 (JPEG/PNG/WebP, 最大 10MB)
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageChange}
                  className="hidden"
                />
              </label>
            )}
          </div>

          {/* Image recognition result */}
          {imageResult && (
            <div
              className={`rounded-lg px-4 py-3 text-sm ${
                imageResult.success
                  ? "bg-accent-blue/5 border border-accent-blue/20 text-accent-blue"
                  : "bg-accent-red/5 border border-accent-red/20 text-accent-red"
              }`}
            >
              <div className="flex items-center gap-1.5 mb-1 font-semibold">
                <ScanLine className="w-4 h-4" />
                YOLO 识别结果
              </div>
              <div className="text-xs">{imageResult.summary}</div>
              {imageResult.success && imageResult.detections.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {imageResult.detections.slice(0, 5).map((d, i) => (
                    <span
                      key={i}
                      className="text-[11px] px-2 py-0.5 rounded-full bg-white/60"
                    >
                      {d.chinese_name} {(d.confidence * 100).toFixed(0)}%
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              作物种类
            </label>
            <input
              value={cropType}
              onChange={(e) => setCropType(e.target.value)}
              placeholder="如：番茄、水稻、苹果"
              className="w-full px-3 py-2.5 text-sm border border-border rounded-lg outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              发病部位
            </label>
            <div className="flex flex-wrap gap-2">
              {AFFECTED_PARTS.map((part) => (
                <button
                  key={part.value}
                  onClick={() => setAffectedPart(part.value)}
                  className={`flex items-center gap-1.5 px-3 py-2 text-sm rounded-lg border transition-all ${
                    affectedPart === part.value
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border hover:border-primary/50 text-text-secondary"
                  }`}
                >
                  <part.icon
                    className={`w-4 h-4 ${
                      affectedPart === part.value ? "text-primary" : part.color
                    }`}
                  />
                  {part.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              症状描述
            </label>
            <textarea
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
              placeholder="详细描述病虫害症状，如颜色、形状、范围、发展程度等..."
              rows={5}
              className="w-full px-3 py-2.5 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
            />
          </div>

          <button
            onClick={handleDiagnose}
            disabled={loading || !cropType || !symptoms}
            className="flex items-center justify-center gap-2 w-full py-2.5 bg-accent-red text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 spinner" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            {loading ? "诊断中..." : "开始诊断"}
          </button>
        </div>

        {/* Result */}
        <div className="bg-bg-card rounded-xl border border-border p-6">
          {result ? (
            <>
              <h3 className="text-sm font-semibold text-text-primary mb-4">
                诊断结果
              </h3>
              <div className="text-sm markdown-body overflow-auto max-h-[60vh]">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result}
                </ReactMarkdown>
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <Bug className="w-12 h-12 text-text-muted opacity-30 mb-3" />
              <div className="text-sm text-text-muted">
                上传图片或填写信息后开始诊断
              </div>
              <div className="text-xs text-text-muted mt-1">
                AI 将基于图片识别和描述给出专业诊断
              </div>
            </div>
          )}
        </div>
      </div>
    </WorkspaceLayout>
  );
}
