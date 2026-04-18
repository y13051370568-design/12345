"""
安全模块：JWT Token生成与验证、密码加密
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.logger import logger


# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordHandler:
    """密码加密与验证工具类"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        加密密码

        Args:
            password: 明文密码

        Returns:
            加密后的密码哈希
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        验证密码

        Args:
            plain_password: 明文密码
            hashed_password: 加密后的密码哈希

        Returns:
            密码是否匹配
        """
        return pwd_context.verify(plain_password, hashed_password)


class JWTHandler:
    """JWT Token生成与验证工具类"""

    @staticmethod
    def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        生成访问令牌

        Args:
            data: 要编码到token中的数据（通常包含user_id, username, role等）
            expires_delta: 过期时间增量，默认使用配置中的值

        Returns:
            JWT访问令牌字符串
        """
        to_encode = data.copy()

        # 设置过期时间
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),  # 签发时间
            "type": "access"
        })

        # 生成JWT
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        logger.debug(f"Created access token for user: {data.get('username')}")
        return encoded_jwt

    @staticmethod
    def create_refresh_token(data: Dict) -> str:
        """
        生成刷新令牌（有效期更长）

        Args:
            data: 要编码的数据

        Returns:
            JWT刷新令牌字符串
        """
        to_encode = data.copy()

        # 刷新令牌有效期设为7天
        expire = datetime.utcnow() + timedelta(days=7)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

        return encoded_jwt

    @staticmethod
    def decode_token(token: str) -> Optional[Dict]:
        """
        解码并验证JWT令牌

        Args:
            token: JWT令牌字符串

        Returns:
            解码后的payload数据，验证失败返回None
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode error: {str(e)}")
            return None

    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict]:
        """
        验证令牌并返回payload

        Args:
            token: JWT令牌
            token_type: 令牌类型（access或refresh）

        Returns:
            验证成功返回payload，失败返回None
        """
        payload = JWTHandler.decode_token(token)

        if payload is None:
            return None

        # 验证令牌类型
        if payload.get("type") != token_type:
            logger.warning(f"Token type mismatch: expected {token_type}, got {payload.get('type')}")
            return None

        # 验证必需字段
        if "user_id" not in payload:
            logger.warning("Token missing user_id")
            return None

        return payload


# 全局实例
password_handler = PasswordHandler()
jwt_handler = JWTHandler()
