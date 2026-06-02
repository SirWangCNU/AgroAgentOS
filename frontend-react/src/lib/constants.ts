export const API_BASE = "/api/v1";

export const STORAGE_KEYS = {
  TOKEN: "agro_token",
  USER: "agro_user",
  KB_ADMIN_TOKEN: "multi_agent_kb_admin_token",
} as const;

export const MAX_IMAGE_SIZE = 10 * 1024 * 1024; // 10MB
export const ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

export const NAV_ITEMS: Array<{
  path: string;
  label: string;
  icon: string;
  adminOnly?: boolean;
}> = [
  { path: "/dashboard", label: "仪表盘", icon: "LayoutDashboard" },
  { path: "/chat", label: "智能问答", icon: "MessageSquare" },
  { path: "/weather", label: "天气", icon: "CloudSun" },
  { path: "/farms", label: "农场管理", icon: "Tractor" },
  { path: "/knowledge", label: "知识库", icon: "BookOpen" },
  { path: "/history", label: "历史记录", icon: "History" },
  { path: "/marketing", label: "营销生成", icon: "Megaphone" },
  { path: "/pest", label: "病虫害诊断", icon: "Bug" },
  { path: "/users", label: "用户管理", icon: "Users", adminOnly: true },
];
