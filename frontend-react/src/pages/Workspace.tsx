import { useNavigate } from "react-router-dom";
import {
  CloudSun,
  Tractor,
  BookOpen,
  Megaphone,
  Bug,
  Users,
  ArrowLeft,
  Activity,
  Database,
  Cpu,
} from "lucide-react";
import { useAuthStore } from "../stores/auth";
import { useHealthStore } from "../stores/health";

const TOOLS = [
  {
    icon: CloudSun,
    label: "天气查询",
    desc: "查看实时天气和农事建议",
    path: "/workspace/weather",
    color: "text-accent-amber",
    bg: "bg-accent-amber/10",
  },
  {
    icon: Tractor,
    label: "农场管理",
    desc: "管理农场、地块和作业轨迹",
    path: "/workspace/farms",
    color: "text-accent-green",
    bg: "bg-accent-green/10",
  },
  {
    icon: BookOpen,
    label: "知识库",
    desc: "上传和管理农业知识文档",
    path: "/workspace/knowledge",
    color: "text-accent-blue",
    bg: "bg-accent-blue/10",
  },
  {
    icon: Megaphone,
    label: "营销生成",
    desc: "生成农产品营销文案",
    path: "/workspace/marketing",
    color: "text-accent-purple",
    bg: "bg-accent-purple/10",
  },
  {
    icon: Bug,
    label: "病虫害诊断",
    desc: "基于症状描述诊断病虫害",
    path: "/workspace/pest",
    color: "text-accent-red",
    bg: "bg-accent-red/10",
  },
];

export default function Workspace() {
  const navigate = useNavigate();
  const isAdmin = useAuthStore((s) => s.isAdmin());
  const health = useHealthStore((s) => s.health);
  const skills = useHealthStore((s) => s.skills);

  return (
    <div className="flex-1 overflow-auto">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <button
            onClick={() => navigate("/")}
            className="p-2 text-text-muted hover:text-text-primary hover:bg-bg-hover rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-bold text-text-primary">工作台</h1>
            <p className="text-sm text-text-muted mt-0.5">
              管理您的农业工具和服务
            </p>
          </div>
        </div>

        {/* System status cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
          <StatusCard
            icon={<Activity className="w-5 h-5" />}
            label="系统状态"
            value={health?.status || "检查中..."}
            color="text-accent-green"
          />
          <StatusCard
            icon={<Database className="w-5 h-5" />}
            label="向量数据库"
            value={health?.dependencies.milvus.status || "检查中..."}
            color="text-accent-blue"
          />
          <StatusCard
            icon={<Cpu className="w-5 h-5" />}
            label="可用技能"
            value={`${skills.length} 个`}
            color="text-accent-purple"
          />
        </div>

        {/* Tools grid */}
        <h2 className="text-lg font-semibold mb-4 text-text-primary">
          功能模块
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {TOOLS.map((tool) => (
            <ToolCard
              key={tool.path}
              icon={tool.icon}
              label={tool.label}
              desc={tool.desc}
              color={tool.color}
              bg={tool.bg}
              onClick={() => navigate(tool.path)}
            />
          ))}

          {isAdmin && (
            <ToolCard
              icon={Users}
              label="用户管理"
              desc="管理平台用户和权限"
              color="text-accent-blue"
              bg="bg-accent-blue/10"
              onClick={() => navigate("/workspace/users")}
            />
          )}
        </div>
      </div>
    </div>
  );
}

function StatusCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-bg-card rounded-xl border border-border p-4 flex items-center gap-3">
      <div className={`${color} opacity-60`}>{icon}</div>
      <div>
        <div className="text-xs text-text-muted">{label}</div>
        <div className={`text-sm font-medium ${color}`}>{value}</div>
      </div>
    </div>
  );
}

function ToolCard({
  icon: Icon,
  label,
  desc,
  color,
  bg,
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  desc: string;
  color: string;
  bg: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="flex items-start gap-4 p-5 bg-bg-card rounded-xl border border-border hover:border-primary/40 hover:shadow-md transition-all text-left group"
    >
      <div
        className={`p-3 rounded-xl ${bg} group-hover:scale-105 transition-transform`}
      >
        <Icon className={`w-6 h-6 ${color}`} />
      </div>
      <div className="min-w-0">
        <div className="text-sm font-semibold text-text-primary">{label}</div>
        <div className="text-xs text-text-muted mt-1 leading-relaxed">
          {desc}
        </div>
      </div>
    </button>
  );
}
