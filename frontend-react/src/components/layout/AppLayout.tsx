import { Outlet } from "react-router-dom";
import ConversationSidebar from "../chat/ConversationSidebar";
import TopBar from "./TopBar";
import ToastContainer from "../ui/ToastContainer";
import { useAuthGuard } from "../../hooks/useAuth";
import { usePolling } from "../../hooks/usePolling";
import { useHealthStore } from "../../stores/health";
import { getHealth, getSkills } from "../../api/health";
import { useUIStore } from "../../stores/ui";

export default function AppLayout() {
  const { isAuthenticated } = useAuthGuard();
  const setHealth = useHealthStore((s) => s.setHealth);
  const setSkills = useHealthStore((s) => s.setSkills);
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);

  // Poll health every 15 seconds
  usePolling(
    async () => {
      try {
        const [health, skills] = await Promise.all([getHealth(), getSkills()]);
        setHealth(health);
        setSkills(skills);
      } catch {
        // silently fail
      }
    },
    15000,
    isAuthenticated
  );

  if (!isAuthenticated) return null;

  return (
    <div className="h-screen overflow-hidden relative">
      {/* TopBar — fixed at top, full width, always same position */}
      <TopBar />

      {/* Sidebar — overlay mode, doesn't push main content */}
      {!collapsed && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/20 z-30"
            onClick={toggleSidebar}
          />
          {/* Sidebar panel */}
          <div className="fixed left-0 top-12 bottom-0 z-40">
            <ConversationSidebar />
          </div>
        </>
      )}

      {/* Main area — always full width */}
      <div className="flex flex-col h-full pt-12">
        <main className="flex-1 overflow-hidden flex flex-col">
          <Outlet />
        </main>
      </div>

      <ToastContainer />
    </div>
  );
}
