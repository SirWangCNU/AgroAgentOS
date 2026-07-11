// SSE 流式请求封装
// 小程序不支持 EventSource，用 wx.request({ enableChunked:true }) + onChunkReceived
// 手动按 \n\n 切分 SSE 事件，解析 "data: {...}" 行。
const config = require('../config');
const storage = require('../utils/storage');

/**
 * 纯 JS 的 UTF-8 解码器兜底
 * 有些小程序基础库 / 环境下 TextDecoder 不可用或不稳定
 * 支持 stream 模式（记录残留字节，避免中文被切断导致乱码）
 */
function createUtf8Decoder() {
  let pending = null; // 残留字节

  return {
    decode(arrayBuffer) {
      const bytes = new Uint8Array(arrayBuffer);
      let buf = bytes;
      // 合并上次残留
      if (pending && pending.length) {
        buf = new Uint8Array(pending.length + bytes.length);
        buf.set(pending, 0);
        buf.set(bytes, pending.length);
        pending = null;
      }

      let str = '';
      let i = 0;
      const len = buf.length;
      while (i < len) {
        const b1 = buf[i];
        let need = 0;
        if (b1 < 0x80) need = 1;
        else if (b1 < 0xC0) { i++; continue; } // 非法起始字节，跳过
        else if (b1 < 0xE0) need = 2;
        else if (b1 < 0xF0) need = 3;
        else need = 4;

        if (i + need > len) {
          // 不完整字符，保留到下次
          pending = buf.slice(i);
          break;
        }

        let cp;
        if (need === 1) cp = b1;
        else if (need === 2) cp = ((b1 & 0x1F) << 6) | (buf[i + 1] & 0x3F);
        else if (need === 3) cp = ((b1 & 0x0F) << 12) | ((buf[i + 1] & 0x3F) << 6) | (buf[i + 2] & 0x3F);
        else cp = ((b1 & 0x07) << 18) | ((buf[i + 1] & 0x3F) << 12) | ((buf[i + 2] & 0x3F) << 6) | (buf[i + 3] & 0x3F);

        if (cp <= 0xFFFF) {
          str += String.fromCharCode(cp);
        } else {
          // 代理对
          cp -= 0x10000;
          str += String.fromCharCode(0xD800 + (cp >> 10), 0xDC00 + (cp & 0x3FF));
        }
        i += need;
      }
      return str;
    },
  };
}

/**
 * 流式 POST 请求
 * @param {Object} opt
 *   url: 接口路径（不含前缀）
 *   data: 请求体
 *   onToken(text): 每收到一段文本增量
 *   onEvent(evt): 收到完整 SSE 事件 { type, ... }
 *   onDone(): 流结束
 *   onError(err): 出错
 */
function stream(opt) {
  const {
    url,
    data = {},
    onToken,
    onEvent,
    onDone,
    onError,
  } = opt;

  const token = storage.get('token', '');
  const header = { 'Content-Type': 'application/json' };
  if (token) header['Authorization'] = `Bearer ${token}`;

  let buffer = '';
  let done = false; // 防止 onDone 重复触发
  const decoder = createUtf8Decoder();
  let chunkCount = 0;

  const finalUrl = config.BASE_URL + config.API_PREFIX + url;
  console.log('[sse] connect', finalUrl, data);

  const task = wx.request({
    url: finalUrl,
    method: 'POST',
    data,
    header,
    enableChunked: true,
    responseType: 'text',
    success(res) {
      console.log('[sse] success statusCode=', res.statusCode, 'chunks=', chunkCount);
      flushBuffer();
      if (!done && onDone) { done = true; onDone(); }
    },
    fail(err) {
      console.error('[sse] fail:', err);
      if (onError) onError(err);
      else wx.showToast({ title: '对话连接失败', icon: 'none' });
    },
  });

  function flushBuffer() {
    let idx;
    // 兼容 \n\n 和 \r\n\r\n
    while (true) {
      const i1 = buffer.indexOf('\n\n');
      const i2 = buffer.indexOf('\r\n\r\n');
      if (i1 === -1 && i2 === -1) break;
      let cut, sep;
      if (i1 !== -1 && (i2 === -1 || i1 < i2)) { cut = i1; sep = 2; }
      else { cut = i2; sep = 4; }
      const raw = buffer.slice(0, cut);
      buffer = buffer.slice(cut + sep);
      parseEvent(raw);
    }
  }

  function parseEvent(raw) {
    const lines = raw.split('\n').filter((l) => l.startsWith('data:'));
    if (lines.length === 0) return;
    const payload = lines.map((l) => l.slice(5).trim()).join('');
    if (!payload) return;
    let evt;
    try {
      evt = JSON.parse(payload);
    } catch (e) {
      console.warn('[sse] parse error:', payload.slice(0, 100));
      return;
    }
    if (onEvent) onEvent(evt);
    if (evt.type === 'token' && evt.content && onToken) {
      onToken(evt.content);
    }
    if (evt.type === 'end' && !done && onDone) {
      done = true;
      onDone();
    }
  }

  if (task.onChunkReceived) {
    task.onChunkReceived((res) => {
      chunkCount++;
      try {
        const text = decoder.decode(res.data);
        buffer += text;
        flushBuffer();
      } catch (e) {
        console.error('[sse] decode error:', e);
      }
    });
  } else {
    console.warn('[sse] task.onChunkReceived 不可用，请升级微信开发者工具/基础库');
  }
  return task;
}

module.exports = { stream };
