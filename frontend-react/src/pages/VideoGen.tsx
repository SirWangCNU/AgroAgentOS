import { useState, useEffect, useRef, useCallback } from "react";
import {
  Film,
  Sparkles,
  Upload,
  X,
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Play,
} from "lucide-react";
import WorkspaceLayout from "../components/layout/WorkspaceLayout";
import { generateVideo, getVideoTask, listVideoTasks } from "../api/video";
import type { VideoTaskDetail, VideoTaskStatus } from "../types/video";

const STATUS_LABEL: Record<VideoTaskStatus, string> = {
  pending: "排队中",
  processing: "生成中",
  completed: "已完成",
  failed: "生成失败",
};

const STATUS_ICON: Record<VideoTaskStatus, typeof Clock> = {
  pending: Clock,
  processing: Loader2,
  completed: CheckCircle2,
  failed: XCircle,
};

export default function VideoGen() {
  const [prompt, setPrompt] = useState("");
  const [image, setImage] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [activeTask, setActiveTask] = useState<VideoTaskDetail | null>(null);
  const [history, setHistory] = useState<VideoTaskDetail[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const loadHistory = async () => {
    try {
      const data = await listVideoTasks(1, 20);
      setHistory(data.tasks);
    } catch {
      // ignore
    }
  };

  const startPolling = useCallback(
    (taskId: string) => {
      stopPolling();
      pollRef.current = setInterval(async () => {
        try {
          const detail = await getVideoTask(taskId);
          setActiveTask(detail);
          if (detail.status === "completed" || detail.status === "failed") {
            stopPolling();
            loadHistory();
          }
        } catch {
          // ignore poll errors
        }
      }, 3000);
    },
    [stopPolling]
  );

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  useEffect(() => {
    listVideoTasks(1, 20)
      .then((data) => setHistory(data.tasks))
      .catch(() => {});
  }, []);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0] || null;
    setImage(file);
    if (file) {
      const reader = new FileReader();
      reader.onload = () => setImagePreview(reader.result as string);
      reader.readAsDataURL(file);
    } else {
      setImagePreview(null);
    }
  };

  const handleSubmit = async () => {
    if (!prompt.trim()) return;
    setSubmitting(true);
    try {
      const resp = await generateVideo(prompt, image);
      const detail: VideoTaskDetail = {
        task_id: resp.task_id,
        prompt,
        image_url: null,
        status: resp.status,
        video_url: null,
        error_message: null,
        duration: null,
        model: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      setActiveTask(detail);
      startPolling(resp.task_id);
    } catch (err) {
      setActiveTask({
        task_id: "",
        prompt,
        image_url: null,
        status: "failed",
        video_url: null,
        error_message: err instanceof Error ? err.message : "提交失败",
        duration: null,
        model: null,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    } finally {
      setSubmitting(false);
    }
  };

  const renderStatus = (task: VideoTaskDetail) => {
    const Icon = STATUS_ICON[task.status];
    const isSpinning = task.status === "processing";
    return (
      <div className="flex items-center gap-2 text-sm">
        <Icon
          className={`w-4 h-4 ${isSpinning ? "animate-spin text-primary" : ""} ${
            task.status === "completed"
              ? "text-accent-green"
              : task.status === "failed"
              ? "text-accent-red"
              : "text-primary"
          }`}
        />
        <span
          className={
            task.status === "completed"
              ? "text-accent-green"
              : task.status === "failed"
              ? "text-accent-red"
              : "text-text-secondary"
          }
        >
          {STATUS_LABEL[task.status]}
        </span>
      </div>
    );
  };

  return (
    <WorkspaceLayout
      title="AI 视频生成"
      icon={Film}
      iconColor="text-accent-purple"
      description="输入文本描述和可选图片, AI 生成农业短视频"
    >
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <div className="bg-bg-card rounded-xl border border-border p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              视频描述 <span className="text-accent-red">*</span>
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="描述您想生成的视频内容, 如: 一片金黄的麦田在微风中摇曳, 阳光洒落..."
              rows={5}
              className="w-full px-3 py-2.5 text-sm border border-border rounded-lg outline-none focus:border-primary resize-none"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-1.5">
              参考图片 (可选)
            </label>
            {imagePreview ? (
              <div className="relative">
                <img
                  src={imagePreview}
                  alt="preview"
                  className="w-full h-40 object-cover rounded-lg border border-border"
                />
                <button
                  onClick={() => {
                    setImage(null);
                    setImagePreview(null);
                  }}
                  className="absolute top-2 right-2 p-1 bg-black/50 rounded-full text-white hover:bg-black/70 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ) : (
              <label className="flex flex-col items-center justify-center h-32 border-2 border-dashed border-border rounded-lg cursor-pointer hover:border-primary/50 transition-colors">
                <Upload className="w-6 h-6 text-text-muted mb-1" />
                <span className="text-xs text-text-muted">点击上传图片 (JPEG/PNG/WebP, 最大 10MB)</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={handleImageChange}
                  className="hidden"
                />
              </label>
            )}
          </div>

          <button
            onClick={handleSubmit}
            disabled={submitting || !prompt.trim()}
            className="flex items-center justify-center gap-2 w-full py-2.5 bg-accent-purple text-white text-sm font-medium rounded-lg hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {submitting ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Sparkles className="w-4 h-4" />
            )}
            {submitting ? "提交中..." : "开始生成"}
          </button>
        </div>

        {/* Result */}
        <div className="bg-bg-card rounded-xl border border-border p-6">
          {activeTask ? (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-text-primary">生成结果</h3>
                {renderStatus(activeTask)}
              </div>

              <div className="text-xs text-text-muted bg-bg-hover rounded-lg px-3 py-2">
                {activeTask.prompt}
              </div>

              {activeTask.status === "completed" && activeTask.video_url && (
                <video
                  controls
                  src={activeTask.video_url}
                  className="w-full rounded-lg border border-border"
                />
              )}

              {activeTask.status === "failed" && activeTask.error_message && (
                <div className="text-sm text-accent-red bg-accent-red/5 rounded-lg px-4 py-3">
                  {activeTask.error_message}
                </div>
              )}

              {(activeTask.status === "pending" || activeTask.status === "processing") && (
                <div className="flex flex-col items-center justify-center py-12">
                  <Loader2 className="w-10 h-10 text-primary animate-spin mb-3" />
                  <div className="text-sm text-text-secondary">
                    {activeTask.status === "pending" ? "任务排队中..." : "视频生成中, 请耐心等待..."}
                  </div>
                  <div className="text-xs text-text-muted mt-1">生成过程通常需要 1-5 分钟</div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <Film className="w-12 h-12 text-text-muted opacity-30 mb-3" />
              <div className="text-sm text-text-muted">填写描述后点击生成</div>
              <div className="text-xs text-text-muted mt-1">AI 将为您生成短视频</div>
            </div>
          )}
        </div>
      </div>

      {/* History */}
      {history.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-semibold text-text-secondary mb-3">历史记录</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {history.map((task) => (
              <button
                key={task.task_id}
                onClick={() => {
                  setActiveTask(task);
                  if (task.status === "pending" || task.status === "processing") {
                    startPolling(task.task_id);
                  }
                }}
                className="flex items-start gap-3 p-4 bg-bg-card rounded-xl border border-border hover:border-primary/40 hover:shadow-md transition-all text-left"
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-accent-purple/10 flex items-center justify-center">
                  {task.status === "completed" ? (
                    <Play className="w-5 h-5 text-accent-purple" />
                  ) : (
                    <Film className="w-5 h-5 text-accent-purple" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm text-text-primary truncate">{task.prompt}</div>
                  <div className="flex items-center gap-2 mt-1">
                    {renderStatus(task)}
                    <span className="text-xs text-text-muted">
                      {new Date(task.created_at).toLocaleString("zh-CN")}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </WorkspaceLayout>
  );
}
