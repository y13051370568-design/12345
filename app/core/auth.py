"""
认证依赖：JWT Token验证、用户身份获取、权限验证
"""
from typing import Optional, List
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.core.security import jwt_handler
from app.service.auth_service import auth_service
from app.core.exceptions import AuthenticationException, AuthorizationException
from app.core.logger import logger


# HTTPBearer安全方案
security = HTTPBearer()


def get_token_from_header(
    authorization: Optional[str] = Header(None)
) -> Optional[str]:
    """
    从请求头中提取Token

    Args:
        authorization: Authorization请求头

    Returns:
        Token字符串或None
    """
    if not authorization:
        return None

    # 支持 "Bearer <token>" 格式
    if authorization.startswith("Bearer "):
        return authorization[7:]

    return authorization


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db_session)
):
    """
    获取当前登录用户（依赖注入）

    Args:
        credentials: HTTP Bearer凭证
        db: 数据库会话

    Returns:
        当前用户对象

    Raises:
        AuthenticationException: Token无效或用户不存在
    """
    token = credentials.credentials

    # 验证Token
    payload = jwt_handler.verify_token(token, token_type="access")

    if not payload:
        logger.warning("Invalid or expired token")
        raise AuthenticationException("Token无效或已过期，请重新登录")

    user_id = payload.get("user_id")

    # 获取用户信息
    user = auth_service.get_user_by_id(db, user_id)

    if not user:
        logger.warning(f"User not found: user_id={user_id}")
        raise AuthenticationException("用户不存在")

    # 检查用户状态
    if user.status != 1:
        logger.warning(f"User disabled: {user.username}")
        raise AuthenticationException("用户已被禁用")

    return user


async def get_current_active_user(
    current_user = Depends(get_current_user)
):
    """
    获取当前活跃用户（已验证状态）

    Args:
        current_user: 当前用户

    Returns:
        当前用户对象
    """
    return current_user


def require_roles(allowed_roles: List[str]):
    """
    角色权限验证装饰器工厂

    Args:
        allowed_roles: 允许的角色列表

    Returns:
        权限验证依赖函数
    """
    async def role_checker(current_user = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            logger.warning(
                f"Permission denied: user '{current_user.username}' "
                f"(role: {current_user.role}) tried to access resource "
                f"requiring roles: {allowed_roles}"
            )
            raise AuthorizationException(
                f"需要以下角色之一: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker


def require_permissions(required_permissions: List[str]):
    """
    权限验证装饰器工厂

    Args:
        required_permissions: 需要的权限列表

    Returns:
        权限验证依赖函数
    """
    async def permission_checker(current_user = Depends(get_current_user)):
        user_permissions = auth_service.get_role_permissions(current_user.role)

        # 管理员拥有所有权限
        if "admin:all" in user_permissions:
            return current_user

        # 检查是否拥有所需权限
        missing_permissions = [
            perm for perm in required_permissions
            if perm not in user_permissions
        ]

        if missing_permissions:
            logger.warning(
                f"Permission denied: user '{current_user.username}' "
                f"missing permissions: {missing_permissions}"
            )
            raise AuthorizationException(
                f"缺少权限: {', '.join(missing_permissions)}"
            )

        return current_user

    return permission_checker


# 常用的权限验证依赖
admin_required = require_roles(["ADMIN"])
developer_required = require_roles(["DEVELOPER", "ADMIN"])
user_or_developer = require_roles(["ZERO_BASIS", "DEVELOPER", "ADMIN"])


# 可选的当前用户（不强制登录）
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db_session)
):
    """
    获取当前用户（可选，未登录返回None）

    Args:
        credentials: HTTP Bearer凭证
        db: 数据库会话

    Returns:
        当前用户对象或None
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, db)
    except Exception:
        return None