import { useState } from "react";
import { Bug, Send, Loader2 } from "lucide-react";
import { chatStream } from "../api/chat";
import { consumeSSE } from "../api/client";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

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
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold flex items-center gap-2">
        <Bug className="w-5 h-5 text-accent-red" /> 病虫害诊断
      </h1>

      <div className="bg-bg-card rounded-xl border border-border p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            作物种类
          </label>
          <input
            value={cropType}
            onChange={(e) => setCropType(e.target.value)}
            placeholder="如：番茄、水稻、苹果"
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            发病部位
          </label>
          <select
            value={affectedPart}
            onChange={(e) => setAffectedPart(e.target.value)}
            className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg-card"
          >
            <option value="leaf">叶片</option>
            <option value="stem">茎部</option>
            <option value="root">根部</option>
            <option value="fruit">果实</option>
            <option value="flower">花朵</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            症状描述
          </label>
          <textarea
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            placeholder="详细描述病虫害症状，如颜色、形状、范围等..."
            rows={4}
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
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

      {result && (
        <div className="bg-bg-card rounded-xl border border-border p-6">
          <h3 className="text-sm font-medium mb-3">诊断结果</h3>
          <div className="text-sm markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{result}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
