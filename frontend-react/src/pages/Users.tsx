import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users as UsersIcon,
  Shield,
  UserPlus,
  Trash2,
  ToggleLeft,
  ToggleRight,
  X,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { useAuthStore } from "../stores/auth";
import { useUIStore } from "../stores/ui";
import { getErrorMessage } from "../api/client";
import {
  getUsers,
  adminCreateUser,
  adminUpdateUser,
  adminDeleteUser,
} from "../api/auth";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import LoadingGrid from "../components/ui/LoadingGrid";
import type { UserInfo } from "../types/api";

export default function Users() {
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const showToast = useUIStore((s) => s.showToast);
  const queryClient = useQueryClient();
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({
    username: "",
    email: "",
    password: "",
    role: "user",
  });

  const { data, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: () => getUsers(1, 100),
    enabled: isAdmin,
  });

  const createMutation = useMutation({
    mutationFn: adminCreateUser,
    onSuccess: () => {
      showToast("用户创建成功", "success");
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setShowModal(false);
      setForm({ username: "", email: "", password: "", role: "user" });
    },
    onError: (err: unknown) => showToast(getErrorMessage(err, "创建失败"), "error"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      adminUpdateUser(id, { is_active }),
    onSuccess: () => {
      showToast("用户状态已更新", "success");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: unknown) => showToast(getErrorMessage(err, "更新失败"), "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: adminDeleteUser,
    onSuccess: () => {
      showToast("用户已禁用", "success");
      queryClient.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (err: unknown) => showToast(getErrorMessage(err, "删除失败"), "error"),
  });

  const users: UserInfo[] = data?.users || [];

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
        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors"
        >
          <UserPlus className="w-4 h-4" /> 添加用户
        </button>
      }
    >
      <div className="bg-bg-card rounded-xl border border-border">
        {/* Current admin info */}
        <div className="px-6 py-4 border-b border-border">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-primary text-white flex items-center justify-center text-sm font-medium">
              {currentUser?.username?.[0]?.toUpperCase() || "U"}
            </div>
            <div>
              <div className="text-sm font-semibold text-text-primary">
                {currentUser?.username}
              </div>
              <div className="text-xs text-text-muted flex items-center gap-1">
                <Shield className="w-3 h-3" />
                管理员（当前登录）
              </div>
            </div>
          </div>
        </div>

        {/* User table */}
        {isLoading ? (
          <div className="p-4">
            <LoadingGrid rows={5} height="h-12" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-text-muted">
                  <th className="text-left px-6 py-3 font-medium">用户名</th>
                  <th className="text-left px-6 py-3 font-medium">邮箱</th>
                  <th className="text-left px-6 py-3 font-medium">角色</th>
                  <th className="text-left px-6 py-3 font-medium">状态</th>
                  <th className="text-left px-6 py-3 font-medium">创建时间</th>
                  <th className="text-right px-6 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-bg-hover transition-colors">
                    <td className="px-6 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-7 h-7 rounded-full bg-accent-blue/10 text-accent-blue flex items-center justify-center text-xs font-medium">
                          {user.username[0]?.toUpperCase()}
                        </div>
                        <span className="font-medium text-text-primary">
                          {user.username}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-3 text-text-secondary">{user.email}</td>
                    <td className="px-6 py-3">
                      <span
                        className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                          user.role === "admin"
                            ? "text-accent-purple bg-accent-purple/10"
                            : "text-text-muted bg-bg-hover"
                        }`}
                      >
                        {user.role === "admin" ? "管理员" : "普通用户"}
                      </span>
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${
                          user.is_active
                            ? "text-accent-green bg-accent-green/10"
                            : "text-accent-red bg-accent-red/10"
                        }`}
                      >
                        {user.is_active ? "正常" : "已禁用"}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-text-muted text-xs">
                      {new Date(user.created_at).toLocaleDateString("zh-CN")}
                    </td>
                    <td className="px-6 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        {/* Don't allow disabling yourself */}
                        {user.id !== currentUser?.id && (
                          <>
                            <button
                              onClick={() =>
                                toggleMutation.mutate({
                                  id: user.id,
                                  is_active: !user.is_active,
                                })
                              }
                              className="p-1.5 text-text-muted hover:text-accent-amber hover:bg-accent-amber/10 rounded-lg transition-colors"
                              title={user.is_active ? "禁用" : "启用"}
                            >
                              {user.is_active ? (
                                <ToggleRight className="w-4 h-4" />
                              ) : (
                                <ToggleLeft className="w-4 h-4" />
                              )}
                            </button>
                            <button
                              onClick={() => {
                                if (
                                  confirm(
                                    `确定禁用用户 "${user.username}"？`
                                  )
                                )
                                  deleteMutation.mutate(user.id);
                              }}
                              className="p-1.5 text-text-muted hover:text-accent-red hover:bg-accent-red/10 rounded-lg transition-colors"
                              title="禁用用户"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Add user modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[70]">
          <div className="bg-bg-card rounded-xl border border-border w-full max-w-md mx-4 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary">添加用户</h2>
              <button
                onClick={() => setShowModal(false)}
                className="p-1 text-text-muted hover:text-text-primary rounded-lg"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                createMutation.mutate(form);
              }}
              className="space-y-4"
            >
              <div>
                <label className="block text-sm text-text-secondary mb-1">
                  用户名
                </label>
                <input
                  type="text"
                  required
                  minLength={3}
                  maxLength={64}
                  value={form.username}
                  onChange={(e) =>
                    setForm({ ...form, username: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
                  placeholder="请输入用户名"
                />
              </div>

              <div>
                <label className="block text-sm text-text-secondary mb-1">
                  邮箱
                </label>
                <input
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) =>
                    setForm({ ...form, email: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
                  placeholder="请输入邮箱"
                />
              </div>

              <div>
                <label className="block text-sm text-text-secondary mb-1">
                  密码
                </label>
                <input
                  type="password"
                  required
                  minLength={6}
                  maxLength={128}
                  value={form.password}
                  onChange={(e) =>
                    setForm({ ...form, password: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
                  placeholder="请输入密码（至少6位）"
                />
              </div>

              <div>
                <label className="block text-sm text-text-secondary mb-1">
                  角色
                </label>
                <select
                  value={form.role}
                  onChange={(e) =>
                    setForm({ ...form, role: e.target.value })
                  }
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary"
                >
                  <option value="user">普通用户</option>
                  <option value="admin">管理员</option>
                </select>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="flex-1 px-4 py-2 text-sm border border-border rounded-lg hover:bg-bg-hover transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="flex-1 px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
                >
                  {createMutation.isPending ? "创建中..." : "创建用户"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </WorkspaceLayout>
  );
}
