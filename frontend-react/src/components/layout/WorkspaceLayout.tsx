import type { LucideIcon } from "lucide-react";
import PageHeader from "../ui/PageHeader";

interface WorkspaceLayoutProps {
  title: string;
  icon?: LucideIcon;
  iconColor?: string;
  description?: string;
  action?: React.ReactNode;
  backTo?: string;
  children: React.ReactNode;
  /** Use full width instead of max-w-6xl */
  fullWidth?: boolean;
}

export default function WorkspaceLayout({
  title,
  icon,
  iconColor,
  description,
  action,
  backTo,
  children,
  fullWidth = false,
}: WorkspaceLayoutProps) {
  return (
    <div className="flex-1 overflow-auto">
      <div
        className={`mx-auto px-4 sm:px-6 lg:px-8 py-6 ${
          fullWidth ? "w-full" : "max-w-6xl"
        }`}
      >
        <PageHeader
          title={title}
          icon={icon}
          iconColor={iconColor}
          description={description}
          action={action}
          backTo={backTo}
        />
        {children}
      </div>
    </div>
  );
}
