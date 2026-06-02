// ============================================================
// AgroAgentOS 智农协同平台 - Frontend Logic
// ============================================================

const API = "/api/v1";

// 使用带认证的 fetch（如果 auth.js 已加载）
const safeFetch = typeof authFetch === 'function' ? authFetch : fetch;

// ---- Utility Functions ----
function escapeHtml(s) {
    if (s == null) return "";
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function renderMarkdown(md) {
    if (!md) return "";
    let s = String(md).replace(/\\n/g, "\n").replace(/\\t/g, "\t");
    let h = escapeHtml(s);
    h = h.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
    h = h.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    h = h.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    h = h.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    h = h.replace(/^# (.+)$/gm, "<h1>$1</h1>");
    h = h.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    h = h.replace(/^[\-\*] (.+)$/gm, "<li>$1</li>");
    h = h.replace(/(<li>[\s\S]*?<\/li>)(\n<li>)/g, "$1$2");
    h = h.replace(/(<li>[\s\S]+?<\/li>)/g, (m) => `<ul>${m}</ul>`);
    h = h.replace(/<\/ul>\s*<ul>/g, "");
    h = h.replace(/\n\n/g, "</p><p>");
    h = h.replace(/\n/g, "<br>");
    return `<p>${h}</p>`;
}

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return document.querySelectorAll(sel); }
function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v; }
function timeAgo(ts) {
    if (!ts) return "";
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "刚刚";
    if (mins < 60) return `${mins} 分钟前`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} 小时前`;
    const days = Math.floor(hrs / 24);
    return `${days} 天前`;
}

// ============================================================
// SSE Consumer (reused from original)
// ============================================================
async function consumeSSE(response, onEvent) {
    if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(`HTTP ${response.status}: ${text.slice(0, 200)}`);
    }
    if (!response.body) throw new Error("浏览器不支持 ReadableStream");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";
    const blockSplit = /\r?\n\r?\n|\n\n/;
    const lineSplit = /\r?\n/;

    while (true) {
        const { done, value } = await reader.read();
        if (done) { if (buffer.trim()) parseBlock(buffer); break; }
        buffer += decoder.decode(value, { stream: true });
        let parts = buffer.split(blockSplit);
        buffer = parts.pop();
        for (const block of parts) parseBlock(block);
    }

    function parseBlock(block) {
        for (const line of block.split(lineSplit)) {
            if (line.startsWith("data:")) {
                const payload = line.slice(5).trim();
                if (!payload) continue;
                try { onEvent(JSON.parse(payload)); }
                catch (e) { console.warn("[SSE] JSON parse error:", payload, e); }
            }
        }
    }
}

// ============================================================
// SPA Router
// ============================================================
const router = {
    current: "dashboard",
    navigate(page) {
        if (!page) page = "dashboard";
        this.current = page;
        $$(".page").forEach(p => p.classList.remove("active"));
        const el = document.getElementById(`page-${page}`);
        if (el) el.classList.add("active");
        $$(".nav-item").forEach(n => n.classList.toggle("active", n.dataset.page === page));
        window.location.hash = page;
        // Trigger page-specific init
        if (page === "dashboard") initDashboard();
        if (page === "kb" && !kbLoaded) loadDocs();
        if (page === "history" && !historyLoaded) loadHistory();
        if (page === "weather") loadWeatherPage();
        if (page === "farms") initFarmsPage();
    }
};

// ============================================================
// Sidebar
// ============================================================
const sidebar = {
    expanded: true,
    init() {
        $$(".nav-item").forEach(item => {
            item.addEventListener("click", () => router.navigate(item.dataset.page));
        });
        $("#sidebar-toggle").addEventListener("click", () => this.toggle());
        // 应用初始展开状态
        if (this.expanded) {
            $("#sidebar").classList.add("expanded");
            $("#main-area").classList.add("shifted");
            const icon = $("#sidebar-toggle i");
            if (icon) icon.className = "fa-solid fa-angles-left";
        }
    },
    toggle() {
        this.expanded = !this.expanded;
        $("#sidebar").classList.toggle("expanded", this.expanded);
        $("#main-area").classList.toggle("shifted", this.expanded);
        const icon = $("#sidebar-toggle i");
        icon.className = this.expanded ? "fa-solid fa-angles-left" : "fa-solid fa-angles-right";
    }
};

// ============================================================
// Global Search (Ctrl+K)
// ============================================================
const searchItems = [
    { icon: "fa-grip", label: "总览", hint: "Dashboard", page: "dashboard" },
    { icon: "fa-comments", label: "智能问答", hint: "Chat", page: "copilot" },
    { icon: "fa-cloud-sun", label: "天气", hint: "Weather", page: "weather" },
    { icon: "fa-tractor", label: "农场管理", hint: "Farm", page: "farms" },
    { icon: "fa-book-open", label: "知识库", hint: "KB", page: "kb" },
    { icon: "fa-bullhorn", label: "营销助手", hint: "Marketing", page: "marketing" },
    { icon: "fa-bug", label: "病虫害诊断", hint: "Pest", page: "pest" },
    { icon: "fa-clock-rotate-left", label: "历史记录", hint: "History", page: "history" },
];

const searchModal = {
    visible: false,
    selectedIdx: 0,
    init() {
        $("#search-trigger").addEventListener("click", () => this.open());
        document.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                this.visible ? this.close() : this.open();
            }
            if (e.key === "Escape" && this.visible) this.close();
        });
        $("#search-modal").addEventListener("click", (e) => {
            if (e.target.id === "search-modal") this.close();
        });
        $("#search-input").addEventListener("input", () => this.render());
        $("#search-input").addEventListener("keydown", (e) => {
            const items = this.filtered();
            if (e.key === "ArrowDown") { e.preventDefault(); this.selectedIdx = Math.min(this.selectedIdx + 1, items.length - 1); this.render(); }
            if (e.key === "ArrowUp") { e.preventDefault(); this.selectedIdx = Math.max(this.selectedIdx - 1, 0); this.render(); }
            if (e.key === "Enter" && items[this.selectedIdx]) { this.close(); router.navigate(items[this.selectedIdx].page); }
        });
    },
    open() {
        this.visible = true;
        this.selectedIdx = 0;
        $("#search-modal").classList.add("visible");
        $("#search-input").value = "";
        $("#search-input").focus();
        this.render();
    },
    close() {
        this.visible = false;
        $("#search-modal").classList.remove("visible");
    },
    filtered() {
        const q = ($("#search-input").value || "").toLowerCase();
        if (!q) return searchItems;
        return searchItems.filter(i => i.label.toLowerCase().includes(q) || i.hint.toLowerCase().includes(q));
    },
    render() {
        const items = this.filtered();
        const container = $("#search-results");
        container.innerHTML = items.map((item, idx) => `
            <div class="search-result-item ${idx === this.selectedIdx ? 'selected' : ''}" data-page="${item.page}">
                <i class="fa-solid ${item.icon}"></i>
                <span class="result-label">${item.label}</span>
                <span class="result-hint">${item.hint}</span>
            </div>
        `).join("");
        container.querySelectorAll(".search-result-item").forEach((el, idx) => {
            el.addEventListener("click", () => { this.close(); router.navigate(el.dataset.page); });
            el.addEventListener("mouseenter", () => { this.selectedIdx = idx; this.render(); });
        });
    }
};

// ============================================================
// Health Check
// ============================================================
let healthState = { ready: false, milvusOk: false, mcpOk: false, mcpTools: 0 };

async function checkHealth() {
    try {
        const r = await safeFetch(`${API}/health/ready`);
        const data = await r.json();
        const ready = data?.data?.status === "ready";
        const milvusOk = data?.data?.dependencies?.milvus?.status === "ok";
        const mcpOk = data?.data?.dependencies?.mcp?.status === "ok";
        const mcpTools = data?.data?.dependencies?.mcp?.tools_count || 0;
        healthState = { ready, milvusOk, mcpOk, mcpTools };

        const dot = $("#health-dot");
        dot.className = "health-dot " + (ready && mcpOk ? "ok" : ready ? "warn" : "error");
        setText("health-text", ready && mcpOk ? `就绪 · MCP ${mcpTools} 工具` : ready ? "就绪 · MCP 未连" : "Milvus 不可用");
    } catch (e) {
        healthState = { ready: false, milvusOk: false, mcpOk: false, mcpTools: 0 };
        $("#health-dot").className = "health-dot error";
        setText("health-text", "服务不可达");
    }
    updateDashboardHealth();
}

// ============================================================
// Skills
// ============================================================
let skillsCache = [];

async function loadSkills() {
    try {
        const r = await safeFetch(`${API}/skills`);
        const data = await r.json();
        if (data?.code !== "SUCCESS") throw new Error(data?.message || "加载失败");
        skillsCache = data?.data?.skills || [];
    } catch (e) {
        skillsCache = [];
    }
    renderDashboardSkills();
    renderAiopsSkillBar();
}

function renderDashboardSkills() {
    const grid = $("#dash-skills-grid");
    const count = $("#dash-skill-count");
    if (!grid) return;
    count.textContent = skillsCache.length ? `(${skillsCache.length})` : "";
    if (!skillsCache.length) {
        grid.innerHTML = '<div class="empty-state" style="grid-column:1/-1"><div class="empty-text">暂无技能</div></div>';
        return;
    }
    grid.innerHTML = skillsCache.map(s => {
        const risk = s.risk_level || "low";
        return `<div class="skill-mini-card">
            <div class="skill-name">${escapeHtml(s.display_name || s.name)}</div>
            <div class="skill-id">${escapeHtml(s.name)}</div>
            <span class="risk-tag ${risk}">${{low:"低风险",medium:"中风险",high:"高风险"}[risk] || "低风险"}</span>
        </div>`;
    }).join("");
}

function renderAiopsSkillBar() {
    const bar = $("#aiops-skill-bar");
    if (!bar) return;
    if (!skillsCache.length) {
        bar.innerHTML = '<span style="color:var(--text-muted);font-size:11px">暂无技能</span>';
        return;
    }
    bar.innerHTML = skillsCache.map(s => `
        <div class="skill-chip" data-skill="${escapeHtml(s.name)}" title="${escapeHtml(s.display_name || s.name)}">${escapeHtml(s.display_name || s.name)}</div>
    `).join("");
}

function highlightAiopsSkill(skillName, reason) {
    $$("#aiops-skill-bar .skill-chip").forEach(c => c.classList.remove("active"));
    const chip = $(`#aiops-skill-bar .skill-chip[data-skill="${CSS.escape(skillName || "")}"]`);
    if (chip) chip.classList.add("active");
    const banner = $("#aiops-skill-banner");
    if (banner) {
        banner.style.display = "inline";
        banner.textContent = skillName || "(未知)";
    }
}

function clearAiopsSkillHighlight() {
    $$("#aiops-skill-bar .skill-chip").forEach(c => c.classList.remove("active"));
    const banner = $("#aiops-skill-banner");
    if (banner) banner.style.display = "none";
}

// ============================================================
// Dashboard
// ============================================================
let dashInitialized = false;

function updateDashboardHealth() {
    const ring = $("#dash-health-ring");
    const status = $("#dash-health-status");
    const deps = $("#dash-health-deps");
    if (!ring) return;

    const { ready, milvusOk, mcpOk, mcpTools } = healthState;
    if (ready && mcpOk) {
        ring.className = "health-ring";
        ring.innerHTML = '<i class="fa-solid fa-heart-pulse" style="color:var(--accent-green);font-size:24px"></i>';
        status.textContent = "系统正常";
        status.style.color = "var(--accent-green)";
    } else if (ready) {
        ring.className = "health-ring warn";
        ring.innerHTML = '<i class="fa-solid fa-heart-pulse" style="color:var(--accent-orange);font-size:24px"></i>';
        status.textContent = "部分就绪";
        status.style.color = "var(--accent-orange)";
    } else {
        ring.className = "health-ring error";
        ring.innerHTML = '<i class="fa-solid fa-triangle-exclamation" style="color:var(--accent-red);font-size:24px"></i>';
        status.textContent = "系统异常";
        status.style.color = "var(--accent-red)";
    }

    deps.innerHTML = `
        <div class="dep-status"><div class="dep-dot ${milvusOk ? '' : 'down'}"></div> Milvus ${milvusOk ? '已连接' : '不可用'}</div>
        <div class="dep-status"><div class="dep-dot ${mcpOk ? '' : 'optional'}"></div> MCP ${mcpOk ? `${mcpTools} 工具` : '未连接'}</div>
    `;
}

async function loadDashboardAlerts() {
    const list = $("#dash-alerts-list");
    const badge = $("#alert-badge");
    const countEl = $("#alert-count");
    try {
        const r = await safeFetch(`${API}/webhook/history?limit=5`);
        const data = await r.json();
        const items = data?.items || [];
        const total = data?.count || items.length;

        if (countEl) countEl.textContent = total;
        if (badge) badge.className = total > 0 ? "alert-badge" : "alert-badge empty";

        if (!items.length) {
            list.innerHTML = '<div class="empty-state"><div class="empty-icon"><i class="fa-solid fa-bell-slash"></i></div><div class="empty-text">暂无告警记录</div></div>';
            return;
        }

        list.innerHTML = items.map(a => {
            const severity = a.error ? "critical" : "warning";
            const alertName = a.alert?.alertname || a.alert?.name || "";
            return `<div class="alert-row" data-goto="alerts">
                <div class="alert-severity ${severity}"></div>
                <div class="alert-body">
                    <div class="alert-title-text">${escapeHtml(a.query || alertName || "未知告警")}</div>
                    <div class="alert-meta">${a.selected_skill ? `Skill: ${escapeHtml(a.selected_skill)}` : ""} · ${timeAgo(a.started_at)}</div>
                </div>
            </div>`;
        }).join("");

        list.querySelectorAll(".alert-row").forEach(row => {
            row.addEventListener("click", () => router.navigate("alerts"));
        });
    } catch (e) {
        list.innerHTML = '<div style="color:var(--text-muted);font-size:12px">加载失败</div>';
    }
}

async function initDashboard() {
    if (dashInitialized) return;
    dashInitialized = true;
    fetchWeather("北京").then(updateDashboardWeather);
}

// Quick action buttons
$$("[data-goto]").forEach(btn => {
    btn.addEventListener("click", () => router.navigate(btn.dataset.goto));
});

// View all alerts
$("#dash-alerts-viewall")?.addEventListener("click", () => router.navigate("alerts"));

// ============================================================
// AIOps Diagnosis
// ============================================================
let aiopsAbortController = null;

const aiopsMonitor = {
    startTs: 0, timer: null,
    toolCount: 0, toolFail: 0,
    tokenCount: 0,
    realInputTokens: 0, realOutputTokens: 0, realTotalTokens: 0,
    cacheHitTokens: 0, cacheMissTokens: 0,
    hasRealUsage: false,
    reset() {
        this.startTs = Date.now();
        this.toolCount = 0; this.toolFail = 0; this.tokenCount = 0;
        this.realInputTokens = 0; this.realOutputTokens = 0; this.realTotalTokens = 0;
        this.cacheHitTokens = 0; this.cacheMissTokens = 0; this.hasRealUsage = false;
        setText("mon-step", "--"); setText("mon-step-label", "路由中...");
        setText("mon-elapsed", "0.0s"); setText("mon-tools", "0"); setText("mon-tools-fail", "失败 0");
        setText("mon-tokens", "0"); setText("mon-tokens-detail", "输入 0 · 输出 0");
        setText("mon-tokens-badge", "~估算"); setText("mon-stream-hint", "等待中");
        $("#mon-stream").innerHTML = '';
        $("#mon-tool-feed").innerHTML = '';
        if (this.timer) clearInterval(this.timer);
        this.timer = setInterval(() => {
            setText("mon-elapsed", ((Date.now() - this.startTs) / 1000).toFixed(1) + "s");
        }, 100);
    },
    stop() { if (this.timer) { clearInterval(this.timer); this.timer = null; } }
};

function showAiopsMonitor() {
    $("#aiops-monitor").style.display = "flex";
    $("#aiops-report").style.display = "none";
}
function showAiopsReport() {
    $("#aiops-monitor").style.display = "none";
    $("#aiops-report").style.display = "flex";
}

$("#aiops-start")?.addEventListener("click", startAiops);
$("#aiops-stop")?.addEventListener("click", () => { if (aiopsAbortController) aiopsAbortController.abort(); });

async function startAiops() {
    const query = $("#aiops-query").value.trim();
    if (!query) return alert("请输入告警内容");

    const planEl = $("#aiops-plan");
    const stepsEl = $("#aiops-steps");
    const reportEl = $("#aiops-report-body");
    const statusBadge = $("#aiops-status-badge");

    planEl.innerHTML = '<span style="color:var(--text-muted);font-size:12px;font-style:italic">等待 Planner...</span>';
    stepsEl.innerHTML = "";
    reportEl.innerHTML = "";
    showAiopsMonitor();
    aiopsMonitor.reset();
    clearAiopsSkillHighlight();
    statusBadge.textContent = "诊断中";
    statusBadge.style.background = "rgba(88,166,255,0.15)";
    statusBadge.style.color = "var(--accent-blue)";

    $("#aiops-start").disabled = true;
    $("#aiops-stop").disabled = false;

    aiopsAbortController = new AbortController();
    try {
        const resp = await safeFetch(`${API}/aiops/diagnose`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: `web-${Date.now()}`, query }),
            signal: aiopsAbortController.signal,
        });
        await consumeSSE(resp, (ev) => handleAiopsEvent(ev, planEl, stepsEl, reportEl, statusBadge));
        statusBadge.textContent = "完成";
        statusBadge.style.background = "rgba(63,185,80,0.15)";
        statusBadge.style.color = "var(--accent-green)";
    } catch (e) {
        if (e.name === "AbortError") {
            statusBadge.textContent = "已停止";
            statusBadge.style.background = "rgba(139,148,158,0.15)";
            statusBadge.style.color = "var(--text-muted)";
        } else {
            statusBadge.textContent = "失败";
            statusBadge.style.background = "rgba(248,81,73,0.15)";
            statusBadge.style.color = "var(--accent-red)";
            showAiopsReport();
            reportEl.innerHTML = `<p style="color:var(--accent-red)">错误: ${escapeHtml(e.message)}</p>`;
        }
    } finally {
        $("#aiops-start").disabled = false;
        $("#aiops-stop").disabled = true;
        aiopsAbortController = null;
        aiopsMonitor.stop();
    }
}

function handleAiopsEvent(ev, planEl, stepsEl, reportEl, statusBadge) {
    const t = ev.type;
    const d = ev.data || {};

    if (t === "start") {
        statusBadge.textContent = "路由中...";
    } else if (t === "skill_selected") {
        highlightAiopsSkill(d.skill, d.reason);
        statusBadge.textContent = `已选: ${d.skill || "(无)"}`;
    } else if (t === "plan") {
        planEl.innerHTML = "";
        (d.plan || []).forEach((step, i) => {
            const div = document.createElement("div");
            div.className = "plan-step";
            div.innerHTML = `<span class="step-num">${i + 1}</span><span>${escapeHtml(step)}</span>`;
            planEl.appendChild(div);
        });
        statusBadge.textContent = `${d.plan.length} 步计划`;
    } else if (t === "step_start") {
        let div = stepsEl.querySelector(`[data-step-iter="${d.iteration}"]`);
        if (!div) {
            div = document.createElement("div");
            div.className = "step-item executing";
            div.dataset.stepIter = String(d.iteration);
            div.innerHTML = `<div style="font-size:12px;font-weight:600;color:var(--accent-blue);margin-bottom:4px"><i class="fa-solid fa-play"></i> 步骤 ${escapeHtml(String(d.iteration))}</div>
                <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">${escapeHtml(d.step || "")}</div>
                <div class="step-stream"></div>`;
            stepsEl.appendChild(div);
        }
        stepsEl.scrollTop = stepsEl.scrollHeight;
        statusBadge.textContent = `执行第 ${d.iteration} 步`;
        setText("mon-step", String(d.iteration));
        setText("mon-step-label", (d.step || "").slice(0, 40));
        setText("mon-stream-hint", "生成中...");
        const stream = $("#mon-stream");
        if (stream) stream.textContent = "";
    } else if (t === "step_token") {
        const iter = d.iteration || 0;
        const content = d.content || "";
        let div = stepsEl.querySelector(`[data-step-iter="${iter}"]`);
        if (!div) {
            div = document.createElement("div");
            div.className = "step-item executing";
            div.dataset.stepIter = String(iter);
            div.innerHTML = `<div style="font-size:12px;font-weight:600;color:var(--accent-blue);margin-bottom:4px"><i class="fa-solid fa-play"></i> 步骤 ${escapeHtml(String(iter))}</div>
                <div class="step-stream"></div>`;
            stepsEl.appendChild(div);
        }
        const stream = div.querySelector(".step-stream");
        if (stream) {
            stream.textContent += content;
            if (stream.textContent.length > 2000) stream.textContent = "..." + stream.textContent.slice(-1800);
        }
        stepsEl.scrollTop = stepsEl.scrollHeight;
        const monStream = $("#mon-stream");
        if (monStream) {
            if (monStream.querySelector(".italic, [style*='italic']")) monStream.textContent = "";
            monStream.textContent += content;
            if (monStream.textContent.length > 4000) monStream.textContent = "..." + monStream.textContent.slice(-3600);
            monStream.scrollTop = monStream.scrollHeight;
        }
        aiopsMonitor.tokenCount += content.length;
        if (!aiopsMonitor.hasRealUsage) {
            setText("mon-tokens", String(aiopsMonitor.tokenCount));
            setText("mon-tokens-detail", `~流字符 ${aiopsMonitor.tokenCount}`);
        }
    } else if (t === "usage") {
        aiopsMonitor.hasRealUsage = true;
        aiopsMonitor.realInputTokens += d.input_tokens || 0;
        aiopsMonitor.realOutputTokens += d.output_tokens || 0;
        aiopsMonitor.realTotalTokens += d.total_tokens || 0;
        if (d.cache_hit_tokens != null) aiopsMonitor.cacheHitTokens += d.cache_hit_tokens;
        if (d.cache_miss_tokens != null) aiopsMonitor.cacheMissTokens += d.cache_miss_tokens;
        setText("mon-tokens", String(aiopsMonitor.realOutputTokens));
        const parts = [`输入 ${aiopsMonitor.realInputTokens}`, `输出 ${aiopsMonitor.realOutputTokens}`];
        if (aiopsMonitor.cacheHitTokens > 0 || aiopsMonitor.cacheMissTokens > 0) parts.push(`缓存命中 ${aiopsMonitor.cacheHitTokens}`);
        const detailEl = $("#mon-tokens-detail");
        if (detailEl) {
            detailEl.textContent = parts.join(" · ");
            detailEl.title = `合计 ${aiopsMonitor.realTotalTokens} tokens` + (d.model ? ` · ${d.model}` : "");
        }
        setText("mon-tokens-badge", "API 实测");
    } else if (t === "tool_call") {
        aiopsMonitor.toolCount += 1;
        const ok = d.success !== false;
        if (!ok) aiopsMonitor.toolFail += 1;
        setText("mon-tools", String(aiopsMonitor.toolCount));
        setText("mon-tools-fail", `失败 ${aiopsMonitor.toolFail}`);
        const feed = $("#mon-tool-feed");
        if (feed) {
            if (feed.querySelector(".italic, [style*='italic']")) feed.innerHTML = "";
            const row = document.createElement("div");
            row.className = "tool-feed-item";
            const elapsed = d.elapsed_ms != null ? `${d.elapsed_ms}ms` : "";
            row.innerHTML = `<span class="tool-status ${ok ? 'ok' : 'fail'}">${ok ? '✓' : '✗'}</span>
                <span class="tool-name">${escapeHtml(d.name || "?")}</span>
                <span class="tool-elapsed">${escapeHtml(elapsed)}</span>`;
            feed.appendChild(row);
            feed.scrollTop = feed.scrollHeight;
        }
    } else if (t === "step_complete") {
        const iter = d.iteration || 0;
        let div = stepsEl.querySelector(`[data-step-iter="${iter}"]`);
        if (!div) {
            div = document.createElement("div");
            div.dataset.stepIter = String(iter);
            stepsEl.appendChild(div);
        }
        div.className = "step-item done";
        div.innerHTML = `<div style="font-size:12px;font-weight:600;color:var(--accent-green);margin-bottom:4px"><i class="fa-solid fa-check"></i> 步骤 ${escapeHtml(String(iter))}</div>
            <div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px">${escapeHtml(d.step || "")}</div>
            <div style="font-size:11px;color:var(--text-muted);font-style:italic">${escapeHtml((d.result_preview || "").slice(0, 200))}</div>`;
        stepsEl.scrollTop = stepsEl.scrollHeight;
        statusBadge.textContent = `已完成 ${iter} 步`;
    } else if (t === "replan") {
        const div = document.createElement("div");
        div.className = "step-item executing";
        div.innerHTML = `<div style="font-size:12px;color:var(--accent-blue)"><i class="fa-solid fa-arrows-rotate"></i> Replanner 调整: 剩余 ${(d.plan || []).length} 步</div>`;
        stepsEl.appendChild(div);
        stepsEl.scrollTop = stepsEl.scrollHeight;
    } else if (t === "report") {
        showAiopsReport();
        reportEl.innerHTML = renderMarkdown(d.report || "");
        statusBadge.textContent = "报告已生成";
        setText("mon-stream-hint", "已完成");
    } else if (t === "complete") {
        statusBadge.textContent = "完成";
        statusBadge.style.background = "rgba(63,185,80,0.15)";
        statusBadge.style.color = "var(--accent-green)";
    } else if (t === "error") {
        showAiopsReport();
        reportEl.innerHTML = `<p style="color:var(--accent-red)">错误: ${escapeHtml(ev.message)}</p>`;
        statusBadge.textContent = "失败";
        statusBadge.style.background = "rgba(248,81,73,0.15)";
        statusBadge.style.color = "var(--accent-red)";
    }
}

// ============================================================
// AI Copilot (Chat)
// ============================================================
const chatState = {
    webEnabled: false,
    mcpEnabled: true,
    currentDetails: { retrieve: [], web: [], tools: [], stats: null },
    activeCtxTab: "detail",
};

// Context panel tabs
$$(".context-tab").forEach(tab => {
    tab.addEventListener("click", () => {
        $$(".context-tab").forEach(t => t.classList.remove("active"));
        tab.classList.add("active");
        chatState.activeCtxTab = tab.dataset.ctx;
        renderContextPanel();
    });
});

function renderContextPanel() {
    const body = $("#context-body");
    if (!body) return;
    const tab = chatState.activeCtxTab;
    const d = chatState.currentDetails;

    if (tab === "detail") {
        // 渲染知识引用
        const citationsHtml = d.citations && d.citations.length ? renderCitations(d.citations) : '';

        const retrieveHtml = d.retrieve.length ? d.retrieve.map((h, i) => {
            const score = h.score != null ? `<span style="color:var(--accent-green)">score ${h.score}</span>` : "";
            const category = h.category ? `<span class="citation-category ${h.category}">${escapeHtml(h.category_name || h.category)}</span>` : "";
            return `<div class="context-item"><div class="ci-label">${i + 1}. ${escapeHtml(h.source || "未知")} ${score} ${category}</div><div style="font-size:11px;color:var(--text-muted);margin-top:2px">${escapeHtml((h.preview || "").slice(0, 120))}</div></div>`;
        }).join("") : '<div style="color:var(--text-muted);font-size:12px">暂无检索结果</div>';

        const webHtml = d.web.length ? d.web.map((r, i) => {
            const title = r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener" style="color:var(--accent-blue)">${escapeHtml(r.title || "(无标题)")}</a>` : escapeHtml(r.title || "(无标题)");
            return `<div class="context-item"><div class="ci-label">${i + 1}. ${title}</div><div style="font-size:11px;color:var(--text-muted);margin-top:2px">${escapeHtml((r.snippet || "").slice(0, 100))}</div></div>`;
        }).join("") : '<div style="color:var(--text-muted);font-size:12px">暂无联网结果</div>';

        body.innerHTML = `
            ${citationsHtml}
            <div class="context-section"><div class="context-section-title">知识库检索</div>${retrieveHtml}</div>
            <div class="context-section"><div class="context-section-title">联网搜索</div>${webHtml}</div>
        `;
    } else if (tab === "tools") {
        if (!d.tools.length) {
            body.innerHTML = '<div class="empty-state"><div class="empty-text">暂无工具调用</div></div>';
            return;
        }
        body.innerHTML = d.tools.map(t => {
            const ok = (t.status || "").toLowerCase() === "ok";
            return `<div class="context-item"><div style="display:flex;justify-content:space-between"><span class="ci-label" style="font-family:monospace">${escapeHtml(t.name || "?")}</span><span style="color:${ok ? 'var(--accent-green)' : 'var(--accent-red)'};font-weight:600">${ok ? '✓' : '✗'}</span></div><div style="font-size:11px;color:var(--text-muted)">耗时 ${t.elapsed_ms ?? 0}ms · ${t.result_chars ?? 0} 字符</div></div>`;
        }).join("");
    } else if (tab === "stats") {
        const s = d.stats;
        if (!s) {
            body.innerHTML = '<div class="empty-state"><div class="empty-text">暂无统计</div></div>';
            return;
        }
        body.innerHTML = `
            <div class="context-item"><div class="ci-label">模型</div><div class="ci-value">${escapeHtml(s.model || "?")}</div></div>
            <div class="context-item"><div class="ci-label">输入 Tokens</div><div class="ci-value">${s.input_tokens ?? 0}</div></div>
            <div class="context-item"><div class="ci-label">输出 Tokens</div><div class="ci-value">${s.output_tokens ?? 0}</div></div>
            <div class="context-item"><div class="ci-label">合计 Tokens</div><div class="ci-value">${s.total_tokens ?? 0}</div></div>
            <div class="context-item"><div class="ci-label">生成耗时</div><div class="ci-value">${s.llm_ms ?? 0} ms</div></div>
            <div class="context-item"><div class="ci-label">总耗时</div><div class="ci-value">${s.total_ms ?? 0} ms</div></div>
            <div class="context-item"><div class="ci-label">回答字数</div><div class="ci-value">${s.answer_chars ?? 0}</div></div>
        `;
    }
}

// 渲染知识引用组件
function renderCitations(citations) {
    if (!citations || citations.length === 0) return '';

    const categoryNames = {
        'planting': '种植技术',
        'pest_control': '病虫害防治',
        'soil': '土壤管理',
        'weather': '气象知识'
    };

    const citationItems = citations.map((c, i) => {
        const categoryClass = c.category || 'unknown';
        const categoryName = c.category_name || categoryNames[c.category] || '未知';
        const scorePercent = c.relevance_score ? Math.round(c.relevance_score * 100) : 0;

        return `
            <div class="citation-item">
                <div class="citation-item-header">
                    <div class="citation-source">
                        <i class="fa-solid fa-file-lines"></i>
                        ${escapeHtml(c.source || '未知来源')}
                    </div>
                    <span class="citation-category ${categoryClass}">${escapeHtml(categoryName)}</span>
                </div>
                ${c.chapter ? `<div class="citation-chapter">${escapeHtml(c.chapter)}</div>` : ''}
                <div class="citation-content">${escapeHtml((c.content || '').slice(0, 150))}</div>
                <div class="citation-footer">
                    <div class="citation-score">
                        <i class="fa-solid fa-chart-line"></i>
                        相关度: ${scorePercent}%
                    </div>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="knowledge-citation">
            <div class="citation-header">
                <i class="fa-solid fa-book-open"></i>
                <span>知识来源</span>
            </div>
            <div class="citation-body">
                ${citationItems}
            </div>
        </div>
    `;
}

// Web/MCP toggles
function renderChatWebToggle() {
    const btn = $("#chat-web-toggle");
    if (!btn) return;
    btn.className = `toggle-btn ${chatState.webEnabled ? 'on' : ''}`;
    setText("chat-web-state", chatState.webEnabled ? "开" : "关");
}
function renderChatMcpToggle() {
    const btn = $("#chat-mcp-toggle");
    if (!btn) return;
    btn.className = `toggle-btn amber ${chatState.mcpEnabled ? 'on' : ''}`;
    setText("chat-mcp-state", chatState.mcpEnabled ? "开" : "关");
}

$("#chat-web-toggle")?.addEventListener("click", () => { chatState.webEnabled = !chatState.webEnabled; renderChatWebToggle(); });
$("#chat-mcp-toggle")?.addEventListener("click", () => { chatState.mcpEnabled = !chatState.mcpEnabled; renderChatMcpToggle(); });
renderChatWebToggle();
renderChatMcpToggle();

$("#chat-send")?.addEventListener("click", sendChat);
$("#chat-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});

function appendChatBubble(role, content) {
    const container = $("#chat-messages");
    const empty = container.querySelector(".empty-state");
    if (empty) empty.remove();

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble ${role}`;
    bubble.innerHTML = role === "user" ? escapeHtml(content) : renderMarkdown(content);
    container.appendChild(bubble);
    container.scrollTop = container.scrollHeight;
    return bubble;
}

function appendThinkingBubble() {
    const container = $("#chat-messages");
    const empty = container.querySelector(".empty-state");
    if (empty) empty.remove();

    const wrap = document.createElement("div");
    wrap.className = "thinking-bubble";
    wrap.innerHTML = `
        <div class="thinking-header">
            <i class="fa-solid fa-brain" style="color:var(--accent-purple)"></i>
            <span>思考过程</span>
            <span class="toggle-icon" style="margin-left:auto">▼ 收起</span>
        </div>
        <div class="thinking-content"></div>`;
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;

    const header = wrap.querySelector(".thinking-header");
    const content = wrap.querySelector(".thinking-content");
    const toggle = wrap.querySelector(".toggle-icon");
    header.addEventListener("click", () => {
        const hidden = content.style.display === "none";
        content.style.display = hidden ? "" : "none";
        toggle.textContent = hidden ? "▼ 收起" : "▶ 展开";
    });
    return { wrap, content, toggle };
}

function appendChatProgress() {
    const container = $("#chat-messages");
    const empty = container.querySelector(".empty-state");
    if (empty) empty.remove();

    const wrap = document.createElement("div");
    wrap.className = "chat-progress";
    wrap.innerHTML = `
        <div class="progress-head">
            <div class="progress-spinner"></div>
            <span>正在检索并生成回答...</span>
        </div>
        <div class="progress-rows"></div>`;
    container.appendChild(wrap);
    container.scrollTop = container.scrollHeight;
    return wrap;
}

function appendProgressRow(progressBox, ev) {
    if (!progressBox) return;
    const rows = progressBox.querySelector(".progress-rows");
    if (!rows) return;
    const icon = iconForRagStage(ev.stage);
    const elapsed = Number.isFinite(ev.elapsed_ms) && ev.elapsed_ms > 0 ? `<span style="color:var(--accent-blue);font-size:10px">${ev.elapsed_ms}ms</span>` : "";
    const detail = ev.detail ? `<span style="color:var(--text-muted);font-size:11px;margin-left:6px">${escapeHtml(ev.detail)}</span>` : "";

    const row = document.createElement("div");
    row.className = "progress-row";
    row.innerHTML = `<span class="progress-icon">${icon}</span><span>${escapeHtml(ev.label || ev.stage || "")}</span>${detail}${elapsed}`;

    // If there are details, make clickable and add expandable panel
    const detailsHtml = renderRagStageDetails(ev.stage, ev.data || {});
    if (detailsHtml) {
        row.style.cursor = "pointer";
        row.innerHTML += `<span style="margin-left:auto;font-size:10px;color:var(--accent-blue);cursor:pointer">详情</span>`;
        const panel = document.createElement("div");
        panel.className = "progress-detail-panel";
        panel.style.display = "none";
        panel.innerHTML = detailsHtml;
        row.addEventListener("click", () => {
            panel.style.display = panel.style.display === "none" ? "" : "none";
        });
        rows.appendChild(row);
        rows.appendChild(panel);
    } else {
        rows.appendChild(row);
    }

    const container = $("#chat-messages");
    container.scrollTop = container.scrollHeight;
}

function renderRagStageDetails(stage, data) {
    if (!data || typeof data !== "object") return "";
    if (stage === "rewrite_done") {
        const orig = data.original || "", rew = data.rewritten || "";
        if (!orig && !rew) return "";
        return `<div><span style="color:var(--text-muted)">原始:</span> ${escapeHtml(orig)}</div><div><span style="color:var(--text-muted)">改写:</span> ${escapeHtml(rew)}</div>`;
    }
    if (stage === "retrieve_done") {
        const hits = Array.isArray(data.hits) ? data.hits : [];
        // Update context panel data
        chatState.currentDetails.retrieve = hits;
        renderContextPanel();
        if (!hits.length) return `<div style="color:var(--text-muted)">无命中片段</div>`;
        return hits.slice(0, 3).map((h, i) => {
            const score = h.score != null ? `<span style="color:var(--accent-green)">score ${h.score}</span>` : "";
            return `<div style="border-left:2px solid var(--accent-blue);padding-left:6px;margin:4px 0"><div style="color:var(--text-primary)">${i + 1}. ${escapeHtml(h.source || "未知")} ${score}</div><div style="color:var(--text-muted)">${escapeHtml((h.preview || "").slice(0, 80))}</div></div>`;
        }).join("");
    }
    if (stage === "web_done") {
        const results = Array.isArray(data.results) ? data.results : [];
        chatState.currentDetails.web = results;
        renderContextPanel();
        if (!results.length) {
            const reason = data.skip_reason || "未触发联网";
            return `<div style="color:var(--text-muted)">${escapeHtml(reason)}</div>`;
        }
        return results.slice(0, 3).map((r, i) => {
            const title = r.url ? `<a href="${escapeHtml(r.url)}" target="_blank" rel="noopener" style="color:var(--accent-blue)">${escapeHtml(r.title || "(无标题)")}</a>` : escapeHtml(r.title || "(无标题)");
            return `<div style="border-left:2px solid var(--accent-green);padding-left:6px;margin:4px 0"><div>${i + 1}. ${title}</div><div style="color:var(--text-muted)">${escapeHtml((r.snippet || "").slice(0, 80))}</div></div>`;
        }).join("");
    }
    if (stage === "stats") {
        chatState.currentDetails.stats = data;
        renderContextPanel();
        return `
            <div>模型: <span style="color:var(--text-primary)">${escapeHtml(data.model || "?")}</span></div>
            <div>输入 tokens: <span style="color:var(--text-primary)">${data.input_tokens ?? 0}</span></div>
            <div>输出 tokens: <span style="color:var(--text-primary)">${data.output_tokens ?? 0}</span></div>
            <div>合计 tokens: <span style="color:var(--text-primary)">${data.total_tokens ?? 0}</span></div>
            <div>生成耗时: <span style="color:var(--text-primary)">${data.llm_ms ?? 0} ms</span></div>
            <div>总耗时: <span style="color:var(--text-primary)">${data.total_ms ?? 0} ms</span></div>`;
    }
    if (stage === "llm_start") {
        const tools = Array.isArray(data.tools) ? data.tools : [];
        if (data.tools_enabled && tools.length) {
            const chips = tools.map(n => `<span style="display:inline-block;padding:1px 6px;border-radius:3px;background:rgba(210,153,34,0.1);color:var(--accent-orange);font-family:monospace;font-size:10px;margin:1px">${escapeHtml(n)}</span>`).join("");
            return `<div style="color:var(--text-muted)">模型: ${escapeHtml(data.model || "?")} · 已启用 ${tools.length} 个只读工具</div><div style="margin-top:4px;display:flex;flex-wrap:wrap">${chips}</div>`;
        }
        return `<div style="color:var(--text-muted)">模型: ${escapeHtml(data.model || "?")} · 工具回合: 未启用</div>`;
    }
    if (stage === "tool_call") {
        const ok = (data.status || "").toLowerCase() === "ok";
        // Add to context panel tools
        chatState.currentDetails.tools.push(data);
        renderContextPanel();
        return `
            <div>工具: <span style="font-family:monospace;color:var(--text-primary)">${escapeHtml(data.name || "?")}</span></div>
            <div>状态: <span style="color:${ok ? 'var(--accent-green)' : 'var(--accent-red)'};font-weight:600">${ok ? '✓' : '✗'} ${escapeHtml(data.status || "?")}</span></div>
            <div>耗时: <span style="color:var(--text-primary)">${data.elapsed_ms ?? 0} ms</span></div>`;
    }
    return "";
}

function iconForRagStage(stage) {
    const map = { rewrite: "✏️", rewrite_done: "✅", retrieve: "🔍", retrieve_done: "📚", retrieve_degraded: "⚠️", web: "🌐", web_done: "🌐", web_degraded: "⚠️", user_context: "🏡", user_context_done: "🏡", llm_start: "🤖", tool_call: "🛠️", stats: "📊" };
    return map[stage] || "•";
}

function finalizeChatProgress(box, failed = false) {
    if (!box) return;
    const head = box.querySelector(".progress-head");
    if (head) {
        head.innerHTML = failed
            ? '<span style="color:var(--accent-red)">✗ 检索流程中断</span>'
            : '<span style="color:var(--accent-green)">✓ 检索流程完成</span>';
    }
}

async function sendChat() {
    const input = $("#chat-input");
    const question = input.value.trim();
    if (!question) return;
    input.value = "";

    // Reset context panel data for new message
    chatState.currentDetails = { retrieve: [], web: [], tools: [], stats: null };
    renderContextPanel();

    appendChatBubble("user", question);
    const progressBox = appendChatProgress();
    const thinkingBundle = appendThinkingBubble();
    thinkingBundle.wrap.style.display = "none";
    const assistantBubble = appendChatBubble("assistant", "");
    assistantBubble.style.display = "none";
    $("#chat-send").disabled = true;

    try {
        // 调试: 确认 token 是否存在
        const _token = typeof getToken === 'function' ? getToken() : null;
        console.log("[chat] token exists:", !!_token, "token preview:", _token ? _token.substring(0, 20) + "..." : "null");

        const resp = await safeFetch(`${API}/chat/stream`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: "web-chat",
                question,
                top_k: 3,
                web_search: chatState.webEnabled,
                mcp_tools: chatState.mcpEnabled,
            }),
        });

        let buf = "", thinkBuf = "";
        let tokenStarted = false, thinkingStarted = false;

        await consumeSSE(resp, (ev) => {
            if (ev.type === "progress") {
                appendProgressRow(progressBox, ev);
            } else if (ev.type === "thinking") {
                if (!thinkingStarted) { thinkingStarted = true; thinkingBundle.wrap.style.display = ""; }
                thinkBuf += ev.content;
                thinkingBundle.content.textContent = thinkBuf;
                const container = $("#chat-messages");
                container.scrollTop = container.scrollHeight;
            } else if (ev.type === "token") {
                if (!tokenStarted) {
                    tokenStarted = true;
                    finalizeChatProgress(progressBox);
                    if (thinkingStarted) {
                        thinkingBundle.content.style.display = "none";
                        thinkingBundle.toggle.textContent = "▶ 展开";
                    }
                    assistantBubble.style.display = "";
                }
                buf += ev.content;
                assistantBubble.innerHTML = renderMarkdown(buf);
                const container = $("#chat-messages");
                container.scrollTop = container.scrollHeight;
            } else if (ev.type === "citations") {
                // 处理知识引用事件
                chatState.currentDetails.citations = ev.citations || [];
                renderContextPanel();
            } else if (ev.type === "error") {
                finalizeChatProgress(progressBox, true);
                assistantBubble.style.display = "";
                assistantBubble.innerHTML = `<span style="color:var(--accent-red)">错误: ${escapeHtml(ev.message)}</span>`;
            }
        });

        if (!tokenStarted) assistantBubble.remove();
        if (!thinkingStarted) thinkingBundle.wrap.remove();
    } catch (e) {
        finalizeChatProgress(progressBox, true);
        assistantBubble.style.display = "";
        assistantBubble.innerHTML = `<span style="color:var(--accent-red)">网络错误: ${escapeHtml(e.message)}</span>`;
    } finally {
        $("#chat-send").disabled = false;
        input.focus();
    }
}

// ============================================================
// Knowledge Base
// ============================================================
let kbLoaded = false;
const KB_ADMIN_TOKEN_KEY = "multi_agent_kb_admin_token";

const uploadZone = $("#upload-zone");
const uploadInput = $("#upload-input");

uploadZone?.addEventListener("click", () => uploadInput.click());
uploadInput?.addEventListener("change", () => uploadInput.files[0] && uploadFile(uploadInput.files[0]));
uploadZone?.addEventListener("dragover", (e) => { e.preventDefault(); uploadZone.classList.add("dragover"); });
uploadZone?.addEventListener("dragleave", () => uploadZone.classList.remove("dragover"));
uploadZone?.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
});
$("#docs-refresh")?.addEventListener("click", () => { kbLoaded = false; loadDocs(); });

async function uploadFile(file) {
    const resultEl = $("#upload-result");
    resultEl.innerHTML = `<div style="color:var(--accent-blue)"><i class="fa-solid fa-spinner fa-spin"></i> 上传 ${escapeHtml(file.name)} ...</div>`;
    const formData = new FormData();
    formData.append("file", file);
    try {
        const r = await safeFetch(`${API}/documents/upload`, {
            method: "POST",
            headers: { "X-KB-Admin-Token": getKbAdminToken() },
            body: formData,
        });
        const data = await r.json().catch(() => null);
        if (!r.ok) {
            if (r.status === 401 || r.status === 403) sessionStorage.removeItem(KB_ADMIN_TOKEN_KEY);
            throw new Error(data?.detail || data?.message || `HTTP ${r.status}`);
        }
        if (data.code === "SUCCESS") {
            resultEl.innerHTML = `<div style="color:var(--accent-green)"><i class="fa-solid fa-check"></i> 已索引 ${data.data.chunks_indexed} 个 chunk (${data.data.bytes} bytes)</div>`;
            loadDocs();
        } else {
            resultEl.innerHTML = `<div style="color:var(--accent-red)"><i class="fa-solid fa-xmark"></i> ${escapeHtml(data?.message || "上传失败")}</div>`;
        }
    } catch (e) {
        resultEl.innerHTML = `<div style="color:var(--accent-red)"><i class="fa-solid fa-xmark"></i> ${escapeHtml(e.message)}</div>`;
    }
}

async function loadDocs() {
    kbLoaded = true;
    const listEl = $("#docs-list");
    listEl.innerHTML = '<div class="skeleton" style="height:40px;margin-bottom:8px"></div><div class="skeleton" style="height:40px;margin-bottom:8px"></div>';
    try {
        const r = await safeFetch(`${API}/documents`);
        const data = await r.json();
        const docs = data?.data?.documents || [];
        if (!docs.length) {
            listEl.innerHTML = '<div class="empty-state"><div class="empty-text">暂无文档</div></div>';
            return;
        }
        listEl.innerHTML = "";
        docs.forEach(d => {
            const div = document.createElement("div");
            div.className = "doc-item";
            div.innerHTML = `
                <div>
                    <div class="doc-name">${escapeHtml(d.source)}</div>
                    <div class="doc-chunks">${d.chunk_count} 个 chunk</div>
                </div>
                <button class="doc-delete" data-source="${escapeHtml(d.source)}"><i class="fa-solid fa-trash-can"></i> 删除</button>`;
            div.querySelector(".doc-delete").addEventListener("click", () => {
                if (confirm(`确认删除 ${d.source}?`)) deleteDoc(d.source);
            });
            listEl.appendChild(div);
        });
    } catch (e) {
        listEl.innerHTML = `<div style="color:var(--accent-red);font-size:13px">加载失败: ${e.message}</div>`;
    }
}

async function deleteDoc(source) {
    try {
        const r = await safeFetch(`${API}/documents/${encodeURIComponent(source)}`, {
            method: "DELETE",
            headers: { "X-KB-Admin-Token": getKbAdminToken() },
        });
        const data = await r.json().catch(() => null);
        if (!r.ok || data?.code !== "SUCCESS") {
            if (r.status === 401 || r.status === 403) sessionStorage.removeItem(KB_ADMIN_TOKEN_KEY);
            throw new Error(data?.detail || data?.message || `HTTP ${r.status}`);
        }
        loadDocs();
    } catch (e) {
        alert(`删除失败: ${e.message}`);
    }
}

function getKbAdminToken() {
    let token = sessionStorage.getItem(KB_ADMIN_TOKEN_KEY) || "";
    if (!token) {
        token = prompt("知识库管理员 Token") || "";
        token = token.trim();
        if (!token) throw new Error("未输入 Token");
        sessionStorage.setItem(KB_ADMIN_TOKEN_KEY, token);
    }
    return token;
}

// ============================================================
// Diagnosis History
// ============================================================
let historyLoaded = false;
let historyPage = 1;
let historySource = "";

$("#history-source-filter")?.addEventListener("change", (e) => {
    historySource = e.target.value;
    historyPage = 1;
    historyLoaded = false;
    loadHistory();
});

$("#history-refresh")?.addEventListener("click", () => {
    historyLoaded = false;
    loadHistory();
});

$("#history-clear")?.addEventListener("click", async () => {
    if (!confirm("确认清空所有诊断历史? 此操作不可恢复。")) return;
    try {
        await safeFetch(`${API}/history`, { method: "DELETE" });
        historyLoaded = false;
        loadHistory();
    } catch (e) {
        alert(`清空失败: ${e.message}`);
    }
});

async function loadHistory() {
    historyLoaded = true;
    const listEl = $("#history-list");
    const paginationEl = $("#history-pagination");
    listEl.innerHTML = '<div class="skeleton" style="height:64px;margin-bottom:12px;border-radius:12px"></div><div class="skeleton" style="height:64px;margin-bottom:12px;border-radius:12px"></div>';
    paginationEl.style.display = "none";

    try {
        const params = new URLSearchParams({ page: historyPage, page_size: 20 });
        if (historySource) params.set("source", historySource);
        const r = await safeFetch(`${API}/history?${params}`);
        const resp = await r.json();
        if (resp?.code !== "SUCCESS") throw new Error(resp?.message || "加载失败");
        const data = resp.data || {};
        const items = data.records || [];
        const total = data.total || 0;
        const totalPages = Math.ceil(total / 20);

        if (!items.length) {
            listEl.innerHTML = '<div style="text-align:center;padding:60px 20px;color:#9ca3af"><div style="font-size:15px;color:#6b7280;font-weight:500">暂无历史记录</div></div>';
            return;
        }

        listEl.innerHTML = "";
        items.forEach(rec => {
            const card = document.createElement("div");
            card.className = "history-card";
            const sourceLabel = rec.source === "aiops" ? "智能诊断" : "AI Copilot";
            const sourceTag = `<span class="history-source-tag ${rec.source || 'chat'}">${sourceLabel}</span>`;
            const skillTag = rec.skill ? `<span class="history-skill"><i class="fa-solid fa-layer-group"></i> ${escapeHtml(rec.skill)}</span>` : "";
            const answerPreview = (rec.answer || "").slice(0, 100);

            const kbUploaded = rec.knowledge_base_uploaded;
            const kbTag = kbUploaded
                ? `<span class="history-skill" style="color:var(--accent-green)"><i class="fa-solid fa-circle-check"></i> 已入知识库</span>`
                : `<span class="history-skill" style="color:var(--accent-orange)"><i class="fa-solid fa-circle-plus"></i> 未入知识库</span>`;

            card.innerHTML = `
                <div class="history-card-header">
                    ${sourceTag}
                    <div class="history-question">${escapeHtml(rec.question)}</div>
                    ${skillTag}
                    ${kbTag}
                    <div class="history-time">${timeAgo(rec.ts_iso || (rec.ts ? new Date(rec.ts * 1000).toISOString() : ""))}</div>
                    <i class="fa-solid fa-chevron-down history-expand-icon"></i>
                </div>
                <div class="history-card-body">
                    <div class="history-detail-section">
                        <div class="history-detail-label">问题</div>
                        <div style="font-size:13px;color:var(--text-primary);line-height:1.6">${escapeHtml(rec.question)}</div>
                    </div>
                    <div class="history-detail-section">
                        <div class="history-detail-label">回答</div>
                        <div class="history-answer-box prose-dark">${renderMarkdown(rec.answer || "(无回答)")}</div>
                    </div>
                    ${rec.sources && rec.sources.length ? `
                    <div class="history-detail-section">
                        <div class="history-detail-label">来源</div>
                        <div class="history-sources-list">
                            ${rec.sources.map(s => `<span class="history-source-chip">${escapeHtml(s)}</span>`).join("")}
                        </div>
                    </div>` : ""}
                    <div style="display:flex;justify-content:flex-end;gap:6px;margin-top:8px">
                        ${!kbUploaded && rec.answer ? `<button class="btn" style="font-size:11px;padding:3px 8px;background:rgba(63,185,80,0.1);color:var(--accent-green);border:1px solid rgba(63,185,80,0.3)" data-upload-kb="${rec.id}"><i class="fa-solid fa-cloud-arrow-up"></i> 上传知识库</button>` : ""}
                        <button class="btn btn-danger" style="font-size:11px;padding:3px 8px" data-delete-history="${rec.id}">
                            <i class="fa-solid fa-trash-can"></i> 删除
                        </button>
                    </div>
                </div>`;

            card.querySelector(".history-card-header").addEventListener("click", () => {
                card.classList.toggle("expanded");
            });
            card.querySelector("[data-delete-history]")?.addEventListener("click", async (e) => {
                e.stopPropagation();
                if (!confirm("确认删除这条记录?")) return;
                try {
                    const dr = await safeFetch(`${API}/history/${rec.id}`, { method: "DELETE" });
                    const dd = await dr.json();
                    if (dd?.code === "SUCCESS") {
                        card.remove();
                        if (!listEl.children.length) {
                            historyLoaded = false;
                            loadHistory();
                        }
                    }
                } catch (err) {
                    alert(`删除失败: ${err.message}`);
                }
            });
            card.querySelector("[data-upload-kb]")?.addEventListener("click", async (e) => {
                e.stopPropagation();
                if (!confirm("确认将此诊断报告上传到知识库？上传后可通过 RAG 检索到。")) return;
                const btn = e.currentTarget;
                btn.disabled = true;
                btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 上传中...';
                try {
                    const r = await safeFetch(`${API}/history/${rec.id}/upload-kb`, { method: "POST" });
                    const d = await r.json();
                    if (d?.code === "SUCCESS") {
                        btn.innerHTML = '<i class="fa-solid fa-circle-check"></i> 已上传';
                        btn.style.color = "var(--accent-green)";
                        btn.style.background = "rgba(63,185,80,0.15)";
                        btn.style.borderColor = "rgba(63,185,80,0.5)";
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> 上传知识库';
                        alert(`上传失败: ${d?.message || "未知错误"}`);
                    }
                } catch (err) {
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> 上传知识库';
                    alert(`上传失败: ${err.message}`);
                }
            });
            listEl.appendChild(card);
        });

        // Pagination
        if (totalPages > 1) {
            paginationEl.style.display = "flex";
            let html = `<button class="page-btn" ${historyPage <= 1 ? 'disabled' : ''} data-page="${historyPage - 1}"><i class="fa-solid fa-chevron-left"></i></button>`;
            html += `<span class="page-info">第 ${historyPage} / ${totalPages} 页 (共 ${total} 条)</span>`;
            html += `<button class="page-btn" ${historyPage >= totalPages ? 'disabled' : ''} data-page="${historyPage + 1}"><i class="fa-solid fa-chevron-right"></i></button>`;
            paginationEl.innerHTML = html;
            paginationEl.querySelectorAll(".page-btn").forEach(btn => {
                btn.addEventListener("click", () => {
                    const p = parseInt(btn.dataset.page);
                    if (p >= 1 && p <= totalPages) {
                        historyPage = p;
                        historyLoaded = false;
                        loadHistory();
                    }
                });
            });
        }
    } catch (e) {
        listEl.innerHTML = `<div style="text-align:center;padding:40px;color:#ef4444;font-size:14px">加载失败: ${escapeHtml(e.message)}</div>`;
    }
}

// ============================================================
// Alert Center (New SQLite-based)
// ============================================================
let alertsLoaded = false;
let alertsSeverity = "";
let alertsStatus = "";

$("#alerts-severity-filter")?.addEventListener("change", (e) => {
    alertsSeverity = e.target.value;
    alertsLoaded = false;
    loadAlerts();
});

$("#alerts-status-filter")?.addEventListener("change", (e) => {
    alertsStatus = e.target.value;
    alertsLoaded = false;
    loadAlerts();
});

$("#alerts-refresh")?.addEventListener("click", () => {
    alertsLoaded = false;
    loadAlerts();
});

async function loadAlerts() {
    alertsLoaded = true;
    const listEl = $("#alerts-list");
    listEl.innerHTML = '<div class="skeleton" style="height:60px;margin-bottom:10px"></div><div class="skeleton" style="height:60px;margin-bottom:10px"></div>';

    try {
        // Load stats
        const statsResp = await safeFetch(`${API}/alerts/stats`);
        const statsData = await statsResp.json();
        if (statsData?.code === "SUCCESS") {
            const stats = statsData.data || {};
            setText("stat-total", stats.total || 0);
            setText("stat-critical", stats.by_severity?.critical || 0);
            setText("stat-warning", stats.by_severity?.warning || 0);
            setText("stat-info", stats.by_severity?.info || 0);
        }

        // Load alerts with filters
        const params = new URLSearchParams({ page: 1, page_size: 50 });
        if (alertsSeverity) params.set("severity", alertsSeverity);
        if (alertsStatus) params.set("status", alertsStatus);

        const r = await safeFetch(`${API}/alerts?${params}`);
        const data = await r.json();
        if (data?.code !== "SUCCESS") throw new Error(data?.message || "加载失败");

        const items = data.data?.alerts || [];
        const total = data.data?.total || 0;

        if (!items.length) {
            listEl.innerHTML = '<div class="empty-state"><div class="empty-text">暂无告警</div></div>';
            return;
        }

        listEl.innerHTML = "";
        items.forEach(a => {
            const card = document.createElement("div");
            card.className = "alert-card";
            const severity = a.severity || "info";
            const status = a.status || "firing";

            const statusBadge = `<span class="alert-status-badge ${status}">${status}</span>`;
            const severityDot = `<div class="severity-dot ${severity}"></div>`;

            card.innerHTML = `
                <div class="alert-card-header">
                    ${severityDot}
                    <div class="alert-name">${escapeHtml(a.alertname || "Unknown")}</div>
                    ${statusBadge}
                    <div class="alert-time">${timeAgo(a.ts_iso)}</div>
                    <i class="fa-solid fa-chevron-down alert-expand-icon"></i>
                </div>
                <div class="alert-card-body">
                    <div class="alert-detail-grid">
                        <div class="alert-detail-item">
                            <span class="detail-label">级别</span>
                            <span class="detail-value">${escapeHtml(severity)}</span>
                        </div>
                        <div class="alert-detail-item">
                            <span class="detail-label">服务</span>
                            <span class="detail-value">${escapeHtml(a.service || "-")}</span>
                        </div>
                        <div class="alert-detail-item">
                            <span class="detail-label">实例</span>
                            <span class="detail-value">${escapeHtml(a.instance || "-")}</span>
                        </div>
                        <div class="alert-detail-item">
                            <span class="detail-label">来源</span>
                            <span class="detail-value">${escapeHtml(a.source || "-")}</span>
                        </div>
                    </div>
                    ${a.summary ? `<div class="alert-summary">${escapeHtml(a.summary)}</div>` : ""}
                    ${a.description ? `<div class="alert-description">${escapeHtml(a.description)}</div>` : ""}
                    <div class="alert-actions">
                        ${status === "firing" ? `<button class="btn btn-sm" data-ack="${a.id}"><i class="fa-solid fa-check"></i> 确认</button>` : ""}
                        ${status !== "resolved" ? `<button class="btn btn-sm btn-success" data-resolve="${a.id}"><i class="fa-solid fa-circle-check"></i> 解决</button>` : ""}
                        <button class="btn btn-sm btn-primary" data-diagnose="${a.id}"><i class="fa-solid fa-stethoscope"></i> 诊断</button>
                    </div>
                </div>`;

            card.querySelector(".alert-card-header").addEventListener("click", () => {
                card.classList.toggle("expanded");
            });

            // Action handlers
            card.querySelector("[data-ack]")?.addEventListener("click", async (e) => {
                e.stopPropagation();
                const id = e.currentTarget.dataset.ack;
                try {
                    await safeFetch(`${API}/alerts/${id}/acknowledge`, { method: "POST" });
                    alertsLoaded = false;
                    loadAlerts();
                } catch (err) {
                    alert(`操作失败: ${err.message}`);
                }
            });

            card.querySelector("[data-resolve]")?.addEventListener("click", async (e) => {
                e.stopPropagation();
                const id = e.currentTarget.dataset.resolve;
                try {
                    await safeFetch(`${API}/alerts/${id}/resolve`, { method: "POST" });
                    alertsLoaded = false;
                    loadAlerts();
                } catch (err) {
                    alert(`操作失败: ${err.message}`);
                }
            });

            card.querySelector("[data-diagnose]")?.addEventListener("click", (e) => {
                e.stopPropagation();
                const query = a.summary || a.alertname || "";
                router.navigate("aiops");
                setTimeout(() => {
                    const input = $("#aiops-query");
                    if (input) input.value = query;
                }, 100);
            });

            listEl.appendChild(card);
        });
    } catch (e) {
        listEl.innerHTML = `<div style="color:var(--accent-red);font-size:13px">加载失败: ${e.message}</div>`;
    }
}

$("#alerts-clear")?.addEventListener("click", async () => {
    if (!confirm("确认清空所有告警?")) return;
    try {
        await safeFetch(`${API}/alerts`, { method: "DELETE" });
        alertsLoaded = false;
        loadAlerts();
    } catch (e) {
        alert(`清空失败: ${e.message}`);
    }
});

// ============================================================
// Observability
// ============================================================
let obsLoaded = false;

async function loadObservability() {
    obsLoaded = true;

    try {
        // Load stats
        const statsResp = await safeFetch(`${API}/observability/stats`);
        const statsData = await statsResp.json();
        if (statsData?.code === "SUCCESS") {
            const stats = statsData.data || {};
            setText("obs-total-runs", stats.total_runs || 0);
            setText("obs-success-rate", `${stats.success_rate || 0}%`);
            setText("obs-avg-tokens", formatNumber(stats.avg_total_tokens || 0));
            setText("obs-avg-ms", formatDuration(stats.avg_ms || 0));

            // Render skill distribution
            renderSkillChart(stats.by_skill || {});

            // Render daily trend
            renderTrendChart(stats.daily_trend || []);
        }

        // Load runs
        const runsResp = await safeFetch(`${API}/observability/runs?page=1&page_size=20`);
        const runsData = await runsResp.json();
        if (runsData?.code === "SUCCESS") {
            renderRunsList(runsData.data?.runs || []);
        }
    } catch (e) {
        console.error("[observability] 加载失败:", e);
    }
}

function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (num >= 1000) return (num / 1000).toFixed(1) + "K";
    return String(num);
}

function formatDuration(ms) {
    if (ms >= 60000) return (ms / 60000).toFixed(1) + "m";
    if (ms >= 1000) return (ms / 1000).toFixed(1) + "s";
    return ms + "ms";
}

function renderSkillChart(bySkill) {
    const container = $("#obs-skill-chart");
    if (!container) return;

    const entries = Object.entries(bySkill).sort((a, b) => b[1] - a[1]);
    if (!entries.length) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:20px">暂无数据</div>';
        return;
    }

    const max = entries[0][1];
    const colors = ["var(--accent-blue)", "var(--accent-green)", "var(--accent-orange)", "var(--accent-purple)", "var(--accent-cyan)", "var(--accent-red)"];

    container.innerHTML = entries.slice(0, 6).map(([skill, count], i) => {
        const pct = max > 0 ? (count / max * 100) : 0;
        return `
            <div class="skill-bar-row">
                <div class="skill-bar-label">${escapeHtml(skill)}</div>
                <div class="skill-bar-track">
                    <div class="skill-bar-fill" style="width:${pct}%;background:${colors[i % colors.length]}"></div>
                </div>
                <div class="skill-bar-count">${count}</div>
            </div>`;
    }).join("");
}

function renderTrendChart(trend) {
    const container = $("#obs-trend-chart");
    if (!container) return;

    if (!trend.length) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:12px;text-align:center;padding:20px">暂无数据</div>';
        return;
    }

    const max = Math.max(...trend.map(d => d.count), 1);

    container.innerHTML = `
        <div class="trend-chart">
            ${trend.map(d => {
                const pct = (d.count / max * 100);
                return `
                    <div class="trend-bar-col">
                        <div class="trend-bar-wrapper">
                            <div class="trend-bar" style="height:${pct}%"></div>
                        </div>
                        <div class="trend-label">${d.date.slice(5)}</div>
                        <div class="trend-count">${d.count}</div>
                    </div>`;
            }).join("")}
        </div>`;
}

function renderRunsList(runs) {
    const container = $("#obs-runs-list");
    if (!container) return;

    if (!runs.length) {
        container.innerHTML = '<div class="empty-state"><div class="empty-icon"><i class="fa-solid fa-chart-line"></i></div><div class="empty-text">暂无运行记录</div></div>';
        return;
    }

    container.innerHTML = runs.map(run => {
        const statusClass = run.status === "completed" ? "success" : run.status === "failed" ? "error" : "pending";
        return `
            <div class="obs-run-item">
                <div class="run-status-dot ${statusClass}"></div>
                <div class="run-info">
                    <div class="run-query">${escapeHtml(run.query || "").slice(0, 60)}</div>
                    <div class="run-meta">
                        ${run.skill ? `<span class="run-skill">${escapeHtml(run.skill)}</span>` : ""}
                        <span class="run-tokens"><i class="fa-solid fa-coins"></i> ${formatNumber(run.total_tokens || 0)}</span>
                        <span class="run-duration"><i class="fa-solid fa-clock"></i> ${formatDuration(run.total_ms || 0)}</span>
                        <span class="run-steps"><i class="fa-solid fa-shoe-prints"></i> ${run.total_steps || 0} steps</span>
                    </div>
                </div>
                <div class="run-time">${timeAgo(run.ts_iso)}</div>
            </div>`;
    }).join("");
}

$("#obs-refresh")?.addEventListener("click", () => {
    obsLoaded = false;
    loadObservability();
});

// ============================================================
// Weather API
// ============================================================
const weatherIcons = {
    "晴": "fa-sun", "多云": "fa-cloud-sun", "阴": "fa-cloud",
    "小雨": "fa-cloud-rain", "中雨": "fa-cloud-showers-heavy", "大雨": "fa-cloud-showers-heavy",
    "暴雨": "fa-poo-storm", "雷阵雨": "fa-bolt", "雪": "fa-snowflake", "雾": "fa-smog",
};

function getWeatherIcon(condition) {
    return weatherIcons[condition] || "fa-cloud";
}

async function fetchWeather(location) {
    try {
        const r = await safeFetch(`${API}/weather?location=${encodeURIComponent(location)}`);
        const data = await r.json();
        if (data?.code === "SUCCESS") return data.data;
    } catch (e) {
        console.warn("[weather] fetch failed:", e);
    }
    return null;
}

function updateDashboardWeather(data) {
    if (!data) return;
    const c = data.current;
    const icon = getWeatherIcon(c.condition);

    // Update status bar weather
    const statusWeather = $("#current-weather");
    if (statusWeather) statusWeather.textContent = `${c.location} ${c.temperature}℃ ${c.condition}`;

    // Update dashboard weather card
    const card = $(".weather-card");
    if (!card) return;
    const weatherIcon = card.querySelector(".weather-icon i");
    const weatherTemp = card.querySelector(".weather-temp");
    const weatherLocation = card.querySelector(".weather-location");
    const details = card.querySelectorAll(".weather-details div");
    const advice = card.querySelector(".weather-advice span");

    if (weatherIcon) weatherIcon.className = `fa-solid ${icon}`;
    if (weatherTemp) weatherTemp.textContent = `${c.temperature}℃`;
    if (weatherLocation) weatherLocation.textContent = c.location;
    if (details[0]) details[0].innerHTML = `<i class="fa-solid fa-droplet"></i> 湿度 ${c.humidity}%`;
    if (details[1]) details[1].innerHTML = `<i class="fa-solid fa-wind"></i> 风速 ${c.wind_level}级`;
    if (details[2]) details[2].innerHTML = `<i class="fa-solid fa-cloud-rain"></i> 降雨 ${c.rain_probability}%`;
    if (advice) advice.textContent = data.agriculture_advice.split("；")[0] || "";
}

function updateWeatherPage(data) {
    if (!data) return;
    const c = data.current;
    const icon = getWeatherIcon(c.condition);

    // Update weather detail card
    const locationSpan = $(".weather-location span");
    if (locationSpan) locationSpan.textContent = c.location;
    const tempLarge = $(".weather-temp-large");
    if (tempLarge) tempLarge.textContent = `${c.temperature}℃`;
    const desc = $(".weather-desc");
    if (desc) desc.textContent = c.condition;
    const iconLarge = $(".weather-icon-large i");
    if (iconLarge) iconLarge.className = `fa-solid ${icon}`;

    // Update metrics
    const metrics = $(".weather-metrics");
    if (metrics) {
        const metricValues = metrics.querySelectorAll(".metric-value");
        if (metricValues[0]) metricValues[0].textContent = `${c.humidity}%`;
        if (metricValues[1]) metricValues[1].textContent = `${c.wind_level}级`;
        if (metricValues[2]) metricValues[2].textContent = `${c.rain_probability}%`;
    }

    // Update advice
    const adviceSection = $(".weather-advice-section .advice-content");
    if (adviceSection && data.agriculture_advice) {
        const adviceList = data.agriculture_advice.split("；");
        adviceSection.innerHTML = adviceList.map(a => {
            const isWarning = a.includes("不建议") || a.includes("注意") || a.includes("避免");
            const cls = isWarning ? "advice-item-warning" : "advice-item-good";
            const iconCls = isWarning ? "fa-exclamation-triangle" : "fa-check-circle";
            return `<div class="${cls}"><i class="fa-solid ${iconCls}"></i><span>${escapeHtml(a)}</span></div>`;
        }).join("");
    }

    // Update forecast
    if (data.forecast) {
        const forecastList = $(".forecast-list");
        if (forecastList) {
            forecastList.innerHTML = data.forecast.map(d => {
                const fIcon = getWeatherIcon(d.condition);
                return `<div class="forecast-item">
                    <div class="forecast-date">${escapeHtml(d.date)}</div>
                    <div class="forecast-icon"><i class="fa-solid ${fIcon}"></i></div>
                    <div class="forecast-temp">${d.temp_low}~${d.temp_high}℃</div>
                    <div class="forecast-rain">${d.rain_probability}%</div>
                </div>`;
            }).join("");
        }
    }

    // Update last update time
    const updateTime = $(".weather-update span");
    if (updateTime) updateTime.textContent = data.source || "";
}

async function loadWeatherPage() {
    const location = "北京";
    const data = await fetchWeather(location);
    if (data) updateWeatherPage(data);
}

// ============================================================
// Init
// ============================================================
function init() {
    sidebar.init();
    searchModal.init();

    // Hash-based routing
    const hash = window.location.hash.slice(1) || "dashboard";
    router.navigate(hash);
    window.addEventListener("hashchange", () => {
        const h = window.location.hash.slice(1) || "dashboard";
        if (h !== router.current) router.navigate(h);
    });

    // Load global data
    checkHealth();
    setInterval(checkHealth, 15000);
    loadSkills();
}

init();
