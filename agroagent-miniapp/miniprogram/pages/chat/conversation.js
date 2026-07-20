const app = getApp();
const { stream } = require('../../services/sse');
const api = require('../../services/api');

// 本地存储 key: 持久化上次会话 ID, 避免每次进页面随机生成新 session 导致历史丢失
const STORAGE_KEY_SESSION_ID = 'last_chat_session_id';

Page({
  data: {
    statusBarHeight: 20,
    messages: [],     // { role, content, thinking, sources, progress, status, errorMessage }
    inputText: '',
    sessionId: '',
    loading: false,
    scrollTop: 0,
    // 分页状态
    hasMoreMessages: false,
    oldestLoadedId: null,
    isLoadingMore: false,
    // 初始化状态: 加载历史中 / 历史加载完成
    isInitializing: true,
  },

  /**
   * 进入对话页流程 (修复 BUG-1: 早期版本每次进页面随机生成 sessionId, 历史永不加载):
   *   1. 读取本地缓存的 sessionId (若有)
   *   2. 无缓存 → 调用后端 createSession 创建新会话并缓存
   *   3. 加载最新 10 条历史消息 (游标分页)
   *   4. 仅当无历史 + 携带 q 参数时才自动发送初始化提示词
   *      (修复用户提到的"浏览别人的应用意外触发对话"问题)
   */
  onLoad(query) {
    const sys = wx.getWindowInfo();
    this.setData({
      statusBarHeight: sys.statusBarHeight || 20,
      isInitializing: true,
    });

    // URL 参数 q (可能来自首页快捷入口的预设问题)
    let q = query.q || '';
    if (q) {
      try { q = decodeURIComponent(q); } catch (e) {}
    }

    this.initSession(q);
  },

  /**
   * 初始化会话: 加载或创建 sessionId, 然后加载历史消息
   */
  async initSession(initialQuestion) {
    try {
      await app.ensureLogin();
    } catch (err) {
      console.error('[login] 对话前登录失败:', err);
      this.setData({ isInitializing: false });
      const msg = (err && (err.message || err.errmsg)) || '登录失败';
      wx.showToast({ title: msg, icon: 'none', duration: 4000 });
      return;
    }

    // 1. 读取本地缓存的 sessionId
    let sessionId = wx.getStorageSync(STORAGE_KEY_SESSION_ID);
    if (!sessionId) {
      // 2. 无缓存 → 创建新会话
      try {
        const session = await api.createSession('新对话');
        sessionId = session.id;
        wx.setStorageSync(STORAGE_KEY_SESSION_ID, sessionId);
      } catch (err) {
        console.error('[chat] 创建会话失败:', err);
        this.setData({ isInitializing: false });
        wx.showToast({ title: '初始化会话失败', icon: 'none' });
        return;
      }
    }
    this.setData({ sessionId });

    // 3. 加载最新 10 条历史消息
    await this.loadHistory();

    // 4. 仅当无历史 + 携带初始化提示词时才自动发送
    //    有历史时仅填入输入框, 由用户主动点击发送 (避免意外触发对话)
    if (initialQuestion) {
      this.setData({ inputText: initialQuestion });
      if (this.data.messages.length === 0) {
        // 无历史 → 自动发送初始化提示词
        this.send(initialQuestion);
      }
    }
  },

  /**
   * 加载历史消息 (最新 limit 条). 首次进入时调用.
   * @param {Number} beforeId 游标, 向前加载更早消息时传入当前最旧 id
   */
  async loadHistory(beforeId) {
    try {
      const result = await api.listMessages(this.data.sessionId, {
        limit: 10,
        beforeId: beforeId || null,
      });
      const newMsgs = (result.messages || []).map((m) => ({
        role: m.role === 'assistant' ? 'ai' : m.role,
        content: m.content,
        thinking: false,
        sources: [],
        progress: '',
        status: m.status || 'success',
        errorMessage: m.error_message || '',
      }));

      if (beforeId) {
        // 向前加载: prepend 到列表头部
        this.setData({
          messages: [...newMsgs.reverse(), ...this.data.messages],
          hasMoreMessages: result.has_more,
          oldestLoadedId: result.oldest_id ?? this.data.oldestLoadedId,
          isLoadingMore: false,
        });
      } else {
        // 首次加载: 替换整个列表 (按时间正序)
        this.setData({
          messages: newMsgs.reverse(),
          hasMoreMessages: result.has_more,
          oldestLoadedId: result.oldest_id,
          isInitializing: false,
        });
        this.scrollToBottom();
      }
    } catch (err) {
      console.error('[chat] 加载历史消息失败:', err);
      if (!beforeId) {
        this.setData({ isInitializing: false });
      } else {
        this.setData({ isLoadingMore: false });
      }
      // 404 表示会话不存在或不属于该用户, 清除本地缓存让下次重新创建
      if (err && (err.status === 404 || (err.statusCode === 404))) {
        wx.removeStorageSync(STORAGE_KEY_SESSION_ID);
      }
    }
  },

  /**
   * 点击"加载更多"按钮: 向前加载更早 10 条历史
   */
  onLoadMore() {
    if (this.data.isLoadingMore || !this.data.hasMoreMessages || !this.data.oldestLoadedId) return;
    this.setData({ isLoadingMore: true });
    this.loadHistory(this.data.oldestLoadedId);
  },

  /**
   * 新建对话: 清除本地缓存, 重新创建会话
   */
  async onNewSession() {
    wx.showModal({
      title: '新建对话',
      content: '将清空当前对话并开始新的会话, 是否继续?',
      success: async (res) => {
        if (!res.confirm) return;
        wx.removeStorageSync(STORAGE_KEY_SESSION_ID);
        this.setData({
          messages: [],
          inputText: '',
          hasMoreMessages: false,
          oldestLoadedId: null,
          isInitializing: true,
        });
        try {
          await app.ensureLogin();
          const session = await api.createSession('新对话');
          wx.setStorageSync(STORAGE_KEY_SESSION_ID, session.id);
          this.setData({ sessionId: session.id, isInitializing: false });
        } catch (err) {
          console.error('[chat] 新建会话失败:', err);
          this.setData({ isInitializing: false });
          wx.showToast({ title: '新建会话失败', icon: 'none' });
        }
      },
    });
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  onSend() {
    const text = this.data.inputText.trim();
    if (!text || this.data.loading) return;
    this.send(text);
  },

  /**
   * 发送消息:
   *   - 本地立即追加 user + ai(占位) 消息
   *   - 前端 POST 持久化 user 消息 (与后端 SSE 兜底形成双保险, 后端 5s 幂等去重)
   *   - assistant 消息由后端 rag_service.stream_chat 收尾时主动持久化, 前端无需调用
   */
  send(question) {
    if (this.data.loading) return;
    if (!this.data.sessionId) {
      wx.showToast({ title: '会话初始化中, 请稍候', icon: 'none' });
      return;
    }
    const messages = this.data.messages.concat([
      { role: 'user', content: question, thinking: false, sources: [], progress: '', status: 'success', errorMessage: '' },
      { role: 'ai', content: '', thinking: true, sources: [], progress: '正在准备…', status: 'success', errorMessage: '' },
    ]);
    this.setData({ messages, inputText: '', loading: true });

    // 持久化 user 消息 (best-effort, 失败不阻塞 SSE)
    api.addSessionMessage(this.data.sessionId, 'user', question).catch((err) => {
      console.warn('[chat] 前端持久化 user 消息失败 (后端 SSE 会兜底):', err);
    });

    const aiIndex = messages.length - 1;
    stream({
      url: '/chat/stream',
      data: { session_id: this.data.sessionId, question, top_k: 3 },
      onEvent: (evt) => {
        console.log('[sse.evt]', evt.type, evt.stage || '');
        const msgs = this.data.messages;
        const ai = msgs[aiIndex];
        if (!ai) return;

        if (evt.type === 'progress') {
          ai.progress = evt.label || evt.stage || '处理中';
          this.setData({ messages: msgs });
        } else if (evt.type === 'token') {
          ai.thinking = false;
          ai.progress = '';
          ai.content += (evt.content || '');
          this.setData({ messages: msgs });
          this.scrollToBottom();
        } else if (evt.type === 'citations') {
          ai.sources = evt.citations || [];
          this.setData({ messages: msgs });
        } else if (evt.type === 'sources') {
          ai.sources = evt.sources || [];
          this.setData({ messages: msgs });
        } else if (evt.type === 'error') {
          ai.thinking = false;
          ai.progress = '';
          ai.content = evt.message || '（服务端返回错误）';
          ai.status = 'error';
          ai.errorMessage = evt.message || '';
          this.setData({ messages: msgs });
        }
      },
      onDone: () => {
        const msgs = this.data.messages;
        const ai = msgs[aiIndex];
        if (ai) {
          ai.thinking = false;
          ai.progress = '';
          if (!ai.content) ai.content = '（未收到回复内容）';
        }
        this.setData({ messages: msgs, loading: false });
        this.scrollToBottom();
        // assistant 消息已由后端 rag_service.stream_chat 主动持久化, 此处不再 POST
      },
      onError: (err) => {
        console.error('[sse] onError', err);
        const msgs = this.data.messages;
        const ai = msgs[aiIndex];
        if (ai) {
          ai.thinking = false;
          ai.progress = '';
          ai.content = '（对话连接失败, 错误消息已记录到历史）';
          ai.status = 'error';
          ai.errorMessage = (err && (err.message || err.errmsg)) || '连接失败';
        }
        this.setData({ messages: msgs, loading: false });
        // 后端 chat.py 的 SSE except 分支会持久化错误消息到 DB, 此处不再重复 POST
      },
    });
  },

  scrollToBottom() {
    wx.nextTick(() => {
      const q = wx.createSelectorQuery();
      q.select('.ca').boundingClientRect();
      q.select('.inner').boundingClientRect();
      q.exec((res) => {
        if (res[0] && res[1]) {
          const scrollTop = res[1].height - res[0].height;
          if (scrollTop > 0) this.setData({ scrollTop });
        }
      });
    });
  },

  onBack() {
    wx.navigateBack({ delta: 1 });
  },
});