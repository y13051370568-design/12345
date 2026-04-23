from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_db_session
from app.schemas.dataset import DatasetCreate, DatasetUpdate, DatasetAudit, DatasetOut
from app.schemas.ai_model import AuditLogOut
from app.service.dataset_service import dataset_service
from app.core.auth import get_current_user, admin_required
from app.models.user import User

router = APIRouter(prefix="/datasets", tags=["数据中心审核与管理"])

@router.post("/", response_model=DatasetOut)
def create_dataset(
    dataset_in: DatasetCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """分享新数据集"""
    return dataset_service.create_dataset(db, dataset_in, current_user.id)

@router.get("/", response_model=List[DatasetOut])
def list_public_datasets(
    category: Optional[str] = Query(None, description="分类过滤"),
    db: Session = Depends(get_db_session)
):
    """获取公开展示的数据集列表 (仅限已审核通过且设为公开)"""
    return dataset_service.list_datasets(db, status=1, is_public=True, category=category)

@router.get("/my", response_model=List[DatasetOut])
def list_my_datasets(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """获取我分享的数据集列表"""
    return dataset_service.list_datasets(db, user_id=current_user.id)

@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(
    dataset_id: int,
    db: Session = Depends(get_db_session)
):
    """获取数据集详情"""
    dataset = dataset_service.get_dataset_by_id(db, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return dataset

# 管理员接口
@router.get("/admin/all", response_model=List[DatasetOut])
def admin_list_all_datasets(
    status: Optional[int] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员获取所有数据集列表"""
    return dataset_service.list_datasets(db, status=status)

@router.post("/{dataset_id}/audit", response_model=DatasetOut)
def audit_dataset(
    dataset_id: int,
    audit_in: DatasetAudit,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员审核数据集 (通过、驳回、分类、打标签、补充材料提示)"""
    return dataset_service.audit_dataset(db, dataset_id, audit_in, admin.id)

@router.post("/{dataset_id}/take-down", response_model=DatasetOut)
def take_down_dataset(
    dataset_id: int,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员下架数据集"""
    return dataset_service.take_down_dataset(db, dataset_id, admin.id, reason)

@router.get("/{dataset_id}/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(
    dataset_id: int,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """获取数据集审核记录和状态变更历史"""
    return dataset_service.get_audit_logs(db, dataset_id)
