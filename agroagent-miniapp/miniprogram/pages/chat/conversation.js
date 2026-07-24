const app = getApp();
const { stream } = require('../../services/sse');

Page({
  data: {
    statusBarHeight: 20,
    messages: [],     // { role, content, thinking, sources, progress }
    inputText: '',
    sessionId: '',
    loading: false,
    scrollTop: 0,
  },

  onLoad(query) {
    const sys = wx.getWindowInfo();
    this.setData({
      statusBarHeight: sys.statusBarHeight || 20,
      sessionId: `mp_${Date.now()}_${Math.floor(Math.random() * 1e6)}`,
    });
    // 页面参数需手动解码（home.js 用了 encodeURIComponent，小程序不自动解码）
    let q = query.q || '';
    if (q) {
      try { q = decodeURIComponent(q); } catch (e) {}
      this.setData({ inputText: q });
      this.send(q);
    }
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  onSend() {
    const text = this.data.inputText.trim();
    if (!text || this.data.loading) return;
    this.send(text);
  },

  send(question) {
    if (this.data.loading) return;
    const messages = this.data.messages.concat([
      { role: 'user', content: question, thinking: false, sources: [], progress: '' },
      { role: 'ai', content: '', thinking: true, sources: [], progress: '正在准备…' },
    ]);
    this.setData({ messages, inputText: '', loading: true });

    app.ensureLogin()
      .then(() => {
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
              // 显示进度到「思考中」下方
              const label = evt.label || evt.stage || '处理中';
              ai.progress = label;
              this.setData({ messages: msgs });
            } else if (evt.type === 'token') {
              // 收到第一个 token 就结束「思考中」
              ai.thinking = false;
              ai.progress = '';
              ai.content += (evt.content || '');
              this.setData({ messages: msgs });
              this.scrollToBottom();
            } else if (evt.type === 'citations') {
              // 后端事件名是 citations，映射到 sources
              ai.sources = evt.citations || [];
              this.setData({ messages: msgs });
            } else if (evt.type === 'sources') {
              // 兼容旧字段
              ai.sources = evt.sources || [];
              this.setData({ messages: msgs });
            } else if (evt.type === 'error') {
              ai.thinking = false;
              ai.progress = '';
              ai.content = evt.message || '（服务端返回错误）';
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
          },
          onError: (err) => {
            console.error('[sse] onError', err);
            const msgs = this.data.messages;
            const ai = msgs[aiIndex];
            if (ai) {
              ai.thinking = false;
              ai.progress = '';
              ai.content = '（对话连接失败，请稍后重试）';
            }
            this.setData({ messages: msgs, loading: false });
          },
        });
      })
      .catch((err) => {
        const msgs = this.data.messages;
        msgs[msgs.length - 1].thinking = false;
        this.setData({ messages: msgs, loading: false });
        console.error('[login] 对话前登录失败:', err);
        const msg = (err && (err.message || err.errmsg)) || '登录失败';
        wx.showToast({ title: msg, icon: 'none', duration: 4000 });
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
