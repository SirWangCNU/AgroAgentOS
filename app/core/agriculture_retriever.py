"""农业知识库检索器: 支持分类过滤、引用溯源.

功能:
  - 基于现有 Hybrid Retriever (BM25 + Vector + RRF)
  - 支持按农业知识分类过滤 (种植技术/病虫害/土壤/气象)
  - 返回带引用信息的检索结果
  - 支持分类权重调整

用法:
  from app.core.agriculture_retriever import agriculture_retriever

  # 基础检索
  results = await agriculture_retriever.search("水稻种植技术")

  # 指定分类检索
  results = await agriculture_retriever.search("病虫害防治", category="pest_control")

  # 带分类权重的检索
  results = await agriculture_retriever.search(
      "施肥方案",
      category_weights={"soil": 1.5, "planting": 1.0}
  )
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from langchain_core.documents import Document
from loguru import logger

from app.config import settings

# 农业知识分类
AGRICULTURE_CATEGORIES = {
    "planting": "种植技术",
    "pest_control": "病虫害防治",
    "soil": "土壤管理",
    "weather": "气象知识",
}

# 分类关键词映射，用于自动识别查询意图
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "planting": [
        "种植", "栽培", "播种", "育苗", "移栽", "插秧", "施肥", "灌溉",
        "收割", "收获", "品种", "种子", "发芽", "分蘖", "抽穗", "灌浆",
        "水稻", "小麦", "玉米", "蔬菜", "大棚", "温室",
    ],
    "pest_control": [
        "病虫害", "病害", "虫害", "防治", "农药", "杀菌剂", "杀虫剂",
        "蚜虫", "红蜘蛛", "螟虫", "稻瘟病", "白粉病", "枯萎病",
        "生物防治", "天敌", "微生物农药",
    ],
    "soil": [
        "土壤", "施肥", "肥料", "有机肥", "化肥", "氮磷钾", "微量元素",
        "土壤检测", "土壤改良", "酸性土壤", "碱性土壤", "盐碱地",
        "配方施肥", "测土配方",
    ],
    "weather": [
        "天气", "气象", "温度", "降雨", "干旱", "洪涝", "霜冻", "冻害",
        "高温热害", "干热风", "冰雹", "大风", "天气预报", "农事安排",
        "灾害", "防灾",
    ],
}


@dataclass
class Citation:
    """知识引用信息."""

    source: str  # 来源文件名
    chapter: str  # 章节标题
    category: str  # 知识分类
    category_name: str  # 分类中文名
    content: str  # 引用内容片段
    relevance_score: float  # 相关度分数 (0-1)

    def to_dict(self) -> Dict:
        """转换为字典格式."""
        return {
            "source": self.source,
            "chapter": self.chapter,
            "category": self.category,
            "category_name": self.category_name,
            "content": self.content[:200] + "..." if len(self.content) > 200 else self.content,
            "relevance_score": round(self.relevance_score, 2),
        }


@dataclass
class RetrievalResult:
    """检索结果，包含文档和引用信息."""

    documents: List[Document]
    citations: List[Citation]
    query: str
    detected_category: Optional[str] = None

    def to_dict(self) -> Dict:
        """转换为字典格式."""
        return {
            "query": self.query,
            "detected_category": self.detected_category,
            "document_count": len(self.documents),
            "citation_count": len(self.citations),
            "citations": [c.to_dict() for c in self.citations],
        }


class AgricultureRetriever:
    """农业知识库检索器.

    特性:
      - 基于 Hybrid Search (BM25 + Vector + RRF)
      - 支持分类过滤
      - 自动检测查询意图分类
      - 返回带引用信息的结果
    """

    def __init__(self):
        """初始化检索器."""
        self._category_cache: Dict[str, List[str]] = {}

    def detect_category(self, query: str) -> Optional[str]:
        """自动检测查询所属的农业知识分类.

        基于关键词匹配，返回最可能的分类。

        Args:
            query: 用户查询

        Returns:
            分类名称，或 None 表示无法确定
        """
        query_lower = query.lower()
        scores: Dict[str, int] = {}

        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > 0:
                scores[category] = score

        if not scores:
            return None

        # 返回得分最高的分类
        return max(scores.items(), key=lambda x: x[1])[0]

    async def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        category_weights: Optional[Dict[str, float]] = None,
        auto_detect: bool = True,
    ) -> RetrievalResult:
        """农业知识检索.

        Args:
            query: 用户查询
            top_k: 返回文档数量
            category: 指定分类过滤 (None 表示全部)
            category_weights: 分类权重调整 (可选)
            auto_detect: 是否自动检测分类

        Returns:
            RetrievalResult: 包含文档和引用信息
        """
        from app.core.vector_store import advanced_search
        from app.core.hybrid_retriever import hybrid_search

        # 自动检测分类
        detected_category = None
        if auto_detect and category is None:
            detected_category = self.detect_category(query)
            if detected_category:
                logger.info(f"[agriculture] 自动检测分类: {detected_category}")

        # 使用指定分类或自动检测的分类
        target_category = category or detected_category

        # 执行检索
        try:
            # 使用 advanced_search 进行向量检索
            vector_results = await advanced_search(
                query=query,
                top_k=top_k * 2,  # 多取一些用于过滤
            )

            # 应用分类过滤
            if target_category:
                filtered_results = self._filter_by_category(
                    vector_results, target_category
                )
            else:
                filtered_results = vector_results

            # 应用分类权重
            if category_weights:
                filtered_results = self._apply_category_weights(
                    filtered_results, category_weights
                )

            # 取 top_k
            final_results = filtered_results[:top_k]

            # 构建引用信息
            citations = self._build_citations(final_results)

            logger.info(
                f"[agriculture] 检索完成: query={query[:40]!r}, "
                f"category={target_category}, results={len(final_results)}"
            )

            return RetrievalResult(
                documents=final_results,
                citations=citations,
                query=query,
                detected_category=detected_category,
            )

        except Exception as e:
            logger.error(f"[agriculture] 检索失败: {e}")
            # 返回空结果
            return RetrievalResult(
                documents=[],
                citations=[],
                query=query,
                detected_category=detected_category,
            )

    def _filter_by_category(
        self, docs: List[Document], category: str
    ) -> List[Document]:
        """按分类过滤文档.

        Args:
            docs: 文档列表
            category: 目标分类

        Returns:
            过滤后的文档列表
        """
        filtered = []
        for doc in docs:
            doc_category = doc.metadata.get("category", "")
            if doc_category == category:
                filtered.append(doc)

        # 如果过滤后没有结果，返回原始结果（降级）
        if not filtered:
            logger.warning(
                f"[agriculture] 分类 {category} 无结果，返回全部结果"
            )
            return docs

        return filtered

    def _apply_category_weights(
        self, docs: List[Document], weights: Dict[str, float]
    ) -> List[Document]:
        """应用分类权重调整.

        权重 > 1.0 表示提高该分类的优先级，
        权重 < 1.0 表示降低该分类的优先级。

        Args:
            docs: 文档列表
            weights: 分类权重字典

        Returns:
            调整权重后的文档列表
        """
        def _get_weight(doc: Document) -> float:
            category = doc.metadata.get("category", "")
            return weights.get(category, 1.0)

        # 按权重排序（保持原有相对顺序的稳定性）
        weighted_docs = [(doc, _get_weight(doc)) for doc in docs]
        weighted_docs.sort(key=lambda x: x[1], reverse=True)

        return [doc for doc, _ in weighted_docs]

    def _build_citations(self, docs: List[Document]) -> List[Citation]:
        """构建引用信息列表.

        Args:
            docs: 文档列表

        Returns:
            Citation 列表
        """
        citations = []
        for i, doc in enumerate(docs):
            meta = doc.metadata or {}
            category = meta.get("category", "unknown")

            citation = Citation(
                source=meta.get("source", "未知来源"),
                chapter=meta.get("chapter", ""),
                category=category,
                category_name=AGRICULTURE_CATEGORIES.get(category, "未知"),
                content=doc.page_content,
                relevance_score=1.0 - (i * 0.1),  # 简化的相关度分数
            )
            citations.append(citation)

        return citations


# 全局单例
agriculture_retriever = AgricultureRetriever()
