import { useState } from "react";
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
} from "lucide-react";
import {
  getFarms,
  getFarmDetail,
  createFarm,
  deleteFarm,
  getTrajectories,
  getTrajectoryPoints,
} from "../api/farms";
import { useUIStore } from "../stores/ui";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import Modal from "../components/ui/Modal";
import EmptyState from "../components/ui/EmptyState";
import LoadingGrid from "../components/ui/LoadingGrid";
import FarmMap from "../components/map/FarmMap";
import type { Field, TrajectoryFile, TrajectoryPoint } from "../types/farm";

export default function Farms() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [selectedFieldId, setSelectedFieldId] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [trajectoryPoints, setTrajectoryPoints] = useState<TrajectoryPoint[]>([]);

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

  const handleLoadTrajectory = async (file: TrajectoryFile) => {
    try {
      const points = await getTrajectoryPoints(file.id);
      setTrajectoryPoints(points);
    } catch (err: any) {
      showToast(`加载轨迹失败: ${err.message}`, "error");
    }
  };

  // Prepare farm markers for map
  const farmMarkers =
    farms?.map((f) => ({
      id: f.id,
      name: f.name,
      location: f.location,
      area_mu: f.area_mu,
      latitude: f.latitude,
      longitude: f.longitude,
    })) || [];

  // Prepare trajectory lines for map
  const trajectoryLines =
    trajectoryPoints.length > 0
      ? [
          {
            points: trajectoryPoints.map((p) => [p.latitude, p.longitude] as [number, number]),
            color: "#3b82f6",
          },
        ]
      : [];

  return (
    <WorkspaceLayout
      title="农场管理"
      icon={Tractor}
      iconColor="text-accent-green"
      description="管理农场、地块和作业轨迹"
      fullWidth
      action={
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors"
        >
          <Plus className="w-4 h-4" /> 新建农场
        </button>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4" style={{ height: "calc(100vh - 180px)" }}>
        {/* Left panel — farm & field list */}
        <div className="lg:col-span-4 flex flex-col gap-4 min-h-0">
          {/* Farm list */}
          <div className="bg-bg-card rounded-xl border border-border flex-1 min-h-0 flex flex-col">
            <div className="px-4 py-3 border-b border-border">
              <h3 className="text-sm font-semibold text-text-primary">
                农场列表
              </h3>
            </div>
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {isLoading ? (
                <LoadingGrid rows={3} height="h-16" />
              ) : farms?.length ? (
                farms.map((farm) => (
                  <div
                    key={farm.id}
                    onClick={() => {
                      setSelectedFarmId(farm.id);
                      setSelectedFieldId(null);
                      setTrajectoryPoints([]);
                    }}
                    className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-all ${
                      selectedFarmId === farm.id
                        ? "bg-primary/10 border border-primary/30"
                        : "hover:bg-bg-hover border border-transparent"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-medium truncate">
                        {farm.name}
                      </div>
                      <div className="text-xs text-text-muted mt-0.5 flex items-center gap-1">
                        <MapPin className="w-3 h-3" />
                        {farm.location} · {farm.area_mu} 亩
                      </div>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
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
                <EmptyState
                  icon={Tractor}
                  title="暂无农场"
                  description="点击右上角创建您的第一个农场"
                />
              )}
            </div>
          </div>

          {/* Field list (when farm selected) */}
          {selectedFarmId && (
            <div className="bg-bg-card rounded-xl border border-border flex-1 min-h-0 flex flex-col">
              <div className="px-4 py-3 border-b border-border">
                <h3 className="text-sm font-semibold text-text-primary">
                  地块列表
                </h3>
              </div>
              <div className="flex-1 overflow-y-auto p-2 space-y-1">
                {fields?.length ? (
                  fields.map((field) => (
                    <div
                      key={field.id}
                      onClick={() => {
                        setSelectedFieldId(field.id);
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
                            <Wheat className="w-3 h-3" />
                            {field.current_crop}
                          </span>
                        )}
                        <span>{field.area_mu} 亩</span>
                        <span>{field.soil_type}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <EmptyState
                    icon={MapPin}
                    title="暂无地块"
                    description="该农场下还没有地块"
                  />
                )}
              </div>
            </div>
          )}

          {/* Trajectory list (when field selected) */}
          {selectedFieldId && trajectories && trajectories.length > 0 && (
            <div className="bg-bg-card rounded-xl border border-border">
              <div className="px-4 py-3 border-b border-border">
                <h3 className="text-sm font-semibold text-text-primary">
                  作业轨迹
                </h3>
              </div>
              <div className="p-2 space-y-1">
                {trajectories.map((traj) => (
                  <button
                    key={traj.id}
                    onClick={() => handleLoadTrajectory(traj)}
                    className="w-full text-left p-3 rounded-lg hover:bg-bg-hover transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-text-muted flex-shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">
                          {traj.filename}
                        </div>
                        <div className="text-xs text-text-muted flex items-center gap-3 mt-0.5">
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
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right — map */}
        <div className="lg:col-span-8 min-h-0">
          <FarmMap
            farms={farmMarkers}
            selectedFarmId={selectedFarmId}
            trajectories={trajectoryLines}
            onFarmClick={(id) => {
              setSelectedFarmId(id);
              setSelectedFieldId(null);
              setTrajectoryPoints([]);
            }}
          />
        </div>
      </div>

      {/* Create Farm Modal */}
      {showCreateModal && (
        <CreateFarmModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false);
            queryClient.invalidateQueries({ queryKey: ["farms"] });
          }}
        />
      )}
    </WorkspaceLayout>
  );
}

function StatusBadge({ status }: { status: Field["status"] }) {
  const config = {
    idle: { label: "空闲", cls: "bg-gray-100 text-gray-600" },
    planting: { label: "种植中", cls: "bg-green-100 text-green-700" },
    fallow: { label: "休耕", cls: "bg-amber-100 text-amber-700" },
  };
  const c = config[status] || config.idle;
  return (
    <span className={`px-1.5 py-0.5 text-xs rounded ${c.cls}`}>{c.label}</span>
  );
}

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
    <Modal
      title="新建农场"
      onClose={onClose}
      footer={
        <>
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border border-border rounded-lg hover:bg-bg-hover transition-colors"
          >
            取消
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.name}
            className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50 transition-colors"
          >
            创建
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            农场名称
          </label>
          <input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="如：张庄有机农场"
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            位置
          </label>
          <input
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
            placeholder="如：山东省寿光市"
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
          />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              面积 (亩)
            </label>
            <input
              type="number"
              value={form.area_mu}
              onChange={(e) =>
                setForm({ ...form, area_mu: Number(e.target.value) })
              }
              className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              纬度
            </label>
            <input
              type="number"
              step="any"
              value={form.latitude}
              onChange={(e) =>
                setForm({ ...form, latitude: Number(e.target.value) })
              }
              className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              经度
            </label>
            <input
              type="number"
              step="any"
              value={form.longitude}
              onChange={(e) =>
                setForm({ ...form, longitude: Number(e.target.value) })
              }
              className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium text-text-secondary mb-1">
            描述
          </label>
          <textarea
            value={form.description}
            onChange={(e) =>
              setForm({ ...form, description: e.target.value })
            }
            rows={2}
            className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
          />
        </div>
      </div>
    </Modal>
  );
}
