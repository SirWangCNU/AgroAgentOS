// app.js 全局逻辑
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
    } else {
      // 未登录，跳转到登录页（延迟以保证首页已注册）
      setTimeout(() => {
        wx.reLaunch({ url: '/pages/login/index' });
      }, 0);
    }
  },

  // 统一登录态检查：返回 Promise<token>，未登录会 reject
  ensureLogin() {
    if (this.globalData.token) {
      return Promise.resolve(this.globalData.token);
    }
    wx.reLaunch({ url: '/pages/login/index' });
    return Promise.reject(new Error('未登录'));
  },
});
