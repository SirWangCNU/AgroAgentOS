"""微信小程序 ↔ Web 账号绑定服务.

流程:
  1. Web 用户 (已登录) 调 POST /auth/wx-bind/init → 后端生成 6 位绑定码存 Redis
     TTL 5 分钟, key: wx_bind:{code} → value: {target_user_id, status}
  2. Web 前端展示绑定码, 并轮询 GET /auth/wx-bind/status?code=xxx
  3. 用户切到小程序 → 输入绑定码 → 调 POST /auth/wx-bind/confirm
     后端: 拿小程序当前用户的 openid → 写到目标 user_id 上 → 迁移历史数据 →
           更新 Redis 状态为 bound
  4. Web 轮询到 bound → 提示绑定成功
"""

import random
import string
from typing import Optional

from loguru import logger

from app.core.database import database_manager
from app.core.redis import redis_manager
from app.exceptions import BadRequestError, NotFoundError
from app.models.farm import Farm
from app.models.session import ChatSession
from app.models.user import User

_BIND_KEY_PREFIX = "wx_bind:"
_BIND_TTL_SEC = 300  # 5 分钟


def _gen_bind_code() -> str:
    """生成 6 位数字绑定码."""
    return "".join(random.choices(string.digits, k=6))


def create_bind_code(target_user_id: int) -> str:
    """为 Web 用户生成绑定码 (Redis 存 5 分钟).

    Args:
        target_user_id: 要绑定的 Web 用户 ID (即当前登录 Web 账号)

    Returns:
        6 位绑定码
    """
    # 重试最多 5 次避免碰撞
    for _ in range(5):
        code = _gen_bind_code()
        key = f"{_BIND_KEY_PREFIX}{code}"
        if not redis_manager.get(key):
            redis_manager.set(
                key,
                {"target_user_id": target_user_id, "status": "pending", "bound_user_id": None},
                expire=_BIND_TTL_SEC,
            )
            logger.info(f"生成绑定码 code={code} target_user_id={target_user_id}")
            return code
    raise BadRequestError(message="生成绑定码失败, 请重试")


def get_bind_status(code: str) -> dict:
    """查询绑定码状态 (Web 前端轮询用).

    Returns:
        { "status": "pending" | "bound" | "expired", "target_user_id": int | None }
    """
    key = f"{_BIND_KEY_PREFIX}{code}"
    data = redis_manager.get(key)
    if not data:
        return {"status": "expired", "target_user_id": None}
    return {
        "status": data.get("status", "pending"),
        "target_user_id": data.get("target_user_id"),
    }


def _migrate_wx_user_data(from_user_id: int, to_user_id: int) -> dict:
    """把匿名微信用户在业务表里产生的历史数据挂到 Web 账号名下.

    涉及表:
      - farms.user_id (int FK)
      - chat_sessions.user_id (str, 存的是 user_id 字符串形式)

    Returns:
        迁移统计: { "farms": N, "chat_sessions": N }
    """
    stats = {"farms": 0, "chat_sessions": 0}
    if from_user_id == to_user_id:
        return stats

    with database_manager.session() as sess:
        # 农场
        farms_updated = (
            sess.query(Farm)
            .filter(Farm.user_id == from_user_id)
            .update({"user_id": to_user_id}, synchronize_session=False)
        )
        stats["farms"] = int(farms_updated or 0)

        # 会话 (user_id 是字符串)
        chat_updated = (
            sess.query(ChatSession)
            .filter(ChatSession.user_id == str(from_user_id))
            .update({"user_id": str(to_user_id)}, synchronize_session=False)
        )
        stats["chat_sessions"] = int(chat_updated or 0)

    logger.info(
        f"数据迁移完成 from_user_id={from_user_id} to_user_id={to_user_id} stats={stats}"
    )
    return stats


def confirm_bind(
    code: str,
    wx_user_id: int,
    wx_openid: str,
    wx_unionid: Optional[str] = None,
) -> dict:
    """小程序端确认绑定.

    Args:
        code: Web 端拿到的绑定码
        wx_user_id: 当前微信用户在 users 表里的 id (通过 wx-login 拿到的 JWT sub)
        wx_openid: 当前微信用户的 openid
        wx_unionid: 可选 unionid

    Returns:
        { "target_user_id": int, "migrated": {...} }
    """
    key = f"{_BIND_KEY_PREFIX}{code}"
    data = redis_manager.get(key)
    if not data:
        raise BadRequestError(message="绑定码已过期或不存在, 请刷新 Web 端重新生成")
    if data.get("status") == "bound":
        raise BadRequestError(message="该绑定码已被使用")

    target_user_id = data["target_user_id"]

    # 先在同一事务里: 清空旧微信匿名账号的 openid → 再写目标账号, 避免唯一约束冲突
    with database_manager.session() as sess:
        target = sess.query(User).filter(User.id == target_user_id).first()
        if not target:
            raise NotFoundError(message="目标账号不存在")

        # 目标账号已经绑定过微信 → 拒绝重复绑定
        if target.wx_openid and target.wx_openid != wx_openid:
            raise BadRequestError(
                message=f"Web 账号 {target.username} 已经绑定了其他微信号, 请先解绑"
            )

        # 先释放旧微信匿名账号的 openid (必须在设置 target.wx_openid 之前, 否则唯一约束冲突)
        if wx_user_id != target_user_id:
            wx_user = sess.query(User).filter(User.id == wx_user_id).first()
            if wx_user and wx_user.username.startswith("wx_"):
                wx_user.wx_openid = None
                wx_user.wx_unionid = None

        # 再写入目标账号的绑定信息
        target.wx_openid = wx_openid
        if wx_unionid:
            target.wx_unionid = wx_unionid
        sess.flush()

    # 迁移数据 (wx_user_id → target_user_id)
    migrated = _migrate_wx_user_data(from_user_id=wx_user_id, to_user_id=target_user_id)

    # 软停用旧的微信匿名账号 (openid 已在上面清空, 这里只处理用户名和状态)
    if wx_user_id != target_user_id:
        with database_manager.session() as sess:
            wx_user = sess.query(User).filter(User.id == wx_user_id).first()
            if wx_user and wx_user.username.startswith("wx_"):
                wx_user.is_active = 0  # 软删除, 不真删避免外键悬空
                wx_user.username = f"{wx_user.username}_merged_{target_user_id}"
                sess.flush()

    # 更新 Redis 状态
    redis_manager.set(
        key,
        {"target_user_id": target_user_id, "status": "bound", "bound_user_id": wx_user_id},
        expire=60,  # 保留 1 分钟供 Web 轮询到最终状态
    )
    logger.info(
        f"绑定成功 code={code} web_user={target_user_id} wx_openid={wx_openid[:8]}..."
    )

    return {"target_user_id": target_user_id, "migrated": migrated}


def unbind_wx(user_id: int) -> None:
    """解绑当前 Web 账号的微信."""
    with database_manager.session() as sess:
        user = sess.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(message="用户不存在")
        if not user.wx_openid:
            raise BadRequestError(message="当前账号未绑定微信")
        user.wx_openid = None
        user.wx_unionid = None
        sess.flush()
        logger.info(f"解绑微信 user_id={user_id}")
