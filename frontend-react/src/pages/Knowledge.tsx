import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BookOpen,
  Upload,
  Trash2,
  RefreshCw,
  Search,
  FileText,
  HardDrive,
} from "lucide-react";
import { uploadDocument, getDocuments, deleteDocument } from "../api/knowledge";
import { useUIStore } from "../stores/ui";
import { STORAGE_KEYS } from "../lib/constants";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import EmptyState from "../components/ui/EmptyState";
import LoadingGrid from "../components/ui/LoadingGrid";

export default function Knowledge() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: docs, isLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  const deleteMutation = useMutation({
    mutationFn: async (source: string) => {
      const token =
        sessionStorage.getItem(STORAGE_KEYS.KB_ADMIN_TOKEN) ||
        prompt("请输入知识库管理员 Token:");
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

    const token =
      sessionStorage.getItem(STORAGE_KEYS.KB_ADMIN_TOKEN) ||
      prompt("请输入知识库管理员 Token:");
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
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const filteredDocs = docs?.filter(
    (d) => !search || d.source.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <WorkspaceLayout
      title="知识库"
      icon={BookOpen}
      iconColor="text-accent-blue"
      description="上传和管理农业知识文档，用于 RAG 检索增强"
      action={
        <button
          onClick={() => queryClient.invalidateQueries({ queryKey: ["documents"] })}
          className="p-2 text-text-muted hover:text-primary hover:bg-bg-hover rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload area */}
        <div>
          <div className="bg-bg-card rounded-xl border border-border p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3">
              上传文档
            </h3>
            <label className="flex flex-col items-center gap-2 p-6 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-primary transition-colors">
              {uploading ? (
                <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full spinner" />
              ) : (
                <Upload className="w-8 h-8 text-text-muted" />
              )}
              <span className="text-sm text-text-muted text-center">
                {uploading ? "上传中..." : "点击选择文件"}
              </span>
              <span className="text-xs text-text-muted">
                支持 .md、.txt 格式
              </span>
              <input
                ref={fileRef}
                type="file"
                accept=".md,.markdown,.txt"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>

          {/* Stats */}
          {docs && (
            <div className="mt-4 bg-bg-card rounded-xl border border-border p-4">
              <div className="flex items-center gap-2 text-sm">
                <HardDrive className="w-4 h-4 text-text-muted" />
                <span className="text-text-secondary">
                  共 <span className="font-semibold text-text-primary">{docs.length}</span> 个文档，
                  <span className="font-semibold text-text-primary">
                    {docs.reduce((s, d) => s + d.chunk_count, 0)}
                  </span>{" "}
                  个片段
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Document list */}
        <div className="lg:col-span-2">
          <div className="bg-bg-card rounded-xl border border-border">
            <div className="px-4 py-3 border-b border-border flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="搜索文档..."
                  className="w-full pl-8 pr-3 py-1.5 text-sm border border-border rounded-lg outline-none focus:border-primary"
                />
              </div>
            </div>

            <div className="divide-y divide-border">
              {isLoading ? (
                <div className="p-4">
                  <LoadingGrid rows={4} height="h-12" />
                </div>
              ) : filteredDocs?.length ? (
                filteredDocs.map((doc) => (
                  <div
                    key={doc.source}
                    className="flex items-center justify-between px-4 py-3 hover:bg-bg-hover transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <FileText className="w-4 h-4 text-text-muted flex-shrink-0" />
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">
                          {doc.source}
                        </div>
                        <div className="text-xs text-text-muted">
                          {doc.chunk_count} 个片段
                        </div>
                      </div>
                    </div>
                    <button
                      onClick={() => {
                        if (confirm(`确定删除 "${doc.source}"？`))
                          deleteMutation.mutate(doc.source);
                      }}
                      className="p-1.5 text-text-muted hover:text-accent-red hover:bg-accent-red/10 rounded-lg transition-colors flex-shrink-0"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))
              ) : (
                <EmptyState
                  icon={BookOpen}
                  title="暂无已索引文档"
                  description="上传 .md 或 .txt 文件来构建知识库"
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </WorkspaceLayout>
  );
}
