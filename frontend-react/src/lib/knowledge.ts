// 知识库文档来源解析与显示工具

export type DocType = "knowledge" | "diagnosis" | "history" | "upload" | "other";

export interface DocDisplayInfo {
  type: DocType;
  typeLabel: string;
  typeColor: string;
  typeBgColor: string;
  displayName: string;
  category: string;
  categoryIcon: "book" | "bug" | "history" | "file" | "folder";
}

// 分类中文名映射
const CATEGORY_MAP: Record<string, { name: string; icon: "book" | "bug" | "folder" }> = {
  "pest_control": { name: "病虫害防治", icon: "bug" },
  "planting": { name: "种植技术", icon: "book" },
  "soil": { name: "土壤肥料", icon: "book" },
  "weather": { name: "气象灾害", icon: "book" },
};

export function parseDocSource(source: string): DocDisplayInfo {
  // 诊断记录: diagnosis:xxx
  if (source.startsWith("diagnosis:")) {
    const id = source.replace("diagnosis:", "").slice(0, 12);
    return {
      type: "diagnosis",
      typeLabel: "诊断记录",
      typeColor: "text-orange-600",
      typeBgColor: "bg-orange-50",
      displayName: `病虫害诊断 #${id}`,
      category: "自动记录",
      categoryIcon: "bug",
    };
  }

  // 历史问答上传: history:xxx
  if (source.startsWith("history:")) {
    const id = source.replace("history:", "").slice(0, 12);
    return {
      type: "history",
      typeLabel: "问答记录",
      typeColor: "text-blue-600",
      typeBgColor: "bg-blue-50",
      displayName: `农业问答 #${id}`,
      category: "用户贡献",
      categoryIcon: "history",
    };
  }

  // 知识库文件: category/filename.md
  if (source.includes("/")) {
    const [category, filename] = source.split("/", 2);
    const categoryInfo = CATEGORY_MAP[category] || { name: category, icon: "folder" as const };
    const displayName = filename.replace(/\.(md|markdown|txt)$/i, "");
    return {
      type: "knowledge",
      typeLabel: "知识库",
      typeColor: "text-green-600",
      typeBgColor: "bg-green-50",
      displayName: displayName,
      category: categoryInfo.name,
      categoryIcon: categoryInfo.icon,
    };
  }

  // 上传文件（不带路径）
  if (source.endsWith(".md") || source.endsWith(".markdown") || source.endsWith(".txt")) {
    return {
      type: "upload",
      typeLabel: "上传文档",
      typeColor: "text-emerald-600",
      typeBgColor: "bg-emerald-50",
      displayName: source.replace(/\.(md|markdown|txt)$/i, ""),
      category: "上传文档",
      categoryIcon: "file",
    };
  }

  // 其他未知来源
  return {
    type: "other",
    typeLabel: "其他",
    typeColor: "text-slate-500",
    typeBgColor: "bg-slate-100",
    displayName: source,
    category: "其他来源",
    categoryIcon: "file",
  };
}

// 风险等级中文化
export function getRiskLevelInfo(level: string): { label: string; color: string } {
  const map: Record<string, { label: string; color: string }> = {
    low: { label: "低风险", color: "text-green-600 bg-green-50" },
    medium: { label: "中风险", color: "text-amber-600 bg-amber-50" },
    high: { label: "高风险", color: "text-red-600 bg-red-50" },
  };
  return map[level] || map.low;
}
