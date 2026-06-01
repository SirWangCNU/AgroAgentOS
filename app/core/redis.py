"""Redis 连接管理.

职责:
  - 管理 Redis 连接池
  - 提供缓存操作封装（get/set/delete/exists）
  - 支持 JSON 序列化/反序列化
  - 连接健康检查

使用方式:
  from app.core.redis import redis_manager
  redis_manager.set("key", {"data": "value"}, expire=3600)
  value = redis_manager.get("key")
"""

from __future__ import annotations

import json
from typing import Any, Optional

import redis
from loguru import logger

from app.config import settings


class RedisManager:
    """Redis 连接管理器."""

    def __init__(self) -> None:
        self._client: redis.Redis | None = None

    def connect(self) -> None:
        """建立 Redis 连接."""
        try:
            self._client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
            )
            # 测试连接
            self._client.ping()
            logger.info(f"Redis 连接成功: {settings.redis_url}")
        except redis.ConnectionError as e:
            logger.warning(f"Redis 连接失败 (缓存功能不可用): {e}")
            self._client = None
        except Exception as e:
            logger.warning(f"Redis 初始化异常: {e}")
            self._client = None

    def disconnect(self) -> None:
        """关闭 Redis 连接."""
        if self._client:
            try:
                self._client.close()
                logger.info("Redis 连接已关闭")
            except Exception as e:
                logger.warning(f"Redis 关闭异常: {e}")
            finally:
                self._client = None

    def is_alive(self) -> bool:
        """检查 Redis 是否可用."""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    @property
    def client(self) -> redis.Redis | None:
        """获取 Redis 客户端实例."""
        return self._client

    # ==================== 缓存操作 ====================

    def get(self, key: str) -> Any | None:
        """获取缓存值（自动 JSON 反序列化）."""
        if not self._client:
            return None
        try:
            value = self._client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except json.JSONDecodeError:
            return value
        except Exception as e:
            logger.warning(f"Redis GET 失败 key={key}: {e}")
            return None

    def set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存值（自动 JSON 序列化）.

        Args:
            key: 缓存键
            value: 缓存值（将被 JSON 序列化）
            expire: 过期时间（秒），默认 1 小时
        """
        if not self._client:
            return False
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
            self._client.set(key, serialized, ex=expire)
            return True
        except Exception as e:
            logger.warning(f"Redis SET 失败 key={key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存."""
        if not self._client:
            return False
        try:
            self._client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis DELETE 失败 key={key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        """按模式删除缓存（如 field:1:*）.

        Args:
            pattern: 匹配模式

        Returns:
            删除的键数量
        """
        if not self._client:
            return 0
        try:
            keys = self._client.keys(pattern)
            if keys:
                return self._client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning(f"Redis DELETE_PATTERN 失败 pattern={pattern}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        """检查缓存是否存在."""
        if not self._client:
            return False
        try:
            return bool(self._client.exists(key))
        except Exception as e:
            logger.warning(f"Redis EXISTS 失败 key={key}: {e}")
            return False

    def expire(self, key: str, seconds: int) -> bool:
        """设置缓存过期时间."""
        if not self._client:
            return False
        try:
            return bool(self._client.expire(key, seconds))
        except Exception as e:
            logger.warning(f"Redis EXPIRE 失败 key={key}: {e}")
            return False

    def incr(self, key: str) -> int | None:
        """原子递增."""
        if not self._client:
            return None
        try:
            return self._client.incr(key)
        except Exception as e:
            logger.warning(f"Redis INCR 失败 key={key}: {e}")
            return None

    # ==================== 缓存键生成 ====================

    @staticmethod
    def trajectory_list_key(field_id: int) -> str:
        """生成轨迹列表缓存键."""
        return f"trajectory:list:field:{field_id}"

    @staticmethod
    def trajectory_points_key(file_id: int) -> str:
        """生成轨迹点缓存键."""
        return f"trajectory:points:file:{file_id}"

    @staticmethod
    def trajectory_stats_key(file_id: int) -> str:
        """生成轨迹统计缓存键."""
        return f"trajectory:stats:file:{file_id}"

    @staticmethod
    def trajectory_file_key(file_id: int) -> str:
        """生成轨迹文件元数据缓存键."""
        return f"trajectory:file:{file_id}"


# 全局单例
redis_manager = RedisManager()
