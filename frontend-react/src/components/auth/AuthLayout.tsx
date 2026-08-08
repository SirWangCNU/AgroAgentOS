import type { ReactNode } from "react";
import { Leaf, Sprout, Bug, LineChart, Users } from "lucide-react";

interface AuthLayoutProps {
  children: ReactNode;
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex overflow-hidden bg-gradient-to-br from-green-50 via-emerald-50 to-teal-50">
      {/* 品牌展示区 - 左侧 */}
      <div className="hidden lg:flex lg:w-3/5 relative overflow-hidden auth-brand-section">
        {/* 渐变光晕装饰 */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-green-300/30 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-amber-200/25 rounded-full blur-3xl translate-y-1/3 -translate-x-1/4" />
        <div className="absolute top-1/3 left-1/4 w-64 h-64 bg-sky-200/20 rounded-full blur-3xl" />

        {/* 装饰性叶子图案 - 使用 CSS/SVG */}
        <svg className="absolute top-20 left-16 w-16 h-16 text-green-500/20 animate-float-slow" viewBox="0 0 24 24" fill="currentColor">
          <path d="M17,8C8,10,5.9,16.17,3.82,21.34L5.71,22L6.66,19.7C7.14,19.87,7.64,20,8,20C19,20,22,3,22,3C21,5,14,5.25,9,6.25C4,7.25,2,11.5,2,13.5C2,15.5,3.75,17.25,3.75,17.25C7,8,17,8,17,8Z" />
        </svg>
        <svg className="absolute bottom-32 right-24 w-20 h-20 text-emerald-500/15 animate-float-medium" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12,2C6.48,2,2,6.48,2,12s4.48,10,10,10s10-4.48,10-10S17.52,2,12,2z M12,20c-4.41,0-8-3.59-8-8s3.59-8,8-8s8,3.59,8,8 S16.41,20,12,20z M11,7h2v6h-2V7z M11,15h2v2h-2V15z" />
        </svg>
        <svg className="absolute top-1/2 right-12 w-12 h-12 text-amber-500/20 animate-float-fast" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12,3L2,12h3v8h6v-6h2v6h6v-8h3L12,3z" />
        </svg>

        {/* 波浪线装饰 */}
        <svg className="absolute bottom-0 left-0 w-full h-32 text-green-600/5" preserveAspectRatio="none" viewBox="0 0 1440 120">
          <path fill="currentColor" d="M0,64L48,69.3C96,75,192,85,288,80C384,75,480,53,576,48C672,43,768,53,864,64C960,75,1056,85,1152,80C1248,75,1344,53,1392,42.7L1440,32L1440,120L1392,120C1344,120,1248,120,1152,120C1056,120,960,120,864,120C768,120,672,120,576,120C480,120,384,120,288,120C192,120,96,120,48,120L0,120Z" />
        </svg>

        {/* 内容区 */}
        <div className="relative z-10 flex flex-col justify-center items-start px-12 xl:px-20 py-12 h-full w-full auth-brand-content">
          {/* Logo */}
          <div className="flex items-center gap-4 mb-8 animate-fade-in-up">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-green-500/30">
              <Leaf className="w-9 h-9 text-white" />
            </div>
            <div>
              <h1 className="text-3xl xl:text-4xl font-bold text-slate-800 tracking-tight">AgroAgentOS</h1>
              <p className="text-green-600 font-medium">智农协同平台</p>
            </div>
          </div>

          {/* Slogan */}
          <div className="mb-12 max-w-lg animate-fade-in-up animation-delay-200">
            <h2 className="text-2xl xl:text-3xl font-semibold text-slate-700 mb-4 leading-tight">
              AI 驱动的<br />
              <span className="text-green-600">现代农业助手</span>
            </h2>
            <p className="text-slate-500 text-base leading-relaxed">
              融合人工智能与农业专家知识，为您提供智能病虫害诊断、农事规划决策、市场行情分析等全方位服务
            </p>
          </div>

          {/* 特性标签 */}
          <div className="grid grid-cols-1 gap-3 w-full max-w-md animate-fade-in-up animation-delay-400">
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/40 backdrop-blur-sm border border-white/60 hover:bg-white/60 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
              <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center flex-shrink-0">
                <Bug className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="font-medium text-slate-700 text-sm">智能病虫害诊断</p>
                <p className="text-xs text-slate-500">AI 图像识别 + 专家知识库</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/40 backdrop-blur-sm border border-white/60 hover:bg-white/60 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
              <div className="w-10 h-10 rounded-lg bg-emerald-100 flex items-center justify-center flex-shrink-0">
                <LineChart className="w-5 h-5 text-emerald-600" />
              </div>
              <div>
                <p className="font-medium text-slate-700 text-sm">农事规划决策</p>
                <p className="text-xs text-slate-500">气象数据 + 种植模型分析</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-xl bg-white/40 backdrop-blur-sm border border-white/60 hover:bg-white/60 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md">
              <div className="w-10 h-10 rounded-lg bg-amber-100 flex items-center justify-center flex-shrink-0">
                <Users className="w-5 h-5 text-amber-600" />
              </div>
              <div>
                <p className="font-medium text-slate-700 text-sm">多端协同工作</p>
                <p className="text-xs text-slate-500">农场团队高效协作</p>
              </div>
            </div>
          </div>

          {/* 底部装饰 */}
          <div className="mt-auto pt-8 flex items-center gap-2 text-slate-400 text-xs animate-fade-in-up animation-delay-600">
            <Sprout className="w-4 h-4" />
            <span>让科技赋能农业 · 让劳作更智慧</span>
          </div>
        </div>
      </div>

      {/* 表单区 - 右侧 */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-8 lg:p-12 relative auth-form-section">
        {/* 移动端 Logo */}
        <div className="lg:hidden absolute top-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-2">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-500 to-emerald-600 flex items-center justify-center shadow-lg shadow-green-500/30">
            <Leaf className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-xl font-bold text-slate-800">AgroAgentOS</h1>
        </div>

        <div className="w-full max-w-md animate-fade-in-right">
          {children}
        </div>
      </div>
    </div>
  );
}
