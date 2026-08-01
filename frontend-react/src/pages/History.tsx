import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  History as HistoryIcon,
  Trash2,
  Upload,
  RefreshCw,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import {
  getHistory,
  clearHistory,
  deleteHistoryItem,
  uploadHistoryToKb,
  type HistoryRecord,
} from "../api/history";
import { useUIStore } from "../stores/ui";
import { formatTime } from "../lib/format";

export default function History() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [source, setSource] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["history", page, source],
    queryFn: () => getHistory(page, 20, source || undefined),
  });

  const clearMutation = useMutation({
    mutationFn: clearHistory,
    onSuccess: () => {
      showToast("已清空", "success");
      queryClient.invalidateQueries({ queryKey: ["history"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteHistoryItem,
    onSuccess: () => {
      showToast("已删除", "success");
      queryClient.invalidateQueries({ queryKey: ["history"] });
    },
  });

  const uploadMutation = useMutation({
    mutationFn: uploadHistoryToKb,
    onSuccess: () => {
      showToast("已上传至知识库", "success");
      queryClient.invalidateQueries({ queryKey: ["history"] });
    },
    onError: (err: any) => showToast(err.message, "error"),
  });

  const records = data?.records || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / 20);

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold flex items-center gap-2">
          <HistoryIcon className="w-5 h-5 text-text-muted" /> 历史记录
        </h1>
        <div className="flex items-center gap-2">
          <select
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setPage(1);
            }}
            className="px-3 py-1.5 text-sm border border-border rounded-lg bg-bg-card"
          >
            <option value="">全部来源</option>
            <option value="chat">智能问答</option>
            <option value="weather">天气</option>
            <option value="marketing">营销</option>
          </select>
          <button
            onClick={() =>
              confirm("确定清空所有历史？") && clearMutation.mutate()
            }
            className="p-2 text-text-muted hover:text-accent-red transition-colors"
            title="清空"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <button
            onClick={() =>
              queryClient.invalidateQueries({ queryKey: ["history"] })
            }
            className="p-2 text-text-muted hover:text-primary transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 skeleton rounded-xl" />
          ))}
        </div>
      ) : records.length ? (
        <div className="space-y-3">
          {records.map((r) => (
            <HistoryCard
              key={r.id}
              record={r}
              expanded={expandedId === r.id}
              onToggle={() =>
                setExpandedId(expandedId === r.id ? null : r.id)
              }
              onDelete={() => deleteMutation.mutate(r.id)}
              onUpload={() => uploadMutation.mutate(r.id)}
            />
          ))}
        </div>
      ) : (
        <div className="text-center py-12 text-text-muted text-sm">
          暂无历史记录
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1 text-sm border border-border rounded-lg disabled:opacity-50"
          >
            上一页
          </button>
          <span className="text-sm text-text-muted">
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1 text-sm border border-border rounded-lg disabled:opacity-50"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}

function HistoryCard({
  record,
  expanded,
  onToggle,
  onDelete,
  onUpload,
}: {
  record: HistoryRecord;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  onUpload: () => void;
}) {
  return (
    <div className="bg-bg-card rounded-xl border border-border overflow-hidden">
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-bg-hover transition-colors"
        onClick={onToggle}
      >
        <span className="px-2 py-0.5 text-xs bg-primary-light text-primary rounded">
          {record.source}
        </span>
        <span className="flex-1 text-sm truncate">{record.question}</span>
        <span className="text-xs text-text-muted">
          {formatTime(record.created_at)}
        </span>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-text-muted" />
        ) : (
          <ChevronDown className="w-4 h-4 text-text-muted" />
        )}
      </div>
      {expanded && (
        <div className="px-4 pb-3 border-t border-border pt-3">
          <div className="text-sm text-text-secondary mb-3 markdown-body whitespace-pre-wrap">
            {record.answer?.slice(0, 500)}
            {record.answer && record.answer.length > 500 && "..."}
          </div>
          <div className="flex items-center gap-2">
            {!record.uploaded_to_kb && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onUpload();
                }}
                className="flex items-center gap-1 px-3 py-1 text-xs text-accent-blue border border-accent-blue/20 rounded-lg hover:bg-accent-blue/5"
              >
                <Upload className="w-3 h-3" /> 上传至知识库
              </button>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="flex items-center gap-1 px-3 py-1 text-xs text-accent-red border border-accent-red/20 rounded-lg hover:bg-accent-red/5"
            >
              <Trash2 className="w-3 h-3" /> 删除
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
