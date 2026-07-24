import { useState } from "react";
import {
  Megaphone,
  Copy,
  Check,
  Sparkles,
  Video,
  BookImage,
  Radio,
  MessageCircle,
} from "lucide-react";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";

const PLATFORMS = [
  { value: "douyin", label: "抖音", icon: Video, color: "text-accent-red" },
  { value: "xiaohongshu", label: "小红书", icon: BookImage, color: "text-accent-amber" },
  { value: "live_stream", label: "直播", icon: Radio, color: "text-accent-purple" },
  { value: "wechat", label: "微信", icon: MessageCircle, color: "text-accent-green" },
];

const STYLES = [
  { value: "professional", label: "专业严谨" },
  { value: "funny", label: "轻松趣味" },
  { value: "emotional", label: "情感共鸣" },
  { value: "storytelling", label: "故事叙述" },
];

export default function Marketing() {
  const [productName, setProductName] = useState("");
  const [features, setFeatures] = useState("");
  const [platform, setPlatform] = useState("douyin");
  const [style, setStyle] = useState("professional");
  const [output, setOutput] = useState("");
  const [copied, setCopied] = useState(false);
  const [generating, setGenerating] = useState(false);

  const handleGenerate = async () => {
    if (!productName) return;
    setGenerating(true);
    // Simulate generation delay
    await new Promise((r) => setTimeout(r, 1500));
    setOutput(
      `## ${productName} 营销文案\n\n` +
        `**平台**: ${PLATFORMS.find((p) => p.value === platform)?.label} | **风格**: ${STYLES.find((s) => s.value === style)?.label}\n\n` +
        `> 🚀 AI 营销生成服务即将上线，敬请期待！\n\n` +
        `**产品特点**\n${features}`
    );
    setGenerating(false);
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <WorkspaceLayout
      title="营销生成"
      icon={Megaphone}
      iconColor="text-accent-purple"
      description="为您的农产品生成专业营销文案"
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-bg-card rounded-xl border border-border p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              产品名称
            </label>
            <input
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              placeholder="如：有机草莓、富硒大米"
              className="w-full px-3 py-2.5 text-sm border border-border rounded-lg outline-none focus:border-primary"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              产品特点
            </label>
            <textarea
              value={features}
              onChange={(e) => setFeatures(e.target.value)}
              placeholder="描述产品的核心卖点、产地优势、品质特点..."
              rows={4}
              className="w-full px-3 py-2.5 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              目标平台
            </label>
            <div className="grid grid-cols-2 gap-2">
              {PLATFORMS.map((p) => (
                <button
                  key={p.value}
                  onClick={() => setPlatform(p.value)}
                  className={`flex items-center gap-2 px-3 py-2.5 text-sm rounded-lg border transition-all ${
                    platform === p.value
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border hover:border-primary/50 text-text-secondary"
                  }`}
                >
                  <p.icon className={`w-4 h-4 ${platform === p.value ? "text-primary" : p.color}`} />
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              内容风格
            </label>
            <div className="flex flex-wrap gap-2">
              {STYLES.map((s) => (
                <button
                  key={s.value}
                  onClick={() => setStyle(s.value)}
                  className={`px-3 py-1.5 text-sm rounded-lg border transition-all ${
                    style === s.value
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border hover:border-primary/50 text-text-secondary"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={generating || !productName}
            className="flex items-center justify-center gap-2 w-full py-2.5 bg-accent-purple text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {generating ? (
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full spinner" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {generating ? "生成中..." : "生成营销文案"}
          </button>
        </div>

        {/* Output */}
        <div className="bg-bg-card rounded-xl border border-border p-6">
          {output ? (
            <>
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-text-primary">
                  生成结果
                </h3>
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-primary border border-border rounded-lg transition-colors"
                >
                  {copied ? (
                    <Check className="w-3 h-3" />
                  ) : (
                    <Copy className="w-3 h-3" />
                  )}
                  {copied ? "已复制" : "复制"}
                </button>
              </div>
              <div className="text-sm text-text-secondary whitespace-pre-line markdown-body">
                {output}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <Megaphone className="w-12 h-12 text-text-muted opacity-30 mb-3" />
              <div className="text-sm text-text-muted">
                填写产品信息后点击生成
              </div>
              <div className="text-xs text-text-muted mt-1">
                AI 将为您生成专业的营销文案
              </div>
            </div>
          )}
        </div>
      </div>
    </WorkspaceLayout>
  );
}
