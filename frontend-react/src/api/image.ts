import { authFetch } from "./client";
import type { ImageAnalysisResult } from "../types/chat";

export async function analyzeImage(file: File): Promise<ImageAnalysisResult> {
  const formData = new FormData();
  formData.append("file", file);
  return authFetch<ImageAnalysisResult>("/image/analyze", {
    method: "POST",
    body: formData,
  });
}
