import { Camera, Sprout, CloudSun, BarChart3, Leaf } from "lucide-react";

interface Props {
  onQuickAction: (text: string) => void;
}

const QUICK_ACTIONS = [
  {
    icon: Camera,
    label: "上传图片识别病虫害",
    text: "请帮我识别这张图片中的病虫害",
    color: "text-accent-red",
    bg: "bg-accent-red/10",
  },
  {
    icon: Sprout,
    label: "农业种植问题咨询",
    text: "我想咨询一下作物种植技术问题",
    color: "text-accent-green",
    bg: "bg-accent-green/10",
  },
  {
    icon: CloudSun,
    label: "天气与农事建议",
    text: "今天的天气适合进行农事操作吗？",
    color: "text-accent-amber",
    bg: "bg-accent-amber/10",
  },
  {
    icon: BarChart3,
    label: "农场数据分析",
    text: "请帮我分析一下农场的生产数据",
    color: "text-accent-blue",
    bg: "bg-accent-blue/10",
  },
];

export default function WelcomeScreen({ onQuickAction }: Props) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 rounded-2xl bg-primary flex items-center justify-center">
          <Leaf className="w-7 h-7 text-white" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-text-primary">AgroAgentOS</h1>
          <p className="text-sm text-text-muted">智农协同平台 · 有什么可以帮你？</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 max-w-lg w-full">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            onClick={() => onQuickAction(action.text)}
            className="flex items-start gap-3 p-4 rounded-xl border border-border bg-bg-card hover:bg-bg-hover transition-colors text-left"
          >
            <div className={`p-2 rounded-lg ${action.bg}`}>
              <action.icon className={`w-5 h-5 ${action.color}`} />
            </div>
            <div className="text-sm font-medium text-text-primary">
              {action.label}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
