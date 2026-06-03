"""数据库切换功能测试脚本.

使用方式:
  python scripts/test_db_switch.py

功能:
  1. 测试 SQLite 连接
  2. 测试 MySQL 连接
  3. 测试数据写入和读取
  4. 验证配置切换
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Windows 控制台编码修复
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_config():
    """测试配置加载."""
    print("=" * 60)
    print("📋 测试 1: 配置加载")
    print("=" * 60)

    from app.config import settings

    print(f"  USE_SQLITE: {settings.use_sqlite}")
    print(f"  SQLITE_DB_PATH: {settings.sqlite_db_path}")
    print(f"  MYSQL_HOST: {settings.mysql_host}")
    print(f"  MYSQL_PORT: {settings.mysql_port}")
    print(f"  MYSQL_DATABASE: {settings.mysql_database}")
    print(f"  数据库 URL: {settings.database_url}")
    print("  ✅ 配置加载成功")
    return True


def test_sqlite_connection():
    """测试 SQLite 连接."""
    print("\n" + "=" * 60)
    print("📋 测试 2: SQLite 连接")
    print("=" * 60)

    import os
    # 临时设置为 SQLite
    os.environ["USE_SQLITE"] = "true"

    # 清除配置缓存
    from app.config import get_settings
    get_settings.cache_clear()

    from app.core.database import DatabaseManager

    db = DatabaseManager()
    try:
        db.connect()
        print(f"  数据库类型: {db.db_type}")

        # 测试写入
        with db.session() as sess:
            from app.core.sqlite import ChatMessage
            msg = ChatMessage(
                session_id="test-session",
                role="user",
                content="测试消息 - SQLite"
            )
            sess.add(msg)
            sess.flush()
            msg_id = msg.id
            print(f"  写入消息 ID: {msg_id}")

        # 测试读取
        with db.session() as sess:
            msg = sess.query(ChatMessage).filter(ChatMessage.id == msg_id).first()
            if msg:
                print(f"  读取消息: {msg.content}")
                # 清理测试数据
                sess.delete(msg)
                sess.flush()
                print("  ✅ SQLite 读写测试通过")
            else:
                print("  ❌ 读取失败")
                return False

        db.disconnect()
        return True
    except Exception as e:
        print(f"  ❌ SQLite 连接失败: {e}")
        return False


def test_mysql_connection():
    """测试 MySQL 连接."""
    print("\n" + "=" * 60)
    print("📋 测试 3: MySQL 连接")
    print("=" * 60)

    import os
    # 临时设置为 MySQL
    os.environ["USE_SQLITE"] = "false"

    # 清除配置缓存
    from app.config import get_settings
    get_settings.cache_clear()

    from app.core.database import DatabaseManager

    db = DatabaseManager()
    try:
        db.connect()
        print(f"  数据库类型: {db.db_type}")

        # 测试写入
        with db.session() as sess:
            from app.core.sqlite import ChatMessage
            msg = ChatMessage(
                session_id="test-session-mysql",
                role="user",
                content="测试消息 - MySQL"
            )
            sess.add(msg)
            sess.flush()
            msg_id = msg.id
            print(f"  写入消息 ID: {msg_id}")

        # 测试读取
        with db.session() as sess:
            msg = sess.query(ChatMessage).filter(ChatMessage.id == msg_id).first()
            if msg:
                print(f"  读取消息: {msg.content}")
                # 清理测试数据
                sess.delete(msg)
                sess.flush()
                print("  ✅ MySQL 读写测试通过")
            else:
                print("  ❌ 读取失败")
                return False

        db.disconnect()
        return True
    except Exception as e:
        print(f"  ❌ MySQL 连接失败: {e}")
        print(f"     请确保 MySQL 服务已启动，并检查 .env 配置")
        return False


def test_backward_compatibility():
    """测试向后兼容性."""
    print("\n" + "=" * 60)
    print("📋 测试 4: 向后兼容性")
    print("=" * 60)

    import os
    os.environ["USE_SQLITE"] = "true"

    from app.config import get_settings
    get_settings.cache_clear()

    try:
        # 测试旧的导入方式
        from app.core.sqlite import sqlite_manager
        print(f"  sqlite_manager 类型: {type(sqlite_manager).__name__}")

        # 测试 session 方法
        with sqlite_manager.session() as sess:
            from app.core.sqlite import ChatMessage
            count = sess.query(ChatMessage).count()
            print(f"  当前消息数: {count}")

        print("  ✅ 向后兼容性测试通过")
        return True
    except Exception as e:
        print(f"  ❌ 向后兼容性测试失败: {e}")
        return False


def test_database_url_property():
    """测试 database_url 属性."""
    print("\n" + "=" * 60)
    print("📋 测试 5: database_url 属性")
    print("=" * 60)

    from app.config import settings

    url = settings.database_url
    print(f"  当前数据库 URL: {url}")
    print(f"  USE_SQLITE: {settings.use_sqlite}")

    if settings.use_sqlite:
        assert url.startswith("sqlite:///"), "SQLite URL 格式错误"
        print("  ✅ SQLite URL 格式正确")
    else:
        assert url.startswith("mysql+pymysql://"), "MySQL URL 格式错误"
        print("  ✅ MySQL URL 格式正确")

    # 验证 URL 包含必要信息
    print(f"  ✅ database_url 属性测试通过")
    return True


def main():
    """运行所有测试."""
    print("\n" + "=" * 60)
    print("AgroAgentOS 数据库切换功能测试")
    print("=" * 60)

    results = []

    # 测试 1: 配置加载
    results.append(("配置加载", test_config()))

    # 测试 2: SQLite 连接
    results.append(("SQLite 连接", test_sqlite_connection()))

    # 测试 3: MySQL 连接
    results.append(("MySQL 连接", test_mysql_connection()))

    # 测试 4: 向后兼容性
    results.append(("向后兼容性", test_backward_compatibility()))

    # 测试 5: database_url 属性
    results.append(("database_url 属性", test_database_url_property()))

    # 汇总结果
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    passed = 0
    failed = 0
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1

    print(f"\n  总计: {passed} 通过, {failed} 失败")

    if failed > 0:
        print("\n⚠️  部分测试失败，请检查:")
        print("  1. MySQL 服务是否已启动")
        print("  2. .env 中的 MySQL 配置是否正确")
        print("  3. pymysql 是否已安装: pip install pymysql")
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过!")
        sys.exit(0)


if __name__ == "__main__":
    main()
