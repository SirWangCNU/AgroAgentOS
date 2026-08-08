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
  Cpu,
  Shield,
} from "lucide-react";
import { uploadDocument, getDocuments, deleteDocument } from "../api/knowledge";
import { getSkills } from "../api/health";
import { useAuthStore } from "../stores/auth";
import { useUIStore } from "../stores/ui";
import { getErrorMessage } from "../api/client";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import EmptyState from "../components/ui/EmptyState";
import LoadingGrid from "../components/ui/LoadingGrid";

const RISK_COLORS: Record<string, string> = {
  low: "text-accent-green bg-accent-green/10",
  medium: "text-accent-amber bg-accent-amber/10",
  high: "text-accent-red bg-accent-red/10",
};

export default function Knowledge() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const { data: skills, isLoading: skillsLoading } = useQuery({
    queryKey: ["skills"],
    queryFn: getSkills,
  });

  const { data: docs, isLoading: docsLoading } = useQuery({
    queryKey: ["documents"],
    queryFn: getDocuments,
  });

  const deleteMutation = useMutation({
    mutationFn: (source: string) => deleteDocument(source),
    onSuccess: () => {
      showToast("删除成功", "success");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (err: unknown) => showToast(getErrorMessage(err, "删除失败"), "error"),
  });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const result = await uploadDocument(file);
      showToast(`上传成功，${result.chunks_indexed} 个片段已索引`, "success");
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    } catch (err: unknown) {
      showToast(`上传失败: ${getErrorMessage(err, "未知错误")}`, "error");
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
      title="智能体技能和知识库"
      icon={BookOpen}
      iconColor="text-accent-blue"
      description="查看智能体技能与管理农业知识文档"
      action={
        <button
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ["skills"] });
            queryClient.invalidateQueries({ queryKey: ["documents"] });
          }}
          className="p-2 text-text-muted hover:text-primary hover:bg-bg-hover rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      }
    >
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column: skills + upload */}
        <div className="space-y-4">
          {/* Skills list */}
          <div className="bg-bg-card rounded-xl border border-border p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-accent-purple" />
              智能体技能
            </h3>
            {skillsLoading ? (
              <LoadingGrid rows={3} height="h-14" />
            ) : skills?.length ? (
              <div className="space-y-2">
                {skills.map((skill) => (
                  <div
                    key={skill.name}
                    className="p-3 rounded-lg border border-border hover:border-primary/30 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-text-primary">
                        {skill.display_name}
                      </span>
                      <span
                        className={`text-xs px-1.5 py-0.5 rounded-full ${
                          RISK_COLORS[skill.risk_level] || RISK_COLORS.low
                        }`}
                      >
                        {skill.risk_level}
                      </span>
                    </div>
                    <div className="text-xs text-text-muted">{skill.description}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-xs text-text-muted text-center py-4">
                暂无已注册技能
              </div>
            )}
          </div>

          {/* Admin: upload area */}
          {isAdmin && (
            <div className="bg-bg-card rounded-xl border border-border p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                上传知识文档
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
          )}

          {/* Stats */}
          {docs && (
            <div className="bg-bg-card rounded-xl border border-border p-4">
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

        {/* Right column: document list */}
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
              {docsLoading ? (
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
                    {isAdmin && (
                      <button
                        onClick={() => {
                          if (confirm(`确定删除 "${doc.source}"？`))
                            deleteMutation.mutate(doc.source);
                        }}
                        className="p-1.5 text-text-muted hover:text-accent-red hover:bg-accent-red/10 rounded-lg transition-colors flex-shrink-0"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <EmptyState
                  icon={BookOpen}
                  title="暂无已索引文档"
                  description={
                    isAdmin
                      ? "上传 .md 或 .txt 文件来构建知识库"
                      : "暂无知识库文档"
                  }
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </WorkspaceLayout>
  );
}
