import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Plus,
  MessageSquare,
  Trash2,
  PenLine,
  Check,
  X,
} from "lucide-react";
import { useConversationStore } from "../../stores/conversation";
import { useUIStore } from "../../stores/ui";

export default function ConversationSidebar() {
  const navigate = useNavigate();
  const toggleSidebar = useUIStore((s) => s.toggleSidebar);
  const {
    conversations,
    activeId,
    refreshConversations,
    createNew,
    deleteOne,
    renameOne,
  } = useConversationStore();

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  // Group by date
  const groups = groupByDate(conversations);

  return (
    <aside className="w-[260px] flex flex-col bg-[#1e1e2e] text-white h-full shadow-xl">
      {/* New Chat button */}
      <button
        onClick={async () => {
          const id = await createNew();
          navigate(`/chat/${id}`);
          toggleSidebar();
        }}
        className="flex items-center gap-2 mx-3 mt-3 px-3 py-2.5 text-sm border border-white/20 rounded-lg hover:bg-white/10 transition-colors"
      >
        <Plus className="w-4 h-4" /> 新对话
      </button>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto mt-3 px-2 space-y-4">
        {groups.map((group) => (
          <div key={group.label}>
            <div className="px-2 py-1 text-xs text-white/40 font-medium">
              {group.label}
            </div>
            <div className="space-y-0.5">
              {group.items.map((conv) => (
                <ConversationItem
                  key={conv.id}
                  id={conv.id}
                  title={conv.title}
                  active={conv.id === activeId}
                  onNavigate={() => toggleSidebar()}
                  onDelete={() => deleteOne(conv.id)}
                  onRename={(title) => renameOne(conv.id, title)}
                />
              ))}
            </div>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="text-center text-white/30 text-sm py-8">
            暂无对话记录
          </div>
        )}
      </div>
    </aside>
  );
}

function ConversationItem({
  id,
  title,
  active,
  onNavigate,
  onDelete,
  onRename,
}: {
  id: string;
  title: string;
  active: boolean;
  onNavigate: () => void;
  onDelete: () => void;
  onRename: (title: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState(title);

  const handleSave = () => {
    if (editValue.trim()) onRename(editValue.trim());
    setEditing(false);
  };

  return (
    <Link
      to={`/chat/${id}`}
      onClick={onNavigate}
      className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors no-underline ${
        active
          ? "bg-white/15 text-white"
          : "text-white/70 hover:bg-white/8"
      }`}
    >
      <MessageSquare className="w-4 h-4 flex-shrink-0 opacity-50" />
      {editing ? (
        <div className="flex-1 flex items-center gap-1">
          <input
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSave();
              if (e.key === "Escape") setEditing(false);
            }}
            className="flex-1 bg-transparent border-b border-white/30 outline-none text-sm"
            autoFocus
            onClick={(e) => e.preventDefault()}
          />
          <button
            onClick={(e) => {
              e.preventDefault();
              handleSave();
            }}
          >
            <Check className="w-3 h-3" />
          </button>
          <button
            onClick={(e) => {
              e.preventDefault();
              setEditing(false);
            }}
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      ) : (
        <>
          <span className="flex-1 truncate">{title}</span>
          <div className="hidden group-hover:flex items-center gap-1">
            <button
              onClick={(e) => {
                e.preventDefault();
                setEditValue(title);
                setEditing(true);
              }}
              className="p-0.5 hover:bg-white/20 rounded"
            >
              <PenLine className="w-3 h-3" />
            </button>
            <button
              onClick={(e) => {
                e.preventDefault();
                onDelete();
              }}
              className="p-0.5 hover:bg-white/20 rounded"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </>
      )}
    </Link>
  );
}

function groupByDate(conversations: { created_at: string; title: string; id: string }[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const weekAgo = new Date(today.getTime() - 7 * 86400000);

  const groups: { label: string; items: typeof conversations }[] = [
    { label: "今天", items: [] },
    { label: "昨天", items: [] },
    { label: "最近7天", items: [] },
    { label: "更早", items: [] },
  ];

  for (const conv of conversations) {
    const d = new Date(conv.created_at);
    // Skip conversations with invalid dates — put them in "更早" as fallback
    if (isNaN(d.getTime())) {
      groups[3].items.push(conv);
      continue;
    }
    if (d >= today) groups[0].items.push(conv);
    else if (d >= yesterday) groups[1].items.push(conv);
    else if (d >= weekAgo) groups[2].items.push(conv);
    else groups[3].items.push(conv);
  }

  return groups.filter((g) => g.items.length > 0);
}
