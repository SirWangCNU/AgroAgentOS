import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: React.ReactNode;
}

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="p-3 rounded-full bg-bg-hover mb-3">
        <Icon className="w-6 h-6 text-text-muted" />
      </div>
      <div className="text-sm font-medium text-text-secondary">{title}</div>
      {description && (
        <div className="text-xs text-text-muted mt-1 max-w-xs">
          {description}
        </div>
      )}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
