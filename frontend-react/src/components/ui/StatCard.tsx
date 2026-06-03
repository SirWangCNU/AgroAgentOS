import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  color?: string;
  sub?: string;
}

export default function StatCard({
  icon: Icon,
  label,
  value,
  color = "text-primary",
  sub,
}: StatCardProps) {
  return (
    <div className="bg-bg-card rounded-xl border border-border p-4 flex items-center gap-3 hover:shadow-sm transition-shadow">
      <div className={`p-2.5 rounded-lg bg-bg-hover ${color}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-text-muted">{label}</div>
        <div className={`text-base font-semibold ${color} truncate`}>
          {value}
        </div>
        {sub && <div className="text-xs text-text-muted mt-0.5">{sub}</div>}
      </div>
    </div>
  );
}
