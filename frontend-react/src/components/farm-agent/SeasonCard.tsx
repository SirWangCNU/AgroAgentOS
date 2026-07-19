import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  CalendarRange,
  Loader2,
  Sprout,
  Target,
  TrendingUp,
} from "lucide-react";
import { listFarmSeasons } from "../../api/farmAgent";
import type { CropSeason } from "../../types/farmAgent";

interface Props {
  farmId: number | null;
  fieldId: number | null;
  refreshKey?: number;
}

const statusLabel: Record<string, string> = {
  planning: "规划中",
  active: "进行中",
  harvested: "已收获",
  abandoned: "已弃收",
};

const statusStyle: Record<string, string> = {
  planning: "bg-sky-50 text-sky-700 border-sky-200",
  active: "bg-emerald-50 text-emerald-700 border-emerald-200",
  harvested: "bg-amber-50 text-amber-800 border-amber-200",
  abandoned: "bg-rose-50 text-rose-700 border-rose-200",
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
}

function calcProgress(start: string | null, end: string | null): number {
  if (!start || !end) return 0;
  const s = new Date(start).getTime();
  const e = new Date(end).getTime();
  if (Number.isNaN(s) || Number.isNaN(e) || e <= s) return 0;
  const now = Date.now();
  return Math.max(0, Math.min(100, ((now - s) / (e - s)) * 100));
}

export default function SeasonCard({ farmId, fieldId, refreshKey = 0 }: Props) {
  const enabled = farmId !== null && fieldId !== null;
  const { data: seasons = [], isLoading } = useQuery({
    queryKey: ["farm-agent-seasons", farmId, fieldId, refreshKey],
    queryFn: () =>
      listFarmSeasons({
        farm_id: farmId as number,
        field_id: fieldId as number,
      }),
    enabled,
  });

  const current = useMemo<CropSeason | null>(() => {
    if (!seasons.length) return null;
    return seasons.find((s) => s.status === "active") ?? seasons[0];
  }, [seasons]);

  if (!enabled) {
    return (
      <section className="rounded-2xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-6 text-center text-xs text-[#8c8375]">
        选择地块后展示茬次信息。
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[#ded5c5] bg-[#fffdf7] p-4 shadow-[0_12px_36px_-30px_rgba(67,50,24,.65)]">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-[#efe8d8] text-[#6f4d2c]">
            <Sprout className="h-4 w-4" />
          </span>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-[#8b785c]">
              Crop season
            </p>
            <h2 className="text-sm font-semibold text-[#2e4036]">当前茬次</h2>
          </div>
        </div>
        <span className="rounded-full bg-[#efe8d8] px-2.5 py-1 text-[10px] font-bold text-[#6f4d2c]">
          {seasons.length} 个茬次
        </span>
      </div>

      {isLoading ? (
        <div className="py-6 text-center text-xs text-[#8c8375]">
          <Loader2 className="mx-auto mb-2 h-4 w-4 animate-spin" />
          加载茬次信息…
        </div>
      ) : !current ? (
        <div className="mt-3 rounded-xl border border-dashed border-[#d6cebf] bg-[#fbfaf5] px-4 py-6 text-center text-xs text-[#8c8375]">
          该地块暂无茬次记录。可在 FarmAgent 页面注入比赛场景以生成茬次。
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          {/* 主体信息 */}
          <div className="rounded-xl border border-[#ece5d8] bg-white/80 p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-[#23372d]">
                {current.crop_name}
              </span>
              {current.variety && (
                <span className="text-[11px] text-[#806c54]">
                  · {current.variety}
                </span>
              )}
              <span
                className={`ml-auto rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                  statusStyle[current.status] ??
                  "bg-slate-50 text-slate-600 border-slate-200"
                }`}
              >
                {statusLabel[current.status] ?? current.status}
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-[#9a8c78]">
              <span>茬次编码 {current.season_code}</span>
              {current.current_stage && (
                <span>· 当前阶段 {current.current_stage}</span>
              )}
            </div>
          </div>

          {/* 生育期进度条 */}
          {current.expected_harvest && (
            <div className="rounded-xl border border-[#ece5d8] bg-white/80 p-3">
              <div className="flex items-center justify-between text-[10px] text-[#806c54]">
                <span className="flex items-center gap-1">
                  <CalendarRange className="h-3 w-3" />
                  {formatDate(current.start_date)}
                </span>
                <span className="flex items-center gap-1">
                  <Target className="h-3 w-3" />
                  {formatDate(current.expected_harvest)}
                </span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-[#efe8d8]">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-[#c2a878] to-[#6f4d2c] transition-all"
                  style={{
                    width: `${calcProgress(
                      current.start_date,
                      current.expected_harvest,
                    ).toFixed(1)}%`,
                  }}
                />
              </div>
              <p className="mt-1 text-right text-[10px] font-bold text-[#6f4d2c]">
                {calcProgress(current.start_date, current.expected_harvest).toFixed(0)}%
                生育期进度
              </p>
            </div>
          )}

          {/* 目标产量 + 面积 */}
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-xl border border-[#ece5d8] bg-white/80 p-2.5">
              <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-[#597461]">
                <TrendingUp className="h-3 w-3" /> 目标产量
              </p>
              <p className="mt-1 text-xs font-semibold text-[#34453b]">
                {current.target_yield || "—"}
              </p>
            </div>
            <div className="rounded-xl border border-[#ece5d8] bg-white/80 p-2.5">
              <p className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-[#597461]">
                <Sprout className="h-3 w-3" /> 种植面积
              </p>
              <p className="mt-1 text-xs font-semibold text-[#34453b]">
                {current.area_mu ? `${current.area_mu} 亩` : "—"}
              </p>
            </div>
          </div>

          {current.note && (
            <p className="rounded-lg bg-[#fbfaf5] px-3 py-2 text-[11px] leading-5 text-[#6f5c43]">
              {current.note}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
