import {
  Search,
  BookOpen,
  Globe,
  Wrench,
  Brain,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Database,
  User,
} from "lucide-react";
import type { ProgressStep } from "../../types/chat";

interface Props {
  steps: ProgressStep[];
}

const STAGE_CONFIG: Record<
  string,
  { icon: typeof Search; color: string; bg: string }
> = {
  rewrite: { icon: Brain, color: "text-accent-purple", bg: "bg-accent-purple/10" },
  rewrite_done: { icon: Brain, color: "text-accent-purple", bg: "bg-accent-purple/10" },
  retrieve: { icon: BookOpen, color: "text-accent-blue", bg: "bg-accent-blue/10" },
  retrieve_done: { icon: BookOpen, color: "text-accent-blue", bg: "bg-accent-blue/10" },
  retrieve_degraded: { icon: AlertCircle, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  web: { icon: Globe, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  web_done: { icon: Globe, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  web_degraded: { icon: AlertCircle, color: "text-accent-amber", bg: "bg-accent-amber/10" },
  user_context: { icon: User, color: "text-accent-green", bg: "bg-accent-green/10" },
  user_context_done: { icon: User, color: "text-accent-green", bg: "bg-accent-green/10" },
  llm_start: { icon: Brain, color: "text-accent-purple", bg: "bg-accent-purple/10" },
  tool_call: { icon: Wrench, color: "text-primary", bg: "bg-primary/10" },
  stats: { icon: Database, color: "text-text-muted", bg: "bg-bg-hover" },
};

export default function ProgressSteps({ steps }: Props) {
  if (!steps.length) return null;

  return (
    <div className="mb-3 px-1">
      <div className="flex flex-wrap gap-2">
        {steps.map((step) => {
          const cfg = STAGE_CONFIG[step.stage] || {
            icon: Search,
            color: "text-text-muted",
            bg: "bg-bg-hover",
          };
          const Icon = cfg.icon;

          return (
            <div
              key={step.id}
              className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-all ${
                step.status === "running"
                  ? "border-primary/30 bg-primary/5"
                  : step.status === "error"
                  ? "border-accent-red/30 bg-accent-red/5"
                  : step.status === "skipped"
                  ? "border-border bg-bg-hover opacity-50"
                  : "border-border bg-bg-card"
              }`}
            >
              <div className={`p-0.5 rounded ${cfg.bg}`}>
                <Icon className={`w-3 h-3 ${cfg.color}`} />
              </div>
              <span
                className={`font-medium ${
                  step.status === "running"
                    ? "text-primary"
                    : step.status === "error"
                    ? "text-accent-red"
                    : "text-text-secondary"
                }`}
              >
                {step.label}
              </span>
              {step.detail && (
                <span className="text-text-muted max-w-[120px] truncate">
                  {step.detail}
                </span>
              )}
              {step.status === "running" ? (
                <Loader2 className="w-3 h-3 text-primary spinner" />
              ) : step.status === "done" ? (
                <CheckCircle2 className="w-3 h-3 text-accent-green" />
              ) : step.status === "error" ? (
                <AlertCircle className="w-3 h-3 text-accent-red" />
              ) : null}
              {step.elapsed_ms != null && step.elapsed_ms > 0 && (
                <span className="text-text-muted text-[10px]">
                  {step.elapsed_ms >= 1000
                    ? `${(step.elapsed_ms / 1000).toFixed(1)}s`
                    : `${step.elapsed_ms}ms`}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
