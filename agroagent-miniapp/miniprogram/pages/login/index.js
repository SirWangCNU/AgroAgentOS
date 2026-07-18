// 账号密码登录页
const { loginWithPassword } = require('../../services/auth');

Page({
  data: {
    username: '',
    password: '',
    loading: false,
    error: '',
  },

  onUsernameInput(e) {
    this.setData({ username: e.detail.value, error: '' });
  },

  onPasswordInput(e) {
    this.setData({ password: e.detail.value, error: '' });
  },

  onLogin() {
    const username = (this.data.username || '').trim();
    const password = this.data.password || '';
    if (!username) {
      this.setData({ error: '请输入用户名' });
      return;
    }
    if (!password) {
      this.setData({ error: '请输入密码' });
      return;
    }
    this.setData({ loading: true, error: '' });

    loginWithPassword(username, password)
      .then(() => {
        // 登录成功，跳到首页（tabBar 页必须用 switchTab）
        wx.switchTab({ url: '/pages/chat/home' });
      })
      .catch((err) => {
        console.error('[login] 登录失败:', err);
        const msg = (err && (err.message || err.errmsg)) || '登录失败';
        this.setData({ loading: false, error: msg });
      });
  },
});
