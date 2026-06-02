import { Search, LogOut } from "lucide-react";
import { useAuthStore } from "../../stores/auth";
import { useUIStore } from "../../stores/ui";

export default function TopBar() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const setSearchOpen = useUIStore((s) => s.setSearchOpen);

  return (
    <header className="flex items-center justify-between h-14 px-4 bg-bg-card border-b border-border">
      {/* Search */}
      <button
        onClick={() => setSearchOpen(true)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm text-text-muted bg-bg-hover rounded-lg hover:bg-border transition-colors"
      >
        <Search className="w-4 h-4" />
        <span>搜索... (Ctrl+K)</span>
      </button>

      {/* User menu */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-sm font-medium">
            {user?.username?.[0]?.toUpperCase() || "U"}
          </div>
          <div className="hidden sm:block">
            <div className="text-sm font-medium text-text-primary">
              {user?.username}
            </div>
            <div className="text-xs text-text-muted">
              {user?.role === "admin" ? "管理员" : "用户"}
            </div>
          </div>
        </div>
        <button
          onClick={logout}
          className="p-2 text-text-muted hover:text-accent-red transition-colors"
          title="退出登录"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
