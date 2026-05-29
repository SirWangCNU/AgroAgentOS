"""农业知识库批量入库脚本: knowledge_base/ -> Milvus.

用途:
  - 把 knowledge_base/ 下的农业知识文档 (种植技术/病虫害/土壤/气象)
    切分 -> embedding -> 写入 Milvus
  - 走和线上 RAG 一致的链路: split_markdown() + get_vector_store().add_documents()
  - 失败的文件单独记录, 不影响其他文件入库
  - 支持按分类增量导入，避免重复入库

用法:
  python scripts/ingest_agriculture_kb.py                    # 入库全部
  python scripts/ingest_agriculture_kb.py --dry-run          # 只切分不入库
  python scripts/ingest_agriculture_kb.py --reset            # 先 drop 老 collection 再入库
  python scripts/ingest_agriculture_kb.py --category planting # 只入指定分类
  python scripts/ingest_agriculture_kb.py --limit 10         # 只入前 10 个文件

前置条件:
  - Milvus 已启动 (docker-compose up -d)
  - DASHSCOPE_API_KEY 已配置
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# 让脚本能从仓库根目录导入 app.*
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from langchain_core.documents import Document  # noqa: E402
from loguru import logger  # noqa: E402

# 农业知识库目录
KNOWLEDGE_BASE_DIR = ROOT / "knowledge_base"

# 支持的知识分类
CATEGORIES = {
    "planting": "种植技术",
    "pest_control": "病虫害防治",
    "soil": "土壤管理",
    "weather": "气象知识",
}


def collect_files(
    category: str | None = None, limit: int = 0
) -> List[Tuple[Path, str, str]]:
    """扫描所有要入库的 (文件路径, source 标识, 分类).

    Args:
        category: 指定分类名称，None 表示全部分类
        limit: 限制文件数量，0 表示不限制

    Returns:
        List of (file_path, source_id, category)
    """
    files: List[Tuple[Path, str, str]] = []

    if not KNOWLEDGE_BASE_DIR.exists():
        logger.error(f"知识库目录不存在: {KNOWLEDGE_BASE_DIR}")
        return files

    # 确定要扫描的分类
    if category:
        if category not in CATEGORIES:
            logger.error(f"未知分类: {category}, 可选: {list(CATEGORIES.keys())}")
            return files
        scan_categories = [category]
    else:
        scan_categories = list(CATEGORIES.keys())

    # 扫描每个分类下的 .md 文件
    for cat in scan_categories:
        cat_dir = KNOWLEDGE_BASE_DIR / cat
        if not cat_dir.exists():
            logger.warning(f"分类目录不存在: {cat_dir}")
            continue

        for p in sorted(cat_dir.glob("*.md")):
            rel = p.relative_to(KNOWLEDGE_BASE_DIR).as_posix()
            files.append((p, rel, cat))

    if limit > 0:
        files = files[:limit]

    return files


def split_all(files: List[Tuple[Path, str, str]]) -> List[Document]:
    """把所有文件切成 Document chunks.

    Args:
        files: List of (file_path, source_id, category)

    Returns:
        List of Document chunks with metadata
    """
    from app.utils.splitter import split_markdown

    all_chunks: List[Document] = []
    failed = 0

    for fpath, source, category in files:
        try:
            content = fpath.read_text(encoding="utf-8")
            # 使用现有切分器，保留章节结构
            chunks = split_markdown(content, source=source)

            # 为每个 chunk 添加农业知识分类 metadata
            for chunk in chunks:
                chunk.metadata["category"] = category
                chunk.metadata["category_name"] = CATEGORIES.get(category, "未知")

            all_chunks.extend(chunks)
        except Exception as e:
            failed += 1
            logger.warning(f"切分失败: {fpath} -> {e}")

    logger.info(
        f"切分完成: {len(files)} 文件 -> {len(all_chunks)} chunks (失败 {failed})"
    )
    return all_chunks


def ingest_to_milvus(chunks: List[Document], batch_size: int = 50) -> None:
    """分批写入 Milvus.

    Args:
        chunks: Document chunks to ingest
        batch_size: Number of chunks per batch (default 50, smaller for stability)
    """
    from app.core.vector_store import get_vector_store

    vs = get_vector_store()
    total = len(chunks)
    logger.info(f"开始入库: {total} chunks, batch_size={batch_size}")

    t0 = time.perf_counter()
    written = 0
    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        try:
            vs.add_documents(batch)
            written += len(batch)
            elapsed = time.perf_counter() - t0
            rate = written / max(elapsed, 0.01)
            eta = (total - written) / max(rate, 0.01)
            logger.info(
                f"  进度 {written}/{total} ({100*written/total:.1f}%), "
                f"速率 {rate:.1f} chunk/s, 剩余 {eta:.0f}s"
            )
        except Exception as e:
            logger.error(f"  batch [{i}:{i+len(batch)}] 失败: {e}")

    elapsed = time.perf_counter() - t0
    logger.info(f"入库完成: {written}/{total}, 总耗时 {elapsed:.1f}s")


def reset_collection() -> None:
    """drop 旧的 collection (慎用)."""
    from pymilvus import MilvusClient

    from app.config import settings

    uri = f"http://{settings.milvus_host}:{settings.milvus_port}"
    client = MilvusClient(uri=uri)
    if client.has_collection(settings.milvus_collection):
        client.drop_collection(settings.milvus_collection)
        logger.info(f"已 drop collection: {settings.milvus_collection}")
    else:
        logger.info(f"collection 不存在, 跳过 drop: {settings.milvus_collection}")
    # 清掉单例缓存, 让下次 get_vector_store 重建
    from app.core.vector_store import get_vector_store

    get_vector_store.cache_clear()


def print_stats(chunks: List[Document]) -> None:
    """打印统计信息."""
    # 按分类统计
    category_stats: Dict[str, int] = {}
    for chunk in chunks:
        cat = chunk.metadata.get("category", "unknown")
        category_stats[cat] = category_stats.get(cat, 0) + 1

    logger.info("=== 统计信息 ===")
    logger.info(f"总 chunks 数: {len(chunks)}")
    logger.info("按分类统计:")
    for cat, count in category_stats.items():
        cat_name = CATEGORIES.get(cat, "未知")
        logger.info(f"  {cat_name} ({cat}): {count} chunks")

    # 计算平均长度
    avg_len = sum(len(c.page_content) for c in chunks) / max(len(chunks), 1)
    logger.info(f"平均 chunk 长度: {avg_len:.0f} 字")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="农业知识库批量入库: knowledge_base/ -> Milvus"
    )
    parser.add_argument("--dry-run", action="store_true", help="只切分不入库")
    parser.add_argument("--reset", action="store_true", help="先 drop 老 collection")
    parser.add_argument(
        "--category",
        type=str,
        choices=list(CATEGORIES.keys()),
        help="只入指定分类 (planting/pest_control/soil/weather)",
    )
    parser.add_argument("--limit", type=int, default=0, help="只入前 N 个文件 (0=全部)")
    parser.add_argument("--batch", type=int, default=50, help="每批入库 chunk 数")
    args = parser.parse_args()

    # 加载 .env (拿 DASHSCOPE_API_KEY / MILVUS_HOST 等)
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    # 扫描文件
    files = collect_files(category=args.category, limit=args.limit)
    logger.info(f"扫描到 {len(files)} 个农业知识文档")

    if not files:
        logger.error(
            f"没有找到任何文件, 请确认 {KNOWLEDGE_BASE_DIR} 下有 .md 文件"
        )
        logger.info("目录结构示例:")
        logger.info("  knowledge_base/")
        logger.info("  ├── planting/")
        logger.info("  │   ├── 水稻种植指南.md")
        logger.info("  │   └── ...")
        logger.info("  ├── pest_control/")
        logger.info("  ├── soil/")
        logger.info("  └── weather/")
        sys.exit(1)

    # 切分文档
    chunks = split_all(files)
    if not chunks:
        logger.error("切分后 0 个 chunk, 退出")
        sys.exit(1)

    # 打印统计
    print_stats(chunks)

    # 估算入库时间
    logger.info(
        f"预计入库耗时: {len(chunks)/30:.0f}-{len(chunks)/15:.0f}s"
    )

    if args.dry_run:
        logger.info("=== dry-run 模式, 不入库 ===")
        logger.info("示例 chunks:")
        for i, c in enumerate(chunks[:3]):
            logger.info(f"--- chunk {i+1} ---")
            logger.info(f"  source: {c.metadata.get('source')}")
            logger.info(f"  category: {c.metadata.get('category')}")
            logger.info(f"  chapter: {c.metadata.get('chapter')}")
            logger.info(f"  content[:120]: {c.page_content[:120]!r}")
        return

    if args.reset:
        logger.info("=== reset 模式, 先删除旧 collection ===")
        reset_collection()

    # 入库
    logger.info("=== 开始入库 ===")
    ingest_to_milvus(chunks, batch_size=args.batch)

    logger.info("=== 入库完成 ===")
    logger.info("提示: 可使用以下命令验证:")
    logger.info("  python -c \"from app.core.vector_store import get_vector_store; vs = get_vector_store(); print(f'Collection: {vs._collection.name}, count: {vs._collection.num_entities}')\"")


if __name__ == "__main__":
    main()
