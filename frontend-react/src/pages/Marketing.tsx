import { useState } from "react";
import { Megaphone, Copy, Check } from "lucide-react";

export default function Marketing() {
  const [productName, setProductName] = useState("");
  const [features, setFeatures] = useState("");
  const [platform, setPlatform] = useState("douyin");
  const [style, setStyle] = useState("professional");
  const [output, setOutput] = useState("");
  const [copied, setCopied] = useState(false);

  const handleGenerate = () => {
    // Stub: no backend API wired yet
    setOutput(
      `## ${productName} 营销文案\n\n` +
        `**平台**: ${platform} | **风格**: ${style}\n\n` +
        `正在接入 AI 营销生成服务，敬请期待...\n\n` +
        `产品特点: ${features}`
    );
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(output);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold flex items-center gap-2">
        <Megaphone className="w-5 h-5 text-accent-purple" /> 营销生成
      </h1>

      <div className="bg-bg-card rounded-xl border border-border p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            产品名称
          </label>
          <input
            value={productName}
            onChange={(e) => setProductName(e.target.value)}
            placeholder="如：有机草莓"
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            产品特点
          </label>
          <textarea
            value={features}
            onChange={(e) => setFeatures(e.target.value)}
            placeholder="描述产品的核心卖点..."
            rows={4}
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              目标平台
            </label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg-card"
            >
              <option value="douyin">抖音</option>
              <option value="xiaohongshu">小红书</option>
              <option value="live_stream">直播</option>
              <option value="wechat">微信</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              内容风格
            </label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-bg-card"
            >
              <option value="professional">专业</option>
              <option value="funny">趣味</option>
              <option value="emotional">情感</option>
              <option value="storytelling">故事</option>
            </select>
          </div>
        </div>
        <button
          onClick={handleGenerate}
          disabled={!productName}
          className="w-full py-2.5 bg-accent-purple text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
        >
          生成营销文案
        </button>
      </div>

      {output && (
        <div className="bg-bg-card rounded-xl border border-border p-6">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium">生成结果</h3>
            <button
              onClick={handleCopy}
              className="flex items-center gap-1 px-2 py-1 text-xs text-text-muted hover:text-primary border border-border rounded-lg"
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
        </div>
      )}
    </div>
  );
}
