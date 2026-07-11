const app = getApp();
const api = require('../../services/api');
const config = require('../../config');

Page({
  data: {
    crop: '水稻',
    crops: ['水稻', '小麦', '玉米', '番茄', '苹果'],
    loading: true,
    overview: null,
  },

  onLoad() {
    this.load();
  },

  onCrop(e) {
    this.setData({ crop: e.currentTarget.dataset.crop, loading: true }, () => this.load());
  },

  async load() {
    try {
      const data = await api.getMarketOverview(this.data.crop, config.DEFAULT_CITY);
      this.setData({ overview: data, loading: false });
    } catch (e) {
      this.setData({ loading: false, overview: null });
    }
  },
});
