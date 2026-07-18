import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Tractor,
  Plus,
  Trash2,
  MapPin,
  ChevronRight,
  FileText,
  Ruler,
  Gauge,
  Wheat,
  Upload,
  BarChart3,
  Loader2,
  Radar,
} from "lucide-react";
import {
  getFarms,
  getFarmDetail,
  createFarm,
  createField,
  deleteFarm,
  getTrajectories,
  getTrajectoryPoints,
  uploadTrajectory,
  deleteTrajectory,
} from "../api/farms";
import { useUIStore } from "../stores/ui";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import EmptyState from "../components/ui/EmptyState";
import LoadingGrid from "../components/ui/LoadingGrid";
import FarmMap from "../components/map/FarmMap";
import TrajectoryAnalysis from "../components/farm/TrajectoryAnalysis";
import type { Field, TrajectoryFile, TrajectoryPoint } from "../types/farm";

export default function Farms() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);
  const [selectedFileId, setSelectedFileId] = useState<number | null>(null);
  const [trajectoryPoints, setTrajectoryPoints] = useState<TrajectoryPoint[]>([]);
  const [showAnalysis, setShowAnalysis] = useState(false);

  // Modal states
  const [createFarmOpen, setCreateFarmOpen] = useState(false);
  const [createFieldOpen, setCreateFieldOpen] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);

  const { data: farms, isLoading } = useQuery({
    queryKey: ["farms"],
    queryFn: getFarms,
  });

  const { data: fields } = useQuery({
    queryKey: ["fields", selectedFarmId],
    queryFn: () => getFarmDetail(selectedFarmId!),
    enabled: !!selectedFarmId,
  });

  const { data: trajectories } = useQuery({
    queryKey: ["trajectories", selectedFieldId],
    queryFn: () => getTrajectories(selectedFieldId!),
    enabled: !!selectedFieldId,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteFarm,
    onSuccess: () => {
      showToast("删除成功", "success");
      queryClient.invalidateQueries({ queryKey: ["farms"] });
      setSelectedFarmId(null);
    },
    onError: (err: any) => showToast(err.message, "error"),
  });

  const deleteTrajectoryMutation = useMutation({
    mutationFn: deleteTrajectory,
    onSuccess: () => {
      showToast("轨迹删除成功", "success");
      queryClient.invalidateQueries({ queryKey: ["trajectories"] });
      setSelectedFileId(null);
      setTrajectoryPoints([]);
    },
    onError: (err: any) => showToast(err.message, "error"),
  });

  const handleLoadTrajectory = async (file: TrajectoryFile) => {
    try {
      setSelectedFileId(file.id);
      setShowAnalysis(false);
      const points = await getTrajectoryPoints(file.id);
      setTrajectoryPoints(points);
    } catch (err: any) {
      showToast(`加载轨迹失败: ${err.message}`, "error");
    }
  };

  const farmMarkers =
    farms?.map((f) => ({
      id: f.id,
      name: f.name,
      location: f.location,
      area_mu: f.area_mu,
      latitude: f.latitude,
      longitude: f.longitude,
    })) || [];

  return (
    <>
      <WorkspaceLayout
        title="农场管理"
        icon={Tractor}
        iconColor="text-accent-green"
        description="管理农场、地块和作业轨迹"
        fullWidth
        action={
          <button
            onClick={() => setCreateFarmOpen(true)}
            className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors"
          >
            <Plus className="w-4 h-4" /> 新建农场
          </button>
        }
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 relative" style={{ height: "calc(100vh - 180px)" }}>
          {/* Left panel — above map */}
          <div className="lg:col-span-4 flex flex-col gap-4 min-h-0 overflow-y-auto relative z-10">
            {/* Farm list */}
            <div className="bg-bg-card rounded-xl border border-border flex-shrink-0">
              <div className="px-4 py-3 border-b border-border">
                <h3 className="text-sm font-semibold text-text-primary">农场列表</h3>
              </div>
              <div className="p-2 space-y-1 max-h-48 overflow-y-auto">
                {isLoading ? (
                  <LoadingGrid rows={3} height="h-16" />
                ) : farms?.length ? (
                  farms.map((farm) => (
                    <div
                      key={farm.id}
                      onClick={() => {
                        setSelectedFarmId(farm.id);
                        setSelectedFieldId(null);
                        setSelectedFileId(null);
                        setTrajectoryPoints([]);
                      }}
                      className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all ${
                        selectedFarmId === farm.id
                          ? "bg-primary/10 border border-primary/30"
                          : "hover:bg-bg-hover border border-transparent"
                      }`}
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{farm.name}</div>
                        <div className="text-xs text-text-muted mt-0.5 flex items-center gap-1">
                          <MapPin className="w-3 h-3" />
                          {farm.location} · {farm.area_mu} 亩
                        </div>
                      </div>
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Link
                          to={`/workspace/farm-agent?farmId=${farm.id}`}
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center gap-1 rounded-md bg-primary/10 px-2 py-1 text-[11px] font-semibold text-primary hover:bg-primary/20"
                          aria-label={`对 ${farm.name} 启动 AI 巡检`}
                        >
                          <Radar className="h-3 w-3" /> AI 巡检
                        </Link>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            if (confirm(`确定删除 "${farm.name}"？`))
                              deleteMutation.mutate(farm.id);
                          }}
                          className="p-1 text-text-muted hover:text-accent-red rounded"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                        <ChevronRight className="w-4 h-4 text-text-muted" />
                      </div>
                    </div>
                  ))
                ) : (
                  <EmptyState icon={Tractor} title="暂无农场" description="点击右上角创建您的第一个农场" />
                )}
              </div>
            </div>

            {/* Field list */}
            {selectedFarmId && (
              <div className="bg-bg-card rounded-xl border border-border flex-shrink-0">
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primary">地块列表</h3>
                  <button
                    onClick={() => setCreateFieldOpen(true)}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-accent-blue border border-accent-blue/20 rounded-lg hover:bg-accent-blue/5 transition-colors"
                  >
                    <Plus className="w-3 h-3" /> 添加地块
                  </button>
                </div>
                <div className="p-2 space-y-1 max-h-48 overflow-y-auto">
                  {fields?.length ? (
                    fields.map((field) => (
                      <div
                        key={field.id}
                        onClick={() => {
                          setSelectedFieldId(field.id);
                          setSelectedFileId(null);
                          setTrajectoryPoints([]);
                        }}
                        className={`p-3 rounded-lg cursor-pointer transition-all ${
                          selectedFieldId === field.id
                            ? "bg-accent-blue/10 border border-accent-blue/30"
                            : "hover:bg-bg-hover border border-transparent"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="text-sm font-medium">{field.name}</div>
                          <StatusBadge status={field.status} />
                        </div>
                        <div className="text-xs text-text-muted mt-1 flex items-center gap-2">
                          {field.current_crop && (
                            <span className="flex items-center gap-0.5">
                              <Wheat className="w-3 h-3" /> {field.current_crop}
                            </span>
                          )}
                          <span>{field.area_mu} 亩</span>
                          <span>{field.soil_type}</span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <EmptyState icon={MapPin} title="暂无地块" />
                  )}
                </div>
              </div>
            )}

            {/* Trajectory list */}
            {selectedFieldId && (
              <div className="bg-bg-card rounded-xl border border-border flex-shrink-0">
                <div className="px-4 py-3 border-b border-border flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primary">作业轨迹</h3>
                  <button
                    onClick={() => setUploadOpen(true)}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-primary border border-primary/20 rounded-lg hover:bg-primary/5 transition-colors"
                  >
                    <Upload className="w-3 h-3" /> 上传
                  </button>
                </div>
                <div className="p-2 space-y-1 max-h-60 overflow-y-auto">
                  {trajectories?.length ? (
                    trajectories.map((traj) => (
                      <div
                        key={traj.id}
                        className={`p-3 rounded-lg transition-all ${
                          selectedFileId === traj.id
                            ? "bg-accent-amber/10 border border-accent-amber/30"
                            : "hover:bg-bg-hover border border-transparent"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <button
                            onClick={() => handleLoadTrajectory(traj)}
                            className="flex-1 text-left min-w-0"
                          >
                            <div className="flex items-center gap-2">
                              <FileText className="w-4 h-4 text-text-muted flex-shrink-0" />
                              <div className="min-w-0">
                                <div className="text-sm font-medium truncate">{traj.filename}</div>
                                <div className="text-xs text-text-muted flex items-center gap-2 mt-0.5">
                                  <span className="flex items-center gap-0.5">
                                    <Ruler className="w-3 h-3" />
                                    {(traj.total_distance_m / 1000).toFixed(1)}km
                                  </span>
                                  <span className="flex items-center gap-0.5">
                                    <Gauge className="w-3 h-3" />
                                    {traj.avg_speed.toFixed(1)}m/s
                                  </span>
                                  <span>{traj.work_area_mu.toFixed(1)}亩</span>
                                </div>
                              </div>
                            </div>
                          </button>
                          <div className="flex items-center gap-1 flex-shrink-0">
                            {selectedFileId === traj.id && (
                              <button
                                onClick={() => setShowAnalysis(!showAnalysis)}
                                className="p-1 text-text-muted hover:text-primary rounded"
                                title="查看分析"
                              >
                                <BarChart3 className="w-4 h-4" />
                              </button>
                            )}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (confirm(`确定删除 "${traj.filename}"？`))
                                  deleteTrajectoryMutation.mutate(traj.id);
                              }}
                              className="p-1 text-text-muted hover:text-accent-red rounded"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <EmptyState icon={FileText} title="暂无轨迹数据" description="点击上传按钮导入 Excel 轨迹文件" />
                  )}
                </div>
              </div>
            )}

            {/* Analysis panel */}
            {selectedFileId && showAnalysis && (
              <div className="bg-bg-card rounded-xl border border-border p-4">
                <TrajectoryAnalysis fileId={selectedFileId} />
              </div>
            )}
          </div>

          {/* Right — map */}
          <div className="lg:col-span-8 min-h-0">
            <FarmMap
              farms={farmMarkers}
              selectedFarmId={selectedFarmId}
              trajectoryPoints={trajectoryPoints}
              onFarmClick={(id) => {
                setSelectedFarmId(id);
                setSelectedFieldId(null);
                setSelectedFileId(null);
                setTrajectoryPoints([]);
              }}
            />
          </div>
        </div>
      </WorkspaceLayout>

      {/* Modals — rendered outside WorkspaceLayout to avoid overflow clipping */}
      {createFarmOpen && (
        <CreateFarmModal
          onClose={() => setCreateFarmOpen(false)}
          onSuccess={() => {
            setCreateFarmOpen(false);
            queryClient.invalidateQueries({ queryKey: ["farms"] });
          }}
        />
      )}
      {uploadOpen && selectedFieldId && (
        <UploadTrajectoryModal
          fieldId={selectedFieldId}
          onClose={() => setUploadOpen(false)}
          onSuccess={() => {
            setUploadOpen(false);
            queryClient.invalidateQueries({ queryKey: ["trajectories"] });
          }}
        />
      )}
      {createFieldOpen && selectedFarmId && (
        <CreateFieldModal
          farmId={selectedFarmId}
          onClose={() => setCreateFieldOpen(false)}
          onSuccess={() => {
            setCreateFieldOpen(false);
            queryClient.invalidateQueries({ queryKey: ["fields", selectedFarmId] });
          }}
        />
      )}
    </>
  );
}

function StatusBadge({ status }: { status: Field["status"] }) {
  const config = {
    idle: { label: "空闲", cls: "bg-gray-100 text-gray-600" },
    planting: { label: "种植中", cls: "bg-green-100 text-green-700" },
    fallow: { label: "休耕", cls: "bg-amber-100 text-amber-700" },
  };
  const c = config[status] || config.idle;
  return <span className={`px-1.5 py-0.5 text-xs rounded ${c.cls}`}>{c.label}</span>;
}

/* ==================== Create Field Modal ==================== */

function CreateFieldModal({
  farmId,
  onClose,
  onSuccess,
}: {
  farmId: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const showToast = useUIStore((s) => s.showToast);
  const [form, setForm] = useState({
    name: "",
    area_mu: 0,
    soil_type: "",
    current_crop: "",
    status: "idle" as "idle" | "planting" | "fallow",
    notes: "",
  });

  const mutation = useMutation({
    mutationFn: () =>
      createField(farmId, {
        ...form,
        planting_date: null as any,
        expected_harvest: null as any,
        growth_stage: "",
      }),
    onSuccess: () => {
      showToast("地块创建成功", "success");
      onSuccess();
    },
    onError: (err: any) => showToast(err.message, "error"),
  });

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-bg-card rounded-2xl shadow-2xl border border-border overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-hover/50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-accent-blue/10">
              <MapPin className="w-4 h-4 text-accent-blue" />
            </div>
            <h3 className="text-base font-semibold text-text-primary">添加地块</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              地块名称 <span className="text-accent-red">*</span>
            </label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：1号大棚、东区地块"
              className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                面积 (亩)
              </label>
              <input
                type="number"
                value={form.area_mu || ""}
                onChange={(e) => setForm({ ...form, area_mu: Number(e.target.value) })}
                placeholder="0"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                土壤类型
              </label>
              <input
                value={form.soil_type}
                onChange={(e) => setForm({ ...form, soil_type: e.target.value })}
                placeholder="如：壤土、沙土"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                当前作物
              </label>
              <input
                value={form.current_crop}
                onChange={(e) => setForm({ ...form, current_crop: e.target.value })}
                placeholder="如：番茄、水稻"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                状态
              </label>
              <div className="flex gap-1.5">
                {[
                  { value: "idle", label: "空闲" },
                  { value: "planting", label: "种植中" },
                  { value: "fallow", label: "休耕" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setForm({ ...form, status: opt.value as any })}
                    className={`flex-1 px-2 py-2 text-xs rounded-lg border transition-all ${
                      form.status === opt.value
                        ? "border-primary bg-primary/5 text-primary"
                        : "border-border text-text-secondary hover:border-primary/50"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              备注
            </label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
              placeholder="地块补充信息..."
              rows={2}
              className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border bg-bg-hover/30">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary border border-border rounded-xl hover:bg-bg-hover transition-colors"
          >
            取消
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.name || mutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-accent-blue text-white rounded-xl hover:opacity-90 disabled:opacity-50 transition-colors"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 spinner" />}
            {mutation.isPending ? "创建中..." : "创建地块"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ==================== Create Farm Modal ==================== */

function CreateFarmModal({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess: () => void;
}) {
  const showToast = useUIStore((s) => s.showToast);
  const [form, setForm] = useState({
    name: "",
    location: "",
    area_mu: 0,
    latitude: 0,
    longitude: 0,
    description: "",
  });

  const mutation = useMutation({
    mutationFn: () => createFarm(form),
    onSuccess: () => {
      showToast("创建成功", "success");
      onSuccess();
    },
    onError: (err: any) => showToast(err.message, "error"),
  });

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-bg-card rounded-2xl shadow-2xl border border-border overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-hover/50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-primary/10">
              <Plus className="w-4 h-4 text-primary" />
            </div>
            <h3 className="text-base font-semibold text-text-primary">新建农场</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              农场名称 <span className="text-accent-red">*</span>
            </label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：张庄有机农场"
              className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              位置
            </label>
            <input
              value={form.location}
              onChange={(e) => setForm({ ...form, location: e.target.value })}
              placeholder="如：山东省寿光市"
              className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                面积 (亩)
              </label>
              <input
                type="number"
                value={form.area_mu || ""}
                onChange={(e) => setForm({ ...form, area_mu: Number(e.target.value) })}
                placeholder="0"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                纬度
              </label>
              <input
                type="number"
                step="any"
                value={form.latitude || ""}
                onChange={(e) => setForm({ ...form, latitude: Number(e.target.value) })}
                placeholder="36.0671"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-1.5">
                经度
              </label>
              <input
                type="number"
                step="any"
                value={form.longitude || ""}
                onChange={(e) => setForm({ ...form, longitude: Number(e.target.value) })}
                placeholder="118.7854"
                className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              描述
            </label>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="农场基本情况描述..."
              rows={2}
              className="w-full px-3 py-2.5 text-sm border border-border rounded-xl outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border bg-bg-hover/30">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary border border-border rounded-xl hover:bg-bg-hover transition-colors"
          >
            取消
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.name || mutation.isPending}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-primary text-white rounded-xl hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            {mutation.isPending && <Loader2 className="w-3.5 h-3.5 spinner" />}
            {mutation.isPending ? "创建中..." : "创建"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ==================== Upload Trajectory Modal ==================== */

function UploadTrajectoryModal({
  fieldId,
  onClose,
  onSuccess,
}: {
  fieldId: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const showToast = useUIStore((s) => s.showToast);
  const [file, setFile] = useState<File | null>(null);
  const [coordSystem, setCoordSystem] = useState("auto");
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      await uploadTrajectory(fieldId, file, coordSystem);
      showToast("轨迹上传成功", "success");
      onSuccess();
    } catch (err: any) {
      showToast(`上传失败: ${err.message}`, "error");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped && (dropped.name.endsWith(".xlsx") || dropped.name.endsWith(".xls"))) {
      setFile(dropped);
    } else {
      showToast("请上传 .xlsx 或 .xls 文件", "error");
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div className="relative w-full max-w-lg bg-bg-card rounded-2xl shadow-2xl border border-border overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-bg-hover/50">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-accent-amber/10">
              <Upload className="w-4 h-4 text-accent-amber" />
            </div>
            <h3 className="text-base font-semibold text-text-primary">上传轨迹文件</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* Drag & drop area */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              选择文件
            </label>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all cursor-pointer ${
                dragOver
                  ? "border-primary bg-primary/5"
                  : file
                  ? "border-accent-green/50 bg-accent-green/5"
                  : "border-border hover:border-primary/50"
              }`}
            >
              <input
                type="file"
                accept=".xlsx,.xls"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              {file ? (
                <div className="flex items-center justify-center gap-2">
                  <FileText className="w-5 h-5 text-accent-green" />
                  <div>
                    <div className="text-sm font-medium text-text-primary">{file.name}</div>
                    <div className="text-xs text-text-muted">{(file.size / 1024).toFixed(1)} KB</div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="ml-2 text-xs text-accent-red hover:underline"
                  >
                    移除
                  </button>
                </div>
              ) : (
                <>
                  <Upload className="w-8 h-8 text-text-muted mx-auto mb-2" />
                  <div className="text-sm text-text-secondary">点击或拖拽文件到此处</div>
                  <div className="text-xs text-text-muted mt-1">支持 .xlsx、.xls 格式</div>
                </>
              )}
            </div>
          </div>

          {/* Coord system */}
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              坐标系
            </label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { value: "auto", label: "自动检测", desc: "智能识别坐标系" },
                { value: "wgs84", label: "WGS-84", desc: "GPS 原始坐标" },
                { value: "gcj02", label: "GCJ-02", desc: "高德/腾讯地图坐标" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setCoordSystem(opt.value)}
                  className={`p-3 rounded-xl border text-left transition-all ${
                    coordSystem === opt.value
                      ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                      : "border-border hover:border-primary/50"
                  }`}
                >
                  <div className={`text-sm font-medium ${coordSystem === opt.value ? "text-primary" : "text-text-primary"}`}>
                    {opt.label}
                  </div>
                  <div className="text-xs text-text-muted mt-0.5">{opt.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="text-xs text-text-muted bg-bg-hover rounded-lg px-3 py-2">
            <span className="font-medium">Excel 格式要求：</span>
            必须包含经度、纬度列。可选列：速度、作业状态、深度、时间、幅宽、农机编号。
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border bg-bg-hover/30">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary border border-border rounded-xl hover:bg-bg-hover transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="flex items-center gap-1.5 px-4 py-2 text-sm bg-primary text-white rounded-xl hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            {uploading && <Loader2 className="w-3.5 h-3.5 spinner" />}
            {uploading ? "上传中..." : "上传"}
          </button>
        </div>
      </div>
    </div>
  );
}
