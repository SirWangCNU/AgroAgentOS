import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Leaf } from "lucide-react";
import { login as apiLogin, register as apiRegister } from "../api/auth";
import { useAuthStore } from "../stores/auth";

export default function Login() {
  const navigate = useNavigate();
  const authLogin = useAuthStore((s) => s.login);
  const [tab, setTab] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Login form
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  // Register form
  const [regUsername, setRegUsername] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await apiLogin(username, password);
      authLogin(data.access_token, data.user);
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      setError(err.message || "登录失败");
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (regPassword !== regConfirm) {
      setError("两次密码不一致");
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
      setTab("login");
      setUsername(regUsername);
      setPassword("");
    } catch (err: any) {
      setError(err.message || "注册失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-main">
      <div className="w-full max-w-sm mx-4">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-primary flex items-center justify-center mb-3">
            <Leaf className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold text-text-primary">AgroAgentOS</h1>
          <p className="text-sm text-text-muted">智农协同平台</p>
        </div>

        {/* Card */}
        <div className="bg-bg-card rounded-xl border border-border p-6 shadow-sm">
          {/* Tabs */}
          <div className="flex mb-6 border-b border-border">
            <button
              onClick={() => { setTab("login"); setError(""); }}
              className={`flex-1 pb-2 text-sm font-medium transition-colors ${
                tab === "login"
                  ? "text-primary border-b-2 border-primary"
                  : "text-text-muted"
              }`}
            >
              登录
            </button>
            <button
              onClick={() => { setTab("register"); setError(""); }}
              className={`flex-1 pb-2 text-sm font-medium transition-colors ${
                tab === "register"
                  ? "text-primary border-b-2 border-primary"
                  : "text-text-muted"
              }`}
            >
              注册
            </button>
          </div>

          {error && (
            <div className="mb-4 px-3 py-2 text-sm text-accent-red bg-accent-red/5 border border-accent-red/20 rounded-lg">
              {error}
            </div>
          )}

          {tab === "login" ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">
                  用户名
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">
                  密码
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary transition-colors"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
              >
                {loading ? "登录中..." : "登录"}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">
                  用户名
                </label>
                <input
                  type="text"
                  value={regUsername}
                  onChange={(e) => setRegUsername(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">
                  邮箱
                </label>
                <input
                  type="email"
                  value={regEmail}
                  onChange={(e) => setRegEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">
                  密码
                </label>
                <input
                  type="password"
                  value={regPassword}
                  onChange={(e) => setRegPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary transition-colors"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-text-secondary mb-1">
                  确认密码
                </label>
                <input
                  type="password"
                  value={regConfirm}
                  onChange={(e) => setRegConfirm(e.target.value)}
                  required
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg outline-none focus:border-primary transition-colors"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 bg-primary text-white text-sm font-medium rounded-lg hover:bg-primary-hover transition-colors disabled:opacity-50"
              >
                {loading ? "注册中..." : "注册"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
