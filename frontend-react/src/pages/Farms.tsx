import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Tractor, Plus, Trash2 } from "lucide-react";
import {
  getFarms,
  getFarmDetail,
  createFarm,
  deleteFarm,
} from "../api/farms";
import { useUIStore } from "../stores/ui";
import type { Field } from "../types/farm";

export default function Farms() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [selectedFarmId, setSelectedFarmId] = useState<number | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const { data: farms, isLoading } = useQuery({
    queryKey: ["farms"],
    queryFn: getFarms,
  });

  const { data: fields } = useQuery({
    queryKey: ["fields", selectedFarmId],
    queryFn: () => getFarmDetail(selectedFarmId!),
    enabled: !!selectedFarmId,
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

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold flex items-center gap-2">
          <Tractor className="w-5 h-5 text-primary" /> 农场管理
        </h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors"
        >
          <Plus className="w-4 h-4" /> 新建农场
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Farm list */}
        <div className="space-y-3">
          {isLoading ? (
            [1, 2, 3].map((i) => <div key={i} className="h-20 skeleton rounded-xl" />)
          ) : farms?.length ? (
            farms.map((farm) => (
              <div
                key={farm.id}
                onClick={() => setSelectedFarmId(farm.id)}
                className={`bg-bg-card rounded-xl border p-4 cursor-pointer transition-all ${
                  selectedFarmId === farm.id
                    ? "border-primary ring-1 ring-primary/20"
                    : "border-border hover:border-primary/50"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <div className="font-medium text-sm">{farm.name}</div>
                    <div className="text-xs text-text-muted mt-1">
                      {farm.location} · {farm.area_mu} 亩
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm(`确定删除 "${farm.name}"？`))
                        deleteMutation.mutate(farm.id);
                    }}
                    className="p-1 text-text-muted hover:text-accent-red"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))
          ) : (
            <div className="text-center py-8 text-sm text-text-muted">
              暂无农场，点击右上角创建
            </div>
          )}
        </div>

        {/* Field list */}
        <div className="lg:col-span-2">
          {selectedFarmId ? (
            <div className="bg-bg-card rounded-xl border border-border p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium">地块列表</h3>
                <button className="flex items-center gap-1 px-2 py-1 text-xs text-primary border border-primary/20 rounded-lg hover:bg-primary-light">
                  <Plus className="w-3 h-3" /> 新建地块
                </button>
              </div>
              {fields?.length ? (
                <div className="space-y-2">
                  {fields.map((field) => (
                    <FieldCard key={field.id} field={field} />
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-sm text-text-muted">
                  暂无地块
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-sm text-text-muted bg-bg-card rounded-xl border border-border">
              请先选择一个农场
            </div>
          )}
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
    </div>
  );
}

function FieldCard({ field }: { field: Field }) {
  const statusColors = {
    idle: "bg-gray-100 text-gray-600",
    planting: "bg-green-100 text-green-700",
    fallow: "bg-amber-100 text-amber-700",
  };
  const statusLabels = { idle: "空闲", planting: "种植中", fallow: "休耕" };

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-border hover:bg-bg-hover transition-colors">
      <div>
        <div className="text-sm font-medium">{field.name}</div>
        <div className="text-xs text-text-muted mt-1">
          {field.current_crop && `${field.current_crop} · `}
          {field.area_mu} 亩 · {field.soil_type}
        </div>
      </div>
      <span
        className={`px-2 py-0.5 text-xs rounded ${statusColors[field.status]}`}
      >
        {statusLabels[field.status]}
      </span>
    </div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-md bg-bg-card rounded-xl border border-border p-6 shadow-lg">
        <h3 className="text-lg font-semibold mb-4">新建农场</h3>
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1">
              农场名称
            </label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
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
              className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
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
              rows={3}
              className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border border-border rounded-lg hover:bg-bg-hover"
          >
            取消
          </button>
          <button
            onClick={() => mutation.mutate()}
            disabled={!form.name}
            className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover disabled:opacity-50"
          >
            创建
          </button>
        </div>
      </div>
    </div>
  );
}
