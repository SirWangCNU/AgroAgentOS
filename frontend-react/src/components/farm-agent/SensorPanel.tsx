import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Bug,
  Droplets,
  Leaf,
  Loader2,
  Radar,
  Sprout,
} from "lucide-react";
import { listFarmSensors } from "../../api/farmAgent";
import type { SensorReading } from "../../types/farmAgent";

interface Props {
  farmId: number | null;
  days?: number;
  refreshKey?: number;
}

const sensorIcon: Record<string, typeof Droplets> = {
  soil_moisture: Droplets,
  soil_nitrogen: Sprout,
  pest_count: Bug,
  ndvi: Leaf,
  anomaly_image: Activity,
};

const sensorLabel: Record<string, string> = {
  soil_moisture: "土壤含水量",
  soil_nitrogen: "速效氮",
  pest_count: "虫情计数",
  ndvi: "NDVI",
  anomaly_image: "田间异常",
};

function formatValue(reading: SensorReading): string {
  if (reading.value_float !== null && reading.value_float !== undefined) {
    return `${reading.value_float}${reading.unit ? ` ${reading.unit}` : ""}`;
  }
  const entries = Object.entries(reading.value ?? {});
  if (entries.length === 0) return "—";
  return entries
    .slice(0, 2)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" · ");
}

function formatObservedAt(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export default function SensorPanel({ farmId, days = 7, refreshKey = 0 }: Props) {
  const enabled = farmId !== null;
  const { data: readings = [], isLoading } = useQuery({
    queryKey: ["farm-agent-sensors", farmId, days, refreshKey],
    queryFn: () => listFarmSensors({ farm_id: farmId as number, days }),
    enabled,
  });

  // 按 field_id 分组，每个 field 只保留最新 5 条
  const grouped = useMemo(() => {
    const buckets = new Map<number, SensorReading[]>();
    for (const reading of readings) {
      const list = buckets.get(reading.field_id) ?? [];
      list.push(reading);
      buckets.set(reading.field_id, list);
    }
    return Array.from(buckets.entries())
      .map(([fieldId, list]) => ({
        fieldId,
        // 后端已按 observed_at desc 排序，取前 5 条
        readings: list.slice(0, 5),
      }))
      .sort((a, b) => a.fieldId - b.fieldId);
  }, [readings]);

  if (!enabled) {
    return (
      <section className="rounded-2xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-8 text-center text-xs text-[#8c8375]">
        选择农场后展示近期感知读数。
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[#ded5c5] bg-[#fffdf7] p-4 shadow-[0_12px_36px_-30px_rgba(67,50,24,.65)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#efe8d8] text-[#6f4d2c]">
            <Radar className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8b785c]">
              Perception panel
            </p>
            <h2 className="text-sm font-semibold text-[#2e4036]">
              近 {days} 天感知读数
            </h2>
          </div>
        </div>
        <span className="rounded-full bg-[#efe8d8] px-2.5 py-1 text-[10px] font-bold text-[#6f4d2c]">
          {readings.length} 条
        </span>
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-xs text-[#8c8375]">
          <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
          加载感知读数…
        </div>
      ) : grouped.length === 0 ? (
        <div className="mt-3 rounded-xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-8 text-center text-xs text-[#8c8375]">
          近 {days} 天暂无感知读数。可在上方选择比赛场景并注入数据。
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {grouped.map(({ fieldId, readings: list }) => (
            <div
              key={fieldId}
              className="rounded-xl border border-[#ece5d8] bg-white/80 p-3"
            >
              <p className="mb-2 text-[10px] font-bold uppercase tracking-wider text-[#597461]">
                地块 #{fieldId}
              </p>
              <ul className="space-y-2">
                {list.map((reading) => {
                  const Icon = sensorIcon[reading.sensor_type] ?? Activity;
                  const label = sensorLabel[reading.sensor_type] ?? reading.sensor_type;
                  return (
                    <li
                      key={reading.id}
                      className="flex items-start justify-between gap-3 text-xs"
                    >
                      <div className="flex items-start gap-2">
                        <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md bg-[#f4eedd] text-[#6f4d2c]">
                          <Icon className="h-3.5 w-3.5" />
                        </span>
                        <div>
                          <p className="font-semibold text-[#34453b]">{label}</p>
                          <p className="text-[10px] text-[#9a8c78]">
                            {formatObservedAt(reading.observed_at)} · 来源 {reading.source}
                          </p>
                        </div>
                      </div>
                      <span className="shrink-0 rounded-md bg-[#fbfaf5] px-2 py-1 text-[11px] font-bold text-[#5a4a32]">
                        {formatValue(reading)}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
