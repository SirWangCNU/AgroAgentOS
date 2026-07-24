import { Outlet } from "react-router-dom";
import { useEffect, useRef } from "react";
import ConversationSidebar from "../chat/ConversationSidebar";
import TopBar from "./TopBar";
import ToastContainer from "../ui/ToastContainer";
import { useAuthGuard } from "../../hooks/useAuth";
import { usePolling } from "../../hooks/usePolling";
import { useHealthStore } from "../../stores/health";
import { getHealth, getSkills } from "../../api/health";
import { useUIStore } from "../../stores/ui";
import { useConversationStore } from "../../stores/conversation";

export default function AppLayout() {
  const { isAuthenticated } = useAuthGuard();
  const setHealth = useHealthStore((s) => s.setHealth);
  const setSkills = useHealthStore((s) => s.setSkills);
  const collapsed = useUIStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const loadConversations = useConversationStore((s) => s.loadConversations);

  // Bug 修复: 认证后立即预加载会话列表
  // 之前: 侧边栏默认 collapsed 不 mount, Chat 组件 mount 时 conversations 为空,
  // 只能走 getSession 拉取, 冷启动时后端缓存为空导致长时间卡在 "加载对话记录中...".
  // 现在: AppLayout mount 时主动拉一次列表, 后续 Chat 组件可直接用 store 中的 stub.
  const preloadedRef = useRef(false);
  useEffect(() => {
    if (!isAuthenticated || preloadedRef.current) return;
    preloadedRef.current = true;
    loadConversations().catch(() => {
      // 失败时允许下次重试
      preloadedRef.current = false;
    });
  }, [isAuthenticated, loadConversations]);

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
