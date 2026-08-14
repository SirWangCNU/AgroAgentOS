import { useCallback, useMemo, useState } from "react";
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
  RotateCcw,
  Save,
  Scissors,
  Sprout,
  ThermometerSun,
  Trash2,
  Tractor,
  Undo2,
  Wind,
  X,
} from "lucide-react";
import {
  createFarm,
  createField,
  deleteFarm,
  deleteField,
  getFarmDetail,
  getFieldWeather,
  getFarms,
  updateFarm,
  updateField,
} from "../api/farms";
import FarmMap, { type FarmMapMarker } from "../components/map/FarmMap";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import EmptyState from "../components/ui/EmptyState";
import { calculateFieldAreaMu, hasBlockingOverlap } from "../lib/field-geometry";
import { useUIStore } from "../stores/ui";
import type { Farm, FarmInput, Field, FieldInput, FieldStatus, GeoJSONPolygon } from "../types/farm";
import type { FarmWeatherAlert, FarmWeatherSummary } from "../types/weather";

type FieldEditorMode = "idle" | "drawing" | "creating" | "editing";

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

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

function defaultFieldForm(): FieldInput {
  return {
    name: "",
    soil_type: "",
    current_crop: "",
    growth_stage: "",
    status: "idle",
    notes: "",
  };
}

function fieldToForm(field: Field): FieldInput {
  return {
    name: field.name,
    soil_type: field.soil_type,
    current_crop: field.current_crop,
    planting_date: field.planting_date,
    expected_harvest: field.expected_harvest,
    growth_stage: field.growth_stage,
    status: field.status,
    notes: field.notes,
  };
}

function formatMu(value: number): string {
  return Number(value || 0).toFixed(2);
}

function trimDraftBoundary(boundary: GeoJSONPolygon | null): GeoJSONPolygon | null {
  if (!boundary) return null;
  const ring = boundary.coordinates[0];
  if (ring.length <= 4) return null;
  const trimmed = [...ring.slice(0, -2), ring[0]];
  return { type: "Polygon", coordinates: [trimmed] };
}

export default function Farms() {
  const queryClient = useQueryClient();
  const showToast = useUIStore((state) => state.showToast);
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);
  const [isLocationEditing, setIsLocationEditing] = useState(false);
  const [draftPosition, setDraftPosition] = useState<LatLngLiteral | null>(null);
  const [isCreateFarmOpen, setIsCreateFarmOpen] = useState(false);
  const [fieldMode, setFieldMode] = useState<FieldEditorMode>("idle");
  const [fieldForm, setFieldForm] = useState<FieldInput>(defaultFieldForm);
  const [draftBoundary, setDraftBoundary] = useState<GeoJSONPolygon | null>(null);

  const farmsQuery = useQuery({ queryKey: ["farms"], queryFn: getFarms });
  const farms = farmsQuery.data ?? [];
  const activeFarmId = selectedFarmId ?? farms[0]?.id ?? null;
  const activeFarm = farms.find((farm) => farm.id === activeFarmId) ?? null;

  const fieldsQuery = useQuery({
    queryKey: ["fields", activeFarmId],
    queryFn: () => getFarmDetail(activeFarmId!),
    enabled: activeFarmId !== null,
  });
  const fields = useMemo(() => fieldsQuery.data ?? [], [fieldsQuery.data]);
  const selectedField = fields.find((field) => field.id === selectedFieldId) ?? null;

  const weatherQuery = useQuery({
    queryKey: ["field-weather", selectedFieldId],
    queryFn: () => getFieldWeather(selectedFieldId!),
    enabled: selectedFieldId !== null,
    staleTime: 30 * 60 * 1000,
  });

  const isFieldEditing = fieldMode !== "idle";
  const editingFieldId = fieldMode === "editing" ? selectedFieldId : null;
  const existingBoundaries = useMemo(
    () =>
      fields
        .filter((field) => field.boundary && field.id !== editingFieldId)
        .map((field) => field.boundary as GeoJSONPolygon),
    [editingFieldId, fields],
  );
  const areaPreview = draftBoundary ? calculateFieldAreaMu(draftBoundary) : 0;
  const hasOverlap = draftBoundary ? hasBlockingOverlap(draftBoundary, existingBoundaries) : false;

  const savePositionMutation = useMutation({
    mutationFn: (position: LatLngLiteral) =>
      updateFarm(activeFarmId!, {
        latitude: position.lat,
        longitude: position.lng,
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      setIsLocationEditing(false);
      setDraftPosition(null);
      showToast("农场位置已保存", "success");
    },
    onError: (error: unknown) => showToast(errorMessage(error, "位置保存失败"), "error"),
  });

  const saveFieldMutation = useMutation({
    mutationFn: () => {
      if (!draftBoundary) throw new Error("请先圈出地块边界");
      const payload: FieldInput = {
        ...fieldForm,
        boundary: draftBoundary,
      };
      if (fieldMode === "editing" && selectedFieldId !== null) {
        return updateField(selectedFieldId, payload);
      }
      return createField(activeFarmId!, payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["fields", activeFarmId] });
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      await queryClient.invalidateQueries({ queryKey: ["field-weather", selectedFieldId] });
      setFieldMode("idle");
      setDraftBoundary(null);
      setFieldForm(defaultFieldForm());
      showToast("地块档案已保存", "success");
    },
    onError: (error: unknown) => showToast(errorMessage(error, "地块保存失败"), "error"),
  });

  const deleteFarmMutation = useMutation({
    mutationFn: deleteFarm,
    onSuccess: async (_, deletedFarmId) => {
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      if (deletedFarmId === activeFarmId) setSelectedFarmId(null);
      setSelectedFieldId(null);
      setIsLocationEditing(false);
      setDraftPosition(null);
      setFieldMode("idle");
      setDraftBoundary(null);
      showToast("农场及其地块已删除", "success");
    },
    onError: (error: unknown) => showToast(errorMessage(error, "删除农场失败"), "error"),
  });

  const deleteFieldMutation = useMutation({
    mutationFn: deleteField,
    onSuccess: async (_, deletedFieldId) => {
      await queryClient.invalidateQueries({ queryKey: ["fields", activeFarmId] });
      await queryClient.invalidateQueries({ queryKey: ["farms"] });
      await queryClient.invalidateQueries({ queryKey: ["field-weather", deletedFieldId] });
      if (deletedFieldId === selectedFieldId) setSelectedFieldId(null);
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
    if (isFieldEditing) {
      showToast("请先保存或取消当前地块编辑", "info");
      return;
    }
    setSelectedFarmId(farmId);
    setSelectedFieldId(null);
    setIsLocationEditing(false);
    setDraftPosition(null);
  };

  const selectField = (fieldId: number) => {
    if (isFieldEditing) {
      showToast("请先保存或取消当前地块编辑", "info");
      return;
    }
    setSelectedFieldId(fieldId);
  };

  const startLocationEditing = () => {
    if (!activeFarm || isFieldEditing) return;
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
      (position) => setDraftPosition({ lat: position.coords.latitude, lng: position.coords.longitude }),
      () => showToast("定位未完成，请直接点击地图设置位置", "info"),
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
    );
  };

  const startCreateField = () => {
    if (!activeFarm) return;
    setSelectedFieldId(null);
    setFieldForm(defaultFieldForm());
    setDraftBoundary(null);
    setFieldMode("drawing");
  };

  const startEditField = (field: Field) => {
    if (!field.boundary) {
      showToast("历史地块需要先重新圈出边界", "info");
      setSelectedFieldId(field.id);
      setFieldForm(fieldToForm(field));
      setDraftBoundary(null);
      setFieldMode("drawing");
      return;
    }
    setSelectedFieldId(field.id);
    setFieldForm(fieldToForm(field));
    setDraftBoundary(field.boundary);
    setFieldMode("editing");
  };

  const handleDraftBoundaryChange = useCallback((boundary: GeoJSONPolygon) => {
    setDraftBoundary(boundary);
    setFieldMode((current) => (current === "drawing" ? "creating" : current));
  }, []);

  const cancelFieldEditing = () => {
    setFieldMode("idle");
    setDraftBoundary(null);
    setFieldForm(defaultFieldForm());
  };

  return (
    <>
      <WorkspaceLayout
        title="农场管理"
        icon={Tractor}
        iconColor="text-emerald-700"
        description="圈定地块边界并查看地块天气风险"
        fullWidth
        action={
          <button
            disabled={isFieldEditing}
            onClick={() => setIsCreateFarmOpen(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-800 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-900 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="h-4 w-4" /> 新增农场
          </button>
        }
      >
        <div className="grid min-h-[calc(100vh-178px)] grid-cols-[340px_minmax(0,1fr)] gap-5">
          <aside className="min-h-0 space-y-4 overflow-y-auto pr-1">
            <FarmSelector
              farms={farms}
              selectedFarmId={activeFarmId}
              isLoading={farmsQuery.isLoading}
              disabled={isFieldEditing}
              onSelect={selectFarm}
            />
            {activeFarm ? (
              <>
                <FarmSummary
                  farm={activeFarm}
                  isEditing={isLocationEditing}
                  isSaving={savePositionMutation.isPending}
                  hasDraft={draftPosition !== null}
                  disabled={isFieldEditing}
                  onEditLocation={startLocationEditing}
                  onLocate={locateCurrentPosition}
                  onSave={() => draftPosition && savePositionMutation.mutate(draftPosition)}
                  onCancel={() => {
                    setIsLocationEditing(false);
                    setDraftPosition(null);
                  }}
                  onDelete={() => {
                    if (window.confirm(`确定删除“${activeFarm.name}”吗？其地块也会一并删除。`)) {
                      deleteFarmMutation.mutate(activeFarm.id);
                    }
                  }}
                />
                {isFieldEditing ? (
                  <FieldEditorPanel
                    mode={fieldMode}
                    form={fieldForm}
                    areaPreview={areaPreview}
                    hasBoundary={draftBoundary !== null}
                    hasOverlap={hasOverlap}
                    isSaving={saveFieldMutation.isPending}
                    onChange={setFieldForm}
                    onSave={() => saveFieldMutation.mutate()}
                    onCancel={cancelFieldEditing}
                    onRedraw={() => {
                      setDraftBoundary(null);
                      setFieldMode("drawing");
                    }}
                    onUndo={() => setDraftBoundary((current) => trimDraftBoundary(current))}
                  />
                ) : (
                  <>
                    <FieldList
                      fields={fields}
                      selectedFieldId={selectedFieldId}
                      isLoading={fieldsQuery.isLoading}
                      onCreate={startCreateField}
                      onSelect={selectField}
                      onEdit={startEditField}
                      onDelete={(field) => {
                        if (window.confirm(`确定删除地块“${field.name}”吗？`)) deleteFieldMutation.mutate(field.id);
                      }}
                    />
                    <WeatherPanel
                      field={selectedField}
                      summary={weatherQuery.data}
                      isLoading={weatherQuery.isLoading}
                      isError={weatherQuery.isError}
                    />
                  </>
                )}
              </>
            ) : (
              <EmptyState
                icon={Sprout}
                title="还没有农场"
                description="创建第一个农场后，即可在地图上标记位置并圈定地块。"
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
              fields={fields}
              selectedFarmId={activeFarmId}
              selectedFieldId={selectedFieldId}
              isLocationEditing={isLocationEditing}
              isDrawingField={fieldMode === "drawing"}
              editingBoundary={fieldMode === "editing" ? draftBoundary : null}
              draftPosition={draftPosition}
              onFarmClick={selectFarm}
              onFieldClick={selectField}
              onDraftPositionChange={setDraftPosition}
              onDraftBoundaryChange={handleDraftBoundaryChange}
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
    </>
  );
}

function FarmSelector({ farms, selectedFarmId, isLoading, disabled, onSelect }: { farms: Farm[]; selectedFarmId: number | null; isLoading: boolean; disabled: boolean; onSelect: (farmId: number) => void }) {
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
        {isLoading ? (
          <div className="flex items-center justify-center py-8"><Loader2 className="h-5 w-5 animate-spin text-emerald-700" /></div>
        ) : (
          farms.map((farm) => (
            <button key={farm.id} disabled={disabled} onClick={() => onSelect(farm.id)} className={`w-full rounded-xl px-3 py-2.5 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${farm.id === selectedFarmId ? "bg-emerald-800 text-white shadow-sm" : "text-slate-700 hover:bg-emerald-50"}`}>
              <div className="truncate text-sm font-semibold">{farm.name}</div>
              <div className={`mt-1 flex items-center gap-1 text-xs ${farm.id === selectedFarmId ? "text-emerald-100" : "text-slate-500"}`}><MapPin className="h-3 w-3" />{farm.location || "位置未设置"} · {formatMu(farm.area_mu)} 亩</div>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function FarmSummary({ farm, isEditing, isSaving, hasDraft, disabled, onEditLocation, onLocate, onSave, onCancel, onDelete }: { farm: Farm; isEditing: boolean; isSaving: boolean; hasDraft: boolean; disabled: boolean; onEditLocation: () => void; onLocate: () => void; onSave: () => void; onCancel: () => void; onDelete: () => void }) {
  return (
    <section className="rounded-2xl border border-emerald-900/10 bg-[#f7faf5] p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">当前农场</p>
          <h2 className="mt-1 text-lg font-bold text-slate-900">{farm.name}</h2>
        </div>
        <button disabled={disabled} onClick={onDelete} className="rounded-lg p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-40" title="删除农场"><Trash2 className="h-4 w-4" /></button>
      </div>
      <div className="mt-3 space-y-2 text-xs text-slate-600">
        <div className="flex gap-2"><MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-700" />{farm.location || "尚未设置位置"}</div>
        <div className="flex gap-2"><Leaf className="h-3.5 w-3.5 shrink-0 text-emerald-700" />总面积 {formatMu(farm.area_mu)} 亩</div>
      </div>
      {isEditing ? (
        <div className="mt-4 grid grid-cols-2 gap-2">
          <button onClick={onLocate} className="inline-flex items-center justify-center gap-1 rounded-lg border border-emerald-200 bg-white px-2 py-2 text-xs font-semibold text-emerald-800"><Navigation className="h-3.5 w-3.5" />定位到我</button>
          <button onClick={onCancel} className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-600"><X className="h-3.5 w-3.5" />取消</button>
          <button disabled={!hasDraft || isSaving} onClick={onSave} className="col-span-2 inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-800 px-2 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}{isSaving ? "保存中" : "保存位置"}</button>
        </div>
      ) : (
        <button disabled={disabled} onClick={onEditLocation} className="mt-4 inline-flex w-full items-center justify-center gap-1 rounded-lg border border-emerald-200 bg-white px-2 py-2 text-xs font-semibold text-emerald-800 disabled:cursor-not-allowed disabled:opacity-50"><Edit3 className="h-3.5 w-3.5" />{farm.latitude === null || farm.longitude === null ? "设置农场位置" : "调整农场位置"}</button>
      )}
    </section>
  );
}

function FieldList({ fields, selectedFieldId, isLoading, onCreate, onSelect, onEdit, onDelete }: { fields: Field[]; selectedFieldId: number | null; isLoading: boolean; onCreate: () => void; onSelect: (fieldId: number) => void; onEdit: (field: Field) => void; onDelete: (field: Field) => void }) {
  return (
    <section className="overflow-hidden rounded-2xl border border-emerald-900/10 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-emerald-900/10 px-4 py-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">地块档案</p>
          <h2 className="mt-0.5 text-sm font-semibold text-slate-900">边界、作物与状态</h2>
        </div>
        <button onClick={onCreate} className="rounded-lg bg-emerald-50 p-2 text-emerald-800 transition hover:bg-emerald-100" title="圈定新地块"><Plus className="h-4 w-4" /></button>
      </div>
      <div className="max-h-72 space-y-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="flex justify-center py-6"><Loader2 className="h-4 w-4 animate-spin text-emerald-700" /></div>
        ) : fields.length ? (
          fields.map((field) => (
            <div key={field.id} className={`rounded-xl px-2.5 py-2.5 transition ${field.id === selectedFieldId ? "bg-emerald-50 ring-1 ring-emerald-200" : "hover:bg-slate-50"}`}>
              <button onClick={() => onSelect(field.id)} className="w-full text-left">
                <div className="truncate text-sm font-semibold text-slate-800">{field.name}</div>
                <div className="mt-1 text-xs text-slate-500">{field.current_crop || "未填写作物"} · {formatMu(field.area_mu)} 亩</div>
              </button>
              <div className="mt-2 flex items-center justify-between gap-2">
                <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${statusStyle[field.status]?.className ?? statusStyle.idle.className}`}>{statusStyle[field.status]?.label ?? field.status}</span>
                <div className="flex items-center gap-1">
                  <button onClick={() => onEdit(field)} className="rounded-md p-1.5 text-slate-500 hover:bg-emerald-100 hover:text-emerald-700" title="编辑地块边界"><Scissors className="h-3.5 w-3.5" /></button>
                  <button onClick={() => onDelete(field)} className="rounded-md p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600" title="删除地块"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="px-2 py-7 text-center text-xs text-slate-500">暂无地块，点击右上角按钮开始圈地。</div>
        )}
      </div>
    </section>
  );
}

function FieldEditorPanel({ mode, form, areaPreview, hasBoundary, hasOverlap, isSaving, onChange, onSave, onCancel, onRedraw, onUndo }: { mode: FieldEditorMode; form: FieldInput; areaPreview: number; hasBoundary: boolean; hasOverlap: boolean; isSaving: boolean; onChange: (value: FieldInput) => void; onSave: () => void; onCancel: () => void; onRedraw: () => void; onUndo: () => void }) {
  return (
    <section className="rounded-2xl border border-emerald-900/10 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">{mode === "editing" ? "编辑地块" : "新增地块"}</p>
          <h2 className="mt-1 text-base font-bold text-slate-900">{hasBoundary ? `${formatMu(areaPreview)} 亩` : "等待圈定边界"}</h2>
        </div>
        <button onClick={onCancel} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button>
      </div>
      {hasOverlap && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">当前边界与已有地块重叠，请调整后保存。</div>}
      <div className="mt-4 space-y-3">
        <FormLabel label="地块名称"><input value={form.name} onChange={(event) => onChange({ ...form, name: event.target.value })} placeholder="如：东侧一号田" className={formInputClass} /></FormLabel>
        <div className="grid grid-cols-2 gap-3">
          <FormLabel label="当前作物"><input value={form.current_crop} onChange={(event) => onChange({ ...form, current_crop: event.target.value })} placeholder="如：玉米" className={formInputClass} /></FormLabel>
          <FormLabel label="土壤类型"><input value={form.soil_type ?? ""} onChange={(event) => onChange({ ...form, soil_type: event.target.value })} placeholder="如：壤土" className={formInputClass} /></FormLabel>
        </div>
        <FormLabel label="状态"><select value={form.status} onChange={(event) => onChange({ ...form, status: event.target.value as FieldStatus })} className={formInputClass}><option value="idle">空闲</option><option value="planting">种植中</option><option value="fallow">休耕</option></select></FormLabel>
        <FormLabel label="备注"><textarea value={form.notes} onChange={(event) => onChange({ ...form, notes: event.target.value })} rows={3} className={`${formInputClass} resize-none`} /></FormLabel>
      </div>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <button disabled={!hasBoundary} onClick={onUndo} className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-600 disabled:cursor-not-allowed disabled:opacity-40"><Undo2 className="h-3.5 w-3.5" />撤销</button>
        <button onClick={onRedraw} className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-2 text-xs font-semibold text-slate-600"><RotateCcw className="h-3.5 w-3.5" />重绘</button>
        <button disabled={!hasBoundary || !form.name.trim() || hasOverlap || isSaving} onClick={onSave} className="inline-flex items-center justify-center gap-1 rounded-lg bg-emerald-800 px-2 py-2 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">{isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}保存</button>
      </div>
    </section>
  );
}

function WeatherPanel({ field, summary, isLoading, isError }: { field: Field | null; summary: FarmWeatherSummary | undefined; isLoading: boolean; isError: boolean }) {
  if (!field) return <section className="rounded-2xl border border-dashed border-emerald-200 bg-emerald-50/50 p-4"><div className="flex gap-2"><CloudSun className="h-5 w-5 text-emerald-700" /><div><h2 className="text-sm font-semibold text-emerald-950">选择地块查看天气</h2><p className="mt-1 text-xs leading-5 text-emerald-800">天气会按地块内部代表点查询。</p></div></div></section>;
  if (!field.boundary) return <section className="rounded-2xl border border-slate-200 bg-white p-4"><div className="flex gap-2"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><h2 className="text-sm font-semibold text-slate-900">需要补画地块边界</h2><p className="mt-1 text-xs leading-5 text-slate-500">历史地块没有边界，暂不能展示地块级天气。</p></div></div></section>;
  if (isLoading) return <section className="flex items-center gap-2 rounded-2xl border border-emerald-900/10 bg-white p-4 text-sm text-slate-500"><Loader2 className="h-4 w-4 animate-spin text-emerald-700" />正在获取地块天气</section>;
  if (isError || !summary?.available || !summary.current) return <section className="rounded-2xl border border-slate-200 bg-white p-4"><div className="flex gap-2"><AlertTriangle className="h-5 w-5 text-amber-600" /><div><h2 className="text-sm font-semibold text-slate-900">天气暂不可用</h2><p className="mt-1 text-xs leading-5 text-slate-500">{summary?.reason === "FIELD_BOUNDARY_REQUIRED" ? "请先为地块补画边界。" : "天气服务未配置或暂时不可用。"}</p></div></div></section>;
  return <section className="overflow-hidden rounded-2xl border border-emerald-900/10 bg-white shadow-sm"><div className="border-b border-emerald-900/10 bg-[#edf6ed] px-4 py-3"><p className="text-xs font-medium uppercase tracking-[0.16em] text-emerald-700">地块天气</p><div className="mt-1 flex items-end justify-between"><h2 className="text-2xl font-bold text-emerald-950">{summary.current.temperature}°</h2><span className="text-sm font-semibold text-emerald-800">{summary.current.condition}</span></div><div className="mt-2 flex gap-3 text-xs text-emerald-900"><span className="inline-flex items-center gap-1"><ThermometerSun className="h-3.5 w-3.5" />湿度 {summary.current.humidity}%</span><span className="inline-flex items-center gap-1"><Wind className="h-3.5 w-3.5" />{summary.current.wind_level} 级风</span></div></div><div className="space-y-3 p-3"><DailyList summary={summary} /><RiskList alerts={summary.alerts} /><p className="text-[11px] text-slate-400">更新于 {summary.current.update_time || "--"}</p></div></section>;
}

function DailyList({ summary }: { summary: FarmWeatherSummary }) {
  if (!summary.daily.length) return null;
  return <div><p className="mb-2 text-xs font-medium text-slate-500">未来 3 天</p><div className="space-y-1.5">{summary.daily.map((day) => <div key={day.date} className="flex items-center justify-between rounded-lg bg-slate-50 px-2.5 py-2 text-xs text-slate-600"><span>{day.date} · {day.condition}</span><span>{day.min_temp}° / {day.max_temp}°</span></div>)}</div></div>;
}

function RiskList({ alerts }: { alerts: FarmWeatherAlert[] }) {
  if (!alerts.length) return <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800">当前未发现明显天气风险</div>;
  return <div><p className="mb-2 text-xs font-medium text-slate-500">天气风险</p><div className="space-y-2">{alerts.map((alert) => <div key={`${alert.alert_type}-${alert.date}`} className={`flex items-center justify-between rounded-lg border px-2.5 py-2 text-xs ${riskStyle[alert.severity] ?? "border-slate-200 bg-slate-50 text-slate-700"}`}><span>{alert.alert_type} · {alert.date}</span><strong>{alert.severity}风险</strong></div>)}</div></div>;
}

function CreateFarmModal({ onClose, onSuccess }: { onClose: () => void; onSuccess: () => Promise<void> }) {
  const showToast = useUIStore((state) => state.showToast);
  const [form, setForm] = useState<FarmInput>({ name: "", location: "", latitude: null, longitude: null, area_mu: 0, description: "" });
  const mutation = useMutation({ mutationFn: () => createFarm(form), onSuccess: () => { showToast("农场创建成功，请在地图上设置位置", "success"); void onSuccess(); }, onError: (error: unknown) => showToast(errorMessage(error, "创建农场失败"), "error") });
  return <Modal title="新增农场" onClose={onClose}><FormLabel label="农场名称"><input autoFocus value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} placeholder="如：东山农场" className={formInputClass} /></FormLabel><FormLabel label="位置说明"><input value={form.location} onChange={(event) => setForm({ ...form, location: event.target.value })} placeholder="如：寿光市" className={formInputClass} /></FormLabel><FormLabel label="备注"><textarea value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} rows={3} className={`${formInputClass} resize-none`} /></FormLabel><button disabled={!form.name.trim() || mutation.isPending} onClick={() => mutation.mutate()} className={modalSubmitClass}>{mutation.isPending ? "创建中" : "创建农场"}</button></Modal>;
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) { return <div className="fixed inset-0 z-[1000] flex items-center justify-center p-4"><button aria-label="关闭弹窗" className="absolute inset-0 bg-slate-950/35" onClick={onClose} /><div className="relative w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl"><div className="mb-5 flex items-center justify-between"><h2 className="text-lg font-bold text-slate-900">{title}</h2><button onClick={onClose} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100"><X className="h-4 w-4" /></button></div><div className="space-y-4">{children}</div></div></div>; }
function FormLabel({ label, children }: { label: string; children: React.ReactNode }) { return <label className="block text-sm font-medium text-slate-700"><span className="mb-1.5 block">{label}</span>{children}</label>; }
