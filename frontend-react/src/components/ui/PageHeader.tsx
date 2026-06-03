import { useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface PageHeaderProps {
  title: string;
  icon?: LucideIcon;
  iconColor?: string;
  description?: string;
  action?: React.ReactNode;
  backTo?: string;
}

export default function PageHeader({
  title,
  icon: Icon,
  iconColor = "text-primary",
  description,
  action,
  backTo = "/workspace",
}: PageHeaderProps) {
  const navigate = useNavigate();

  return (
    <div className="flex items-center justify-between mb-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => navigate(backTo)}
          className="p-2 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex items-center gap-2.5">
          {Icon && (
            <div className={`p-2 rounded-lg bg-bg-hover ${iconColor}`}>
              <Icon className="w-5 h-5" />
            </div>
          )}
          <div>
            <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
            {description && (
              <p className="text-xs text-text-muted mt-0.5">{description}</p>
            )}
          </div>
        </div>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
