// app.js 全局逻辑
const { login } = require('./services/auth');

App({
  globalData: {
    userInfo: null,      // 登录后的用户资料
    token: '',           // JWT
    sessionId: '',       // 当前对话 session
  },

  onLaunch() {
    // 读取本地缓存的登录态
    const token = wx.getStorageSync('token');
    const userInfo = wx.getStorageSync('userInfo');
    if (token) {
      this.globalData.token = token;
      this.globalData.userInfo = userInfo || null;
    }
  },

  // 统一登录入口：返回 Promise<token>
  ensureLogin() {
    if (this.globalData.token) {
      return Promise.resolve(this.globalData.token);
    }
    return login().then((token) => {
      this.globalData.token = token;
      this.globalData.userInfo = wx.getStorageSync('userInfo');
      return token;
    });
  },
});
