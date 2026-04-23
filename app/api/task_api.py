from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime

from app.db import SessionLocal
from app.core.config import settings
from app.core.auth import get_current_user
from app.core.logger import logger
from app.service.quota_service import quota_service

router = APIRouter(prefix="/tasks", tags=["任务中心"])

UPLOAD_DIR = "uploads/csv"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/upload")
async def upload_csv(
    file: UploadFile = File(...),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    上传CSV文件

    - **file**: CSV文件（最大100MB）
    """
    # 1. 额度检查 (上传操作预扣或检查)
    quota_check = quota_service.check_quota(db, current_user.id, required_tokens=100)  # 假设上传消耗100 tokens
    if not quota_check["allowed"]:
        raise HTTPException(status_code=402, detail=quota_check["message"])

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="仅支持CSV文件")


    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件大小超过{settings.MAX_UPLOAD_SIZE_MB}MB限制")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_id = str(uuid.uuid4())
    filename = f"{file_id}_{file.filename}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    row_count = len(content.decode("utf-8").splitlines())

    if row_count > settings.MAX_ROWS_PER_CSV:
        os.remove(filepath)
        raise HTTPException(status_code=400, detail=f"CSV行数超过{settings.MAX_ROWS_PER_CSV}行限制")

    logger.info(f"User {current_user.username} uploaded file: {file.filename}, {row_count} rows")

    # 3. 额度消耗记录
    consumption = quota_service.consume_quota(
        db, current_user.id, tokens=100, action="file_upload", task_id=file_id
    )

    return {
        "success": True,
        "message": "文件上传成功",
        "warning": consumption["warning"],
        "data": {
            "file_id": file_id,
            "filename": file.filename,
            "size": len(content),
            "rows": row_count,
            "upload_time": datetime.now().isoformat()
        }
    }


@router.get("/list")
def list_tasks(
    page: int = 1,
    page_size: int = 10,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的上传任务列表"""
    return {
        "total": 0,
        "list": []
    }