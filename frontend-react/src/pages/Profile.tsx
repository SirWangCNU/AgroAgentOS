import { useEffect, useState } from "react";
import { authFetch } from "../api/client";
import { useAuthStore } from "../stores/auth";
import type { ApiResponse, User } from "../types/api";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";

export default function Profile() {
  const { user, login, logout } = useAuthStore();
  const [me, setMe] = useState<User | null>(user);

  // 刷新用户信息
  const refreshMe = async () => {
    try {
      const resp = await authFetch<ApiResponse<User>>("/auth/me");
      if (resp.code === "SUCCESS") {
        setMe(resp.data);
        // 同步到 store, 让 header/sidebar 也更新
        const token = localStorage.getItem("token");
        if (token) login(token, resp.data);
      }
    } catch {
      // 静默
    }
  };

  useEffect(() => {
    refreshMe();
  }, []);

  return (
    <WorkspaceLayout title="个人中心" description="账号信息管理">
      <div className="max-w-3xl mx-auto space-y-6">
        {/* 用户信息卡 */}
        <div className="bg-bg-card border border-border rounded-2xl p-6">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-primary/20 flex items-center justify-center text-primary text-2xl font-semibold">
              {me?.username?.[0]?.toUpperCase() || "?"}
            </div>
            <div className="flex-1">
              <div className="text-lg font-semibold">{me?.username}</div>
              <div className="text-sm text-text-muted">{me?.email}</div>
              <div className="text-xs text-text-muted mt-1">
                角色: {me?.role === "admin" ? "管理员" : "普通用户"}
              </div>
            </div>
          </div>
        </div>

        {/* 账号安全 */}
        <div className="bg-bg-card border border-border rounded-2xl p-6">
          <div className="font-semibold mb-2">账号安全</div>
          <div className="text-sm text-text-muted">
            小程序和网页端共用同一套账号体系，直接使用账号密码登录即可同步数据。
          </div>
        </div>

        {/* 退出 */}
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
