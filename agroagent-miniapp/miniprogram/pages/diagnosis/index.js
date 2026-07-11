const app = getApp();
const api = require('../../services/api');

Page({
  data: {
    imagePath: '',
    analyzing: false,
    result: null, // { success, summary, detections:[{chinese_name, confidence}] }
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      success: (res) => {
        const path = res.tempFiles[0].tempFilePath;
        this.setData({ imagePath: path, result: null });
      },
    });
  },

  async onAnalyze() {
    if (!this.data.imagePath) {
      wx.showToast({ title: '请先选择图片', icon: 'none' });
      return;
    }
    this.setData({ analyzing: true });
    try {
      await app.ensureLogin();
      const data = await api.analyzeImage(this.data.imagePath);
      this.setData({ analyzing: false, result: data });
    } catch (e) {
      this.setData({ analyzing: false });
      this.setData({
        result: { success: false, summary: '识别失败，请稍后重试', detections: [] },
      });
    }
  },
});
