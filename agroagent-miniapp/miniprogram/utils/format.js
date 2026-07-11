// 格式化工具
const format = {
  // 友好时间：刚刚 / x分钟前 / x小时前 / MM-DD
  timeAgo(ts) {
    if (!ts) return '';
    const d = typeof ts === 'number' ? new Date(ts) : new Date(ts);
    const diff = (Date.now() - d.getTime()) / 1000;
    if (diff < 60) return '刚刚';
    if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`;
    const M = `${d.getMonth() + 1}`.padStart(2, '0');
    const D = `${d.getDate()}`.padStart(2, '0');
    return `${M}-${D}`;
  },
  // 简单 Markdown -> 文本（保留换行与符号，用于无富文本场景）
  stripMarkdown(md) {
    return (md || '')
      .replace(/\*\*(.*?)\*\*/g, '$1')
      .replace(/^\s*[-*]\s+/gm, '• ')
      .replace(/^\s*#{1,6}\s+/gm, '');
  },
};

module.exports = format;
