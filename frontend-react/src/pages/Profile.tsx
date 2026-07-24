import { useEffect, useState } from "react";
import { authFetch } from "../api/client";
import { useAuthStore } from "../stores/auth";
import { User as UserIcon, Smartphone, Copy, Check, X, RefreshCw } from "lucide-react";
import type { ApiResponse, User } from "../types/api";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";

interface BindInitResp {
  bind_code: string;
  expires_in: number;
}

interface BindStatusResp {
  status: "pending" | "bound" | "expired";
  target_user_id: number | null;
}

export default function Profile() {
  const { user, login, logout } = useAuthStore();
  const [me, setMe] = useState<User | null>(user);
  const [bindCode, setBindCode] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [polling, setPolling] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // 刷新用户信息 (拿到最新 wx_openid 字段)
  const refreshMe = async () => {
    try {
      const resp = await authFetch<ApiResponse<User>>("/auth/me");
      if (resp.code === "SUCCESS") {
        setMe(resp.data);
        // 同步到 store, 让 header/sidebar 也更新
        const token = localStorage.getItem("token");
        if (token) login(token, resp.data);
      }
    } catch (e) {
      // 静默
    }
  };

  useEffect(() => {
    refreshMe();
  }, []);

  // 倒计时
  useEffect(() => {
    if (countdown <= 0) return;
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          setBindCode(null);
          setPolling(false);
          return 0;
        }
        return c - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [countdown]);

  // 轮询绑定状态
  useEffect(() => {
    if (!bindCode || !polling) return;
    const timer = setInterval(async () => {
      try {
        const resp = await authFetch<ApiResponse<BindStatusResp>>(
          `/auth/wx-bind/status?code=${bindCode}`
        );
        if (resp.code === "SUCCESS") {
          if (resp.data.status === "bound") {
            setSuccess("绑定成功! 已迁移小程序历史数据到当前账号");
            setBindCode(null);
            setPolling(false);
            setCountdown(0);
            refreshMe();
          } else if (resp.data.status === "expired") {
            setError("绑定码已过期, 请重新生成");
            setBindCode(null);
            setPolling(false);
            setCountdown(0);
          }
        }
      } catch (e) {
        // 静默
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [bindCode, polling]);

  const handleGenerateCode = async () => {
    setError(null);
    setSuccess(null);
    try {
      const resp = await authFetch<ApiResponse<BindInitResp>>("/auth/wx-bind/init", {
        method: "POST",
      });
      if (resp.code === "SUCCESS") {
        setBindCode(resp.data.bind_code);
        setCountdown(resp.data.expires_in);
        setPolling(true);
      } else {
        setError(resp.message || "生成绑定码失败");
      }
    } catch (e: any) {
      setError(e.message || "生成绑定码失败");
    }
  };

  const handleCancel = () => {
    setBindCode(null);
    setPolling(false);
    setCountdown(0);
  };

  const handleUnbind = async () => {
    if (!confirm("确定要解绑微信吗? 解绑后小程序需要重新绑定才能同步数据")) return;
    setError(null);
    setSuccess(null);
    try {
      const resp = await authFetch<ApiResponse<null>>("/auth/wx-bind", {
        method: "DELETE",
      });
      if (resp.code === "SUCCESS") {
        setSuccess("已解绑微信");
        refreshMe();
      } else {
        setError(resp.message || "解绑失败");
      }
    } catch (e: any) {
      setError(e.message || "解绑失败");
    }
  };

  const handleCopy = async () => {
    if (!bindCode) return;
    try {
      await navigator.clipboard.writeText(bindCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {}
  };

  return (
    <WorkspaceLayout title="个人中心" description="账号信息与绑定管理">
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

        {/* 微信绑定卡 */}
        <div className="bg-bg-card border border-border rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-green-500/20 flex items-center justify-center">
              <Smartphone className="w-5 h-5 text-green-500" />
            </div>
            <div>
              <div className="font-semibold">微信小程序绑定</div>
              <div className="text-xs text-text-muted">
                绑定后, 用微信登录小程序会看到与 Web 完全相同的数据
              </div>
            </div>
          </div>

          {me?.wx_openid ? (
            // 已绑定
            <div className="space-y-3">
              <div className="flex items-center gap-2 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-sm">
                <Check className="w-4 h-4 text-green-500" />
                已绑定微信 (openid: {me.wx_openid.slice(0, 8)}...{me.wx_openid.slice(-4)})
              </div>
              <button
                onClick={handleUnbind}
                className="px-4 py-2 text-sm border border-red-500/50 text-red-500 rounded-lg hover:bg-red-500/10 transition-colors"
              >
                解绑微信
              </button>
            </div>
          ) : bindCode ? (
            // 展示绑定码
            <div className="space-y-4">
              <div className="text-sm text-text-muted">
                在微信小程序「我的 → 绑定 Web 账号」输入以下 6 位绑定码:
              </div>
              <div className="flex items-center justify-center gap-2 py-6 bg-bg-elevated rounded-xl">
                {bindCode.split("").map((d, i) => (
                  <div
                    key={i}
                    className="w-12 h-14 flex items-center justify-center text-3xl font-mono font-bold bg-bg-card border-2 border-primary/50 rounded-lg"
                  >
                    {d}
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-between text-sm">
                <div className="text-text-muted">
                  剩余 <span className="text-primary font-semibold">{countdown}s</span>
                  {polling && <span className="ml-2 inline-flex items-center gap-1"><RefreshCw className="w-3 h-3 animate-spin" /> 等待小程序确认...</span>}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleCopy}
                    className="px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-bg-elevated flex items-center gap-1"
                  >
                    {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                    {copied ? "已复制" : "复制"}
                  </button>
                  <button
                    onClick={handleCancel}
                    className="px-3 py-1.5 text-xs border border-border rounded-lg hover:bg-bg-elevated flex items-center gap-1"
                  >
                    <X className="w-3 h-3" /> 取消
                  </button>
                </div>
              </div>
            </div>
          ) : (
            // 未绑定
            <button
              onClick={handleGenerateCode}
              className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary/90 transition-colors"
            >
              生成绑定码
            </button>
          )}

          {error && (
            <div className="mt-3 p-3 text-sm text-red-500 bg-red-500/10 border border-red-500/30 rounded-lg">
              {error}
            </div>
          )}
          {success && (
            <div className="mt-3 p-3 text-sm text-green-500 bg-green-500/10 border border-green-500/30 rounded-lg">
              {success}
            </div>
          )}
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
