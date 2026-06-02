import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  MessageSquare,
  CloudSun,
  Tractor,
  BookOpen,
  History,
  Megaphone,
  Bug,
  Users,
  Leaf,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useUIStore } from "../../stores/ui";
import { useAuthStore } from "../../stores/auth";
import { NAV_ITEMS } from "../../lib/constants";

const iconMap: Record<string, React.ElementType> = {
  LayoutDashboard,
  MessageSquare,
  CloudSun,
  Tractor,
  BookOpen,
  History,
  Megaphone,
  Bug,
  Users,
};

export default function Sidebar() {
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggle = useUIStore((s) => s.toggleSidebar);
  const isAdmin = useAuthStore((s) => s.isAdmin());

  return (
    <aside
      className={`flex flex-col bg-bg-sidebar border-r border-border transition-all duration-200 ${
        collapsed ? "w-16" : "w-56"
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 h-14 border-b border-border">
        <Leaf className="w-6 h-6 text-primary flex-shrink-0" />
        {!collapsed && (
          <span className="font-semibold text-sm text-text-primary truncate">
            AgroAgentOS
          </span>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          if (item.adminOnly && !isAdmin) return null;
          const Icon = iconMap[item.icon] || LayoutDashboard;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 mx-2 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? "bg-primary-light text-primary font-medium"
                    : "text-text-secondary hover:bg-bg-hover hover:text-text-primary"
                }`
              }
            >
              <Icon className="w-5 h-5 flex-shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={toggle}
        className="flex items-center justify-center h-10 border-t border-border text-text-muted hover:text-text-primary transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="w-4 h-4" />
        ) : (
          <ChevronLeft className="w-4 h-4" />
        )}
      </button>
    </aside>
  );
}
