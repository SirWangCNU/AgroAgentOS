import { Check, Circle } from "lucide-react";

interface Step {
  id: string;
  label: string;
}

const STEPS: Step[] = [
  { id: "scenario", label: "准备场景" },
  { id: "inspect", label: "运行巡检" },
  { id: "evidence", label: "查看证据" },
  { id: "approve", label: "批准行动" },
  { id: "execute", label: "执行任务" },
];

interface Props {
  activeStep: number;
}

export default function InspectionStepper({ activeStep }: Props) {
  return (
    <nav aria-label="巡检流程" className="flex items-center gap-1 sm:gap-2">
      {STEPS.map((step, index) => {
        const isCompleted = index < activeStep;
        const isCurrent = index === activeStep;
        const isPending = index > activeStep;

        return (
          <div key={step.id} className="flex items-center">
            <div
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1.5 text-xs font-medium transition-colors sm:px-3 sm:text-sm ${
                isCompleted
                  ? "bg-emerald-100 text-emerald-700"
                  : isCurrent
                  ? "bg-emerald-600 text-white shadow-sm"
                  : "bg-slate-100 text-slate-500"
              }`}
            >
              {isCompleted ? (
                <Check className="h-3.5 w-3.5" />
              ) : (
                <span
                  className={`flex h-4 w-4 items-center justify-center rounded-full text-[10px] ${
                    isCurrent
                      ? "bg-white/20 text-white"
                      : "bg-slate-200 text-slate-500"
                  }`}
                >
                  {isPending ? <Circle className="h-2.5 w-2.5" /> : index + 1}
                </span>
              )}
              <span className="hidden sm:inline">{step.label}</span>
            </div>
            {index < STEPS.length - 1 && (
              <div
                className={`mx-1 h-px w-3 sm:mx-1.5 sm:w-4 ${
                  isCompleted ? "bg-emerald-300" : "bg-slate-200"
                }`}
              />
            )}
          </div>
        );
      })}
    </nav>
  );
}
