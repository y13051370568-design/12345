from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db import get_db_session
from app.schemas.ai_model import ModelCreate, ModelUpdate, ModelAudit, ModelOut, AuditLogOut
from app.service.model_service import model_service
from app.core.auth import get_current_user, admin_required
from app.models.user import User

router = APIRouter(prefix="/models", tags=["模型广场管理"])

@router.post("/", response_model=ModelOut)
def create_model(
    model_in: ModelCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """发布新模型"""
    return model_service.create_model(db, model_in, current_user.id)

@router.get("/", response_model=List[ModelOut])
def list_public_models(
    category: Optional[str] = Query(None, description="分类过滤"),
    db: Session = Depends(get_db_session)
):
    """获取公开展示的模型列表 (仅限已审核通过且设为公开的模型)"""
    return model_service.list_models(db, status=1, is_public=True, category=category)

@router.get("/my", response_model=List[ModelOut])
def list_my_models(
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """获取我发布的模型列表"""
    return model_service.list_models(db, user_id=current_user.id)

@router.get("/{model_id}", response_model=ModelOut)
def get_model(
    model_id: int,
    db: Session = Depends(get_db_session)
):
    """获取模型详情"""
    model = model_service.get_model_by_id(db, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    return model

@router.put("/{model_id}", response_model=ModelOut)
def update_model(
    model_id: int,
    model_in: ModelUpdate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """更新自己的模型"""
    return model_service.update_model(db, model_id, model_in, current_user.id)

# 管理员接口
@router.get("/admin/all", response_model=List[ModelOut])
def admin_list_all_models(
    status: Optional[int] = Query(None, description="状态过滤"),
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员获取所有模型列表"""
    return model_service.list_models(db, status=status)

@router.post("/{model_id}/audit", response_model=ModelOut)
def audit_model(
    model_id: int,
    audit_in: ModelAudit,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员审核模型 (通过、驳回、分类、打标签、推荐、补充材料提示)"""
    return model_service.audit_model(db, model_id, audit_in, admin.id)

@router.post("/{model_id}/take-down", response_model=ModelOut)
def take_down_model(
    model_id: int,
    reason: str = Body(..., embed=True),
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员下架模型"""
    return model_service.take_down_model(db, model_id, admin.id, reason)

@router.put("/{model_id}/admin", response_model=ModelOut)
def update_model_admin(
    model_id: int,
    model_in: ModelUpdate,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员修改模型信息 (分类、标签等)"""
    return model_service.update_model_admin(db, model_id, model_in)

@router.post("/{model_id}/publish", response_model=ModelOut)
def republish_model(
    model_id: int,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """管理员重新上架模型"""
    return model_service.republish_model(db, model_id, admin.id)

@router.get("/{model_id}/audit-logs", response_model=List[AuditLogOut])
def get_audit_logs(
    model_id: int,
    db: Session = Depends(get_db_session),
    admin: User = Depends(admin_required)
):
    """获取模型审核记录和状态变更历史"""
    return model_service.get_audit_logs(db, model_id)
