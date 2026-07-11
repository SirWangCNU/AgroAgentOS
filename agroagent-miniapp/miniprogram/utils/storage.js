// 本地缓存封装
const storage = {
  set(key, value) {
    wx.setStorageSync(key, value);
  },
  get(key, def = '') {
    const v = wx.getStorageSync(key);
    return v === '' || v === undefined || v === null ? def : v;
  },
  remove(key) {
    wx.removeStorageSync(key);
  },
};

module.exports = storage;
