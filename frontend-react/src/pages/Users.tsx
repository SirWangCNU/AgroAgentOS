import { Users as UsersIcon, Shield, UserPlus } from "lucide-react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../stores/auth";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";

export default function Users() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.isAdmin());

  if (!isAdmin) {
    return <Navigate to="/workspace" replace />;
  }

  return (
    <WorkspaceLayout
      title="用户管理"
      icon={UsersIcon}
      iconColor="text-accent-blue"
      description="管理平台用户和权限"
      action={
        <button className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors">
          <UserPlus className="w-4 h-4" /> 邀请用户
        </button>
      }
    >
      <div className="bg-bg-card rounded-xl border border-border">
        {/* Current user info */}
        <div className="px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center text-sm font-medium">
              {user?.username?.[0]?.toUpperCase() || "U"}
            </div>
            <div>
              <div className="text-sm font-semibold text-text-primary">
                {user?.username}
              </div>
              <div className="text-xs text-text-muted flex items-center gap-1">
                <Shield className="w-3 h-3" />
                {user?.role === "admin" ? "管理员" : "普通用户"}
              </div>
            </div>
          </div>
        </div>

        {/* User list placeholder */}
        <div className="px-6 py-12 text-center">
          <UsersIcon className="w-12 h-12 text-text-muted opacity-30 mx-auto mb-3" />
          <div className="text-sm text-text-muted">
            用户管理功能正在开发中
          </div>
          <div className="text-xs text-text-muted mt-1">
            后续版本将支持用户列表、角色管理和权限配置
          </div>
        </div>
      </div>
    </WorkspaceLayout>
  );
}
