"""用户 ORM 模型."""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.core.sqlite import Base


class User(Base):
    """用户表."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(128), unique=True, nullable=False, index=True)
    hashed_password = Column(String(256), nullable=False)
    role = Column(String(32), nullable=False, default="user")  # "admin" | "user"
    is_active = Column(Integer, nullable=False, default=1)  # 1=启用, 0=禁用
    # 微信小程序绑定信息 (由 006 迁移新增)
    wx_openid = Column(String(128), unique=True, nullable=True, index=True)
    wx_unionid = Column(String(128), nullable=True, index=True)
    nickname = Column(String(64), nullable=True)  # 微信昵称或自定义显示名
    avatar_url = Column(String(512), nullable=True)  # 头像 URL
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
