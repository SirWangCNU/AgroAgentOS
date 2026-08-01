"""知识库检索工具 (RAG Tool).

Agent 拿到这个工具，可以查询农业知识库（种植、病虫害、农资、市场等资料）。
返回 top-k 相关片段 + 元数据 (来源、章节).

设计要点:
  - 使用 @tool 装饰器, LangChain 会自动从函数签名 + docstring 生成 schema
  - 描述要写得清楚: LLM 决定何时调用工具完全靠 description
  - 返回字符串 (不是 dict), 因为 Agent 把工具返回值当 ToolMessage 内容
  - 失败兜底: collection 不存在/Milvus 挂了 → 返回友好提示, 不抛异常
"""

from langchain_core.tools import tool
from loguru import logger

from app.config import settings
from app.core.vector_store import safe_similarity_search


@tool
def search_knowledge_base(query: str) -> str:
    """搜索农业知识库（种植技术、病虫害防治、市场政策等）。

    在以下场景调用本工具:
    - 需要查询作物的种植和田间管理方法
    - 需要参考病虫害识别与防治资料
    - 需要了解农业政策、市场或气象影响
    - 需要查找用户上传的农业专业文档

    Args:
        query: 查询关键词或问题，例如“水稻稻瘟病如何防治”或“玉米追肥时期”

    Returns:
        相关文档片段 (Markdown 格式), 包含来源信息. 如果没有匹配返回提示信息.
    """
    docs = safe_similarity_search(query, k=settings.rag_top_k)

    if not docs:
        logger.info(f"[knowledge_tool] 无匹配: query={query!r}")
        return (
            f"知识库中没有找到与 '{query}' 直接相关的文档。"
            f"请尝试换个关键词搜索, 或基于已有经验给出建议。"
        )

    logger.info(f"[knowledge_tool] 命中 {len(docs)} 篇: query={query!r}")

    # 拼接为可读的上下文
    chunks = []
    for i, doc in enumerate(docs, 1):
        meta = doc.metadata or {}
        source = meta.get("source") or meta.get("file") or "未知来源"
        chapter = meta.get("chapter") or meta.get("title") or ""
        header = f"### 片段 {i} | 来源: {source}"
        if chapter:
            header += f" | 章节: {chapter}"
        chunks.append(f"{header}\n{doc.page_content.strip()}")

    return "\n\n---\n\n".join(chunks)
