from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.db import SessionLocal
from app.service.user_service import *
from app.schemas.user import UserOut
from app.core.auth import admin_required

router = APIRouter(prefix="/admin", tags=["管理员"])

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class RoleUpdate(BaseModel):
    role: str


class StatusUpdate(BaseModel):
    status: int


@router.get("/users")
def get_users(
        page: int = 1,
        page_size: int = 10,
        username: str = None,
        role: str = None,
        status: int = None,
        db: Session = Depends(get_db),
        admin=Depends(admin_required)
):
    total, users = get_user_list(db, page, page_size, role, status, username)
    return {
        "total": total,
        "list": [UserOut.from_orm(u) for u in users]
    }


@router.put("/users/{user_id}/role")
def change_role(
        user_id: int,
        role_data: RoleUpdate,
        db: Session = Depends(get_db),
        admin=Depends(admin_required)
):
    update_user_role(db, user_id, role_data.role)
    return {"msg": "角色修改成功"}


@router.patch("/users/{user_id}/status")
def change_status(
        user_id: int,
        status_data: StatusUpdate,
        db: Session = Depends(get_db),
        admin=Depends(admin_required)
):
    toggle_user_status(db, user_id, status_data.status)
    return {"msg": "状态修改成功"}