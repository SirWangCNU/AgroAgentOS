export type VideoTaskStatus = "pending" | "processing" | "completed" | "failed";

export interface VideoGenResponse {
  task_id: string;
  status: VideoTaskStatus;
  message: string;
}

export interface VideoTaskDetail {
  task_id: string;
  prompt: string;
  image_url: string | null;
  status: VideoTaskStatus;
  video_url: string | null;
  error_message: string | null;
  duration: number | null;
  model: string | null;
  created_at: string;
  updated_at: string;
}

export interface VideoTaskListResponse {
  total: number;
  tasks: VideoTaskDetail[];
}
