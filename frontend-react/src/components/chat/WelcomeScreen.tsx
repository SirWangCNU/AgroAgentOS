import { Leaf } from "lucide-react";

export default function WelcomeScreen() {
  return (
    <header className="text-center">
      <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 text-white shadow-lg shadow-emerald-200">
        <Leaf className="h-6 w-6" strokeWidth={1.8} />
      </div>
      <h1 className="mt-6 text-[32px] font-semibold leading-[1.2] tracking-tight text-[#16271c] sm:text-[40px]">
        今天想解决什么农业问题？
      </h1>
      <p className="mt-3 text-sm text-slate-500 sm:text-base">
        选择下方智能体，或直接在输入框描述你的农田情况
      </p>
    </header>
  );
}
