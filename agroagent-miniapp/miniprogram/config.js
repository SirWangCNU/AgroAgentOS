// 全局配置
// 开发期：在微信开发者工具中勾选「不校验合法域名」即可直接用 localhost/内网 IP。
// 生产期：BASE_URL 改为已备案 HTTPS 域名（需在公众平台配置 request 合法域名）。
const config = {
  // 后端服务地址：请改成你本机/服务器可达地址
  // 本地调试用电脑局域网 IP，例如 http://192.168.1.100:9800
  // 当前电脑局域网 IP: 10.2.82.211 （真机预览务必用局域网 IP，不能用 localhost）
  BASE_URL: 'http://10.2.82.211:9800',
  API_PREFIX: '/api/v1',
  // 默认城市（天气定位失败时使用）
  DEFAULT_CITY: '北京',
};

module.exports = config;
