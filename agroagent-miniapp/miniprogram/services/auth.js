// 登录服务：wx.login -> 后端 wx-login -> 缓存 token/userInfo
const { request } = require('./request');
const storage = require('../utils/storage');

let loggingIn = null; // 防止并发重复登录

function login() {
  if (loggingIn) return loggingIn;
  loggingIn = new Promise((resolve, reject) => {
    wx.login({
      success(res) {
        if (!res.code) {
          reject(new Error('wx.login 未返回 code'));
          return;
        }
        request({
          url: '/auth/wx-login',
          method: 'POST',
          data: { code: res.code },
          auth: false, // 登录接口本身不需要带 token
          showError: true,
        })
          .then((data) => {
            storage.set('token', data.access_token);
            storage.set('userInfo', data.user);
            getApp().globalData.token = data.access_token;
            getApp().globalData.userInfo = data.user;
            resolve(data.access_token);
          })
          .catch((err) => reject(err));
      },
      fail(err) {
        reject(err);
      },
    });
  });
  // 无论成败都清空进行中的标志
  loggingIn.finally(() => { loggingIn = null; });
  return loggingIn;
}

function logout() {
  storage.remove('token');
  storage.remove('userInfo');
  getApp().globalData.token = '';
  getApp().globalData.userInfo = null;
}

module.exports = { login, logout };
