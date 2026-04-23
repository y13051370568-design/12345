from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_db_session
from app.schemas.user import UserQuotaAdjust, UserOut
from app.schemas.quota_log import QuotaLogOut
from app.service.quota_service import quota_service
from app.core.auth import get_current_user, admin_required
from app.models.user import User

router = APIRouter(prefix="/quota", tags=["API 额度管理"])

@router.get("/me")
def get_my_quota(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """用户查看自己的额度信息"""
    return quota_service.get_user_quota_info(db, current_user.id)

# 管理员接口
@router.put("/admin/adjust/{user_id}", response_model=UserOut)
def adjust_user_quota(
    user_id: int,
    quota_in: UserQuotaAdjust,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员调整用户额度配置"""
    return quota_service.adjust_user_quota(
        db, 
        user_id, 
        limit=quota_in.api_token_limit, 
        threshold=quota_in.api_token_warning_threshold
    )

@router.get("/admin/logs")
def list_quota_logs(
    user_id: Optional[int] = Query(None, description="按用户ID过滤"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员查看消耗明细和记录"""
    total, logs = quota_service.get_quota_logs(db, user_id, page, page_size)
    return {
        "total": total,
        "items": [QuotaLogOut.from_attributes(log) for log in logs]
    }
