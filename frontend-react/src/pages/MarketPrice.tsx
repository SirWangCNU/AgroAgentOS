import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Search,
  Package,
  Scale,
  FileText,
  Lightbulb,
  AlertTriangle,
  MapPin,
} from "lucide-react";
import { getMarketAnalysis, getMarketOverview } from "../api/market";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import StatCard from "../components/ui/StatCard";
import LoadingGrid from "../components/ui/LoadingGrid";

const CROPS = ["水稻", "小麦", "玉米", "大豆", "苹果", "番茄", "黄瓜", "辣椒"];

function trendText(trend: string): string {
  return { up: "上涨", down: "下跌", stable: "平稳" }[trend] || trend;
}

export default function MarketPrice() {
  const [crop, setCrop] = useState("水稻");
  const [inputCrop, setInputCrop] = useState("水稻");
  const [location, setLocation] = useState("");
  const [inputLocation, setInputLocation] = useState("");

  const { data: overview, isLoading } = useQuery({
    queryKey: ["market-overview", crop, location],
    queryFn: () => getMarketOverview(crop, location, false),
    staleTime: 30 * 60 * 1000, // 30 分钟
  });

  const { data: analysis, isLoading: isAnalysisLoading } = useQuery({
    queryKey: ["market-analysis", crop, location],
    queryFn: () => getMarketAnalysis(crop, location),
    staleTime: 30 * 60 * 1000, // 30 分钟
    enabled: !!overview,
  });

  const marketAnalysis = analysis ?? overview?.analysis ?? null;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputCrop.trim()) setCrop(inputCrop.trim());
    setLocation(inputLocation.trim());
  };

  return (
    <WorkspaceLayout
      title="市场行情"
      icon={TrendingUp}
      iconColor="text-accent-green"
      description="农产品价格、供需分析、政策补贴与销售建议"
    >
      {/* 搜索栏 */}
      <form onSubmit={handleSearch} className="mb-6 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={inputCrop}
            onChange={(e) => setInputCrop(e.target.value)}
            placeholder="输入农产品名称..."
            className="w-full pl-9 pr-4 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary bg-bg-card transition-colors"
          />
        </div>
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
          <input
            value={inputLocation}
            onChange={(e) => setInputLocation(e.target.value)}
            placeholder="位置 (空则用默认)"
            className="w-full pl-9 pr-4 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary bg-bg-card transition-colors"
          />
        </div>
      </form>

      {/* 快捷作物选择 */}
      <div className="mb-6 flex flex-wrap gap-2">
        {CROPS.map((c) => (
          <button
            key={c}
            onClick={() => {
              setCrop(c);
              setInputCrop(c);
            }}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
              crop === c
                ? "border-primary bg-primary/10 text-primary"
                : "border-border bg-bg-card text-text-muted hover:border-primary"
            }`}
          >
            {c}
          </button>
        ))}
      </div>

      {isLoading ? (
        <LoadingGrid rows={2} cols={3} height="h-24" />
      ) : overview ? (
        <div className="space-y-6">
          {/* 概览统计卡片 */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="当前均价"
              value={overview.price ? `¥${overview.price.average_price}` : "-"}
              sub="元/公斤"
              icon={Package}
              color="text-accent-green"
            />
            <StatCard
              label="价格趋势"
              value={
                overview.price ? trendText(overview.price.trend) : "-"
              }
              sub={overview.price ? overview.price.location : ""}
              icon={
                overview.price?.trend === "up"
                  ? TrendingUp
                  : overview.price?.trend === "down"
                  ? TrendingDown
                  : Minus
              }
              color={
                overview.price?.trend === "up"
                  ? "text-accent-green"
                  : overview.price?.trend === "down"
                  ? "text-accent-red"
                  : "text-text-muted"
              }
            />
            <StatCard
              label="供需比"
              value={
                overview.supply_demand
                  ? overview.supply_demand.supply_demand_ratio.toFixed(2)
                  : "-"
              }
              sub=">1 供应宽松"
              icon={Scale}
              color="text-accent-blue"
            />
            <StatCard
              label="可申请政策"
              value={
                overview.policy ? `${overview.policy.policies.length} 项` : "-"
              }
              sub={overview.policy?.location || ""}
              icon={FileText}
              color="text-accent-purple"
            />
          </div>

          {/* 价格行情 */}
          {overview.price && (
            <section className="bg-bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Package className="w-5 h-5 text-accent-green" />
                价格行情
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-text-muted">
                      <th className="text-left py-2 px-3">市场</th>
                      <th className="text-right py-2 px-3">价格 (元/公斤)</th>
                      <th className="text-right py-2 px-3">涨跌</th>
                      <th className="text-right py-2 px-3">涨跌幅</th>
                      <th className="text-right py-2 px-3">日期</th>
                    </tr>
                  </thead>
                  <tbody>
                    {overview.price.items.map((item, i) => (
                      <tr key={i} className="border-b border-border/50">
                        <td className="py-2 px-3">{item.market}</td>
                        <td className="text-right py-2 px-3 font-medium">
                          {item.price.toFixed(2)}
                        </td>
                        <td className="text-right py-2 px-3">
                          <span
                            className={
                              item.change > 0
                                ? "text-accent-green"
                                : item.change < 0
                                ? "text-accent-red"
                                : "text-text-muted"
                            }
                          >
                            {item.change > 0 ? "+" : ""}
                            {item.change.toFixed(2)}
                          </span>
                        </td>
                        <td className="text-right py-2 px-3">
                          <span
                            className={
                              item.change_percent > 0
                                ? "text-accent-green"
                                : item.change_percent < 0
                                ? "text-accent-red"
                                : "text-text-muted"
                            }
                          >
                            {item.change_percent > 0 ? "+" : ""}
                            {item.change_percent.toFixed(2)}%
                          </span>
                        </td>
                        <td className="text-right py-2 px-3 text-text-muted">
                          {item.date}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 text-xs text-text-muted">
                数据来源: {overview.price.source} | 更新时间:{" "}
                {overview.price.update_time}
              </p>
            </section>
          )}

          {/* 供需分析 */}
          {overview.supply_demand && (
            <section className="bg-bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Scale className="w-5 h-5 text-accent-blue" />
                供需分析
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div>
                  <div className="text-xs text-text-muted">产量</div>
                  <div className="text-lg font-semibold">
                    {overview.supply_demand.production} 万吨
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">消费量</div>
                  <div className="text-lg font-semibold">
                    {overview.supply_demand.consumption} 万吨
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">库存</div>
                  <div className="text-lg font-semibold">
                    {overview.supply_demand.stock} 万吨
                  </div>
                </div>
                <div>
                  <div className="text-xs text-text-muted">供需比</div>
                  <div className="text-lg font-semibold">
                    {overview.supply_demand.supply_demand_ratio.toFixed(2)}
                  </div>
                </div>
              </div>
              <p className="text-sm text-text-muted">
                {overview.supply_demand.analysis}
              </p>
            </section>
          )}

          {/* 政策补贴 */}
          {overview.policy && overview.policy.policies.length > 0 && (
            <section className="bg-bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <FileText className="w-5 h-5 text-accent-purple" />
                政策补贴 ({overview.policy.location})
              </h3>
              <div className="space-y-4">
                {overview.policy.policies.map((p, i) => (
                  <div
                    key={i}
                    className="border-l-2 border-accent-purple pl-4 py-1"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-2 py-0.5 rounded bg-accent-purple/10 text-accent-purple">
                        {p.category}
                      </span>
                      <h4 className="font-medium">{p.title}</h4>
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-text-muted">
                      <div>
                        <span className="font-medium text-text">
                          补贴标准:
                        </span>{" "}
                        {p.subsidy_amount}
                      </div>
                      <div>
                        <span className="font-medium text-text">
                          截止日期:
                        </span>{" "}
                        {p.deadline}
                      </div>
                      <div className="md:col-span-2">
                        <span className="font-medium text-text">
                          补贴对象:
                        </span>{" "}
                        {p.target}
                      </div>
                      <div className="md:col-span-2">
                        <span className="font-medium text-text">
                          申报条件:
                        </span>{" "}
                        {p.conditions}
                      </div>
                    </div>
                    <a
                      href={p.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-block text-xs text-primary hover:underline"
                    >
                      来源: {p.source_url}
                    </a>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* AI 综合分析 */}
          {isAnalysisLoading ? (
            <section className="bg-bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-accent-amber" />
                AI 综合分析
              </h3>
              <LoadingGrid rows={1} cols={1} height="h-24" />
            </section>
          ) : marketAnalysis && (
            <section className="bg-bg-card rounded-xl border border-border p-6">
              <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                <Lightbulb className="w-5 h-5 text-accent-amber" />
                AI 综合分析
              </h3>
              <div className="space-y-4 text-sm">
                <div>
                  <div className="font-medium mb-1">价格摘要</div>
                  <p className="text-text-muted">
                    {marketAnalysis.price_summary}
                  </p>
                </div>
                <div>
                  <div className="font-medium mb-1">走势预测</div>
                  <p className="text-text-muted">
                    {marketAnalysis.trend_forecast}
                  </p>
                </div>
                <div>
                  <div className="font-medium mb-1">供需摘要</div>
                  <p className="text-text-muted">
                    {marketAnalysis.supply_demand_summary}
                  </p>
                </div>
                <div>
                  <div className="font-medium mb-1">政策摘要</div>
                  <p className="text-text-muted">
                    {marketAnalysis.policy_summary}
                  </p>
                </div>
                <div className="p-4 rounded-lg bg-accent-green/5 border border-accent-green/20">
                  <div className="font-medium mb-1 flex items-center gap-2">
                    <Lightbulb className="w-4 h-4 text-accent-green" />
                    销售建议
                  </div>
                  <p>{marketAnalysis.sales_advice}</p>
                </div>
                <div className="p-4 rounded-lg bg-accent-red/5 border border-accent-red/20">
                  <div className="font-medium mb-1 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-accent-red" />
                    风险提示
                  </div>
                  <p className="text-text-muted">
                    {marketAnalysis.risk_warning}
                  </p>
                </div>
              </div>
              <p className="mt-4 text-xs text-text-muted">
                分析来源: {marketAnalysis.source}
              </p>
            </section>
          )}
        </div>
      ) : (
        <div className="text-center py-12 text-text-muted">暂无数据</div>
      )}
    </WorkspaceLayout>
  );
}
