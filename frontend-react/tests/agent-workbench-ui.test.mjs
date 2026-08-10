import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const welcome = readFileSync("src/components/chat/WelcomeScreen.tsx", "utf8");
const input = readFileSync("src/components/chat/ChatInput.tsx", "utf8");
const chat = readFileSync("src/pages/Chat.tsx", "utf8");
const bubble = readFileSync("src/components/chat/MessageBubble.tsx", "utf8");

assert.ok(
  welcome.includes("今天要处理哪块田的问题"),
  "Welcome screen should lead with an agriculture task-workbench prompt.",
);

assert.ok(
  welcome.includes("当前诊断上下文"),
  "Welcome screen should expose the current diagnosis context panel.",
);

assert.ok(
  welcome.includes("已连接能力"),
  "Welcome screen should show connected agent capabilities.",
);

assert.ok(
  input.includes("提交给智能体处理"),
  "Chat input should read as a task submission control.",
);

assert.equal(
  input.includes(">MCP 工具<"),
  false,
  "Chat input should not expose raw MCP wording as primary product copy.",
);

assert.ok(
  input.includes("containerClassName"),
  "Chat input should let page layouts own the composer width when needed.",
);

assert.ok(
  chat.includes(
    'className="mx-auto flex min-h-full w-full max-w-6xl flex-col justify-center gap-6"',
  ),
  "Empty chat should use one shared workbench shell for welcome content and composer.",
);

assert.ok(
  chat.includes(
    'className="grid w-full gap-6 lg:grid-cols-[minmax(0,1.55fr)_360px]"',
  ) &&
    chat.includes('className="lg:col-start-1"') &&
    chat.includes('containerClassName="w-full"'),
  "Welcome composer should align to the left workbench column on desktop.",
);

assert.ok(
  chat.includes("fileToDataUrl") && chat.includes("imageUrl: imagePreviewUrl"),
  "Chat should attach a local image preview URL to image messages.",
);

assert.ok(
  chat.indexOf("await addMessage({") < chat.indexOf("const result = await analyzeImage(image)"),
  "Chat should render the user's image message before waiting for image analysis.",
);

assert.ok(
  bubble.includes("msg.imageUrl") && bubble.includes("<img"),
  "Message bubble should render uploaded images in user messages.",
);

console.log("Agent workbench UI checks passed.");
