const app = getApp();
const api = require('../../services/api');
const storage = require('../../utils/storage');
const { logout } = require('../../services/auth');

Page({
  data: {
    user: { name: '未登录', role: '农场主', initial: '?', bound: false, bound_username: '' },
    groups: [
      [
        { id: 'info', title: '个人信息', icon: '👤', color: '#f0fdf4', extra: '' },
        { id: 'farm', title: '我的农场', icon: '🗺️', color: '#eff6ff', extra: '2个农场' },
        { id: 'notify', title: '通知设置', icon: '🔔', color: '#fffbeb', extra: '' },
      ],
      [
        { id: 'faq', title: '常见问题', icon: '❓', color: '#f0fdf4', extra: '' },
        { id: 'feedback', title: '意见反馈', icon: '💬', color: '#eff6ff', extra: '' },
        { id: 'about', title: '关于我们', icon: 'ℹ️', color: '#f5f3ff', extra: '' },
      ],
    ],
    // 绑定弹窗
    bindDialog: false,
    bindCode: '',
    bindLoading: false,
    bindError: '',
  },

  onShow() {
    this.applyLocalUser();
    this.loadUserInfo();
  },

  applyLocalUser() {
    const info = wx.getStorageSync('userInfo');
    if (info && info.username) {
      this.setData({ user: this._buildUser(info) });
    }
  },

  loadUserInfo() {
    api.getUserInfo()
      .then((u) => {
        // 顺便更新本地缓存和 globalData
        storage.set('userInfo', u);
        if (app && app.globalData) app.globalData.userInfo = u;
        this.setData({ user: this._buildUser(u) });
      })
      .catch(() => {});
  },

  // 把后端 UserInfo 映射为页面 user
  _buildUser(u) {
    const bound = !!u.wx_openid && !u.username.startsWith('wx_');
    // 显示名：绑定后用真实 username；未绑定就是 wx_xxx，截短
    const displayName = bound
      ? u.username
      : (u.nickname || (u.username || '').slice(0, 12) + '...');
    const initial = (displayName || '农').replace('wx_', '').slice(0, 1).toUpperCase();
    return {
      name: displayName,
      role: u.role === 'admin' ? '管理员' : '农场主',
      initial,
      bound,
      bound_username: bound ? u.username : '',
    };
  },

  onItem(e) {
    const id = e.currentTarget.dataset.id;
    if (id === 'about') {
      wx.showModal({ title: '关于 AgroAgentOS', content: '智农协同平台 v1.0.0' });
    } else {
      wx.showToast({ title: '敬请期待', icon: 'none' });
    }
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      success: (r) => {
        if (r.confirm) {
          logout();
          app.ensureLogin().then(() => this.loadUserInfo());
        }
      },
    });
  },

  // ==================== 绑定 Web 账号 ====================

  onOpenBind() {
    this.setData({ bindDialog: true, bindCode: '', bindError: '' });
  },

  onCloseBind() {
    if (this.data.bindLoading) return;
    this.setData({ bindDialog: false });
  },

  onBindCodeInput(e) {
    // 只保留数字
    const raw = (e.detail.value || '').replace(/\D/g, '').slice(0, 6);
    this.setData({ bindCode: raw, bindError: '' });
  },

  onConfirmBind() {
    const code = this.data.bindCode.trim();
    if (code.length !== 6) {
      this.setData({ bindError: '请输入 6 位绑定码' });
      return;
    }
    this.setData({ bindLoading: true, bindError: '' });

    api.wxBindConfirm(code)
      .then((data) => {
        // 后端返回新的 JWT（挂到 Web 账号上）+ 新用户信息
        if (data && data.access_token) {
          storage.set('token', data.access_token);
          storage.set('userInfo', data.user);
          if (app && app.globalData) {
            app.globalData.token = data.access_token;
            app.globalData.userInfo = data.user;
          }
        }
        this.setData({
          bindDialog: false,
          bindLoading: false,
          bindCode: '',
          user: this._buildUser(data.user),
        });
        wx.showToast({ title: '绑定成功', icon: 'success', duration: 2000 });
      })
      .catch((err) => {
        console.error('[bind] 绑定失败:', err);
        const msg = (err && (err.message || err.errmsg)) || '绑定失败';
        this.setData({ bindLoading: false, bindError: msg });
      });
  },
});
