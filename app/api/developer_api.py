"""
开发者申请 API 路由
提供零基础用户申请成为开发者、管理员审核申请等功能
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db_session
from app.core.auth import get_current_user, admin_required, require_roles

zero_basis_required = require_roles(["ZERO_BASIS"])
from app.schemas.developer_application import (
    DeveloperApplyRequest,
    DeveloperApplicationOut,
    ReviewApplicationRequest,
)
from app.service.developer_application_service import developer_application_service

router = APIRouter(tags=["开发者申请"])


# ---------- 零基础用户端 ----------

@router.post("/developer/apply", response_model=DeveloperApplicationOut, summary="申请成为开发者")
def apply_for_developer(
    body: DeveloperApplyRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(zero_basis_required),
):
    """
    零基础用户提交开发者申请

    需登录，仅 ZERO_BASIS 角色可操作。
    - **reason**: 申请理由（可选，最多500字）
    """
    application = developer_application_service.submit_application(
        db=db,
        user_id=current_user.id,
        reason=body.reason,
    )
    return DeveloperApplicationOut.model_validate(application)


@router.get("/developer/application/me", summary="查看我的开发者申请")
def get_my_application(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    查看当前用户最近的开发者申请记录及审核状态
    """
    application = developer_application_service.get_user_application(
        db=db,
        user_id=current_user.id,
    )
    if not application:
        return {"has_application": False, "application": None}

    return {
        "has_application": True,
        "application": DeveloperApplicationOut.model_validate(application),
    }


# ---------- 管理员端 ----------

admin_router = APIRouter(prefix="/admin", tags=["管理员-开发者申请审核"])


@admin_router.get("/developer/applications", summary="获取开发者申请列表")
def list_applications(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页数量"),
    status: str = Query(None, description="筛选状态: PENDING, APPROVED, REJECTED"),
    db: Session = Depends(get_db_session),
    admin=Depends(admin_required),
):
    """
    管理员分页查看开发者申请列表，支持按状态筛选
    """
    total, items = developer_application_service.get_application_list(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
    )
    return {"total": total, "list": items}


@admin_router.put("/developer/applications/{application_id}/review", summary="审核开发者申请")
def review_application(
    application_id: int,
    body: ReviewApplicationRequest,
    db: Session = Depends(get_db_session),
    admin=Depends(admin_required),
):
    """
    管理员审核开发者申请

    - **action**: APPROVED（通过）或 REJECTED（驳回）
    - **review_comment**: 审核意见（可选）
    - 通过后自动将用户角色变更为 DEVELOPER
    """
    application = developer_application_service.review_application(
        db=db,
        application_id=application_id,
        action=body.action,
        reviewer_id=admin.id,
        review_comment=body.review_comment,
    )
    return {
        "msg": "审核完成",
        "application": DeveloperApplicationOut.model_validate(application),
    }
