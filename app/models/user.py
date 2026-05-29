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
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
