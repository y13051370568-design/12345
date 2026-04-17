from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.service.user_service import *
from app.schemas.user import UserOut#
from app.core.auth import admin_required

router = APIRouter()

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ✅ 用户列表（分页 + 筛选）
@router.get("/users")
def get_users(
        page: int = 1,
        page_size: int = 10,
        role: str = None,
        status: int = None,
        db: Session = Depends(get_db),
        admin=Depends(admin_required)
):
    total, users = get_user_list(db, page, page_size, role, status)

    return {
        "total": total,
        "list": [UserOut.from_orm(u) for u in users]
    }


# ✅ 修改角色
@router.put("/users/{user_id}/role")
def change_role(
        user_id: int,
        role: str,
        db: Session = Depends(get_db),
        admin=Depends(admin_required)
):
    update_user_role(db, user_id, role)
    return {"msg": "角色修改成功"}


# ✅ 启用/禁用
@router.put("/users/{user_id}/status")
def change_status(
        user_id: int,
        status: int,
        db: Session = Depends(get_db),
        admin=Depends(admin_required)
):
    toggle_user_status(db, user_id, status)
    return {"msg": "状态修改成功"}