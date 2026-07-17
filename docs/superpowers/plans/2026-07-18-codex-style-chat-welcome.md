# Codex Style Chat Welcome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the empty-chat portal composition with a restrained Codex-style welcome screen centered on one integrated agricultural AI input workspace.

**Architecture:** Keep all existing message, upload, web-search, MCP, and streaming behavior in `Chat.tsx` and `ChatInput.tsx`. Reduce `WelcomeScreen.tsx` to presentation-only branding and place all controls, state indication, and image preview inside one stable input surface.

**Tech Stack:** React 19, TypeScript 6, Tailwind CSS v4, lucide-react, Vite 8.

## Global Constraints

- Do not add dependencies or change API/store contracts.
- Preserve `onSend(text, image)`, web-search, MCP, upload validation, keyboard send, and streaming stop behavior.
- Use warm off-white, ink/slate, and one restrained emerald accent; do not use glow effects or decorative gradients.
- Keep icon controls at least 40px square and provide `title` and `aria-label` text.
- Protect all unrelated dirty-worktree changes.

---

### Task 1: Reduce the Welcome Content to One Visual Focus

**Files:**
- Modify: `frontend-react/src/components/chat/WelcomeScreen.tsx:1-72`

**Interfaces:**
- Consumes: no props.
- Produces: default `WelcomeScreen` component containing only the AgroAgentOS mark and heading.

- [ ] **Step 1: Confirm the old portal elements exist**

Run:

```powershell
rg -n "SUGGESTIONS|农业知识库|上传叶片" frontend-react/src/components/chat/WelcomeScreen.tsx
```

Expected: matches for the status strip and suggestion content that will be removed.

- [ ] **Step 2: Replace the component with the minimal heading**

Use this complete component:

```tsx
import { Leaf } from "lucide-react";

export default function WelcomeScreen() {
  return (
    <header className="text-center">
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-[8px] border border-emerald-100 bg-emerald-50 text-emerald-700">
        <Leaf className="h-6 w-6" strokeWidth={1.8} />
      </div>
      <h1 className="mt-7 text-[32px] font-semibold leading-tight text-[#17201b] sm:text-[36px]">
        今天想解决什么农业问题？
      </h1>
    </header>
  );
}
```

- [ ] **Step 3: Verify removed content and lint the component**

Run:

```powershell
rg -n "SUGGESTIONS|农业知识库|上传叶片" frontend-react/src/components/chat/WelcomeScreen.tsx
npx eslint src/components/chat/WelcomeScreen.tsx
```

Expected: `rg` returns no matches; ESLint exits successfully.

---

### Task 2: Build the Integrated Input Workspace

**Files:**
- Modify: `frontend-react/src/components/chat/ChatInput.tsx:1-229`

**Interfaces:**
- Consumes: existing `Props` contract, including `mode: "chat" | "welcome"`.
- Produces: the same `ChatInput` API with a welcome-mode editor surface and unchanged compact chat mode.

- [ ] **Step 1: Move the preview inside the input surface**

Keep the existing file validation and FileReader behavior. Render the preview before the textarea inside the bordered workspace:

```tsx
{image && imagePreview && (
  <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
    <img
      src={imagePreview}
      alt="已选择的图片"
      className="h-11 w-11 rounded-[6px] object-cover"
    />
    <span className="min-w-0 flex-1 truncate text-sm text-slate-600">
      {image.name}
    </span>
    <button
      type="button"
      onClick={() => {
        setImage(null);
        setImagePreview(null);
      }}
      className="rounded-[6px] px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-800"
    >
      移除
    </button>
  </div>
)}
```

- [ ] **Step 2: Restructure the welcome editor and toolbar**

The input surface must use one vertical composition:

```tsx
<div
  className={`overflow-hidden border bg-white transition-shadow focus-within:border-slate-300 ${
    isWelcomeMode
      ? "rounded-[16px] border-slate-200 shadow-[0_18px_50px_rgba(32,45,38,0.10)] focus-within:shadow-[0_22px_58px_rgba(32,45,38,0.13)]"
      : "rounded-[10px] border-slate-200 shadow-[0_10px_30px_rgba(15,23,42,0.08)]"
  }`}
>
  {image && imagePreview && (
    <div className="flex items-center gap-3 border-b border-slate-100 px-4 py-3">
      <img
        src={imagePreview}
        alt="已选择的图片"
        className="h-11 w-11 rounded-[6px] object-cover"
      />
      <span className="min-w-0 flex-1 truncate text-sm text-slate-600">
        {image.name}
      </span>
      <button
        type="button"
        onClick={() => {
          setImage(null);
          setImagePreview(null);
        }}
        className="flex h-9 w-9 items-center justify-center rounded-[6px] text-slate-400 hover:bg-slate-100 hover:text-slate-700"
        title="移除图片"
        aria-label="移除图片"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )}
  <textarea
    ref={textareaRef}
    value={text}
    onChange={(event) => setText(event.target.value)}
    onKeyDown={handleKeyDown}
    placeholder={isWelcomeMode ? "描述你要处理的农业问题" : "输入问题或上传图片..."}
    rows={isWelcomeMode ? 3 : 1}
    className={`block max-h-[200px] w-full resize-none bg-transparent px-5 text-[15px] leading-6 text-slate-800 outline-none placeholder:text-slate-400 ${
      isWelcomeMode ? "min-h-[76px] pt-5" : "min-h-11 py-3"
    }`}
    disabled={disabled}
  />
  <div className="flex min-h-14 items-center justify-between gap-3 px-3 pb-3">
    <div className="flex items-center gap-1">
      <button
        type="button"
        onClick={() => fileRef.current?.click()}
        className="flex h-10 w-10 items-center justify-center rounded-[8px] text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
        title="上传图片"
        aria-label="上传图片"
      >
        <Camera className="h-[18px] w-[18px]" />
      </button>
      <button
        type="button"
        onClick={() => onWebSearchChange?.(!webSearch)}
        className={`flex h-10 w-10 items-center justify-center rounded-[8px] transition-colors ${
          webSearch
            ? "bg-emerald-50 text-emerald-700"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
        title={webSearch ? "关闭联网搜索" : "开启联网搜索"}
        aria-label={webSearch ? "关闭联网搜索" : "开启联网搜索"}
      >
        <Globe className="h-[18px] w-[18px]" />
      </button>
      <button
        type="button"
        onClick={() => onMcpToolsChange?.(!mcpTools)}
        className={`flex h-10 w-10 items-center justify-center rounded-[8px] transition-colors ${
          mcpTools
            ? "bg-emerald-50 text-emerald-700"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-800"
        }`}
        title={mcpTools ? "关闭 MCP 工具" : "开启 MCP 工具"}
        aria-label={mcpTools ? "关闭 MCP 工具" : "开启 MCP 工具"}
      >
        <Wrench className="h-[18px] w-[18px]" />
      </button>
    </div>
    {streaming ? (
      <button
        type="button"
        onClick={onStop}
        className="flex h-10 w-10 items-center justify-center rounded-[8px] bg-slate-900 text-white hover:bg-slate-700"
        title="停止生成"
        aria-label="停止生成"
      >
        <Square className="h-4 w-4 fill-current" />
      </button>
    ) : (
      <button
        type="button"
        onClick={handleSend}
        disabled={disabled || (!text.trim() && !image)}
        className="flex h-10 w-10 items-center justify-center rounded-[8px] bg-[#17201b] text-white transition-colors hover:bg-[#28342d] disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
        title="发送"
        aria-label="发送"
      >
        {disabled ? (
          <Loader2 className="h-[18px] w-[18px] animate-spin" />
        ) : (
          <ArrowUp className="h-5 w-5" />
        )}
      </button>
    )}
  </div>
</div>
```

- [ ] **Step 3: Confirm the controls use one consistent icon system**

Update the icon import to include `ArrowUp` and `X`, then inspect the JSX from Step 2. Confirm the upload/web/MCP/send controls are 40px square, tool state is represented on the button only, and every control has `type="button"`, a matching `title`, and `aria-label`. Remove the old divider, external status indicators, green send gradient, hover translation, and external MCP badge.

```tsx
import {
  ArrowUp,
  Camera,
  Globe,
  Loader2,
  Square,
  Wrench,
  X,
} from "lucide-react";
```

- [ ] **Step 4: Preserve auto-resize without shrinking welcome mode**

Update the effect to keep a stable welcome minimum:

```tsx
useEffect(() => {
  const element = textareaRef.current;
  if (!element) return;

  element.style.height = "auto";
  const minimumHeight = mode === "welcome" ? 76 : 44;
  element.style.height = `${Math.max(minimumHeight, Math.min(element.scrollHeight, 200))}px`;
}, [mode, text]);
```

- [ ] **Step 5: Lint the input component**

Run:

```powershell
npx eslint src/components/chat/ChatInput.tsx
```

Expected: exits successfully with no errors.

---

### Task 3: Align the Empty Chat Page and Verify the Result

**Files:**
- Modify: `frontend-react/src/pages/Chat.tsx:347-368`

**Interfaces:**
- Consumes: prop-free `WelcomeScreen` and existing `ChatInput` callbacks.
- Produces: centered empty-state composition; message-state rendering remains unchanged.

- [ ] **Step 1: Replace the empty-state wrapper**

Use a plain background and one width constraint:

```tsx
if (!messages.length) {
  return (
    <div className="flex flex-1 overflow-y-auto bg-[#f7f8f6]">
      <div className="mx-auto flex min-h-full w-full max-w-[816px] flex-col justify-center px-6 pb-[12vh] pt-10 sm:px-8">
        <WelcomeScreen />
        <div className="mt-10 w-full">
          <ChatInput
            onSend={handleSend}
            streaming={isStreaming}
            disabled={isStreaming}
            webSearch={webSearch}
            onWebSearchChange={setWebSearch}
            mcpTools={mcpTools}
            onMcpToolsChange={setMcpTools}
            mode="welcome"
          />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Run focused and project validation**

Run:

```powershell
npx eslint src/components/chat/WelcomeScreen.tsx src/components/chat/ChatInput.tsx
npm run build
npm run lint
```

Expected: focused lint and build pass. Report any full-project lint failures separately if they are pre-existing and outside these files.

- [ ] **Step 3: Visually inspect desktop and mobile**

Start the Vite server if needed and inspect `/chat` at `1440x900` and `390x844`. Confirm the editor remains centered, no controls overlap, the title wraps cleanly, image preview stays inside the workspace, and the send button does not shift the layout.

- [ ] **Step 4: Review the final diff**

Run:

```powershell
git diff -- frontend-react/src/components/chat/WelcomeScreen.tsx frontend-react/src/components/chat/ChatInput.tsx frontend-react/src/pages/Chat.tsx
```

Expected: only the approved empty-state presentation and input composition changed; message and API behavior remain intact.
