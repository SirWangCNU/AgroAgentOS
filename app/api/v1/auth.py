"""认证 API 路由."""

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
    WxBindConfirmRequest,
    WxLoginRequest,
)
from app.schemas.common import ApiResponse
from app.services import auth_service, wx_bind_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=ApiResponse)
def register(req: RegisterRequest) -> ApiResponse:
    """用户注册."""
    if req.password != req.confirm_password:
        return ApiResponse.error(message="两次密码不一致")

    user = auth_service.register_user(req.username, req.email, req.password)
    return ApiResponse.success(
        data={"user_id": user.id, "username": user.username},
        message="注册成功",
    )


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(req: LoginRequest) -> ApiResponse:
    """用户登录."""
    user = auth_service.authenticate_user(req.username, req.password)

    # 生成 JWT token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "username": user.username,
            "role": user.role,
        }
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
    """获取当前用户信息."""
    return ApiResponse.success(data=UserInfo.model_validate(current_user))


@router.post("/wx-login", summary="微信小程序登录", response_model=ApiResponse[TokenResponse])
def wx_login(req: WxLoginRequest) -> ApiResponse:
    """微信小程序登录.

    小程序通过 wx.login() 获取临时 code, 调用本接口换取 JWT token。
    服务端用 code 调微信 code2Session 得到 openid, 自动创建/匹配用户并签发 token。
    """
    access_token, user = auth_service.wx_login(req.code)
    return ApiResponse.success(
        data=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserInfo.model_validate(user),
        ),
        message="登录成功",
    )


# ==================== 微信 ↔ Web 账号绑定 ====================


@router.post("/wx-bind/init", response_model=ApiResponse, summary="Web 端: 生成微信绑定码")
def wx_bind_init(current_user: User = Depends(get_current_user)) -> ApiResponse:
    """已登录 Web 用户调用, 后端生成一个 6 位绑定码 (Redis 存 5 分钟)."""
    if current_user.wx_openid:
        return ApiResponse.error(
            code="ALREADY_BOUND",
            message=f"当前账号已绑定微信, 请先解绑",
        )
    code = wx_bind_service.create_bind_code(current_user.id)
    return ApiResponse.success(data={"bind_code": code, "expires_in": 300})


@router.get("/wx-bind/status", response_model=ApiResponse, summary="Web 端: 轮询绑定状态")
def wx_bind_status(
    code: str = Query(..., min_length=6, max_length=6, description="绑定码"),
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """Web 前端轮询: pending / bound / expired."""
    return ApiResponse.success(data=wx_bind_service.get_bind_status(code))


@router.post("/wx-bind/confirm", response_model=ApiResponse[TokenResponse], summary="小程序端: 确认绑定")
def wx_bind_confirm(
    req: WxBindConfirmRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """小程序端调用: 输入 Web 端拿到的绑定码后, 把当前微信身份写到 Web 账号上.

    调用成功后, 后端会:
      1. 把 wx_openid 挂到 Web 账号上
      2. 迁移当前匿名微信账号的历史数据 (农场/会话) 到 Web 账号
      3. 停用旧匿名微信账号
      4. 重新签发 Web 账号的 JWT 返回, 小程序应立即替换本地 token
    """
    if not current_user.wx_openid:
        return ApiResponse.error(code="NOT_WX_USER", message="当前会话不是微信用户")

    result = wx_bind_service.confirm_bind(
        code=req.bind_code,
        wx_user_id=current_user.id,
        wx_openid=current_user.wx_openid,
        wx_unionid=current_user.wx_unionid,
    )
    target_user_id = result["target_user_id"]

    # 重新为 Web 账号签发 JWT (小程序换 token, 后续以 Web 账号身份操作)
    from app.services.auth_service import get_user_by_id
    target = get_user_by_id(target_user_id)
    access_token = create_access_token(
        data={"sub": str(target.id), "username": target.username, "role": target.role}
    )
    return ApiResponse.success(
        data=TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserInfo.model_validate(target),
        ),
        message=f"绑定成功, 已迁移 {result['migrated']['farms']} 个农场 / {result['migrated']['chat_sessions']} 个会话",
    )


@router.delete("/wx-bind", response_model=ApiResponse, summary="Web 端: 解绑微信")
def wx_unbind(current_user: User = Depends(get_current_user)) -> ApiResponse:
    """Web 端解除当前账号的微信绑定 (不影响历史数据)."""
    wx_bind_service.unbind_wx(current_user.id)
    return ApiResponse.success(message="已解绑微信")


@router.put("/password", response_model=ApiResponse)
def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """修改密码."""
    if req.new_password != req.confirm_password:
        return ApiResponse.error(message="两次密码不一致")

    auth_service.change_password(current_user.id, req.old_password, req.new_password)
    return ApiResponse.success(message="密码修改成功")


# ==================== 管理员接口 ====================


@router.get("/users", response_model=ApiResponse[UserListResponse])
def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """获取用户列表 (管理员)."""
    users, total = auth_service.list_users(page, page_size)
    return ApiResponse.success(
        data=UserListResponse(
            total=total,
            users=[UserInfo.model_validate(u) for u in users],
        )
    )


@router.post("/users", response_model=ApiResponse[UserInfo])
def create_user(
    req: AdminCreateUserRequest,
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """管理员创建用户."""
    user = auth_service.admin_create_user(req.username, req.email, req.password, req.role)
    return ApiResponse.success(
        data=UserInfo.model_validate(user),
        message="用户创建成功",
    )


@router.put("/users/{user_id}", response_model=ApiResponse[UserInfo])
def update_user(
    user_id: int,
    req: AdminUpdateUserRequest,
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """管理员更新用户."""
    user = auth_service.admin_update_user(user_id, req.role, req.is_active)
    return ApiResponse.success(
        data=UserInfo.model_validate(user),
        message="用户更新成功",
    )


@router.delete("/users/{user_id}", response_model=ApiResponse)
def disable_user(
    user_id: int,
    current_user: User = Depends(require_admin),
) -> ApiResponse:
    """管理员禁用用户 (软删除)."""
    auth_service.admin_update_user(user_id, is_active=False)
    return ApiResponse.success(message="用户已禁用")
