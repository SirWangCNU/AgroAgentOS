import { Users as UsersIcon } from "lucide-react";
import { useAuthStore } from "../stores/auth";
import { Navigate } from "react-router-dom";

export default function Users() {
  const isAdmin = useAuthStore((s) => s.isAdmin());

  if (!isAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <h1 className="text-lg font-semibold flex items-center gap-2">
        <UsersIcon className="w-5 h-5 text-accent-blue" /> 用户管理
      </h1>
      <div className="bg-bg-card rounded-xl border border-border p-8 text-center text-sm text-text-muted">
        用户管理功能开发中...
      </div>
    </div>
  );
}
