import { useAuthStore } from "../stores/auth";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";

export default function Profile() {
  const { user, logout } = useAuthStore();

  return (
    <WorkspaceLayout title="个人中心" description="账户信息">
      <div className="max-w-3xl mx-auto space-y-6">
        <div className="bg-bg-card border border-border rounded-2xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary text-2xl font-semibold">
              {user?.username?.[0]?.toUpperCase() || "?"}
            </div>
            <div className="flex-1">
              <div className="text-lg font-semibold">{user?.username}</div>
              <div className="text-sm text-text-muted">{user?.email}</div>
              <div className="text-xs text-text-muted mt-1">
                角色: {user?.role === "admin" ? "管理员" : "普通用户"}
              </div>
            </div>
          </div>
        </div>

        <div className="bg-bg-card border border-border rounded-2xl p-6">
          <button
            onClick={logout}
            className="px-4 py-2 text-sm border border-red-500/50 text-red-500 rounded-lg hover:bg-red-500/10 transition-colors"
          >
            退出登录
          </button>
        </div>
      </div>
    </WorkspaceLayout>
  );
}
