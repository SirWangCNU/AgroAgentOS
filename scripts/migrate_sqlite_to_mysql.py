"""SQLite 到 MySQL 数据迁移脚本.

使用方式:
  python scripts/migrate_sqlite_to_mysql.py

功能:
  1. 连接 SQLite 数据库读取所有数据
  2. 连接 MySQL 数据库创建表结构
  3. 迁移所有表的数据
  4. 验证迁移结果

注意事项:
  - 运行前请确保 MySQL 服务已启动
  - 请确保 .env 中的 MySQL 配置正确
  - 迁移前会自动备份 SQLite 数据库
"""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Windows 控制台编码修复
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings


# ==================== 表迁移顺序（考虑外键依赖） ====================
TABLE_ORDER = [
    "chat_sessions",
    "chat_messages",
    "agent_execution_logs",
    "history_records",
    "business_records",
    "weather_queries",
    "marketing_tasks",
    "pest_diagnoses",
    "agent_runs",
    "users",
    "farms",
    "fields",
    "trajectory_files",
    "trajectory_points",
]


def backup_sqlite() -> Path:
    """备份 SQLite 数据库."""
    db_path = Path(settings.sqlite_db_path)
    if not db_path.exists():
        print(f"⚠️  SQLite 数据库不存在: {db_path}")
        return db_path

    backup_path = db_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
    shutil.copy2(db_path, backup_path)
    print(f"✅ SQLite 数据库已备份到: {backup_path}")
    return backup_path


def get_sqlite_engine():
    """获取 SQLite 引擎."""
    db_path = settings.sqlite_db_path
    if not Path(db_path).exists():
        print(f"❌ SQLite 数据库不存在: {db_path}")
        sys.exit(1)
    return create_engine(f"sqlite:///{db_path}")


def get_mysql_engine():
    """获取 MySQL 引擎（不含数据库名）."""
    url = (
        f"mysql+pymysql://{settings.mysql_user}:{settings.mysql_password}"
        f"@{settings.mysql_host}:{settings.mysql_port}/?charset={settings.mysql_charset}"
    )
    return create_engine(url)


def get_mysql_db_engine():
    """获取 MySQL 引擎（含数据库名）."""
    return create_engine(settings.database_url)


def ensure_mysql_database() -> None:
    """确保 MySQL 数据库存在."""
    engine = get_mysql_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                f"CHARACTER SET {settings.mysql_charset} COLLATE {settings.mysql_charset}_general_ci"
            ))
            conn.commit()
        print(f"✅ MySQL 数据库 '{settings.mysql_database}' 已就绪")
    finally:
        engine.dispose()


def get_table_columns(engine, table_name: str) -> list[str]:
    """获取表的列名列表."""
    inspector = inspect(engine)
    columns = inspector.get_columns(table_name)
    return [col["name"] for col in columns]


def get_table_count(engine, table_name: str) -> int:
    """获取表的记录数."""
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
        return result.scalar()


def migrate_table(
    src_session: Session,
    dst_session: Session,
    table_name: str,
    src_columns: list[str],
    dst_columns: list[str],
) -> int:
    """迁移单个表的数据."""
    # 获取公共列
    common_columns = [col for col in src_columns if col in dst_columns]
    if not common_columns:
        print(f"  ⚠️  表 {table_name} 没有公共列，跳过")
        return 0

    # 读取源数据
    cols_str = ", ".join([f"`{col}`" for col in common_columns])
    result = src_session.execute(text(f"SELECT {cols_str} FROM `{table_name}`"))
    rows = result.fetchall()

    if not rows:
        print(f"  ℹ️  表 {table_name} 无数据")
        return 0

    # 构建插入语句
    placeholders = ", ".join([":col_" + col for col in common_columns])
    insert_sql = text(f"INSERT INTO `{table_name}` ({cols_str}) VALUES ({placeholders})")

    # 批量插入
    count = 0
    for row in rows:
        params = {f"col_{col}": row[i] for i, col in enumerate(common_columns)}
        try:
            dst_session.execute(insert_sql, params)
            count += 1
        except Exception as e:
            print(f"  ⚠️  插入失败: {e}")
            print(f"     数据: {row}")

    dst_session.commit()
    return count


def create_mysql_tables(drop_existing: bool = False) -> None:
    """在 MySQL 中创建表结构.

    Args:
        drop_existing: 是否先删除已存在的表
    """
    # 只导入 models 包中的模型（避免与 sqlite.py 中的重复定义冲突）
    # models 包中的模型会自动导入 Base
    from app.core.sqlite import Base
    from app.models.user import User  # noqa: F401
    from app.models.farm import Farm, Field  # noqa: F401
    from app.models.trajectory import TrajectoryFile, TrajectoryPoint  # noqa: F401

    engine = get_mysql_db_engine()
    try:
        if drop_existing:
            # 删除所有表（按外键依赖逆序）
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
                for table in reversed(TABLE_ORDER):
                    conn.execute(text(f"DROP TABLE IF EXISTS `{table}`"))
                conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
                conn.commit()
            print("  ✅ 已清理旧表")

        # 创建表（只使用 sqlite.py 中定义的模型，不导入 session.py 避免重复）
        Base.metadata.create_all(engine, checkfirst=True)
        print("✅ MySQL 表结构创建完成")
    finally:
        engine.dispose()


def run_migration() -> None:
    """执行迁移."""
    print("=" * 60)
    print("AgroAgentOS 数据迁移工具: SQLite → MySQL")
    print("=" * 60)

    # 1. 备份 SQLite
    print("\n📦 步骤 1: 备份 SQLite 数据库")
    backup_sqlite()

    # 2. 确保 MySQL 数据库存在
    print("\n🔧 步骤 2: 准备 MySQL 数据库")
    ensure_mysql_database()

    # 3. 创建 MySQL 表结构
    print("\n📋 步骤 3: 创建 MySQL 表结构")
    create_mysql_tables(drop_existing=True)

    # 4. 连接数据库
    print("\n🔌 步骤 4: 连接数据库")
    sqlite_engine = get_sqlite_engine()
    mysql_engine = get_mysql_db_engine()

    src_session = sessionmaker(bind=sqlite_engine)()
    dst_session = sessionmaker(bind=mysql_engine)()

    try:
        # 5. 迁移数据
        print("\n📤 步骤 5: 迁移数据")
        total_migrated = 0

        for table_name in TABLE_ORDER:
            print(f"\n  📂 迁移表: {table_name}")

            # 检查源表是否存在
            src_inspector = inspect(sqlite_engine)
            if table_name not in src_inspector.get_table_names():
                print(f"    ℹ️  源表不存在，跳过")
                continue

            # 检查目标表是否存在
            dst_inspector = inspect(mysql_engine)
            if table_name not in dst_inspector.get_table_names():
                print(f"    ⚠️  目标表不存在，跳过")
                continue

            # 获取列信息
            src_columns = get_table_columns(sqlite_engine, table_name)
            dst_columns = get_table_columns(mysql_engine, table_name)

            # 获取源表记录数
            src_count = get_table_count(sqlite_engine, table_name)
            print(f"    📊 源表记录数: {src_count}")

            if src_count == 0:
                continue

            # 迁移数据
            migrated = migrate_table(src_session, dst_session, table_name, src_columns, dst_columns)
            total_migrated += migrated
            print(f"    ✅ 已迁移: {migrated} 条")

            # 验证
            dst_count = get_table_count(mysql_engine, table_name)
            print(f"    📊 目标表记录数: {dst_count}")

            if migrated != src_count:
                print(f"    ⚠️  迁移数量不匹配! 源: {src_count}, 已迁移: {migrated}")

        # 6. 汇总
        print("\n" + "=" * 60)
        print(f"✅ 迁移完成! 共迁移 {total_migrated} 条记录")
        print("=" * 60)

        # 7. 验证建议
        print("\n📝 后续步骤:")
        print("  1. 检查 MySQL 数据是否正确")
        print("  2. 修改 .env 文件: USE_SQLITE=false")
        print("  3. 重启应用: uvicorn app.main:app --reload")
        print("  4. 验证应用功能正常后，可删除 SQLite 备份文件")

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        dst_session.rollback()
        sys.exit(1)
    finally:
        src_session.close()
        dst_session.close()
        sqlite_engine.dispose()
        mysql_engine.dispose()


def verify_migration() -> None:
    """验证迁移结果."""
    print("\n🔍 验证迁移结果...")

    sqlite_engine = get_sqlite_engine()
    mysql_engine = get_mysql_db_engine()

    try:
        print(f"\n{'表名':<25} {'SQLite':>10} {'MySQL':>10} {'状态':>10}")
        print("-" * 60)

        all_ok = True
        for table_name in TABLE_ORDER:
            src_inspector = inspect(sqlite_engine)
            dst_inspector = inspect(mysql_engine)

            if table_name not in src_inspector.get_table_names():
                continue

            src_count = get_table_count(sqlite_engine, table_name)

            if table_name not in dst_inspector.get_table_names():
                print(f"{table_name:<25} {src_count:>10} {'N/A':>10} {'❌':>10}")
                all_ok = False
                continue

            dst_count = get_table_count(mysql_engine, table_name)
            status = "✅" if src_count == dst_count else "⚠️"
            if src_count != dst_count:
                all_ok = False
            print(f"{table_name:<25} {src_count:>10} {dst_count:>10} {status:>10}")

        print("-" * 60)
        if all_ok:
            print("✅ 所有表数据一致!")
        else:
            print("⚠️  部分表数据不一致，请检查")

    finally:
        sqlite_engine.dispose()
        mysql_engine.dispose()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--verify":
        verify_migration()
    else:
        run_migration()
