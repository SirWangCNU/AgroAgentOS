import {
  AlertTriangle,
  BarChart3,
  BookOpenCheck,
  Camera,
  CheckCircle2,
  CloudSun,
  Leaf,
  MapPin,
  Sprout,
  Tractor,
} from "lucide-react";

interface Props {
  onQuickAction: (text: string) => void;
}

const TASKS = [
  {
    icon: Camera,
    label: "病虫害问诊",
    detail: "上传叶片、果实或田间照片，生成诊断依据和防治建议",
    text: "请帮我识别这张图片中的病虫害，并给出诊断依据、防治建议和用药注意事项。",
    tone: "text-accent-red bg-accent-red/10 border-accent-red/20",
  },
  {
    icon: Sprout,
    label: "种植技术咨询",
    detail: "围绕作物、土壤、肥水、长势提出可执行方案",
    text: "我想咨询一个作物种植技术问题，请按现象、可能原因、处理步骤和风险提醒来回答。",
    tone: "text-primary bg-primary/10 border-primary/20",
  },
  {
    icon: CloudSun,
    label: "天气农事判断",
    detail: "结合天气、湿度和作业窗口，判断今天适合做什么",
    text: "请根据当前天气和作物情况，判断今天适合进行哪些农事操作，并说明风险。",
    tone: "text-accent-amber bg-accent-amber/10 border-accent-amber/20",
  },
  {
    icon: BarChart3,
    label: "农场数据复盘",
    detail: "分析产量、投入、病害记录，找出下一步优化点",
    text: "请帮我分析农场生产数据，找出异常、趋势和下一阶段的管理建议。",
    tone: "text-accent-blue bg-accent-blue/10 border-accent-blue/20",
  },
];

const CONTEXT_ITEMS = [
  { label: "作物", value: "待确认", icon: Leaf },
  { label: "地块", value: "未选择", icon: MapPin },
  { label: "天气风险", value: "高湿需留意", icon: CloudSun },
  { label: "知识库", value: "农业资料已启用", icon: BookOpenCheck },
];

const CAPABILITIES = ["图像识别", "知识库检索", "天气判断", "农场工具"];

export default function WelcomeScreen({ onQuickAction }: Props) {
  return (
    <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6 lg:px-8">
      <div className="mx-auto flex min-h-full w-full max-w-6xl items-center">
        <div className="grid w-full gap-6 lg:grid-cols-[minmax(0,1.55fr)_360px]">
          <section className="min-w-0">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-primary/20 bg-primary text-white shadow-sm">
                <Tractor className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium uppercase tracking-[0.18em] text-primary">
                  AgroAgentOS
                </p>
                <h1 className="text-2xl font-semibold text-text-primary sm:text-3xl">
                  今天要处理哪块田的问题？
                </h1>
              </div>
            </div>

            <div className="mb-5 max-w-2xl border-l-2 border-primary/30 pl-4">
              <p className="text-sm leading-6 text-text-secondary">
                把作物、地块、天气、图片和历史记录交给智能体，它会检索知识库、调用工具，并把处理步骤整理成可执行建议。
              </p>
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              {TASKS.map((task) => (
                <button
                  key={task.label}
                  onClick={() => onQuickAction(task.text)}
                  className="group min-h-[118px] rounded-lg border border-border bg-bg-card p-4 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-md"
                >
                  <div className="mb-4 flex items-center justify-between gap-3">
                    <div className={`rounded-md border p-2 ${task.tone}`}>
                      <task.icon className="h-5 w-5" />
                    </div>
                    <span className="text-xs text-text-muted transition-colors group-hover:text-primary">
                      提交给智能体处理
                    </span>
                  </div>
                  <div className="text-base font-semibold text-text-primary">
                    {task.label}
                  </div>
                  <p className="mt-2 text-sm leading-5 text-text-secondary">
                    {task.detail}
                  </p>
                </button>
              ))}
            </div>
          </section>

          <aside className="space-y-4">
            <section className="rounded-lg border border-border bg-bg-card p-4 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-text-primary">
                    当前诊断上下文
                  </h2>
                  <p className="mt-1 text-xs text-text-muted">
                    会随地块、图片和对话内容更新
                  </p>
                </div>
                <span className="rounded-md border border-accent-amber/20 bg-accent-amber/10 px-2 py-1 text-xs font-medium text-accent-amber">
                  待补全
                </span>
              </div>

              <div className="space-y-2">
                {CONTEXT_ITEMS.map((item) => (
                  <div
                    key={item.label}
                    className="flex items-center justify-between gap-3 rounded-md border border-border/70 bg-bg-main px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <item.icon className="h-4 w-4 shrink-0 text-primary" />
                      <span className="text-sm text-text-secondary">
                        {item.label}
                      </span>
                    </div>
                    <span className="truncate text-sm font-medium text-text-primary">
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-border bg-bg-card p-4 shadow-sm">
              <div className="mb-3 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <h2 className="text-sm font-semibold text-text-primary">
                  已连接能力
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {CAPABILITIES.map((item) => (
                  <span
                    key={item}
                    className="rounded-md border border-primary/15 bg-primary/5 px-2.5 py-1 text-xs font-medium text-primary"
                  >
                    {item}
                  </span>
                ))}
              </div>
            </section>

            <section className="rounded-lg border border-accent-red/20 bg-accent-red/5 p-4">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-accent-red" />
                <div>
                  <h2 className="text-sm font-semibold text-text-primary">
                    近期重点
                  </h2>
                  <p className="mt-1 text-sm leading-5 text-text-secondary">
                    连续阴雨或棚内湿度偏高时，优先排查霜霉病、灰霉病和根系缺氧风险。
                  </p>
                </div>
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
