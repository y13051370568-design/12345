"""
认证服务层：用户登录、注册、Token生成等业务逻辑
"""
from sqlalchemy.orm import Session
from typing import Optional, Dict

from app.models.user import User
from app.core.security import password_handler, jwt_handler
from app.core.exceptions import (
    AuthenticationException,
    DataValidationException,
    BusinessException
)
from app.core.logger import logger


class AuthService:
    """认证服务类"""

    @staticmethod
    def register_user(db: Session, username: str, password: str, role: str = "ZERO_BASIS") -> User:
        """
        用户注册

        Args:
            db: 数据库会话
            username: 用户名
            password: 明文密码
            role: 用户角色

        Returns:
            新创建的用户对象

        Raises:
            DataValidationException: 用户名已存在
        """
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            logger.warning(f"Registration failed: username '{username}' already exists")
            raise DataValidationException(f"用户名 '{username}' 已被使用")

        # 验证角色
        valid_roles = ["ZERO_BASIS", "DEVELOPER", "ADMIN"]
        if role not in valid_roles:
            raise DataValidationException(f"无效的角色，允许的角色: {', '.join(valid_roles)}")

        # 加密密码
        hashed_password = password_handler.hash_password(password)

        # 创建用户
        new_user = User(
            username=username,
            password_hash=hashed_password,
            role=role,
            status=1,  # 默认启用
            api_token_limit=1000000,  # 默认配额
            api_token_used=0
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"User registered successfully: {username} (role: {role})")
        return new_user

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
        """
        验证用户凭证

        Args:
            db: 数据库会话
            username: 用户名
            password: 明文密码

        Returns:
            验证成功返回用户对象，失败返回None
        """
        # 查询用户
        user = db.query(User).filter(User.username == username).first()

        if not user:
            logger.warning(f"Authentication failed: user '{username}' not found")
            return None

        # 验证密码
        if not password_handler.verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: invalid password for user '{username}'")
            return None

        # 检查用户状态
        if user.status != 1:
            logger.warning(f"Authentication failed: user '{username}' is disabled")
            return None

        logger.info(f"User authenticated successfully: {username}")
        return user

    @staticmethod
    def login(db: Session, username: str, password: str) -> Dict:
        """
        用户登录

        Args:
            db: 数据库会话
            username: 用户名
            password: 密码

        Returns:
            包含用户信息和Token的字典

        Raises:
            AuthenticationException: 认证失败
        """
        # 验证用户
        user = AuthService.authenticate_user(db, username, password)

        if not user:
            raise AuthenticationException("用户名或密码错误")

        # 生成Token
        token_data = {
            "user_id": user.id,
            "username": user.username,
            "role": user.role
        }

        access_token = jwt_handler.create_access_token(token_data)
        refresh_token = jwt_handler.create_refresh_token(token_data)

        # 获取跳转路由
        redirect_route = AuthService.get_redirect_route(user.role)

        return {
            "user": {
                "id": user.id,
                "username": user.username,
                "role": user.role,
                "status": user.status,
                "api_token_limit": user.api_token_limit,
                "api_token_used": user.api_token_used,
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "redirect_route": redirect_route,
            "permissions": AuthService.get_role_permissions(user.role)
        }

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """
        根据ID获取用户

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            用户对象或None
        """
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_redirect_route(role: str) -> str:
        """
        根据角色返回登录后的跳转路由

        Args:
            role: 用户角色

        Returns:
            前端路由路径
        """
        route_mapping = {
            "ZERO_BASIS": "/tasks",  # 零基础用户 -> 任务中心
            "DEVELOPER": "/developer",  # 开发者 -> 开发者工作台
            "ADMIN": "/admin/dashboard"  # 管理员 -> 管理后台
        }
        return route_mapping.get(role, "/")

    @staticmethod
    def get_role_permissions(role: str) -> list:
        """
        根据角色返回权限列表

        Args:
            role: 用户角色

        Returns:
            权限标识列表
        """
        permission_mapping = {
            "ZERO_BASIS": [
                "task:create",  # 创建任务
                "task:view",    # 查看自己的任务
                "task:execute", # 执行任务
                "community:view",  # 浏览社区资源
                "community:comment",  # 评论资源
            ],
            "DEVELOPER": [
                "task:create",
                "task:view",
                "task:execute",
                "task:intervene",  # 人机协同干预
                "task:code_edit",  # 编辑代码
                "task:download",   # 下载代码
                "community:view",
                "community:comment",
                "workflow:create",  # 创建工作流
                "workflow:fork",    # Fork工作流
                "workflow:publish", # 发布工作流
            ],
            "ADMIN": [
                "admin:all",  # 管理员拥有所有权限
                "user:manage",  # 用户管理
                "quota:manage",  # 配额管理
                "audit:manage",  # 资源审核
                "monitor:view",  # 监控查看
            ]
        }
        return permission_mapping.get(role, [])

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict:
        """
        使用刷新令牌生成新的访问令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            包含新访问令牌的字典

        Raises:
            AuthenticationException: 刷新令牌无效
        """
        # 验证刷新令牌
        payload = jwt_handler.verify_token(refresh_token, token_type="refresh")

        if not payload:
            raise AuthenticationException("刷新令牌无效或已过期")

        # 生成新的访问令牌
        token_data = {
            "user_id": payload["user_id"],
            "username": payload["username"],
            "role": payload["role"]
        }

        new_access_token = jwt_handler.create_access_token(token_data)

        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }


# 全局服务实例
auth_service = AuthService()
