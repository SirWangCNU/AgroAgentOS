const app = getApp();
const api = require('../../services/api');
const config = require('../../config');

Page({
  data: {
    city: '',
    loading: true,
    current: null,
    advice: '正在获取农事建议...',
  },

  onLoad() {
    this.load();
  },

  async load() {
    this.setData({ loading: true });
    try {
      const data = await api.getWeather(config.DEFAULT_CITY);
      const cur = data && data.current;
      this.setData({
        city: (cur && cur.location) || config.DEFAULT_CITY,
        current: cur,
        advice: this.buildAdvice(cur),
        loading: false,
      });
    } catch (e) {
      this.setData({ loading: false, advice: '暂无天气数据' });
    }
  },

  buildAdvice(cur) {
    if (!cur) return '暂无天气数据';
    const t = cur.temperature;
    const cond = cur.condition || '';
    if (cond.includes('雨')) return '今日有降雨，建议推迟户外农事与浇水。';
    if (t > 30) return '气温偏高，注意作物补水与遮荫防暑。';
    if (t < 10) return '气温较低，注意防冻保温。';
    return '天气适宜，可进行常规田间管理。';
  },

  onRefresh() {
    this.load();
  },
});
