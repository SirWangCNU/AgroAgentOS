const app = getApp();
const api = require('../../services/api');
const config = require('../../config');

Page({
  data: {
    stats: [
      { value: '12', label: '今日对话' },
      { value: '8', label: '处理问题' },
      { value: '156', label: '知识文档' },
    ],
    tools: [
      { id: 'weather', title: '天气查询', desc: '28°C 晴', badge: '', color: '#fffbeb', icon: '☀️', path: '/pages/weather/index' },
      { id: 'pest', title: '病虫害诊断', desc: '智能识别病害', badge: 'AI识别', color: '#fef2f2', icon: '🐛', path: '/pages/diagnosis/index' },
      { id: 'market', title: '市场行情', desc: '农产品价格', badge: '实时价格', color: '#eff6ff', icon: '📈', path: '/pages/market/index' },
      { id: 'copy', title: '营销文案', desc: '一键生成', badge: '', color: '#f5f3ff', icon: '✍️', path: '' },
    ],
    more: [
      { id: 'farm', title: '农场管理', color: '#f0fdf4', icon: '🗺️', path: '' },
      { id: 'kb', title: '知识库', color: '#eff6ff', icon: '📚', path: '' },
      { id: 'video', title: 'AI视频生成', desc: 'NEW', color: '#fef2f2', icon: '🎬', path: '' },
    ],
    recent: [
      { id: 'r1', title: '今日天气', big: '28°C', sub: '晴转多云 · 东南风3级', tip: '适合户外农事', tipColor: '#16a34a' },
      { id: 'r2', title: '诊断记录', big: '番茄早疫病', sub: '置信度 92% · 中等风险', tip: '需及时防治', tipColor: '#ef4444' },
    ],
  },

  onShow() {
    this.loadWeather();
  },

  loadWeather() {
    api.getWeather(config.DEFAULT_CITY)
      .then((d) => {
        const cur = d && d.current;
        if (!cur) return;
        const tools = this.data.tools.map((t) =>
          t.id === 'weather'
            ? { ...t, desc: `${cur.temperature}°C ${cur.condition || ''}` }
            : t
        );
        const recent = this.data.recent.map((r) =>
          r.id === 'r1'
            ? { ...r, big: `${cur.temperature}°C`, sub: `${cur.condition || ''} · 湿度${cur.humidity || '--'}%` }
            : r
        );
        this.setData({ tools, recent });
      })
      .catch(() => {});
  },

  onTool(e) {
    const path = e.currentTarget.dataset.path;
    if (path) wx.navigateTo({ url: path });
    else wx.showToast({ title: '敬请期待', icon: 'none' });
  },

  onMore(e) {
    const path = e.currentTarget.dataset.path;
    if (path) wx.navigateTo({ url: path });
    else wx.showToast({ title: '敬请期待', icon: 'none' });
  },
});
