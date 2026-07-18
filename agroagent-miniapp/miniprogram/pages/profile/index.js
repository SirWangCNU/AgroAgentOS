const app = getApp();
const api = require('../../services/api');
const storage = require('../../utils/storage');
const { logout } = require('../../services/auth');

Page({
  data: {
    user: { name: '未登录', role: '农场主', initial: '?' },
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
    const displayName = u.nickname || u.username || '用户';
    const initial = (displayName || '农').slice(0, 1).toUpperCase();
    return {
      name: displayName,
      role: u.role === 'admin' ? '管理员' : '农场主',
      initial,
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
          logout(); // logout 内部已 reLaunch 到登录页
        }
      },
    });
  },
});
