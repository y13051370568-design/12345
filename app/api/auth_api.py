"""
认证相关API路由：登录、注册、Token刷新、获取当前用户信息
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.schemas.user import (
    UserRegister,
    UserLogin,
    UserOut,
    UserInfo,
    LoginResponse
)
from app.service.auth_service import auth_service
from app.core.auth import get_current_user, get_current_active_user
from app.core.logger import logger


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=UserOut, summary="用户注册")
def register(
    user_data: UserRegister,
    db: Session = Depends(get_db_session)
):
    """
    用户注册接口

    - **username**: 用户名（3-50个字符，只能包含字母、数字和下划线）
    - **password**: 密码（6-50个字符）
    - **role**: 角色（可选，默认为ZERO_BASIS）
      - ZERO_BASIS: 零基础用户
      - DEVELOPER: AI开发者
      - ADMIN: 管理员
    """
    user = auth_service.register_user(
        db=db,
        username=user_data.username,
        password=user_data.password,
        role=user_data.role
    )

    return UserOut.from_orm(user)


@router.post("/login", summary="用户登录")
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db_session)
):
    """
    用户登录接口

    返回数据包含：
    - **user**: 用户基本信息
    - **access_token**: 访问令牌（有效期30分钟）
    - **refresh_token**: 刷新令牌（有效期7天）
    - **token_type**: 令牌类型（bearer）
    - **redirect_route**: 登录后跳转路由
    - **permissions**: 用户权限列表
    """
    login_result = auth_service.login(
        db=db,
        username=login_data.username,
        password=login_data.password
    )

    logger.info(f"User login: {login_data.username}")

    return {
        "success": True,
        "message": "登录成功",
        "data": login_result
    }


@router.post("/refresh", summary="刷新访问令牌")
def refresh_token(refresh_token: str):
    """
    使用刷新令牌获取新的访问令牌

    - **refresh_token**: 刷新令牌字符串
    """
    result = auth_service.refresh_access_token(refresh_token)

    return {
        "success": True,
        "message": "令牌刷新成功",
        "data": result
    }


@router.get("/me", response_model=UserInfo, summary="获取当前用户信息")
def get_current_user_info(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db_session)
):
    """
    获取当前登录用户的详细信息

    需要在请求头中携带Token：
    ```
    Authorization: Bearer <access_token>
    ```
    """
    permissions = auth_service.get_role_permissions(current_user.role)

    return UserInfo(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role,
        status=current_user.status,
        api_token_limit=current_user.api_token_limit,
        api_token_used=current_user.api_token_used,
        api_token_warning_threshold=current_user.api_token_warning_threshold,
        permissions=permissions,
        created_at=current_user.created_at
    )


@router.post("/logout", summary="用户登出")
def logout(current_user = Depends(get_current_user)):
    """
    用户登出接口

    注意：JWT是无状态的，真正的登出需要前端删除Token。
    此接口主要用于记录登出日志。
    """
    logger.info(f"User logout: {current_user.username}")

    return {
        "success": True,
        "message": "登出成功"
    }


@router.get("/permissions", summary="获取当前用户权限列表")
def get_permissions(current_user = Depends(get_current_user)):
    """
    获取当前用户的权限列表
    """
    permissions = auth_service.get_role_permissions(current_user.role)

    return {
        "success": True,
        "data": {
            "role": current_user.role,
            "permissions": permissions
        }
    }


@router.get("/routes", summary="获取角色对应的前端路由")
def get_routes(current_user = Depends(get_current_user)):
    """
    获取当前用户角色对应的前端路由配置

    用于前端根据角色动态生成菜单和路由
    """
    redirect_route = auth_service.get_redirect_route(current_user.role)

    # 根据角色返回可访问的路由列表
    routes_mapping = {
        "ZERO_BASIS": [
            {"path": "/tasks", "name": "任务中心", "icon": "task"},
            {"path": "/community", "name": "社区资源", "icon": "community"},
            {"path": "/profile", "name": "个人中心", "icon": "user"},
        ],
        "DEVELOPER": [
            {"path": "/developer", "name": "开发者工作台", "icon": "code"},
            {"path": "/tasks", "name": "任务中心", "icon": "task"},
            {"path": "/workflows", "name": "我的工作流", "icon": "workflow"},
            {"path": "/community", "name": "社区资源", "icon": "community"},
            {"path": "/profile", "name": "个人中心", "icon": "user"},
        ],
        "ADMIN": [
            {"path": "/admin/dashboard", "name": "控制台", "icon": "dashboard"},
            {"path": "/admin/users", "name": "用户管理", "icon": "users"},
            {"path": "/admin/audit", "name": "资源审核", "icon": "audit"},
            {"path": "/admin/monitor", "name": "系统监控", "icon": "monitor"},
        ]
    }

    return {
        "success": True,
        "data": {
            "redirect_route": redirect_route,
            "routes": routes_mapping.get(current_user.role, [])
        }
    }
