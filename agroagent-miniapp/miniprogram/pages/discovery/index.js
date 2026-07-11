Page({
  data: {
    articles: [
      { id: 1, tag: '种植技术', title: '番茄早疫病识别与综合防治', read: '1.2万' },
      { id: 2, tag: '政策补贴', title: '2026年小麦种植补贴申领指南', read: '8653' },
      { id: 3, tag: '病害图谱', title: '常见叶部病害高清图鉴', read: '2.3万' },
      { id: 4, tag: '市场洞察', title: '夏季果蔬价格走势分析', read: '5431' },
    ],
  },
  onArticle(e) {
    wx.showToast({ title: '详情敬请期待', icon: 'none' });
  },
});
