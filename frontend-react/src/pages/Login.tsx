import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, User, Lock, Mail, AlertCircle } from "lucide-react";
import { login as apiLogin, register as apiRegister } from "../api/auth";
import { getErrorMessage } from "../api/client";
import { useAuthStore } from "../stores/auth";
import AuthLayout from "../components/auth/AuthLayout";
import FloatingInput from "../components/auth/FloatingInput";
import PasswordStrength from "../components/auth/PasswordStrength";

export default function Login() {
  const navigate = useNavigate();
  const authLogin = useAuthStore((s) => s.login);
  const [tab, setTab] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const [regUsername, setRegUsername] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");
  const [regError, setRegError] = useState("");

  const usernameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    usernameRef.current?.focus();
  }, [tab]);

  const switchTab = (newTab: "login" | "register") => {
    setTab(newTab);
    setError("");
    setRegError("");
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiLogin(username, password);
      authLogin(data.access_token, data.user);
      navigate("/dashboard", { replace: true });
    } catch (err: unknown) {
      setError(getErrorMessage(err, "登录失败，请检查用户名和密码"));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setRegError("");

    if (regPassword.length < 6) {
      setRegError("密码长度至少为 6 位");
      return;
    }
    if (regPassword !== regConfirm) {
      setRegError("两次输入的密码不一致");
      return;
    }
    if (!agreeTerms) {
      setRegError("请先同意服务条款和隐私政策");
      return;
    }

    setLoading(true);
    try {
      await apiRegister({
        username: regUsername,
        email: regEmail,
        password: regPassword,
        confirm_password: regConfirm,
      });
      switchTab("login");
      setUsername(regUsername);
      setPassword("");
    } catch (err: unknown) {
      setError(getErrorMessage(err, "注册失败，请稍后重试"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout>
      <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 p-8 sm:p-10">
        <div className="mb-8">
          <h2 className="text-2xl font-bold text-slate-800 mb-2">
            {tab === "login" ? "欢迎回来" : "创建账户"}
          </h2>
          <p className="text-slate-500 text-sm">
            {tab === "login" ? "登录您的账户继续使用" : "注册一个新账户开始使用"}
          </p>
        </div>

        <div className="relative flex mb-6 bg-slate-100 rounded-xl p-1">
          <div
            className={`absolute top-1 bottom-1 w-[calc(50%-4px)] rounded-lg bg-white shadow-sm transition-all duration-300 ease-out ${
              tab === "login" ? "left-1" : "left-[calc(50%+2px)]"
            }`}
          />
          <button
            onClick={() => switchTab("login")}
            className={`relative flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors z-10 ${
              tab === "login" ? "text-green-600" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            登录
          </button>
          <button
            onClick={() => switchTab("register")}
            className={`relative flex-1 py-2.5 text-sm font-medium rounded-lg transition-colors z-10 ${
              tab === "register" ? "text-green-600" : "text-slate-500 hover:text-slate-700"
            }`}
          >
            注册
          </button>
        </div>

        {error && (
          <div className="mb-5 px-4 py-3 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl flex items-start gap-2 animate-fade-in-up">
            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {tab === "login" ? (
          <form onSubmit={handleLogin} className="space-y-4">
            <FloatingInput
              ref={usernameRef}
              label="用户名"
              icon={User}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
            <FloatingInput
              label="密码"
              icon={Lock}
              isPassword
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />

            <div className="flex items-center justify-between text-sm">
              <label className="flex items-center gap-2 cursor-pointer select-none group">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-300 text-green-600 focus:ring-green-500 focus:ring-offset-0 cursor-pointer"
                />
                <span className="text-slate-500 group-hover:text-slate-700 transition-colors">记住我</span>
              </label>
              <button
                type="button"
                className="text-green-600 hover:text-green-700 font-medium transition-colors"
              >
                忘记密码？
              </button>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-sm font-semibold rounded-xl
                         hover:from-green-600 hover:to-emerald-700 transition-all duration-200
                         hover:-translate-y-0.5 hover:shadow-lg hover:shadow-green-500/25
                         active:translate-y-0 active:shadow-md
                         disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none
                         flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 spinner" />
                  登录中...
                </>
              ) : (
                "登录"
              )}
            </button>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-slate-200" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="px-4 bg-white text-slate-400">其他登录方式</span>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <button
                type="button"
                disabled
                className="w-full py-3 border border-slate-200 rounded-xl text-slate-400 text-sm font-medium
                           hover:border-slate-300 hover:text-slate-500 transition-colors
                           flex items-center justify-center gap-2 cursor-not-allowed opacity-60"
              >
                <span className="text-base">💬</span>
                微信登录（即将推出）
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleRegister} className="space-y-4">
            <FloatingInput
              ref={usernameRef}
              label="用户名"
              icon={User}
              value={regUsername}
              onChange={(e) => setRegUsername(e.target.value)}
              required
              autoComplete="username"
              error={regError && regError.includes("用户名") ? regError : undefined}
            />
            <FloatingInput
              label="邮箱"
              icon={Mail}
              type="email"
              value={regEmail}
              onChange={(e) => setRegEmail(e.target.value)}
              required
              autoComplete="email"
            />
            <div>
              <FloatingInput
                label="密码"
                icon={Lock}
                isPassword
                value={regPassword}
                onChange={(e) => setRegPassword(e.target.value)}
                required
                autoComplete="new-password"
              />
              <PasswordStrength password={regPassword} />
            </div>
            <FloatingInput
              label="确认密码"
              icon={Lock}
              isPassword
              value={regConfirm}
              onChange={(e) => setRegConfirm(e.target.value)}
              required
              autoComplete="new-password"
              error={regError && regError.includes("密码") ? regError : undefined}
            />

            <label className="flex items-start gap-2.5 cursor-pointer select-none group pt-1">
              <input
                type="checkbox"
                checked={agreeTerms}
                onChange={(e) => setAgreeTerms(e.target.checked)}
                className="w-4 h-4 mt-0.5 rounded border-slate-300 text-green-600 focus:ring-green-500 focus:ring-offset-0 cursor-pointer flex-shrink-0"
              />
              <span className="text-xs text-slate-500 leading-relaxed group-hover:text-slate-600 transition-colors">
                我已阅读并同意
                <button type="button" className="text-green-600 hover:text-green-700 mx-0.5">服务条款</button>
                和
                <button type="button" className="text-green-600 hover:text-green-700 mx-0.5">隐私政策</button>
              </span>
            </label>

            {regError && !regError.includes("密码") && !regError.includes("用户名") && (
              <div className="px-4 py-3 text-sm text-red-600 bg-red-50 border border-red-100 rounded-xl flex items-start gap-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <span>{regError}</span>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-2 py-3.5 bg-gradient-to-r from-green-500 to-emerald-600 text-white text-sm font-semibold rounded-xl
                         hover:from-green-600 hover:to-emerald-700 transition-all duration-200
                         hover:-translate-y-0.5 hover:shadow-lg hover:shadow-green-500/25
                         active:translate-y-0 active:shadow-md
                         disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none
                         flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 spinner" />
                  注册中...
                </>
              ) : (
                "创建账户"
              )}
            </button>
          </form>
        )}
      </div>

      <div className="mt-6 text-center text-xs text-slate-400">
        © {new Date().getFullYear()} AgroAgentOS · 智农协同平台
      </div>
    </AuthLayout>
  );
}
