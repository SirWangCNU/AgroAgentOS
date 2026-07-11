Component({
  options: { styleIsolation: 'shared' },
  properties: {
    role: { type: String, value: 'ai' },       // 'user' | 'ai'
    content: { type: String, value: '' },       // 文本内容
    thinking: { type: Boolean, value: false },  // 是否显示「思考中」
    sources: { type: Array, value: [] },        // 引用来源列表
    progress: { type: String, value: '' },      // 当前进度阶段文案（思考中时展示）
  },
  methods: {},
});
