"""
开发者申请相关的 Pydantic Schema 定义
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DeveloperApplyRequest(BaseModel):
    """零基础用户申请成为开发者的请求"""
    reason: Optional[str] = Field(None, max_length=500, description="申请理由")


class DeveloperApplicationOut(BaseModel):
    """开发者申请基本信息输出"""
    id: int
    user_id: int
    reason: Optional[str] = None
    status: str
    reviewed_by: Optional[int] = None
    review_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DeveloperApplicationListOut(BaseModel):
    """开发者申请列表输出（含申请人信息）"""
    id: int
    user_id: int
    username: str
    reason: Optional[str] = None
    status: str
    reviewed_by: Optional[int] = None
    review_comment: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ReviewApplicationRequest(BaseModel):
    """管理员审核开发者申请的请求"""
    action: str = Field(..., description="审核动作: APPROVED(通过), REJECTED(驳回)")
    review_comment: Optional[str] = Field(None, max_length=255, description="审核意见")
