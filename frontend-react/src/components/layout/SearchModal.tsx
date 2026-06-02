import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X } from "lucide-react";
import { useUIStore } from "../../stores/ui";
import { NAV_ITEMS } from "../../lib/constants";

export default function SearchModal() {
  const open = useUIStore((s) => s.searchOpen);
  const setOpen = useUIStore((s) => s.setSearchOpen);
  const navigate = useNavigate();
  const [query, setQuery] = useState("");

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setOpen(!open);
      }
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, setOpen]);

  const filtered = NAV_ITEMS.filter(
    (item) =>
      item.label.includes(query) || item.path.includes(query.toLowerCase())
  );

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      <div
        className="absolute inset-0 bg-black/30"
        onClick={() => setOpen(false)}
      />
      <div className="relative w-full max-w-md bg-bg-card rounded-xl shadow-lg border border-border overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Search className="w-4 h-4 text-text-muted" />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索页面..."
            className="flex-1 bg-transparent outline-none text-sm"
          />
          <button onClick={() => setOpen(false)}>
            <X className="w-4 h-4 text-text-muted" />
          </button>
        </div>
        <div className="max-h-64 overflow-y-auto py-1">
          {filtered.map((item) => (
            <button
              key={item.path}
              onClick={() => {
                navigate(item.path);
                setOpen(false);
                setQuery("");
              }}
              className="w-full text-left px-4 py-2 text-sm hover:bg-bg-hover transition-colors"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
