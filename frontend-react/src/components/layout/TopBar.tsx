import { useState, useRef, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  PanelLeft,
  ChevronDown,
  LogOut,
  LayoutDashboard,
  CloudSun,
  Tractor,
  BookOpen,
  Bug,
  Users,
  Leaf,
  MessageSquare,
  TrendingUp,
  UserCircle,
  Radar,
  Bot,
} from "lucide-react";
import { useAuthStore } from "../../stores/auth";
import { useUIStore } from "../../stores/ui";
import WeatherBadge from "./WeatherBadge";

interface WorkspaceItem {
  icon: typeof Bot;
  label: string;
  path: string;
  adminOnly?: boolean;
}

interface WorkspaceGroup {
  title: string;
  items: WorkspaceItem[];
}

const WORKSPACE_GROUPS: WorkspaceGroup[] = [
  {
    title: "核心",
    items: [
      { icon: Radar, label: "AI 农场驾驶舱", path: "/workspace/farm-agent" },
      { icon: Tractor, label: "农场管理", path: "/workspace/farms" },
      { icon: LayoutDashboard, label: "数据仪表盘", path: "/workspace/dashboard" },
    ],
  },
  {
    title: "工具",
    items: [
      { icon: CloudSun, label: "天气查询", path: "/workspace/weather" },
      { icon: Bug, label: "病虫害诊断", path: "/workspace/pest" },
      { icon: TrendingUp, label: "市场行情", path: "/workspace/market" },
      { icon: BookOpen, label: "知识库管理", path: "/workspace/knowledge" },
    ],
  },
  {
    title: "管理",
    items: [
      { icon: Bot, label: "智能体能力中心", path: "/workspace" },
      { icon: Users, label: "用户管理", path: "/workspace/users", adminOnly: true },
    ],
  },
];

export default function TopBar() {
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  const [wsOpen, setWsOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const wsRef = useRef<HTMLDivElement>(null);
  const userRef = useRef<HTMLDivElement>(null);

  const isWorkspace = location.pathname.startsWith("/workspace");

  // Close dropdowns on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wsRef.current && !wsRef.current.contains(e.target as Node))
        setWsOpen(false);
      if (userRef.current && !userRef.current.contains(e.target as Node))
        setUserOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <header className="fixed left-0 right-0 top-0 z-50 flex h-14 items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 shadow-[0_10px_30px_rgba(15,23,42,0.05)] backdrop-blur">
      {/* Left: sidebar toggle + brand */}
      <div className="flex items-center gap-2">
        <button
          onClick={toggleSidebar}
          className="rounded-[8px] p-2 text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
          title="打开对话列表"
        >
          <PanelLeft className="w-5 h-5" />
        </button>
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-2 rounded-[8px] px-1 py-1 transition-opacity hover:opacity-85"
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-[8px] bg-emerald-50 text-emerald-600">
            <Leaf className="w-5 h-5" />
          </span>
          <span className="hidden sm:block text-left">
            <span className="block text-sm font-black leading-4 text-slate-900">
              AgroAgentOS
            </span>
            <span className="block text-[11px] font-medium text-slate-500">
              智农协同平台
            </span>
          </span>
        </button>
      </div>

      {/* Center: quick nav to chat */}
      <div className="hidden items-center gap-1 rounded-full border border-slate-200 bg-slate-50 p-1 md:flex">
        <button
          onClick={() => navigate("/")}
          className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-semibold transition-colors ${
            !isWorkspace
              ? "bg-white text-emerald-700 shadow-sm"
              : "text-slate-500 hover:bg-white hover:text-slate-800"
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          对话
        </button>
        <button
          onClick={() => navigate("/workspace")}
          className={`flex items-center gap-1.5 rounded-full px-4 py-1.5 text-sm font-semibold transition-colors ${
            isWorkspace
              ? "bg-white text-emerald-700 shadow-sm"
              : "text-slate-500 hover:bg-white hover:text-slate-800"
          }`}
        >
          <LayoutDashboard className="w-4 h-4" />
          工作台
        </button>
      </div>

      {/* Right: workspace + user */}
      <div className="flex items-center gap-2">
        {/* Workspace dropdown */}
        <div ref={wsRef} className="relative">
          <button
            onClick={() => setWsOpen(!wsOpen)}
            className={`flex items-center gap-1 rounded-[8px] px-3 py-2 text-sm font-semibold transition-colors ${
              isWorkspace
                ? "bg-emerald-50 text-emerald-700"
                : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span className="hidden sm:inline">工作台</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {wsOpen && (
            <div className="absolute right-0 top-full z-[60] mt-2 w-56 rounded-[8px] border border-slate-200 bg-white py-2 shadow-[0_18px_45px_rgba(15,23,42,0.12)]">
              {WORKSPACE_GROUPS.map((group) => {
                const visibleItems = group.items.filter(
                  (item) => !item.adminOnly || isAdmin
                );
                if (visibleItems.length === 0) return null;
                return (
                  <div key={group.title}>
                    <div className="px-4 pt-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                      {group.title}
                    </div>
                    {visibleItems.map((item) => (
                      <button
                        key={item.path}
                        onClick={() => {
                          navigate(item.path);
                          setWsOpen(false);
                        }}
                        className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-slate-600 transition-colors hover:bg-emerald-50 hover:text-emerald-700"
                      >
                        <item.icon className="w-4 h-4" />
                        {item.label}
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Weather badge */}
        <WeatherBadge />

        {/* Divider */}
        <div className="mx-1 hidden h-6 w-px bg-slate-200 sm:block" />

        {/* User avatar — 直接跳转个人中心 */}
        <div ref={userRef} className="relative">
          <button
            onClick={() => navigate("/profile")}
            className="flex items-center gap-2 rounded-[8px] px-2 py-1.5 transition-colors hover:bg-slate-100"
            title="个人中心"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[linear-gradient(135deg,#16a34a,#2563eb)] text-xs font-bold text-white shadow-sm">
              {user?.username?.[0]?.toUpperCase() || "U"}
            </div>
            <span className="hidden text-sm font-semibold text-slate-700 sm:inline">
              {user?.username}
            </span>
          </button>
          {userOpen && (
            <div className="absolute top-full right-0 mt-1 w-48 bg-bg-card border border-border rounded-xl shadow-lg py-1 z-[60]">
              <div className="px-4 py-2 border-b border-border">
                <div className="text-sm font-medium">{user?.username}</div>
                <div className="text-xs text-text-muted">
                  {user?.role === "admin" ? "管理员" : "用户"}
                </div>
              </div>
              <button
                onClick={() => {
                  navigate("/profile");
                  setUserOpen(false);
                }}
                className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
              >
                <UserCircle className="w-4 h-4" />
                个人中心
              </button>
              <button
                onClick={() => {
                  logout();
                  setUserOpen(false);
                }}
                className="flex items-center gap-2 w-full px-4 py-2 text-sm text-accent-red hover:bg-bg-hover transition-colors"
              >
                <LogOut className="w-4 h-4" />
                退出登录
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
