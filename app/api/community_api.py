from fastapi import APIRouter, Depends, Query, Body, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Any, Dict

from app.db import get_db_session
from app.schemas.comment import CommentCreate, CommentOut
from app.schemas.dataset import DatasetOut
from app.schemas.ai_model import ModelOut
from app.schemas.agent import WorkflowOut, ApiResponse
from app.service.community_service import community_service
from app.core.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/community", tags=["社区资源与互动"])

@router.get("/resources", summary="检索社区资源 (数据集/模型/工作流)")
def list_resources(
    type: str = Query(..., description="资源类型: DATASET, MODEL, WORKFLOW"),
    category: Optional[str] = Query(None, description="分类过滤"),
    sort_by: str = Query("created_at", description="排序维度: created_at, heat, recommended"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db_session)
):
    """
    通用资源检索接口，支持按类型、分类、热度和时间筛选分页。
    """
    data = community_service.list_resources(db, type.upper(), category, sort_by, page, page_size, search)
    
    # 根据类型转换 items 为对应的 Schema
    items = data["items"]
    if type.upper() == "DATASET":
        data["items"] = [DatasetOut.model_validate(item) for item in items]
    elif type.upper() == "MODEL":
        data["items"] = [ModelOut.model_validate(item) for item in items]
    elif type.upper() == "WORKFLOW":
        data["items"] = [WorkflowOut.model_validate(item) for item in items]
        
    return ApiResponse(data=data)

@router.get("/resources/{type}/{resource_id}", summary="获取资源详情")
def get_resource_detail(
    type: str,
    resource_id: int,
    db: Session = Depends(get_db_session)
):
    """
    获取单一资源详情，并自动增加浏览量。
    """
    resource = community_service.get_resource_detail(db, type.upper(), resource_id)
    
    if type.upper() == "DATASET":
        return ApiResponse(data=DatasetOut.model_validate(resource))
    elif type.upper() == "MODEL":
        return ApiResponse(data=ModelOut.model_validate(resource))
    elif type.upper() == "WORKFLOW":
        return ApiResponse(data=WorkflowOut.model_validate(resource))
    
    return ApiResponse(data=resource)

@router.post("/comments", response_model=ApiResponse, summary="发表评论与评分")
def add_comment(
    comment_in: CommentCreate,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    对社区资源进行评分和文字评论。
    """
    comment = community_service.add_comment(db, comment_in, current_user.id)
    return ApiResponse(message="评论发表成功", data=CommentOut.model_validate(comment))

@router.get("/comments", summary="获取资源评论列表")
def list_comments(
    type: str = Query(..., description="资源类型"),
    resource_id: int = Query(..., description="资源ID"),
    db: Session = Depends(get_db_session)
):
    """
    获取指定资源的全部评论。
    """
    comments = community_service.list_comments(db, type.upper(), resource_id)
    return ApiResponse(data=comments)

@router.delete("/comments/{comment_id}", summary="删除评论")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    """
    删除自己的评论，管理员可删除任何评论。
    """
    is_admin = current_user.role == "ADMIN"
    community_service.delete_comment(db, comment_id, current_user.id, is_admin)
    return ApiResponse(message="评论已删除")
