"""农业知识库检索: 支持分类过滤和引用溯源.

功能:
  - 基于 advanced_search 进行检索
  - 支持农业知识分类过滤
  - 返回带引用信息的检索结果
  - 与现有 RAG 服务集成
"""

from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from app.core.agriculture_retriever import (
    AGRICULTURE_CATEGORIES,
    Citation,
    RetrievalResult,
    agriculture_retriever,
)
from app.core.vector_store import advanced_search

# 单个片段截断上限
CHUNK_CHAR_LIMIT = 800


async def build_agriculture_context(
    question: str,
    top_k: int = 5,
    category: Optional[str] = None,
    auto_detect: bool = True,
) -> Tuple[str, int, List[str], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """农业知识库检索，拼接成 context 字符串.

    Args:
        question: 用户问题
        top_k: 返回文档数量
        category: 指定分类过滤 (可选)
        auto_detect: 是否自动检测分类

    Returns:
        (context_text, hit_count, sources, hits_meta, citations)
        hits_meta: [{"source", "chapter", "preview", "score", "category"}, ...]
        citations: [{"source", "chapter", "category", "category_name", "content", "relevance_score"}, ...]
    """
    # 使用农业检索器进行检索
    result = await agriculture_retriever.search(
        query=question,
        top_k=top_k,
        category=category,
        auto_detect=auto_detect,
    )

    if not result.documents:
        return "(知识库未命中相关内容)", 0, [], [], []

    # 构建 context
    chunks: List[str] = []
    sources: List[str] = []
    hits_meta: List[Dict[str, Any]] = []

    for i, doc in enumerate(result.documents, 1):
        meta = doc.metadata or {}
        source = meta.get("source") or "未知"
        sources.append(str(source))
        chapter = meta.get("chapter") or ""
        category = meta.get("category", "unknown")
        category_name = AGRICULTURE_CATEGORIES.get(category, "未知")

        # 构建带分类信息的 header
        header = f"## 来源 {i} | {source}"
        if chapter:
            header += f" | 章节: {chapter}"
        header += f" | 分类: {category_name}"

        raw_text = doc.page_content.strip()
        truncated = raw_text[:CHUNK_CHAR_LIMIT]
        if len(raw_text) > CHUNK_CHAR_LIMIT:
            truncated += "... (已截断)"

        chunks.append(f"{header}\n{truncated}")

        # 构建 hits_meta
        score = meta.get("score") or meta.get("rerank_score") or meta.get("distance")
        try:
            score_val = round(float(score), 4) if score is not None else None
        except Exception:
            score_val = None

        preview = raw_text.replace("\n", " ")
        hits_meta.append(
            {
                "source": str(source),
                "chapter": str(chapter) if chapter else "",
                "preview": preview[:240] + ("..." if len(preview) > 240 else ""),
                "score": score_val,
                "category": category,
                "category_name": category_name,
            }
        )

    # 构建 citations
    citations = [c.to_dict() for c in result.citations]

    context_text = "\n\n".join(chunks)

    logger.info(
        f"[agriculture] 检索完成: question={question[:40]!r}, "
        f"detected_category={result.detected_category}, "
        f"hits={len(result.documents)}, citations={len(citations)}"
    )

    return context_text, len(result.documents), sources, hits_meta, citations


def get_category_suggestions(query: str) -> List[Dict[str, str]]:
    """获取分类建议，帮助用户选择合适的分类.

    Args:
        query: 用户查询

    Returns:
        List of {"category": str, "category_name": str, "confidence": float}
    """
    detected = agriculture_retriever.detect_category(query)
    if detected:
        return [
            {
                "category": detected,
                "category_name": AGRICULTURE_CATEGORIES.get(detected, "未知"),
                "confidence": 0.8,
            }
        ]
    return []
