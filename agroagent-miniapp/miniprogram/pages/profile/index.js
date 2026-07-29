const app = getApp();
const api = require('../../services/api');
const storage = require('../../utils/storage');
const { logout } = require('../../utils/auth');

Page({
  data: {
    user: { name: '', role: '', initial: '?' },
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
  },

  onShow() {
    this.applyLocalUser();
    this.loadUserInfo();
  },

  applyLocalUser() {
    const info = wx.getStorageSync('userInfo');
    if (info && info.username) this.setData({ user: this._buildUser(info) });
  },

  loadUserInfo() {
    api.getUserInfo()
      .then((user) => {
        storage.set('userInfo', user);
        if (app && app.globalData) app.globalData.userInfo = user;
        this.setData({ user: this._buildUser(user) });
      })
      .catch(() => {});
  },

  _buildUser(user) {
    const name = user.nickname || (user.username || '').replace('wx_', '').slice(0, 12);
    return {
      name,
      role: user.role === 'admin' ? '管理员' : '农场主',
      initial: (name || '农').slice(0, 1).toUpperCase(),
    };
  },

  onItem(event) {
    if (event.currentTarget.dataset.id === 'about') {
      wx.showModal({ title: '关于 AgroAgentOS', content: '智农协同平台 v1.0.0' });
      return;
    }
    wx.showToast({ title: '敬请期待', icon: 'none' });
  },

  onLogout() {
    wx.showModal({
      title: '退出登录',
      success: (result) => {
        if (result.confirm) {
          logout();
          app.ensureLogin().then(() => this.loadUserInfo());
        }
      },
    });
  },
});
