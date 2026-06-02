import { X, CheckCircle, AlertCircle, Info } from "lucide-react";
import { useUIStore } from "../../stores/ui";

const icons = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
};

const colors = {
  success: "text-accent-green border-accent-green/20 bg-accent-green/5",
  error: "text-accent-red border-accent-red/20 bg-accent-red/5",
  info: "text-accent-blue border-accent-blue/20 bg-accent-blue/5",
};

export default function ToastContainer() {
  const toasts = useUIStore((s) => s.toasts);
  const remove = useUIStore((s) => s.removeToast);

  if (!toasts.length) return null;

  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((toast) => {
        const Icon = icons[toast.type];
        return (
          <div
            key={toast.id}
            className={`flex items-center gap-2 px-4 py-3 rounded-lg border shadow-sm text-sm ${colors[toast.type]}`}
          >
            <Icon className="w-4 h-4 flex-shrink-0" />
            <span>{toast.message}</span>
            <button onClick={() => remove(toast.id)} className="ml-2">
              <X className="w-3 h-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
