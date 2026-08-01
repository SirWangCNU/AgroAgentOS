"""RAG Chat 的联网搜索上下文构造.

策略:
  - 联网查询仅围绕用户农业问题和当前会话中的实体/术语构建
  - 命中黑名单 / 敏感词直接拒
  - 真正的 provider 调度走 app.core.web_search
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

from loguru import logger

from app.config import settings
from app.core.web_search import format_results, get_provider, search


_SENSITIVE_WEB_PATTERNS = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\.\-_]+", re.IGNORECASE),
    re.compile(r"\b1\d{10}\b"),
    re.compile(r"\b\d{15,18}\b"),
)

_BLOCKED_WEB_KEYWORDS = (
    "password", "passwd", "api_key", "api-key", "token", "secret", "私钥",
)


_QUERY_TERM_RE = re.compile(
    r"""
    [A-Za-z][A-Za-z0-9_.\-]{1,}
    |
    [\u4e00-\u9fffA-Za-z0-9_.\-]*(?:作物|品种|病害|虫害|农药|肥料|土壤|天气|气象|市场|价格|补贴|政策)[\u4e00-\u9fffA-Za-z0-9_.\-]*
    """,
    re.IGNORECASE | re.VERBOSE,
)

_QUERY_TERM_STOPWORDS = {
    "什么", "怎么", "为什么", "刚刚", "刚才", "之前", "前面", "说的", "这个", "那个",
    "帮我", "一下", "可以", "联网", "搜索", "查询", "分析", "结果", "问题", "原因",
    "what", "why", "how", "the", "and", "for", "with", "this", "that",
}

_WEB_QUERY_PREFIX_RE = re.compile(
    r"^\s*(?:请)?(?:帮我)?(?:联网(?:搜索|查询|查找|看看|看一下|查一下)?|搜索|查询|查找|查一下|看一下)[：:\s，,、-]*",
    re.IGNORECASE,
)

def _normalize_web_query(query: str) -> str:
    normalized = re.sub(r"\s+", " ", query.strip())
    for _ in range(3):
        updated = _WEB_QUERY_PREFIX_RE.sub("", normalized).strip()
        if updated == normalized:
            break
        normalized = updated
    return normalized


def _allowed_web_keywords() -> list[str]:
    return [
        item.strip().lower()
        for item in settings.rag_chat_web_search_keywords.split(",")
        if item.strip()
    ]


def _extract_web_topics(text: str) -> list[str]:
    lower = text.lower()
    topics = []
    for keyword in _allowed_web_keywords():
        pattern = rf"(?<![a-z0-9_\-]){re.escape(keyword)}(?![a-z0-9_\-])"
        if re.search(pattern, lower) and keyword not in topics:
            topics.append(keyword)
    return topics


def _web_query_block_reason(text: str) -> str:
    lower = text.lower()
    for keyword in _BLOCKED_WEB_KEYWORDS:
        if keyword.lower() in lower:
            return f"命中禁止联网关键词: {keyword}"
    for pattern in _SENSITIVE_WEB_PATTERNS:
        if pattern.search(text):
            return "query 含敏感信息"
    return ""


def _extract_query_terms(text: str) -> set[str]:
    terms: set[str] = set()
    for raw in _QUERY_TERM_RE.findall(text or ""):
        term = raw.strip("`'\"“”‘’,。！？；：:;,.()()[]【】<>《》")
        if not term:
            continue
        lower = term.lower()
        if len(lower) < 2 or lower in _QUERY_TERM_STOPWORDS:
            continue
        if lower.isdigit():
            continue
        terms.add(lower)
    return terms


def build_restricted_web_query(
    rewritten_question: str,
    *,
    summary: str,
    recent_messages: list[dict[str, Any]],
) -> tuple[str, list[str], str]:
    """联网 query 校验器.

    联网查询只允许农业主题，并从当前问题中提取检索主题。
    """
    block_reason = _web_query_block_reason(rewritten_question)
    if block_reason:
        return "", [], block_reason

    query = _normalize_web_query(rewritten_question)
    if not query:
        return "", [], "查询为空"

    topics = _extract_web_topics(rewritten_question)
    if not topics:
        topics = list(_extract_query_terms(query))[:3]

    return query[:180].strip(), topics, ""


async def build_web_context(
    rewritten_question: str,
    *,
    summary: str,
    recent_messages: list[dict[str, Any]],
    enabled: bool,
) -> tuple[str, list[str], list[dict[str, Any]], str]:
    """联网搜索 + 拼 context.

    Returns:
        (web_context_text, sources, web_hits, skip_reason)
        web_hits: [{"title", "url", "snippet"}, ...]
        skip_reason: 非空表示被跳过的原因 (用于前端展开显示)
    """
    if not enabled:
        return "(本轮未启用联网搜索)", [], [], "本轮未启用联网搜索"
    if not settings.rag_chat_web_search_enabled:
        reason = "联网搜索未启用: RAG_CHAT_WEB_SEARCH_ENABLED=false"
        return f"({reason})", [], [], reason

    query, topics, blocked = build_restricted_web_query(
        rewritten_question,
        summary=summary,
        recent_messages=recent_messages,
    )
    if not query:
        logger.info(f"[rag-web] skip | topics={topics} | reason={blocked}")
        return f"(联网搜索已跳过: {blocked})", [], [], blocked

    provider = get_provider()
    max_results = max(1, min(settings.rag_chat_web_search_max_results, 5))
    logger.info(
        f"[rag-web] search | provider={provider} | topics={topics} | query={query!r}"
    )
    try:
        raw_hits = await asyncio.to_thread(search, query, max_results, provider)
    except Exception as e:
        logger.warning(f"[rag-web] 联网搜索失败: {type(e).__name__}: {e}")
        return (
            f"(联网搜索失败: {type(e).__name__}: {e})",
            [],
            [],
            f"{type(e).__name__}: {e}",
        )

    if not raw_hits:
        return (
            f"(联网搜索未找到与 '{query}' 相关的结果)",
            [],
            [],
            "未找到相关结果",
        )

    text = format_results(raw_hits, provider=provider)
    sources = [f"web:{topic}" for topic in topics] or [f"web:{query[:20]}"]
    web_hits = [
        {
            "title": h.get("title", "")[:120],
            "url": h.get("url", "")[:300],
            "snippet": (h.get("snippet", "") or "")[:240],
        }
        for h in raw_hits
    ]
    return text, sources, web_hits, ""
