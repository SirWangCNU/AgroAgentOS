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
  Megaphone,
  Bug,
  Users,
  Leaf,
  MessageSquare,
  TrendingUp,
} from "lucide-react";
import { useAuthStore } from "../../stores/auth";
import { useUIStore } from "../../stores/ui";

const WORKSPACE_ITEMS = [
  { icon: LayoutDashboard, label: "仪表盘", path: "/workspace" },
  { icon: CloudSun, label: "天气查询", path: "/workspace/weather" },
  { icon: Tractor, label: "农场管理", path: "/workspace/farms" },
  { icon: BookOpen, label: "智能体技能和知识库", path: "/workspace/knowledge" },
  { icon: Megaphone, label: "营销生成", path: "/workspace/marketing" },
  { icon: Bug, label: "病虫害诊断", path: "/workspace/pest" },
  { icon: TrendingUp, label: "市场行情", path: "/workspace/market" },
  { icon: Users, label: "用户管理", path: "/workspace/users", adminOnly: true },
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
    <header className="fixed top-0 left-0 right-0 h-12 px-3 bg-bg-card border-b border-border flex items-center justify-between z-50">
      {/* Left: sidebar toggle + brand */}
      <div className="flex items-center gap-2">
        <button
          onClick={toggleSidebar}
          className="p-1.5 text-text-muted hover:text-text-primary rounded-lg hover:bg-bg-hover transition-colors"
        >
          <PanelLeft className="w-5 h-5" />
        </button>
        <button
          onClick={() => navigate("/")}
          className="flex items-center gap-1.5 hover:opacity-80 transition-opacity"
        >
          <Leaf className="w-5 h-5 text-primary" />
          <span className="text-sm font-semibold text-text-primary hidden sm:inline">
            AgroAgentOS
          </span>
        </button>
      </div>

      {/* Center: quick nav to chat */}
      <div className="hidden md:flex items-center">
        <button
          onClick={() => navigate("/")}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors ${
            !isWorkspace
              ? "text-primary bg-primary/10"
              : "text-text-secondary hover:text-text-primary hover:bg-bg-hover"
          }`}
        >
          <MessageSquare className="w-4 h-4" />
          对话
        </button>
      </div>

      {/* Right: workspace + user */}
      <div className="flex items-center gap-1">
        {/* Workspace dropdown */}
        <div ref={wsRef} className="relative">
          <button
            onClick={() => setWsOpen(!wsOpen)}
            className={`flex items-center gap-1 px-3 py-1.5 text-sm rounded-lg transition-colors ${
              isWorkspace
                ? "text-primary bg-primary/10"
                : "text-text-secondary hover:text-text-primary hover:bg-bg-hover"
            }`}
          >
            <LayoutDashboard className="w-4 h-4" />
            <span className="hidden sm:inline">工作台</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          {wsOpen && (
            <div className="absolute top-full right-0 mt-1 w-48 bg-bg-card border border-border rounded-xl shadow-lg py-1 z-[60]">
              {WORKSPACE_ITEMS.map((item) => {
                if (item.adminOnly && !isAdmin) return null;
                return (
                  <button
                    key={item.path}
                    onClick={() => {
                      navigate(item.path);
                      setWsOpen(false);
                    }}
                    className="flex items-center gap-2 w-full px-4 py-2 text-sm text-text-secondary hover:bg-bg-hover hover:text-text-primary transition-colors"
                  >
                    <item.icon className="w-4 h-4" />
                    {item.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-border mx-1" />

        {/* User avatar */}
        <div ref={userRef} className="relative">
          <button
            onClick={() => setUserOpen(!userOpen)}
            className="flex items-center gap-2 p-1.5 rounded-lg hover:bg-bg-hover transition-colors"
          >
            <div className="w-7 h-7 rounded-full bg-primary text-white flex items-center justify-center text-xs font-medium">
              {user?.username?.[0]?.toUpperCase() || "U"}
            </div>
            <span className="text-sm text-text-secondary hidden sm:inline">
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
