"""认证相关的 Pydantic 模型。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    confirm_password: str = Field(..., description="确认密码")


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class WxLoginRequest(BaseModel):
    """微信小程序登录请求。"""

    code: str = Field(..., description="wx.login 返回的临时登录凭证 code")


class ChangePasswordRequest(BaseModel):
    """修改密码请求。"""

    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=128, description="新密码")
    confirm_password: str = Field(..., description="确认新密码")


class AdminCreateUserRequest(BaseModel):
    """管理员创建用户请求。"""

    username: str = Field(..., min_length=3, max_length=64, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    role: str = Field(default="user", description="角色：admin / user")


class AdminUpdateUserRequest(BaseModel):
    """管理员更新用户请求。"""

    role: Optional[str] = Field(None, description="角色：admin / user")
    is_active: Optional[bool] = Field(None, description="是否启用")


class UserInfo(BaseModel):
    """用户信息。"""

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    wx_openid: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """登录成功响应。"""

    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class UserListResponse(BaseModel):
    """用户列表响应。"""

    total: int
    users: list[UserInfo]
