// 登录服务：账号密码登录 -> 后端 /auth/login -> 缓存 token/userInfo
const { request } = require('./request');
const storage = require('../utils/storage');

let loggingIn = null; // 防止并发重复登录

/**
 * 账号密码登录
 * @param {string} username
 * @param {string} password
 * @returns Promise<token>
 */
function loginWithPassword(username, password) {
  if (loggingIn) return loggingIn;
  loggingIn = request({
    url: '/auth/login',
    method: 'POST',
    data: { username, password },
    auth: false, // 登录接口本身不需要带 token
    showError: false, // 由调用方展示错误
  })
    .then((data) => {
      storage.set('token', data.access_token);
      storage.set('userInfo', data.user);
      const app = getApp();
      if (app && app.globalData) {
        app.globalData.token = data.access_token;
        app.globalData.userInfo = data.user;
      }
      return data.access_token;
    })
    .finally(() => { loggingIn = null; });
  return loggingIn;
}

function logout() {
  storage.remove('token');
  storage.remove('userInfo');
  const app = getApp();
  if (app && app.globalData) {
    app.globalData.token = '';
    app.globalData.userInfo = null;
  }
  // 退出后跳回登录页
  wx.reLaunch({ url: '/pages/login/index' });
}

module.exports = { loginWithPassword, logout };
