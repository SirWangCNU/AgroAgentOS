import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { LatLngLiteral } from "leaflet";
import {
  AlertTriangle,
  CloudSun,
  Edit3,
  Leaf,
  Loader2,
  MapPin,
  Navigation,
  Plus,
  Save,
  Sprout,
  ThermometerSun,
  Trash2,
  Tractor,
  Wind,
  X,
} from "lucide-react";
import {
  createFarm,
  createField,
  deleteFarm,
  deleteField,
  getFarmDetail,
  getFarmWeather,
  getFarms,
  updateFarm,
} from "../api/farms";
import FarmMap, { type FarmMapMarker } from "../components/map/FarmMap";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import EmptyState from "../components/ui/EmptyState";
import { useUIStore } from "../stores/ui";
import type { Farm, FarmInput, Field, FieldInput, FieldStatus } from "../types/farm";
import type { FarmWeatherAlert, FarmWeatherSummary } from "../types/weather";

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

const statusStyle: Record<FieldStatus, { label: string; className: string }> = {
  idle: { label: "空闲", className: "bg-slate-100 text-slate-600" },
  planting: { label: "种植中", className: "bg-emerald-100 text-emerald-700" },
  fallow: { label: "休耕", className: "bg-amber-100 text-amber-700" },
};

const riskStyle: Record<string, string> = {
  高: "border-rose-200 bg-rose-50 text-rose-700",
  中: "border-amber-200 bg-amber-50 text-amber-700",
  低: "border-sky-200 bg-sky-50 text-sky-700",
};

const formInputClass = "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-100";
const modalSubmitClass = "w-full rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-50";

export default function Farms() {
  const queryClient = useQueryClient();
  const showToast = useUIStore((state) => state.showToast);
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [isLocationEditing, setIsLocationEditing] = useState(false);
  const [draftPosition, setDraftPosition] = useState<LatLngLiteral | null>(null);
  const [isCreateFarmOpen, setIsCreateFarmOpen] = useState(false);
  const [isCreateFieldOpen, setIsCreateFieldOpen] = useState(false);

  const farmsQuery = useQuery({ queryKey: ["farms"], queryFn: getFarms });
  const farms = farmsQuery.data ?? [];
  const activeFarmId = selectedFarmId ?? farms[0]?.id ?? null;
  const activeFarm = farms.find((farm) => farm.id === activeFarmId) ?? null;

  const fieldsQuery = useQuery({
    queryKey: ["fields", activeFarmId],
    queryFn: () => getFarmDetail(activeFarmId!),
    enabled: activeFarmId !== null,
  });
  const weatherQuery = useQuery({
    queryKey: ["farm-weather", activeFarmId],
    queryFn: () => getFarmWeather(activeFarmId!),
    enabled:
      activeFarmId !== null &&
      activeFarm?.latitude !== null &&
      activeFarm?.latitude !== undefined &&
      activeFarm?.longitude !== null &&
      activeFarm?.longitude !== undefined,
    staleTime: 30 * 60 * 1000,
  });

  const savePositionMutation = useMutation({
    mutationFn: (position: LatLngLiteral) =>
      updateFarm(activeFarmId!, {
        latitude: position.lat,
        longitude: position.lng,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      await queryClient.invalidateQueries({ queryKey: ["farm-weather", activeFarmId] });
      setIsLocationEditing(false);
      setDraftPosition(null);
      showToast("农场位置已保存", "success");
    },
    onError: (error: unknown) => showToast(errorMessage(error, "位置保存失败"), "error"),
  });

  const deleteFarmMutation = useMutation({
    mutationFn: deleteFarm,
    onSuccess: async (_, deletedFarmId) => {
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      if (deletedFarmId === activeFarmId) setSelectedFarmId(null);
      setIsLocationEditing(false);
      setDraftPosition(null);
      showToast("农场及其地块已删除", "success");
    },
    onError: (error: unknown) => showToast(errorMessage(error, "删除农场失败"), "error"),
  });

  const deleteFieldMutation = useMutation({
    mutationFn: deleteField,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["fields", activeFarmId] });
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      showToast("地块已删除", "success");
    },
    onError: (error: unknown) => showToast(errorMessage(error, "删除地块失败"), "error"),
  });

  const mapMarkers: FarmMapMarker[] = farms.map((farm) => ({
    id: farm.id,
    name: farm.name,
    location: farm.location,
    area_mu: farm.area_mu,
    latitude: farm.latitude,
    longitude: farm.longitude,
  }));

  const selectFarm = (farmId: number) => {
    setSelectedFarmId(farmId);
    setIsLocationEditing(false);
    setDraftPosition(null);
  };

  const startLocationEditing = () => {
    if (!activeFarm) return;
    if (activeFarm.latitude !== null && activeFarm.longitude !== null) {
      setDraftPosition({ lat: activeFarm.latitude, lng: activeFarm.longitude });
    } else {
      setDraftPosition(null);
    }
    setIsLocationEditing(true);
  };

  const locateCurrentPosition = () => {
    if (!navigator.geolocation) {
      showToast("当前浏览器不支持定位，请直接点击地图设置位置", "info");
      return;
    }
    setIsLocationEditing(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setDraftPosition({ lat: position.coords.latitude, lng: position.coords.longitude });
      },
      () => showToast("定位未完成，请直接点击地图设置位置", "info"),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 }
    );
  };

  const cancelLocationEditing = () => {
    setIsLocationEditing(false);
    setDraftPosition(null);
  };

  return (
    <>
      <WorkspaceLayout
        title="农场管理"
        icon={Tractor}
        iconColor="text-emerald-700"
        description="查看农场位置与天气风险"
        fullWidth
        action={
          <button
            onClick={() => setIsCreateFarmOpen(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900"
          >
            <Plus className="h-4 w-4" /> 新增农场
          </button>
        }
      >
        <div className="grid min-h-[calc(100vh-178px)] grid-cols-[320px_minmax(0,1fr)] gap-5">
          <aside className="min-h-0 space-y-4 overflow-y-auto pr-1">
            <FarmSelector
              farms={farms}
              selectedFarmId={activeFarmId}
              isLoading={farmsQuery.isLoading}
              onSelect={selectFarm}
            />
            {activeFarm ? (
              <>
                <FarmSummary
                  farm={activeFarm}
                  isEditing={isLocationEditing}
                  isSaving={savePositionMutation.isPending}
                  hasDraft={draftPosition !== null}
                  onEditLocation={startLocationEditing}
                  onLocate={locateCurrentPosition}
                  onSave={() => draftPosition && savePositionMutation.mutate(draftPosition)}
                  onCancel={cancelLocationEditing}
                  onDelete={() => {
                    if (window.confirm(`确定删除“${activeFarm.name}”吗？其地块也会一并删除。`)) {
                      deleteFarmMutation.mutate(activeFarm.id);
                    }
                  }}
                />
                <WeatherPanel
                  summary={weatherQuery.data}
                  isLoading={weatherQuery.isLoading}
                  isError={weatherQuery.isError}
                  hasLocation={activeFarm.latitude !== null && activeFarm.longitude !== null}
                />
                <FieldList
                  fields={fieldsQuery.data ?? []}
                  isLoading={fieldsQuery.isLoading}
                  onCreate={() => setIsCreateFieldOpen(true)}
                  onDelete={(field) => {
                    if (window.confirm(`确定删除地块“${field.name}”吗？`)) deleteFieldMutation.mutate(field.id);
                  }}
                />
              </>
            ) : (
              <EmptyState
                icon={Sprout}
                title="还没有农场"
                description="创建第一个农场后，即可在地图上标记位置并查看天气。"
                action={
                  <button onClick={() => setIsCreateFarmOpen(true)} className="rounded-lg bg-emerald-800 px-3 py-2 text-xs font-semibold text-white">
                    创建第一个农场
                  </button>
                }
              />
            )}
          </aside>

          <section className="min-w-0">
            <FarmMap
              farms={mapMarkers}
              selectedFarmId={activeFarmId}
              isEditing={isLocationEditing}
              draftPosition={draftPosition}
              onFarmClick={selectFarm}
              onDraftPositionChange={setDraftPosition}
            />
          </section>
        </div>
      </WorkspaceLayout>

      {isCreateFarmOpen && (
        <CreateFarmModal
          onClose={() => setIsCreateFarmOpen(false)}
          onSuccess={async () => {
            setIsCreateFarmOpen(false);
            await queryClient.invalidateQueries({ queryKey: ["farms"] });
          }}
        />
      )}
      {isCreateFieldOpen && activeFarmId !== null && (
        <CreateFieldModal
          farmId={activeFarmId}
          onClose={() => setIsCreateFieldOpen(false)}
          onSuccess={async () => {
            setIsCreateFieldOpen(false);
            await queryClient.invalidateQueries({ queryKey: ["fields", activeFarmId] });
            await queryClient.invalidateQueries({ queryKey: ["farms"] });
          }}
        />
      )}
    </>
  );
}

function FarmSelector({ farms, selectedFarmId, isLoading, onSelect }: { farms: Farm[]; selectedFarmId: number | null; isLoading: boolean; onSelect: (farmId: number) => void }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-emerald-900/10 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-emerald-900/10 px-4 py-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">我的农场</p>
          <h2 className="mt-0.5 text-sm font-semibold text-slate-900">选择当前农场</h2>
        </div>
        <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">{farms.length}</span>
      </div>
      <div className="max-h-52 space-y-1 overflow-y-auto p-2">
        {isLoading ? <div className="flex items-center justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-emerald-700" /></div> : farms.map((farm) => (
          <button key={farm.id} onClick={() => onSelect(farm.id)} className={`w-full rounded-xl px-3 py-2.5 text-left transition ${farm.id === selectedFarmId ? "bg-emerald-800 text-white shadow-sm" : "text-slate-700 hover:bg-emerald-50"}`}>
            <div className="truncate text-sm font-semibold">{farm.name}</div>
            <div className={`mt-1 flex items-center gap-1 text-xs ${farm.id === selectedFarmId ? "text-emerald-100" : "text-slate-500"}`}><MapPin className="h-3 w-3" />{farm.location || "位置未设置"} · {farm.area_mu} 亩</div>
          </button>
        ))}
      </div>
    </section>
  );
}

function FarmSummary({ farm, isEditing, isSaving, hasDraft, onEditLocation, onLocate, onSave, onCancel, onDelete }: { farm: Farm; isEditing: boolean; isSaving: boolean; hasDraft: boolean; onEditLocation: () => void; onLocate: () => void; onSave: () => void; onCancel: () => void; onDelete: () => void }) {
  return <section className="rounded-2xl border border-emerald-900/10 bg-[#f7faf5] p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">当前农场</p><h2 className="mt-1 text-lg font-bold text-slate-900">{farm.name}</h2></div><button onClick={onDelete} className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600" title="删除农场"><Trash2 className="h-4 w-4" /></button></div><div className="mt-3 space-y-2 text-xs text-slate-600"><div className="flex gap-2"><MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-700" />{farm.location || "尚未设置位置"}</div><div className="flex gap-2"><Leaf className="h-3.5 w-3.5 shrink-0 text-emerald-700" />总面积 {farm.area_mu} 亩</div></div>{isEditing ? <div className="mt-4 grid grid-cols-2 gap-2"><button onClick={onLocate} className="inline-flex items-center justify-center gap-1 rounded-lg border border-emerald-200 bg-white px-2 py-2 text-xs font-semibold text-emerald-800"><Navigation className="h-3.5 w-3.5" />定位到我</button><button onClick={onCancel} className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-600"><X className="h-3.5 w-3.5" />取消</button><button disabled={!hasDraft || isSaving} onClick={onSave} className="col-span-2 inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-800 px-2 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}{isSaving ? "保存中" : "保存位置"}</button></div> : <button onClick={onEditLocation} className="mt-4 inline-flex w-full items-center justify-center gap-1 rounded-lg border border-emerald-200 bg-white px-2 py-2 text-xs font-semibold text-emerald-800"><Edit3 className="h-3.5 w-3.5" />{farm.latitude === null || farm.longitude === null ? "设置农场位置" : "调整农场位置"}</button>}</section>;
}

function WeatherPanel({ summary, isLoading, isError, hasLocation }: { summary: FarmWeatherSummary | undefined; isLoading: boolean; isError: boolean; hasLocation: boolean }) {
  if (!hasLocation) return <section className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/50 p-4"><div className="flex gap-2"><CloudSun className="h-5 w-5 text-emerald-700" /><div><h2 className="text-sm font-semibold text-emerald-950">设置位置后查看天气</h2><p className="mt-1 text-xs leading-5 text-emerald-800">天气与风险会根据农场标记位置实时查询。</p></div></div></section>;
  if (isLoading) return <section className="flex items-center gap-2 rounded-2xl border border-emerald-900/10 bg-white p-4 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin text-emerald-700" />正在获取农场天气</section>;
  if (isError || !summary?.available || !summary.current) return <section className="rounded-2xl border border-slate-200 bg-white p-4"><div className="flex gap-2"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><h2 className="text-sm font-semibold text-slate-900">天气暂不可用</h2><p className="mt-1 text-xs leading-5 text-slate-500">{summary?.reason === "WEATHER_SERVICE_UNAVAILABLE" ? "天气服务未配置或暂时不可用。" : "稍后可重新进入页面查询。"}</p></div></div></section>;
  return <section className="overflow-hidden rounded-2xl border border-emerald-900/10 bg-white shadow-sm"><div className="border-b border-emerald-900/10 bg-[#edf6ed] px-4 py-3"><p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">实时天气</p><div className="mt-1 flex items-end justify-between"><h2 className="text-2xl font-bold text-emerald-950">{summary.current.temperature}°</h2><span className="text-sm font-semibold text-emerald-800">{summary.current.condition}</span></div><div className="mt-2 flex gap-3 text-xs text-emerald-900"><span className="inline-flex items-center gap-1"><ThermometerSun className="h-3.5 w-3.5" />湿度 {summary.current.humidity}%</span><span className="inline-flex items-center gap-1"><Wind className="h-3.5 w-3.5" />{summary.current.wind_level} 级风</span></div></div><div className="p-3"><p className="mb-2 text-xs font-medium text-slate-500">天气风险</p><RiskList alerts={summary.alerts} /><p className="mt-3 text-[11px] text-slate-400">更新于 {summary.current.update_time || "--"}</p></div></section>;
}

function RiskList({ alerts }: { alerts: FarmWeatherAlert[] }) {
  if (!alerts.length) return <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">当前未发现明显天气风险</div>;
  return <div className="space-y-2">{alerts.map((alert) => <div key={`${alert.alert_type}-${alert.date}`} className={`flex items-center justify-between rounded-lg border px-2.5 py-2 text-xs ${riskStyle[alert.severity] ?? "border-slate-200 bg-slate-50 text-slate-700"}`}><span>{alert.alert_type} · {alert.date}</span><strong>{alert.severity}风险</strong></div>)}</div>;
}

function FieldList({ fields, isLoading, onCreate, onDelete }: { fields: Field[]; isLoading: boolean; onCreate: () => void; onDelete: (field: Field) => void }) {
  return <section className="overflow-hidden rounded-2xl border border-emerald-900/10 bg-white shadow-sm"><div className="flex items-center justify-between border-b border-emerald-900/10 px-4 py-3"><div><p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">地块档案</p><h2 className="mt-0.5 text-sm font-semibold text-slate-900">简单管理，不增加流程</h2></div><button onClick={onCreate} className="rounded-lg bg-emerald-50 p-2 text-emerald-800 transition hover:bg-emerald-100" title="添加地块"><Plus className="h-4 w-4" /></button></div><div className="max-h-64 space-y-1 overflow-y-auto p-2">{isLoading ? <div className="flex justify-center py-6"><Loader2 className="h-4 w-4 animate-spin text-emerald-700" /></div> : fields.length ? fields.map((field) => <div key={field.id} className="flex items-center justify-between rounded-xl px-2.5 py-2.5 hover:bg-slate-50"><div className="min-w-0"><div className="truncate text-sm font-semibold text-slate-800">{field.name}</div><div className="mt-1 text-xs text-slate-500">{field.current_crop || "未填写作物"} · {field.area_mu} 亩</div></div><div className="ml-2 flex items-center gap-1"><span className={`rounded-full px-2 py-1 text-[11px] font-medium ${statusStyle[field.status].className}`}>{statusStyle[field.status].label}</span><button onClick={() => onDelete(field)} className="rounded-md p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" title="删除地块"><Trash2 className="h-3.5 w-3.5" /></button></div></div>) : <div className="px-2 py-7 text-center text-xs text-slate-500">暂无地块，添加后可记录作物和面积。</div>}</div></section>;
}

function CreateFarmModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => Promise<void> }) {
  const showToast = useUIStore((state) => state.showToast);
  const [form, setForm] = useState<FarmInput>({ name: "", location: "", latitude: null, longitude: null, area_mu: 0, description: "" });
  const mutation = useMutation({ mutationFn: () => createFarm(form), onSuccess: () => { showToast("农场创建成功，请在地图上设置位置", "success"); void onSuccess(); }, onError: (error: unknown) => showToast(errorMessage(error, "创建农场失败"), "error") });
  return <Modal title="新增农场" onClose={onClose}><FormLabel label="农场名称"><input autoFocus value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="如：东山农场" className={formInputClass} /></FormLabel><div className="grid grid-cols-2 gap-3"><FormLabel label="位置说明"><input value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="如：寿光市" className={formInputClass} /></FormLabel><FormLabel label="面积（亩）"><input type="number" min="0" value={form.area_mu || ""} onChange={(event) => setForm({ ...form, area_mu: Number(event.target.value) })} className={formInputClass} /></FormLabel></div><FormLabel label="备注"><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={3} className={`${formInputClass} resize-none`} /></FormLabel><button disabled={!form.name.trim() || mutation.isPending} onClick={() => mutation.mutate()} className={modalSubmitClass}>{mutation.isPending ? "创建中" : "创建农场"}</button></Modal>;
}

function CreateFieldModal({ farmId, onClose, onSuccess }: { farmId: number; onClose: () => void; onSuccess: () => Promise<void> }) {
  const showToast = useUIStore((state) => state.showToast);
  const [form, setForm] = useState<FieldInput>({ name: "", area_mu: 0, current_crop: "", status: "idle", notes: "" });
  const mutation = useMutation({ mutationFn: () => createField(farmId, form), onSuccess: () => { showToast("地块创建成功", "success"); void onSuccess(); }, onError: (error: unknown) => showToast(errorMessage(error, "创建地块失败"), "error") });
  return <Modal title="添加地块" onClose={onClose}><FormLabel label="地块名称"><input autoFocus value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="如：东侧一号田" className={formInputClass} /></FormLabel><div className="grid grid-cols-2 gap-3"><FormLabel label="当前作物"><input value={form.current_crop} onChange={(event) => setForm({ ...form, current_crop: event.target.value })} placeholder="如：玉米" className={formInputClass} /></FormLabel><FormLabel label="面积（亩）"><input type="number" min="0" value={form.area_mu || ""} onChange={(event) => setForm({ ...form, area_mu: Number(event.target.value) })} className={formInputClass} /></FormLabel></div><FormLabel label="状态"><select value={form.status} onChange={(event) => setForm({ ...form, status: event.target.value as FieldStatus })} className={formInputClass}><option value="idle">空闲</option><option value="planting">种植中</option><option value="fallow">休耕</option></select></FormLabel><FormLabel label="备注"><textarea value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} rows={3} className={`${formInputClass} resize-none`} /></FormLabel><button disabled={!form.name.trim() || mutation.isPending} onClick={() => mutation.mutate()} className={modalSubmitClass}>{mutation.isPending ? "创建中" : "创建地块"}</button></Modal>;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) { return <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4"><button aria-label="关闭弹窗" className="absolute inset-0 bg-slate-950/35" onClick={onClose} /><div className="relative w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl"><div className="mb-5 flex items-center justify-between"><h2 className="text-lg font-bold text-slate-900">{title}</h2><button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button></div><div className="space-y-4">{children}</div></div></div>; }
function FormLabel({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block text-sm font-medium text-slate-700"><span className="mb-1.5 block">{label}</span>{children}</label>; }
