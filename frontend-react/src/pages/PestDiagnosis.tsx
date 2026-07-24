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
} from "lucide-react";
import { chatStream } from "../api/chat";
import { consumeSSE } from "../api/client";
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

  const handleDiagnose = async () => {
    if (!cropType || !symptoms) return;

    setLoading(true);
    setResult("");
    const question = `请诊断以下病虫害：\n作物：${cropType}\n症状：${symptoms}\n发病部位：${affectedPart}\n请给出详细的诊断和防治方案。`;

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
      description="基于症状描述，AI 智能诊断病虫害并给出防治方案"
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-bg-card rounded-xl border border-border p-6 space-y-5">
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
                填写作物和症状信息后开始诊断
              </div>
              <div className="text-xs text-text-muted mt-1">
                AI 将根据描述给出专业的诊断和防治建议
              </div>
            </div>
          )}
        </div>
      </div>
    </WorkspaceLayout>
  );
}
