// 各业务 API 集中定义（对接现有后端路由）
const config = require('../config');
const { request } = require('./request');

const api = {
  // ===== 认证 =====
  getUserInfo: () => request({ url: '/auth/me', method: 'GET' }),

  // ===== 聊天（流式在 sse.js） =====
  createSession: (title = '') => request({ url: '/sessions', method: 'POST', data: { title } }),
  listSessions: () => request({ url: '/sessions', method: 'GET' }),
  getSession: (sessionId) => request({ url: `/sessions/${sessionId}`, method: 'GET' }),

  /**
   * 分页查询会话消息 (游标分页).
   * @param {string} sessionId 会话 ID
   * @param {Object} opt { limit=10, beforeId=null }
   *   - limit:     每页条数 (1-50)
   *   - beforeId:  游标, 返回 id < before_id 的消息. 首次加载留空.
   * @returns Promise<{ messages, has_more, oldest_id }>
   */
  listMessages: (sessionId, opt = {}) => {
    const limit = opt.limit || 10;
    const beforeId = opt.beforeId;
    let url = `/sessions/${sessionId}/messages?limit=${limit}`;
    if (beforeId != null) url += `&before_id=${beforeId}`;
    return request({ url, method: 'GET' });
  },

  /**
   * 添加消息 (仅 user 消息需要前端调用).
   * assistant 消息由后端 rag_service.stream_chat 收尾时主动持久化, 前端无需调用.
   */
  addSessionMessage: (sessionId, role, content, imageUrl) => {
    let url = `/sessions/${sessionId}/messages?role=${encodeURIComponent(role)}&content=${encodeURIComponent(content)}`;
    if (imageUrl) url += `&image_url=${encodeURIComponent(imageUrl)}`;
    return request({ url, method: 'POST' });
  },

  // ===== 天气 =====
  getWeather: (location) => request({ url: `/weather?location=${encodeURIComponent(location)}`, method: 'GET' }),

  // ===== 市场行情 =====
  getMarketOverview: (crop, location) =>
    request({ url: `/market/overview?crop=${encodeURIComponent(crop)}&location=${encodeURIComponent(location)}`, method: 'GET' }),

  // ===== 工作台统计 / 工具 =====
  listSkills: () => request({ url: '/skills', method: 'GET' }),

  // ===== 农场 =====
  listFarms: () => request({ url: '/farms', method: 'GET' }),

  // ===== 诊断记录 =====
  listDiagnosis: () => request({ url: '/diagnosis/records', method: 'GET' }),

  // ===== 图片上传（病虫害识别）=====
  // 后端接口: POST /api/v1/image/analyze (multipart, 字段名 file)
  analyzeImage: (filePath) =>
    new Promise((resolve, reject) => {
      const token = wx.getStorageSync('token');
      wx.uploadFile({
        url: config.BASE_URL + config.API_PREFIX + '/image/analyze',
        filePath,
        name: 'file',
        header: token ? { Authorization: `Bearer ${token}` } : {},
        success(res) {
          try {
            const body = JSON.parse(res.data);
            resolve(body.data || body);
          } catch (e) {
            reject(e);
          }
        },
        fail: reject,
      });
    }),
};

module.exports = api;
