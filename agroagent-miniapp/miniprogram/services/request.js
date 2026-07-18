// 封装 wx.request，统一注入 JWT、错误提示、401 处理
const config = require('../config');
const storage = require('../utils/storage');

/**
 * 发起请求
 * @param {Object} opt { url, method, data, auth=true, showError=true }
 * @returns Promise<data> （已剥离 ApiResponse 的 data 字段）
 */
function request(opt) {
  const { url, method = 'GET', data = {}, auth = true, showError = true } = opt;
  const header = { 'Content-Type': 'application/json' };
  if (auth) {
    const token = storage.get('token', '');
    if (token) header['Authorization'] = `Bearer ${token}`;
  }

  return new Promise((resolve, reject) => {
    wx.request({
      url: config.BASE_URL + config.API_PREFIX + url,
      method,
      data,
      header,
      success(res) {
        const body = res.data || {};
        if (res.statusCode === 401) {
          storage.remove('token');
          storage.remove('userInfo');
          const app = getApp();
          if (app && app.globalData) {
            app.globalData.token = '';
            app.globalData.userInfo = null;
          }
          if (showError) wx.showToast({ title: '登录已过期', icon: 'none' });
          // 跳回登录页
          wx.reLaunch({ url: '/pages/login/index' });
          reject(body);
          return;
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 'SUCCESS') {
          resolve(body.data);
        } else {
          if (showError) {
            wx.showToast({ title: body.message || '请求失败', icon: 'none' });
          }
          reject(body);
        }
      },
      fail(err) {
        if (showError) wx.showToast({ title: '网络异常', icon: 'none' });
        reject(err);
      },
    });
  });
}

module.exports = { request };
