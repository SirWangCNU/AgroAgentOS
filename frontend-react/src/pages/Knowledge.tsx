import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Upload, Trash2, RefreshCw, ArrowLeft } from "lucide-react";
import { uploadDocument, getDocuments, deleteDocument } from "../api/knowledge";
import { useUIStore } from "../stores/ui";
import { STORAGE_KEYS } from "../lib/constants";

export default function Knowledge() {
  const navigate = useNavigate();
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);

  const { data: docs, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  const deleteMutation = useMutation({
    mutationFn: async (source: string) => {
      const token = sessionStorage.getItem(STORAGE_KEYS.KB_ADMIN_TOKEN) || prompt("请输入知识库管理员 Token:");
      if (!token) throw new Error("需要管理员 Token");
      sessionStorage.setItem(STORAGE_KEYS.KB_ADMIN_TOKEN, token);
      await deleteDocument(source, token);
    },
    onSuccess: () => {
      showToast("删除成功", "success");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (err: any) => showToast(err.message, "error"),
  });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const token = sessionStorage.getItem(STORAGE_KEYS.KB_ADMIN_TOKEN) || prompt("请输入知识库管理员 Token:");
    if (!token) return;
    sessionStorage.setItem(STORAGE_KEYS.KB_ADMIN_TOKEN, token);

    setUploading(true);
    try {
      const result = await uploadDocument(file, token);
      showToast(`上传成功，${result.chunks_indexed} 个片段已索引`, "success");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch (err: any) {
      showToast(`上传失败: ${err.message}`, "error");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate("/workspace")} className="p-2 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <h1 className="text-lg font-semibold flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-accent-blue" /> 知识库
        </h1>
      </div>

      {/* Upload */}
      <div className="bg-bg-card rounded-xl border border-border p-6">
        <h3 className="text-sm font-medium mb-3">上传文档</h3>
        <label className="flex flex-col items-center gap-2 p-8 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-primary transition-colors">
          <Upload className="w-8 h-8 text-text-muted" />
          <span className="text-sm text-text-muted">
            {uploading ? "上传中..." : "点击或拖拽文件上传 (.md, .txt)"}
          </span>
          <input
            type="file"
            accept=".md,.markdown,.txt"
            className="hidden"
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {/* Document list */}
      <div className="bg-bg-card rounded-xl border border-border p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium">已索引文档</h3>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["documents"] })}
            className="p-1 text-text-muted hover:text-primary transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {isLoading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 skeleton rounded" />
            ))}
          </div>
        ) : docs?.length ? (
          <div className="space-y-2">
            {docs.map((doc) => (
              <div
                key={doc.source}
                className="flex items-center justify-between py-2 px-3 rounded-lg hover:bg-bg-hover transition-colors"
              >
                <div>
                  <div className="text-sm font-medium">{doc.source}</div>
                  <div className="text-xs text-text-muted">
                    {doc.chunk_count} 个片段
                  </div>
                </div>
                <button
                  onClick={() => {
                    if (confirm(`确定删除 "${doc.source}"？`))
                      deleteMutation.mutate(doc.source);
                  }}
                  className="p-1 text-text-muted hover:text-accent-red transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-text-muted text-center py-8">
            暂无已索引文档
          </div>
        )}
      </div>
    </div>
  );
}
