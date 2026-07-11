const app = getApp();

Page({
  data: {
    statusBarHeight: 20,
    quickActions: [
      { id: 'pest', title: '拍照识别', sub: '病虫害', color: '#fef2f2', icon: '🐛' },
      { id: 'plant', title: '农业种植', sub: '咨询', color: '#f0fdf4', icon: '🌿' },
      { id: 'weather', title: '天气与', sub: '农事建议', color: '#fffbeb', icon: '☀️' },
      { id: 'board', title: '农场数据', sub: '看板', color: '#eff6ff', icon: '📊' },
    ],
    suggests: ['今天适合浇水吗？', '番茄叶子发黄怎么办？', '最近小麦行情如何？'],
    inputText: '',
  },

  onLoad() {
    const sys = wx.getWindowInfo();
    this.setData({ statusBarHeight: sys.statusBarHeight || 20 });
    // 调试期：把登录失败原因打到 Console 并弹窗，便于定位
    app.ensureLogin().catch((err) => {
      console.error('[login] ensureLogin 失败:', err);
      const msg = (err && (err.message || err.errmsg)) || '登录失败';
      wx.showToast({ title: msg, icon: 'none', duration: 4000 });
    });
  },

  onInput(e) {
    this.setData({ inputText: e.detail.value });
  },

  // 点击快捷入口
  onQuick(e) {
    const id = e.currentTarget.dataset.id;
    if (id === 'pest') {
      wx.navigateTo({ url: '/pages/diagnosis/index' });
    } else if (id === 'weather') {
      wx.navigateTo({ url: '/pages/weather/index' });
    } else if (id === 'board') {
      wx.switchTab({ url: '/pages/workspace/index' });
    } else {
      // plant / 其他 -> 进入对话并预填问题
      this.goConversation('我想咨询农业种植问题');
    }
  },

  onSuggest(e) {
    const q = e.currentTarget.dataset.q;
    this.goConversation(q);
  },

  onSend() {
    const text = this.data.inputText.trim();
    if (!text) return;
    this.goConversation(text);
  },

  goConversation(question) {
    wx.navigateTo({ url: `/pages/chat/conversation?q=${encodeURIComponent(question)}` });
    this.setData({ inputText: '' });
  },
});
