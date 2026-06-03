import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Clock,
  Route,
  Gauge,
  BarChart3,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { getTrajectoryAnalysis } from "../../api/farms";
import StatCard from "../ui/StatCard";

interface Props {
  fileId: number;
}

export default function TrajectoryAnalysis({ fileId }: Props) {
  const [chartsOpen, setChartsOpen] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["trajectory-analysis", fileId],
    queryFn: () => getTrajectoryAnalysis(fileId),
    enabled: !!fileId,
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 text-primary spinner" />
        <span className="ml-2 text-sm text-text-muted">加载分析数据...</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-6 text-sm text-text-muted">
        无法加载分析数据
      </div>
    );
  }

  const vol = data.work_volume as Record<string, number>;
  const eff = data.work_efficiency as Record<string, number>;

  return (
    <div className="space-y-4">
      {/* Work volume stats */}
      <div>
        <h4 className="text-xs font-semibold text-text-secondary mb-2">
          作业量指标
        </h4>
        <div className="grid grid-cols-2 gap-2">
          <StatCard
            icon={Clock}
            label="作业时长"
            value={`${(vol.work_duration_hours || 0).toFixed(1)}h`}
            color="text-accent-blue"
          />
          <StatCard
            icon={Route}
            label="总行程"
            value={`${(vol.total_distance_km || vol.work_distance_km || 0).toFixed(2)}km`}
            color="text-accent-green"
          />
          <StatCard
            icon={BarChart3}
            label="作业面积"
            value={`${(vol.work_area_mu || 0).toFixed(1)}亩`}
            color="text-accent-amber"
          />
          <StatCard
            icon={Gauge}
            label="平均速度"
            value={`${(vol.avg_field_speed_kmh || 0).toFixed(1)}km/h`}
            color="text-accent-purple"
          />
        </div>
      </div>

      {/* Efficiency metrics */}
      <div>
        <h4 className="text-xs font-semibold text-text-secondary mb-2">
          作业质量
        </h4>
        <div className="space-y-2">
          <MetricBar
            label="综合合规率"
            value={eff.compliance_rate || 0}
            color="bg-accent-green"
          />
          <MetricBar
            label="深度合格率"
            value={eff.depth_compliance || 0}
            color="bg-accent-blue"
          />
          <MetricBar
            label="速度合格率"
            value={eff.speed_compliance || 0}
            color="bg-accent-amber"
          />
          <MetricBar
            label="时间利用率"
            value={eff.time_utilization_rate || 0}
            color="bg-accent-purple"
          />
        </div>
      </div>

      {/* Charts */}
      {(data.work_volume_chart || data.work_efficiency_chart) && (
        <div className="border border-border rounded-lg overflow-hidden">
          <button
            onClick={() => setChartsOpen(!chartsOpen)}
            className="flex items-center gap-2 w-full px-3 py-2 text-xs font-semibold text-text-secondary hover:bg-bg-hover transition-colors"
          >
            <BarChart3 className="w-3 h-3" />
            详细图表
            {chartsOpen ? (
              <ChevronUp className="w-3 h-3 ml-auto" />
            ) : (
              <ChevronDown className="w-3 h-3 ml-auto" />
            )}
          </button>
          {chartsOpen && (
            <div className="p-3 space-y-3">
              {data.work_volume_chart && (
                <img
                  src={`data:image/png;base64,${data.work_volume_chart}`}
                  alt="作业量图表"
                  className="w-full rounded"
                />
              )}
              {data.work_efficiency_chart && (
                <img
                  src={`data:image/png;base64,${data.work_efficiency_chart}`}
                  alt="效率图表"
                  className="w-full rounded"
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* Summary stats */}
      {eff.total_points != null && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <CheckCircle2 className="w-3 h-3" />
          共 {eff.total_points} 个轨迹点，
          {eff.compliant_points || 0} 个达标
        </div>
      )}
    </div>
  );
}

function MetricBar({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: string;
}) {
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="text-text-secondary">{label}</span>
        <span className="font-medium text-text-primary">
          {pct.toFixed(1)}%
        </span>
      </div>
      <div className="h-1.5 bg-bg-hover rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
