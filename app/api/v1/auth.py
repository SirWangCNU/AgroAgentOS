"""认证 API 路由。"""

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, require_admin
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    AdminCreateUserRequest,
    AdminUpdateUserRequest,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
    UserListResponse,
    WxLoginRequest,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse)
def register(req: RegisterRequest) -> ApiResponse:
    """用户注册。"""
    if req.password != req.confirm_password:
        return ApiResponse.error(message="两次密码不一致")

    user = auth_service.register_user(req.username, req.email, req.password)
    return ApiResponse.success(
        data={"user_id": user.id, "username": user.username},
        message="注册成功",
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(req: LoginRequest) -> ApiResponse:
    """用户登录。"""
    user = auth_service.authenticate_user(req.username, req.password)
    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username, "role": user.role}
    )
    return ApiResponse.success(
        data=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserInfo.model_validate(user),
        ),
        message="登录成功",
    )


@router.get("/me", response_model=ApiResponse[UserInfo])
def get_me(current_user: User = Depends(get_current_user)) -> ApiResponse:
    """获取当前用户信息。"""
    return ApiResponse.success(data=UserInfo.model_validate(current_user))


@router.post("/wx-login", summary="微信小程序登录", response_model=ApiResponse[TokenResponse])
def wx_login(req: WxLoginRequest) -> ApiResponse:
    """通过微信临时登录凭证换取 JWT。"""
    access_token, user = auth_service.wx_login(req.code)
    return ApiResponse.success(
        data=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserInfo.model_validate(user),
        ),
        message="登录成功",
    )


@router.put("/password", response_model=ApiResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """修改密码。"""
    if req.new_password != req.confirm_password:
        return ApiResponse.error(message="两次密码不一致")
    auth_service.change_password(current_user.id, req.old_password, req.new_password)
    return ApiResponse.success(message="密码修改成功")


@router.get("/users", response_model=ApiResponse[UserListResponse])
def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """获取用户列表（管理员）。"""
    users, total = auth_service.list_users(page, page_size)
    return ApiResponse.success(
        data=UserListResponse(
            total=total,
            users=[UserInfo.model_validate(user) for user in users],
        )
    )


@router.post("/users", response_model=ApiResponse[UserInfo])
def create_user(
    req: AdminCreateUserRequest,
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """管理员创建用户。"""
    user = auth_service.admin_create_user(req.username, req.email, req.password, req.role)
    return ApiResponse.success(data=UserInfo.model_validate(user), message="用户创建成功")


@router.put("/users/{user_id}", response_model=ApiResponse[UserInfo])
def update_user(
    user_id: int,
    req: AdminUpdateUserRequest,
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """管理员更新用户。"""
    user = auth_service.admin_update_user(user_id, req.role, req.is_active)
    return ApiResponse.success(data=UserInfo.model_validate(user), message="用户更新成功")


@router.delete("/users/{user_id}", response_model=ApiResponse)
def disable_user(
    user_id: int,
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """管理员禁用用户（软删除）。"""
    auth_service.admin_update_user(user_id, is_active=False)
    return ApiResponse.success(message="用户已禁用")
