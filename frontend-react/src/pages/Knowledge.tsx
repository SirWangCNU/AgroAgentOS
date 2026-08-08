import { useState, useMemo, useRef } from "react";
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
  Bug,
  History,
  FolderOpen,
  Filter,
  FileUp,
  Layers,
} from "lucide-react";
import { uploadDocument, getDocuments, deleteDocument } from "../api/knowledge";
import { getSkills } from "../api/health";
import { useAuthStore } from "../stores/auth";
import { useUIStore } from "../stores/ui";
import { getErrorMessage } from "../api/client";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import EmptyState from "../components/ui/EmptyState";
import LoadingGrid from "../components/ui/LoadingGrid";
import { parseDocSource, getRiskLevelInfo } from "../lib/knowledge";
import type { DocType } from "../lib/knowledge";

type FilterType = "all" | DocType;

const FILTER_OPTIONS: { key: FilterType; label: string; icon: typeof FileText }[] = [
  { key: "all", label: "全部", icon: Layers },
  { key: "knowledge", label: "知识库", icon: BookOpen },
  { key: "diagnosis", label: "诊断记录", icon: Bug },
  { key: "history", label: "问答记录", icon: History },
  { key: "upload", label: "上传文档", icon: FileUp },
];

const CATEGORY_ICONS = {
  book: BookOpen,
  bug: Bug,
  history: History,
  file: FileText,
  folder: FolderOpen,
} as const;

export default function Knowledge() {
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const [uploading, setUploading] = useState(false);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterType>("all");
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

  // 处理文档列表：解析显示信息 + 筛选
  const processedDocs = useMemo(() => {
    if (!docs) return [];
    return docs
      .map((d) => ({
        ...d,
        display: parseDocSource(d.source),
      }))
      .filter((d) => {
        // 类型筛选
        if (filter !== "all" && d.display.type !== filter) return false;
        // 搜索筛选
        if (search) {
          const term = search.toLowerCase();
          return (
            d.display.displayName.toLowerCase().includes(term) ||
            d.display.category.toLowerCase().includes(term) ||
            d.source.toLowerCase().includes(term)
          );
        }
        return true;
      })
      .sort((a, b) => {
        // 排序：知识库文档在前，然后是诊断记录、问答记录
        const typeOrder: Record<DocType, number> = {
          knowledge: 0,
          upload: 1,
          diagnosis: 2,
          history: 3,
          other: 4,
        };
        return typeOrder[a.display.type] - typeOrder[b.display.type];
      });
  }, [docs, search, filter]);

  // 统计信息
  const stats = useMemo(() => {
    if (!docs) return { total: 0, chunks: 0, byType: {} as Record<DocType, number> };
    const byType: Record<DocType, number> = { knowledge: 0, diagnosis: 0, history: 0, upload: 0, other: 0 };
    let totalChunks = 0;
    docs.forEach((d) => {
      const info = parseDocSource(d.source);
      byType[info.type] = (byType[info.type] || 0) + 1;
      totalChunks += d.chunk_count;
    });
    return { total: docs.length, chunks: totalChunks, byType };
  }, [docs]);

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
        {/* 左侧：技能 + 上传 + 统计 */}
        <div className="space-y-4">
          {/* 智能体技能 */}
          <div className="bg-bg-card rounded-xl border border-border p-5">
            <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
              <Cpu className="w-4 h-4 text-accent-purple" />
              智能体技能
            </h3>
            {skillsLoading ? (
              <LoadingGrid rows={3} height="h-14" />
            ) : skills?.length ? (
              <div className="space-y-2">
                {skills.map((skill) => {
                  const riskInfo = getRiskLevelInfo(skill.risk_level);
                  return (
                    <div
                      key={skill.name}
                      className="p-3 rounded-lg border border-border hover:border-primary/30 hover:bg-primary/[0.02] transition-all duration-200 group"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium text-text-primary group-hover:text-primary transition-colors">
                          {skill.display_name}
                        </span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full font-medium ${riskInfo.color}`}
                        >
                          {riskInfo.label}
                        </span>
                      </div>
                      <div className="text-xs text-text-muted leading-relaxed">{skill.description}</div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-xs text-text-muted text-center py-4">
                暂无已注册技能
              </div>
            )}
          </div>

          {/* 上传区域（管理员） */}
          {isAdmin && (
            <div className="bg-bg-card rounded-xl border border-border p-5">
              <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
                <Shield className="w-4 h-4 text-primary" />
                上传知识文档
              </h3>
              <label className="flex flex-col items-center gap-2 p-6 border-2 border-dashed border-border rounded-xl cursor-pointer hover:border-primary hover:bg-primary/[0.02] transition-all duration-200 group">
                {uploading ? (
                  <div className="w-10 h-10 border-2 border-primary border-t-transparent rounded-full spinner" />
                ) : (
                  <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                    <Upload className="w-6 h-6 text-primary" />
                  </div>
                )}
                <span className="text-sm font-medium text-text-primary">
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

          {/* 统计信息 */}
          {docs && (
            <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl border border-green-100 p-5">
              <h3 className="text-sm font-semibold text-slate-700 mb-4 flex items-center gap-2">
                <HardDrive className="w-4 h-4 text-green-600" />
                知识库统计
              </h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-white/80 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-green-600">{stats.total}</div>
                  <div className="text-xs text-slate-500 mt-0.5">文档总数</div>
                </div>
                <div className="bg-white/80 rounded-lg p-3 text-center">
                  <div className="text-2xl font-bold text-emerald-600">{stats.chunks}</div>
                  <div className="text-xs text-slate-500 mt-0.5">索引片段</div>
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-green-100 space-y-2">
                {stats.byType.knowledge > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-slate-600">
                      <BookOpen className="w-3.5 h-3.5 text-green-500" />
                      内置知识库
                    </span>
                    <span className="font-medium text-slate-700">{stats.byType.knowledge}</span>
                  </div>
                )}
                {stats.byType.diagnosis > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-slate-600">
                      <Bug className="w-3.5 h-3.5 text-orange-500" />
                      诊断记录
                    </span>
                    <span className="font-medium text-slate-700">{stats.byType.diagnosis}</span>
                  </div>
                )}
                {stats.byType.history > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-slate-600">
                      <History className="w-3.5 h-3.5 text-blue-500" />
                      问答记录
                    </span>
                    <span className="font-medium text-slate-700">{stats.byType.history}</span>
                  </div>
                )}
                {stats.byType.upload > 0 && (
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-slate-600">
                      <FileUp className="w-3.5 h-3.5 text-emerald-500" />
                      上传文档
                    </span>
                    <span className="font-medium text-slate-700">{stats.byType.upload}</span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* 右侧：文档列表 */}
        <div className="lg:col-span-2">
          <div className="bg-bg-card rounded-xl border border-border overflow-hidden">
            {/* 搜索和筛选栏 */}
            <div className="px-4 py-3 border-b border-border space-y-3">
              <div className="flex items-center gap-3">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="搜索文档名称、分类..."
                    className="w-full pl-9 pr-4 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary focus:ring-2 focus:ring-primary/10 transition-all bg-white"
                  />
                </div>
              </div>

              {/* 类型筛选 */}
              <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5">
                <Filter className="w-3.5 h-3.5 text-text-muted flex-shrink-0 mr-1" />
                {FILTER_OPTIONS.map((opt) => {
                  const OptIcon = opt.icon;
                  const isActive = filter === opt.key;
                  const count = opt.key === "all" ? stats.total : (stats.byType[opt.key] || 0);
                  return (
                    <button
                      key={opt.key}
                      onClick={() => setFilter(opt.key)}
                      className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg transition-all whitespace-nowrap ${
                        isActive
                          ? "bg-primary text-white shadow-sm"
                          : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                      }`}
                    >
                      <OptIcon className="w-3.5 h-3.5" />
                      {opt.label}
                      {count > 0 && (
                        <span className={`px-1.5 py-px rounded-full text-[10px] ${
                          isActive ? "bg-white/20" : "bg-slate-200"
                        }`}>
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 文档列表 */}
            <div className="divide-y divide-border max-h-[calc(100vh-340px)] overflow-y-auto">
              {docsLoading ? (
                <div className="p-4">
                  <LoadingGrid rows={6} height="h-16" />
                </div>
              ) : processedDocs.length ? (
                processedDocs.map((doc) => {
                  const CatIcon = CATEGORY_ICONS[doc.display.categoryIcon];
                  return (
                    <div
                      key={doc.source}
                      className="flex items-center justify-between px-4 py-3.5 hover:bg-bg-hover transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0 flex-1">
                        {/* 类型图标 */}
                        <div className={`w-10 h-10 rounded-xl ${doc.display.typeBgColor} flex items-center justify-center flex-shrink-0`}>
                          <CatIcon className={`w-5 h-5 ${doc.display.typeColor}`} />
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-text-primary truncate">
                              {doc.display.displayName}
                            </span>
                            <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0 ${doc.display.typeBgColor} ${doc.display.typeColor}`}>
                              {doc.display.typeLabel}
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-text-muted">
                              {doc.display.category}
                            </span>
                            <span className="text-text-muted">·</span>
                            <span className="text-xs text-text-muted flex items-center gap-1">
                              <Layers className="w-3 h-3" />
                              {doc.chunk_count} 个片段
                            </span>
                          </div>
                        </div>
                      </div>

                      {isAdmin && (
                        <button
                          onClick={() => {
                            if (confirm(`确定删除「${doc.display.displayName}」？\n\n来源: ${doc.source}\n将删除 ${doc.chunk_count} 个索引片段`))
                              deleteMutation.mutate(doc.source);
                          }}
                          className="p-2 text-text-muted hover:text-accent-red hover:bg-accent-red/10 rounded-lg transition-all opacity-0 group-hover:opacity-100 flex-shrink-0"
                          title="删除文档"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  );
                })
              ) : (
                <EmptyState
                  icon={BookOpen}
                  title={search || filter !== "all" ? "未找到匹配的文档" : "暂无已索引文档"}
                  description={
                    isAdmin
                      ? search || filter !== "all"
                        ? "尝试调整搜索关键词或筛选条件"
                        : "上传 .md 或 .txt 文件来构建知识库"
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
