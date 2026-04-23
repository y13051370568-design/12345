"""
用户相关的Pydantic Schema定义
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime


class UserRegister(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=50, description="密码")
    role: Optional[str] = Field("ZERO_BASIS", description="角色")

    @validator("username")
    def username_alphanumeric(cls, v):
        """验证用户名只包含字母、数字和下划线"""
        if not v.replace("_", "").isalnum():
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class UserOut(BaseModel):
    """用户基本信息输出"""
    id: int
    username: str
    role: str
    status: int
    api_token_limit: int
    api_token_used: int
    api_token_warning_threshold: int
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2 使用 from_attributes 替代 orm_mode


class UserInfo(BaseModel):
    """用户详细信息（包含权限等）"""
    id: int
    username: str
    role: str
    status: int
    api_token_limit: int
    api_token_used: int
    api_token_warning_threshold: int
    permissions: list = []  # 权限列表
    created_at: datetime

    class Config:
        from_attributes = True


class UserQuotaAdjust(BaseModel):
    """用户额度调整请求"""
    api_token_limit: Optional[int] = Field(None, ge=0, description="Token 额度上限")
    api_token_warning_threshold: Optional[int] = Field(None, ge=0, description="预警阈值")


class LoginResponse(BaseModel):
    """登录响应"""
    success: bool = True
    message: str = "登录成功"
    data: dict = Field(..., description="用户数据和Token")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "登录成功",
                "data": {
                    "user": {
                        "id": 1,
                        "username": "admin",
                        "role": "ADMIN",
                        "status": 1
                    },
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "redirect_route": "/admin/dashboard"
                }
            }
        }


class TokenPayload(BaseModel):
    """Token载荷"""
    user_id: int
    username: str
    role: str
    exp: Optional[datetime] = None