---
feature: video-generation
status: delivered
plans:
  - .mimocode/plans/1781931451889-swift-engine.md
---

# AI 视频生成模块 — Final Report

## What Was Built

在工作台中新增了 AI 短视频生成模块，对接 Seedance 2.0（火山引擎 Ark API），支持文本+图片多模态输入异步生成短视频。用户在工作台页面输入视频描述、可选上传参考图片，系统异步提交任务到第三方 API，前端轮询状态直到视频生成完成。

模块采用异步任务模式：提交 → 轮询 → 结果。未配置 API Key 时自动启用 mock 模式返回示例视频，方便开发调试。

## Architecture

### Backend

| Layer | File | Role |
|-------|------|------|
| Config | `app/config.py` | 4 个 `video_gen_*` 字段 (api_key, base_url, model, timeout) |
| Schema | `app/schemas/video.py` | Pydantic 请求/响应模型 (VideoGenRequest, VideoGenResponse, VideoTaskDetail, VideoTaskListResponse) |
| ORM | `app/core/sqlite.py` | `VideoTask` 模型，遵循 `_json` 后缀模式 |
| Service | `app/services/video_gen_service.py` | httpx.AsyncClient 异步调用，mock 兜底，模块级单例 |
| Router | `app/api/v1/video.py` | 3 个端点：POST /generate, GET /tasks, GET /tasks/{task_id} |
| Migration | `alembic/versions/005_add_video_tasks.py` | 创建 video_tasks 表 |
| Exceptions | `app/exceptions.py` | VideoGenerationError, VideoTaskNotFoundError |

### Frontend

| File | Role |
|------|------|
| `frontend-react/src/types/video.ts` | TypeScript 类型定义 |
| `frontend-react/src/api/video.ts` | API 客户端 (generateVideo, getVideoTask, listVideoTasks) |
| `frontend-react/src/pages/VideoGen.tsx` | 工作台页面 (表单+结果+历史记录) |

### Data Flow

```
用户输入 → VideoGen.tsx → POST /api/v1/video/generate (FormData)
  → video.py router → video_gen_service.submit_task() → Seedance API
  → 写入 video_tasks DB → 返回 task_id

前端轮询 → GET /api/v1/video/tasks/{task_id}
  → video.py router → 查询 DB，若 pending/processing 则调用 service.query_task()
  → 更新 DB 状态 → 返回详情

完成 → 前端显示 <video> 播放器
```

### Design Decisions

- **异步任务模式**：视频生成耗时 1-5 分钟，采用提交+轮询而非 SSE 流式，因为第三方 API 本身是异步的
- **mock 兜底**：api_key 为空时返回 mock 数据，无需真实 API 即可开发调试
- **.env 动态配置**：base_url + model 可切换，支持切换到 Kling、Pika 等其他 provider
- **轮询在 router 层**：查询任务时自动触发第三方 API 轮询，对前端透明

## Usage

### 配置

在 `.env` 中设置：
```
VIDEO_GEN_API_KEY=your-volcengine-api-key
VIDEO_GEN_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
VIDEO_GEN_MODEL=seedance-2.0-lite
VIDEO_GEN_TIMEOUT=300
```

不配置 API Key 时自动启用 mock 模式。

### API

- `POST /api/v1/video/generate` — FormData: prompt (必填), image (可选), model (可选)
- `GET /api/v1/video/tasks?page=1&page_size=20` — 任务列表
- `GET /api/v1/video/tasks/{task_id}` — 任务详情

### 前端

访问工作台 → 点击 "AI 视频生成" 卡片 → 输入描述 → 可选上传图片 → 点击 "开始生成"

## Verification

- Backend import: all modules import successfully (schemas, service, router, ORM)
- Frontend lint: 0 new errors in VideoGen files
- Frontend build: `tsc -b && vite build` passes (7.49s)
- Mock mode:未配置 API Key 时提交任务返回 mock 视频 URL

## Source Materials

| File | Role |
|------|------|
| `.mimocode/plans/1781931451889-swift-engine.md` | Implementation plan |
