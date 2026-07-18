import { useState } from "react";
import { CheckCircle2, Clock3, Loader2, Play, Send, Undo2 } from "lucide-react";
import type { FarmTask, TaskSubmitRequest } from "../../types/farmAgent";
import TaskVerificationCard from "./TaskVerificationCard";

interface Props {
  tasks: FarmTask[];
  busyTaskId: string | null;
  onStart: (taskId: string) => void;
  onSubmit: (taskId: string, request: TaskSubmitRequest) => void;
  onComplete: (taskId: string, note: string) => void;
  onReturn: (taskId: string, note: string) => void;
}

const groups = [
  { title: "待执行", statuses: ["pending", "returned"], tone: "border-[#d9c8aa]" },
  { title: "执行中", statuses: ["in_progress"], tone: "border-[#9ebca8]" },
  { title: "待复核", statuses: ["submitted"], tone: "border-[#e3b965]" },
  { title: "已归档", statuses: ["completed", "cancelled"], tone: "border-[#cfd7d1]" },
] as const;

function SubmissionForm({ task, busy, onSubmit }: { task: FarmTask; busy: boolean; onSubmit: Props["onSubmit"] }) {
  const [note, setNote] = useState("");
  const [trajectoryIds, setTrajectoryIds] = useState("");
  const [attachments, setAttachments] = useState("");
  const trajectory_file_ids = trajectoryIds.split(",").map((item) => Number(item.trim())).filter((item) => Number.isInteger(item) && item > 0);
  const attachment_urls = attachments.split("\n").map((item) => item.trim()).filter(Boolean);
  const valid = note.trim().length > 0 || trajectory_file_ids.length > 0 || attachment_urls.length > 0;
  return <div className="mt-3 space-y-2 rounded-xl bg-[#f4f5ef] p-3">
    <textarea aria-label="执行说明" value={note} onChange={(e) => setNote(e.target.value)} placeholder="执行说明" rows={2} className="w-full resize-none rounded-lg border border-[#d8d9cd] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#4e8063]" />
    <input aria-label="轨迹文件编号" value={trajectoryIds} onChange={(e) => setTrajectoryIds(e.target.value)} placeholder="轨迹文件 ID，逗号分隔" className="w-full rounded-lg border border-[#d8d9cd] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#4e8063]" />
    <textarea aria-label="附件地址" value={attachments} onChange={(e) => setAttachments(e.target.value)} placeholder="附件 URL，每行一个" rows={2} className="w-full resize-none rounded-lg border border-[#d8d9cd] bg-white px-2.5 py-2 text-xs outline-none focus:border-[#4e8063]" />
    <button type="button" disabled={!valid || busy} onClick={() => onSubmit(task.task_id, { note, trajectory_file_ids, attachment_urls })} className="ml-auto flex items-center gap-1.5 rounded-lg bg-[#8b5d2e] px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-50">{busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}提交作业证据</button>
  </div>;
}

export default function FarmTaskBoard({ tasks, busyTaskId, onStart, onSubmit, onComplete, onReturn }: Props) {
  return (
    <section className="rounded-3xl border border-[#d8d4c9] bg-[#f2f1e9] p-5">
      <div className="mb-4 flex items-end justify-between"><div><p className="text-[10px] font-bold uppercase tracking-[0.24em] text-[#7f725e]">Field operations</p><h2 className="mt-1 text-lg font-semibold text-[#263a30]">农事任务闭环</h2></div><span className="text-xs text-[#7c776b]">{tasks.length} 项任务</span></div>
      <div className="grid gap-4 xl:grid-cols-4">
        {groups.map((group) => {
          const grouped = tasks.filter((task) => group.statuses.some((status) => status === task.status));
          return <div key={group.title} className={`min-h-44 rounded-2xl border-t-4 ${group.tone} bg-white/70 p-3`}>
            <div className="mb-3 flex items-center justify-between text-xs font-semibold text-[#3f5147]"><span>{group.title}</span><span className="rounded-full bg-[#e8e8df] px-2 py-0.5 text-[10px]">{grouped.length}</span></div>
            <div className="space-y-3">{grouped.map((task) => {
              const busy = busyTaskId === task.task_id;
              return <article key={task.task_id} className="rounded-xl border border-[#deddd3] bg-white p-3 shadow-sm">
                <div className="flex items-start justify-between gap-2"><h3 className="text-sm font-semibold leading-5 text-[#2d3e34]">{task.title}</h3><span className="rounded bg-[#f0ede4] px-1.5 py-0.5 text-[9px] font-bold uppercase text-[#7a6b53]">{task.priority}</span></div>
                <p className="mt-1.5 line-clamp-2 text-[11px] leading-4 text-[#72756e]">{task.instructions}</p>
                {task.due_at && <p className="mt-2 flex items-center gap-1 text-[10px] text-[#947042]"><Clock3 className="h-3 w-3" />{new Date(task.due_at).toLocaleString()}</p>}
                {(task.status === "pending" || task.status === "returned") && <button type="button" disabled={busy} onClick={() => onStart(task.task_id)} className="mt-3 flex items-center gap-1.5 rounded-lg bg-[#1f6a4b] px-2.5 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50">{task.status === "returned" ? <Undo2 className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}{task.status === "returned" ? "再次执行" : "开始任务"}</button>}
                {task.status === "in_progress" && <SubmissionForm task={task} busy={busy} onSubmit={onSubmit} />}
                {task.status === "submitted" && <TaskVerificationCard task={task} busy={busy} onComplete={(note) => onComplete(task.task_id, note)} onReturn={(note) => onReturn(task.task_id, note)} />}
                {task.status === "completed" && <p className="mt-3 flex items-center gap-1 text-[11px] font-semibold text-emerald-700"><CheckCircle2 className="h-3.5 w-3.5" />人工验收完成</p>}
              </article>;
            })}{grouped.length === 0 && <p className="py-10 text-center text-xs text-[#a09c91]">暂无任务</p>}</div>
          </div>;
        })}
      </div>
    </section>
  );
}
