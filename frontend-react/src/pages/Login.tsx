import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertCircle,
  BarChart3,
  CheckCircle2,
  CloudSun,
  Leaf,
  Lock,
  Mail,
  MapPinned,
  RefreshCw,
  ShieldCheck,
  Sprout,
  User,
} from "lucide-react";
import {
  getCaptcha,
  login as apiLogin,
  register as apiRegister,
} from "../api/auth";
import loginVisual from "../assets/login-agri-operations.png";
import { useAuthStore } from "../stores/auth";

const REMEMBERED_USERNAME_KEY = "agro_login_username";

const navItems = [
  ["HOME PAGE", "首页"],
  ["TECHNICAL PRODUCTS", "技术产品"],
  ["APPLICATION CASE", "应用案例"],
  ["PLATFORM FUNCTION", "平台功能"],
  ["ABOUT US", "关于我们"],
];

const telemetryCards = [
  { label: "作业覆盖率", value: "96.8%", icon: BarChart3 },
  { label: "田块在线", value: "128", icon: MapPinned },
  { label: "气象同步", value: "实时", icon: CloudSun },
];

function getErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error) {
    try {
      const parsed = JSON.parse(err.message) as { message?: unknown };
      if (typeof parsed.message === "string" && parsed.message.trim()) {
        return parsed.message;
      }
    } catch {
      return err.message || fallback;
    }
    return err.message || fallback;
  }
  return fallback;
}

export default function Login() {
  const navigate = useNavigate();
  const authLogin = useAuthStore((s) => s.login);
  const [tab, setTab] = useState<"login" | "register">("login");
  const [loading, setLoading] = useState(false);
  const [captchaLoading, setCaptchaLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [username, setUsername] = useState(
    () => localStorage.getItem(REMEMBERED_USERNAME_KEY) ?? ""
  );
  const [password, setPassword] = useState("");
  const [rememberUsername, setRememberUsername] = useState(
    () => Boolean(localStorage.getItem(REMEMBERED_USERNAME_KEY))
  );
  const [captchaToken, setCaptchaToken] = useState("");
  const [captchaSvg, setCaptchaSvg] = useState("");
  const [captchaAnswer, setCaptchaAnswer] = useState("");

  const [regUsername, setRegUsername] = useState("");
  const [regEmail, setRegEmail] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");

  const captchaImageSrc = useMemo(() => {
    if (!captchaSvg) return "";
    return `data:image/svg+xml;utf8,${encodeURIComponent(captchaSvg)}`;
  }, [captchaSvg]);

  const refreshCaptcha = useCallback(async () => {
    setCaptchaLoading(true);
    try {
      const challenge = await getCaptcha();
      setCaptchaToken(challenge.captcha_token);
      setCaptchaSvg(challenge.image_svg);
      setCaptchaAnswer("");
    } catch (err) {
      setError(getErrorMessage(err, "验证码加载失败，请刷新重试"));
    } finally {
      setCaptchaLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      refreshCaptcha();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [refreshCaptcha]);

  const switchTab = (nextTab: "login" | "register") => {
    setTab(nextTab);
    setError("");
    setSuccess("");
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!captchaToken) {
      setError("验证码加载中，请稍后再试");
      return;
    }
    setLoading(true);
    try {
      const data = await apiLogin(
        username.trim(),
        password,
        captchaToken,
        captchaAnswer.trim()
      );
      if (rememberUsername) {
        localStorage.setItem(REMEMBERED_USERNAME_KEY, username.trim());
      } else {
        localStorage.removeItem(REMEMBERED_USERNAME_KEY);
      }
      authLogin(data.access_token, data.user);
      navigate("/workspace", { replace: true });
    } catch (err) {
      setError(getErrorMessage(err, "登录失败"));
      refreshCaptcha();
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (regPassword !== regConfirm) {
      setError("两次密码不一致");
      return;
    }
    setLoading(true);
    try {
      await apiRegister({
        username: regUsername.trim(),
        email: regEmail.trim(),
        password: regPassword,
        confirm_password: regConfirm,
      });
      setTab("login");
      setUsername(regUsername.trim());
      setPassword("");
      setCaptchaAnswer("");
      setSuccess("注册成功，请使用新账号登录");
      refreshCaptcha();
    } catch (err) {
      setError(getErrorMessage(err, "注册失败"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-portal-shell relative min-h-screen overflow-hidden bg-[#0c7ecc] text-white">
      <div className="absolute inset-0 bg-[linear-gradient(180deg,#2c8ed0_0%,#1296d8_46%,#34bee7_100%)]" />
      <div className="absolute inset-0 opacity-35 [background-image:linear-gradient(rgba(255,255,255,.12)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.12)_1px,transparent_1px)] [background-size:13.333vw_13.333vw]" />
      <div className="absolute inset-x-0 top-0 h-36 bg-[linear-gradient(180deg,rgba(255,255,255,.2),rgba(255,255,255,0))]" />
      <div className="absolute left-[-10%] top-[19%] h-28 w-[62%] -rotate-12 bg-[#21aae2]/26 [clip-path:polygon(0_28%,100%_0,92%_100%,0_78%)]" />
      <div className="absolute right-[-16%] top-[42%] h-32 w-[52%] rotate-12 bg-[#8ee86c]/18 [clip-path:polygon(8%_0,100%_22%,100%_76%,0_100%)]" />
      <div className="absolute inset-x-0 bottom-0 h-48 bg-[#64d5f2]/65 [clip-path:ellipse(82%_70%_at_70%_100%)]" />
      <div className="absolute inset-x-0 bottom-5 h-36 bg-[#18aee4]/65 [clip-path:ellipse(60%_68%_at_25%_100%)]" />
      <div className="absolute inset-x-0 bottom-0 h-24 bg-[#95e6f6]/35 [clip-path:polygon(0_62%,18%_100%,54%_44%,78%_100%,100%_45%,100%_100%,0_100%)]" />

      <header className="relative z-10 border-b border-white/15 bg-[#79b7e5]/28 shadow-[0_18px_50px_rgba(5,64,112,0.16)] backdrop-blur-md">
        <div className="mx-auto grid min-h-24 max-w-[1480px] grid-cols-2 text-center md:grid-cols-5">
        {navItems.map(([en, zh], index) => (
          <button
            key={zh}
            type="button"
            className={`group relative flex min-h-24 flex-col items-center justify-center gap-1 px-3 text-white/90 transition-colors hover:bg-white/10 ${
              index > 1 ? "hidden md:flex" : ""
            }`}
          >
            <span className="text-[11px] font-bold tracking-[0.22em] text-white/90">{en}</span>
            <span className="text-xl font-black drop-shadow-[0_2px_5px_rgba(22,67,106,.35)]">{zh}</span>
            {index === 0 && (
              <span className="absolute bottom-4 h-1 w-28 rounded-full bg-[#f5f84b] shadow-[0_6px_16px_rgba(17,91,130,0.4)]" />
            )}
            <span className="absolute inset-x-5 bottom-0 h-px scale-x-0 bg-white/60 transition-transform duration-300 group-hover:scale-x-100" />
          </button>
        ))}
        </div>
      </header>

      <main className="relative z-10 flex min-h-[calc(100vh-6rem)] items-center justify-center px-4 py-10 lg:py-12">
        <section className="login-portal-card grid w-full max-w-6xl overflow-hidden border border-white/40 bg-white shadow-[0_36px_90px_rgba(5,67,120,0.3)] md:grid-cols-[1.05fr_0.95fr]">
          <div className="relative hidden min-h-[548px] overflow-hidden bg-[#1d98e7] md:block">
            <img
              src={loginVisual}
              alt="农机精准作业监管插画"
              className="absolute inset-0 h-full w-full object-cover"
            />
            <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(8,75,130,.12),rgba(8,75,130,.02)_42%,rgba(4,53,68,.18))]" />

            <div className="absolute inset-x-0 top-0 flex items-center justify-between gap-4 px-8 py-7">
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center rounded-md border border-white/35 bg-white/18 shadow-[0_10px_24px_rgba(4,68,112,.18)] backdrop-blur">
                <Sprout className="h-6 w-6 text-white" />
                </div>
                <div>
                  <div className="text-sm font-semibold uppercase tracking-[0.22em] text-white/80">
                    AgroAgentOS
                  </div>
                  <div className="text-2xl font-black">智农协同平台</div>
                </div>
              </div>
              <div className="rounded-full border border-white/30 bg-white/16 px-4 py-2 text-xs font-semibold text-white/90 backdrop-blur">
                ONLINE COMMAND
              </div>
            </div>

            <div className="absolute left-7 top-32 grid w-48 gap-3">
              {telemetryCards.map(({ label, value, icon: Icon }, index) => (
                <div
                  key={label}
                  className="login-float-card rounded-md border border-white/35 bg-white/18 p-3 shadow-[0_14px_34px_rgba(4,65,105,.2)] backdrop-blur-md"
                  style={{ animationDelay: `${index * 140}ms` }}
                >
                  <div className="mb-2 flex items-center justify-between text-white/85">
                    <span className="text-[11px] font-semibold">{label}</span>
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="text-2xl font-black">{value}</div>
                </div>
              ))}
            </div>

            <div className="absolute bottom-8 left-8 right-8">
              <div className="mb-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.24em] text-[#e8fbff]">
                <span className="h-px flex-1 bg-white/45" />
                Precision Agriculture
                <span className="h-px flex-1 bg-white/45" />
              </div>
              <div className="grid grid-cols-3 gap-3 text-sm text-white/90">
                {["农机作业监管", "数据驱动决策", "多智能体协同"].map((item) => (
                  <div key={item} className="rounded-md border border-white/25 bg-white/12 px-3 py-2 text-center backdrop-blur">
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="relative flex min-h-[548px] items-center justify-center bg-[linear-gradient(135deg,#ffffff_0%,#f8fcff_55%,#eef8ff_100%)] px-5 py-8 text-[#243447] sm:px-10">
            <div className="absolute right-0 top-0 h-28 w-28 border-b border-l border-[#dceef9] bg-[#f6fbff]" />
            <div className="absolute right-5 top-5 h-3 w-3 rounded-full bg-[#f5f84b] shadow-[0_0_0_6px_rgba(245,248,75,.18)]" />
            <div className="w-full max-w-[440px]">
              <div className="mb-8 login-form-enter">
                <div className="mb-5 inline-flex items-center gap-2 rounded-md border border-[#cde8f7] bg-[#e8f6ff] px-3 py-2 text-xs font-semibold text-[#1679b9] shadow-sm">
                  <Leaf className="h-4 w-4" />
                  AgroAgentOS
                </div>
                <h1 className="text-2xl font-black text-[#1d2f3f] sm:text-3xl">
                  农机精准作业监管与服务系统
                </h1>
                <p className="mt-3 text-sm leading-6 text-[#6c7a86]">
                  登录后进入工作台，统一管理农场、知识库、天气、病虫害诊断与市场分析。
                </p>
              </div>

              <div className="mb-6 grid grid-cols-2 rounded-md bg-[#eef6fc] p-1">
                <button
                  type="button"
                  onClick={() => switchTab("login")}
                  className={`rounded-[5px] py-2.5 text-sm font-bold transition-all ${
                    tab === "login"
                      ? "bg-white text-[#1389d4] shadow-[0_6px_16px_rgba(19,137,212,.14)]"
                      : "text-[#8a98a5] hover:text-[#3b4b5a]"
                  }`}
                >
                  登录
                </button>
                <button
                  type="button"
                  onClick={() => switchTab("register")}
                  className={`rounded-[5px] py-2.5 text-sm font-bold transition-all ${
                    tab === "register"
                      ? "bg-white text-[#1389d4] shadow-[0_6px_16px_rgba(19,137,212,.14)]"
                      : "text-[#8a98a5] hover:text-[#3b4b5a]"
                  }`}
                >
                  注册
                </button>
              </div>

              {error && (
                <div className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
                  <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {success && (
                <div className="mb-4 flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{success}</span>
                </div>
              )}

              {tab === "login" ? (
                <form onSubmit={handleLogin} className="space-y-4">
                  <label className="block">
                    <span className="sr-only">用户名</span>
                    <span className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-3 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                      <User className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                      <input
                        type="text"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                        placeholder="用户名"
                        className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                      />
                    </span>
                  </label>

                  <label className="block">
                    <span className="sr-only">密码</span>
                    <span className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-3 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                      <Lock className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                      <input
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        placeholder="密码"
                        className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                      />
                    </span>
                  </label>

                  <div className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-2 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                    <ShieldCheck className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                    <input
                      type="text"
                      value={captchaAnswer}
                      onChange={(e) => setCaptchaAnswer(e.target.value)}
                      required
                      inputMode="numeric"
                      maxLength={4}
                      placeholder="验证码"
                      className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                    />
                    <button
                      type="button"
                      onClick={refreshCaptcha}
                      disabled={captchaLoading}
                      className="flex h-12 min-w-36 items-center justify-center gap-2 rounded-md border border-[#dbe7f0] bg-[#f8fbff] px-2 text-xs font-semibold text-[#1679b9] transition-all hover:border-[#9bd2f3] hover:bg-white disabled:opacity-60"
                      title="刷新验证码"
                    >
                      {captchaImageSrc ? (
                        <img
                          src={captchaImageSrc}
                          alt="验证码"
                          className="h-10 w-28 object-contain"
                        />
                      ) : (
                        <span>加载中</span>
                      )}
                      <RefreshCw
                        className={`h-4 w-4 ${
                          captchaLoading ? "animate-spin" : ""
                        }`}
                      />
                    </button>
                  </div>

                  <label className="flex items-center justify-end gap-2 pt-1 text-sm text-[#6f7d89]">
                    <input
                      type="checkbox"
                      checked={rememberUsername}
                      onChange={(e) => setRememberUsername(e.target.checked)}
                      className="h-4 w-4 rounded border-[#b8c8d6] accent-[#1389d4]"
                    />
                    记住账号
                  </label>

                  <button
                    type="submit"
                    disabled={loading || captchaLoading}
                    className="mt-3 w-full rounded-md bg-[linear-gradient(135deg,#168fda,#0878bf)] px-4 py-3.5 text-sm font-bold text-white shadow-[0_14px_30px_rgba(18,136,210,0.32)] transition-all hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(18,136,210,0.38)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                  >
                    {loading ? "登录中..." : "登录"}
                  </button>
                </form>
              ) : (
                <form onSubmit={handleRegister} className="space-y-4">
                  <label className="block">
                    <span className="sr-only">用户名</span>
                    <span className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-3 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                      <User className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                      <input
                        type="text"
                        value={regUsername}
                        onChange={(e) => setRegUsername(e.target.value)}
                        required
                        placeholder="用户名"
                        className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                      />
                    </span>
                  </label>
                  <label className="block">
                    <span className="sr-only">邮箱</span>
                    <span className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-3 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                      <Mail className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                      <input
                        type="email"
                        value={regEmail}
                        onChange={(e) => setRegEmail(e.target.value)}
                        required
                        placeholder="邮箱"
                        className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                      />
                    </span>
                  </label>
                  <label className="block">
                    <span className="sr-only">密码</span>
                    <span className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-3 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                      <Lock className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                      <input
                        type="password"
                        value={regPassword}
                        onChange={(e) => setRegPassword(e.target.value)}
                        required
                        placeholder="密码"
                        className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                      />
                    </span>
                  </label>
                  <label className="block">
                    <span className="sr-only">确认密码</span>
                    <span className="login-field flex items-center gap-3 rounded-md border border-[#dfeaf2] bg-white px-3.5 py-3 text-[#8d98a3] shadow-sm transition-all focus-within:border-[#1389d4] focus-within:shadow-[0_10px_24px_rgba(19,137,212,.12)]">
                      <Lock className="h-5 w-5 shrink-0 text-[#7ca8c4]" />
                      <input
                        type="password"
                        value={regConfirm}
                        onChange={(e) => setRegConfirm(e.target.value)}
                        required
                        placeholder="确认密码"
                        className="min-w-0 flex-1 bg-transparent text-sm text-[#243447] outline-none placeholder:text-[#a7b1ba]"
                      />
                    </span>
                  </label>

                  <button
                    type="submit"
                    disabled={loading}
                    className="mt-3 w-full rounded-md bg-[linear-gradient(135deg,#168fda,#0878bf)] px-4 py-3.5 text-sm font-bold text-white shadow-[0_14px_30px_rgba(18,136,210,0.32)] transition-all hover:-translate-y-0.5 hover:shadow-[0_18px_36px_rgba(18,136,210,0.38)] disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
                  >
                    {loading ? "注册中..." : "注册"}
                  </button>
                </form>
              )}
            </div>
          </div>
        </section>
      </main>

      <div className="relative z-10 hidden pb-6 text-center text-sm font-semibold text-white/75 md:block">
        下滑更多精彩内容
      </div>
    </div>
  );
}
