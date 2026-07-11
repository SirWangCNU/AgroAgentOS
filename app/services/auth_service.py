"""认证业务逻辑服务."""

import httpx
from loguru import logger

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
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


def get_or_create_wx_user(openid: str, unionid: str | None = None) -> User:
    """根据微信 openid 查找或创建小程序用户.

    优先级:
      1. wx_openid 字段命中 (已绑定用户或已初始化过的微信用户) → 直接复用
      2. 兼容旧数据: username = wx_{openid} → 回填 wx_openid 字段后返回
      3. 都没有 → 新建匿名微信账号 (username = wx_{openid}, wx_openid = openid)

    Args:
        openid: 微信用户唯一标识
        unionid: 微信开放平台 unionid (可选)

    Returns:
        对应的 User 对象
    """
    # 1) 按 openid 精确匹配 (绑定后 / 二次登录走这里)
    with sqlite_manager.session() as sess:
        user = sess.query(User).filter(User.wx_openid == openid).first()
        if user:
            # 顺便回填 unionid
            if unionid and not user.wx_unionid:
                user.wx_unionid = unionid
                sess.flush()
            sess.expunge(user)
            return user

    # 2) 兼容旧数据: 之前用 username = wx_{openid} 存的匿名用户
    wx_username = f"wx_{openid}"
    existing = get_user_by_username(wx_username)
    if existing:
        with sqlite_manager.session() as sess:
            existing = sess.query(User).filter(User.username == wx_username).first()
            if existing and not existing.wx_openid:
                existing.wx_openid = openid
                if unionid:
                    existing.wx_unionid = unionid
                sess.flush()
                sess.expunge(existing)
                logger.info(f"回填旧微信用户 openid: {wx_username}")
                return existing
            if existing:
                sess.expunge(existing)
                return existing

    # 3) 全新用户
    with sqlite_manager.session() as sess:
        user = User(
            username=wx_username,
            email=f"{wx_username}@wx.miniapp",
            hashed_password=hash_password(openid),
            role="user",
            is_active=1,
            wx_openid=openid,
            wx_unionid=unionid,
        )
        sess.add(user)
        sess.flush()
        sess.expunge(user)
        logger.info(f"微信小程序用户首次登录, 已创建账号: {wx_username}")
        return user


def wx_code2session(code: str) -> tuple[str, str | None]:
    """调用微信 code2Session 接口, 用登录 code 换取 openid.

    Args:
        code: wx.login 返回的临时登录凭证

    Returns:
        (openid, unionid)

    Raises:
        BadRequestError: 微信接口返回错误
    """
    if not settings.wx_appid or not settings.wx_secret:
        raise BadRequestError(message="服务端未配置微信小程序 AppID/Secret")

    resp = httpx.get(
        settings.wx_code2session_url,
        params={
            "appid": settings.wx_appid,
            "secret": settings.wx_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=10.0,
    )
    data = resp.json()
    if "errcode" in data and data["errcode"] != 0:
        logger.error(f"微信 code2Session 失败: {data}")
        raise BadRequestError(message=f"微信登录失败: {data.get('errmsg', '未知错误')}")

    openid = data.get("openid")
    if not openid:
        raise BadRequestError(message="微信登录未返回 openid")
    return openid, data.get("unionid")


def wx_login(code: str) -> tuple[str, User]:
    """微信小程序登录, 返回 (JWT token, 用户对象).

    Args:
        code: wx.login 返回的临时登录凭证

    Returns:
        (access_token, user)
    """
    openid, unionid = wx_code2session(code)
    user = get_or_create_wx_user(openid, unionid)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role}
    )
    return access_token, user


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
