"""FastAPI 依赖注入."""

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_access_token
from app.core.sqlite import sqlite_manager
from app.exceptions import AuthenticationError, ForbiddenError
from app.models.user import User

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """获取当前认证用户.

    从 Authorization: Bearer <token> 头提取 token，解码后从数据库查用户。

    Returns:
        当前用户对象

    Raises:
        AuthenticationError: token 无效或用户不存在
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError(message="无效的 token")

    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise AuthenticationError(message="用户不存在")
        if not user.is_active:
            raise AuthenticationError(message="账号已禁用")
        sess.expunge(user)
        return user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """要求管理员权限.

    Returns:
        管理员用户对象

    Raises:
        ForbiddenError: 非管理员
    """
    if current_user.role != "admin":
        raise ForbiddenError(message="需要管理员权限")
    return current_user
