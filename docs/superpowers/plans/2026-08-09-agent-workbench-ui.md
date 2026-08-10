# Agent Workbench UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the chat welcome state into a practical agriculture agent workbench that feels less like a generic AI landing screen.

**Architecture:** Keep the existing chat flow and API calls unchanged. Refine the presentation layer in the chat welcome component, input component, and global design tokens.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4, lucide-react.

## Global Constraints

- Do not change backend endpoints or conversation store behavior.
- Keep the initial screen usable as the main agent experience, not a marketing page.
- Avoid generic AI aesthetics: oversized centered logo, purple gradients, glass panels, and empty hero space.
- Prefer operational agriculture language over exposed implementation terms such as MCP.

---

### Task 1: Workbench Regression Check

**Files:**
- Create: `frontend-react/tests/agent-workbench-ui.test.mjs`

**Interfaces:**
- Consumes: `src/components/chat/WelcomeScreen.tsx`, `src/components/chat/ChatInput.tsx`
- Produces: a text-level regression check for the expected workbench language.

- [ ] **Step 1: Write the failing test**
- [ ] **Step 2: Run the test and confirm it fails because the new workbench copy is absent**
- [ ] **Step 3: Keep the test as verification for the visual pass**

### Task 2: Welcome Screen Workbench

**Files:**
- Modify: `frontend-react/src/components/chat/WelcomeScreen.tsx`

**Interfaces:**
- Consumes: `onQuickAction(text: string)`
- Produces: a task-oriented welcome screen with prompt examples, live context, and connected capabilities.

- [ ] **Step 1: Replace the centered logo/card grid with a two-column workbench layout**
- [ ] **Step 2: Add agriculture task entries with short operational descriptions**
- [ ] **Step 3: Add a right-side context panel for crop, location, weather risk, knowledge base, and tools**

### Task 3: Task Submission Input

**Files:**
- Modify: `frontend-react/src/components/chat/ChatInput.tsx`

**Interfaces:**
- Consumes: existing `webSearch` and `mcpTools` toggles
- Produces: a more productized task submission bar.

- [ ] **Step 1: Update placeholder and labels to agriculture-agent wording**
- [ ] **Step 2: Replace visible MCP wording with connected capability wording**
- [ ] **Step 3: Tighten spacing and button styling so it reads like a work tool**

### Task 4: Design Tokens

**Files:**
- Modify: `frontend-react/src/index.css`

**Interfaces:**
- Produces: warmer neutral tokens and deeper agriculture colors.

- [ ] **Step 1: Adjust primary, background, border, and text tokens**
- [ ] **Step 2: Keep existing semantic token names to avoid touching unrelated pages**

### Task 5: Verification

**Files:**
- Use existing build and lint commands.

- [ ] **Step 1: Run `node tests/agent-workbench-ui.test.mjs` from `frontend-react`**
- [ ] **Step 2: Run `npm run build` from `frontend-react`**
- [ ] **Step 3: Run `npm run lint` from `frontend-react`**
