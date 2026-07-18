import { Leaf } from "lucide-react";

export default function WelcomeScreen() {
  return (
    <header className="text-center">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-[8px] border border-emerald-100 bg-emerald-50 text-emerald-700">
        <Leaf className="h-6 w-6" strokeWidth={1.8} />
      </div>
      <h1 className="mt-7 text-[30px] font-semibold leading-[1.25] text-[#17201b] sm:text-[36px]">
        <span className="block sm:inline">今天想解决什么</span>
        <span className="block sm:inline">农业问题？</span>
      </h1>
    </header>
  );
}
