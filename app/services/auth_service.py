"""认证业务逻辑服务."""

from loguru import logger

from app.config import settings
from app.core.security import hash_password, verify_password
from app.core.sqlite import sqlite_manager
from app.exceptions import (
    BadRequestError,
    EmailAlreadyExistsError,
    NotFoundError,
    UsernameAlreadyExistsError,
)
from app.models.user import User


def register_user(username: str, email: str, password: str) -> User:
    """用户注册.

    Args:
        username: 用户名
        email: 邮箱
        password: 密码

    Returns:
        创建的用户对象

    Raises:
        UsernameAlreadyExistsError: 用户名已存在
        EmailAlreadyExistsError: 邮箱已存在
    """
    with sqlite_manager.session() as sess:
        # 检查用户名是否已存在
        existing = sess.query(User).filter(User.username == username).first()
        if existing:
            raise UsernameAlreadyExistsError()

        # 检查邮箱是否已存在
        existing = sess.query(User).filter(User.email == email).first()
        if existing:
            raise EmailAlreadyExistsError()

        # 创建用户
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role="user",
            is_active=1,
        )
        sess.add(user)
        sess.flush()
        sess.expunge(user)
        logger.info(f"用户注册成功: {username}")
        return user


def authenticate_user(username: str, password: str) -> User:
    """用户认证.

    Args:
        username: 用户名
        password: 密码

    Returns:
        认证成功的用户对象

    Raises:
        NotFoundError: 用户名或密码错误
        BadRequestError: 账号已禁用
    """
    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.username == username).first()
        if not user or not verify_password(password, user.hashed_password):
            raise NotFoundError(message="用户名或密码错误")

        if not user.is_active:
            raise BadRequestError(message="账号已禁用，请联系管理员")

        sess.expunge(user)
        return user


def get_user_by_id(user_id: int) -> User | None:
    """根据 ID 获取用户."""
    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.id == user_id).first()
        if user:
            sess.expunge(user)
        return user


def get_user_by_username(username: str) -> User | None:
    """根据用户名获取用户."""
    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.username == username).first()
        if user:
            sess.expunge(user)
        return user


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """修改密码.

    Args:
        user_id: 用户 ID
        old_password: 旧密码
        new_password: 新密码

    Returns:
        是否修改成功

    Raises:
        NotFoundError: 用户不存在
        BadRequestError: 旧密码错误
    """
    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(message="用户不存在")

        if not verify_password(old_password, user.hashed_password):
            raise BadRequestError(message="旧密码错误")

        user.hashed_password = hash_password(new_password)
        sess.flush()
        logger.info(f"用户 {user.username} 修改密码成功")
        return True


def list_users(page: int = 1, page_size: int = 20) -> tuple[list[User], int]:
    """获取用户列表 (管理员).

    Args:
        page: 页码
        page_size: 每页数量

    Returns:
        (用户列表, 总数)
    """
    with sqlite_manager.session() as sess:
        query = sess.query(User)
        total = query.count()
        offset = (page - 1) * page_size
        users = (
            query.order_by(User.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        for user in users:
            sess.expunge(user)
        return users, total


def admin_create_user(
    username: str,
    email: str,
    password: str,
    role: str = "user",
) -> User:
    """管理员创建用户.

    Args:
        username: 用户名
        email: 邮箱
        password: 密码
        role: 角色

    Returns:
        创建的用户对象
    """
    with sqlite_manager.session() as sess:
        # 检查用户名是否已存在
        existing = sess.query(User).filter(User.username == username).first()
        if existing:
            raise UsernameAlreadyExistsError()

        # 检查邮箱是否已存在
        existing = sess.query(User).filter(User.email == email).first()
        if existing:
            raise EmailAlreadyExistsError()

        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=role,
            is_active=1,
        )
        sess.add(user)
        sess.flush()
        sess.expunge(user)
        logger.info(f"管理员创建用户: {username}, 角色: {role}")
        return user


def admin_update_user(
    user_id: int,
    role: str | None = None,
    is_active: bool | None = None,
) -> User:
    """管理员更新用户.

    Args:
        user_id: 用户 ID
        role: 新角色
        is_active: 是否启用

    Returns:
        更新后的用户对象
    """
    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.id == user_id).first()
        if not user:
            raise NotFoundError(message="用户不存在")

        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = 1 if is_active else 0

        sess.flush()
        sess.expunge(user)
        logger.info(f"管理员更新用户 {user_id}: role={role}, is_active={is_active}")
        return user


def ensure_admin_exists() -> None:
    """确保管理员账号存在.

    在应用启动时调用，如果 admin 账号不存在则创建。
    """
    admin = get_user_by_username("admin")
    if admin:
        logger.info("管理员账号已存在")
        return

    with sqlite_manager.session() as sess:
        user = User(
            username="admin",
            email="admin@agro.com",
            hashed_password=hash_password(settings.admin_default_password),
            role="admin",
            is_active=1,
        )
        sess.add(user)
        sess.flush()
        logger.info("管理员账号已创建: admin")
