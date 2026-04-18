from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import os
import uuid
from datetime import datetime

from app.db import SessionLocal
from app.core.config import settings
from app.core.auth import get_current_user
from app.core.logger import logger

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
    current_user = Depends(get_current_user)
):
    """
    上传CSV文件

    - **file**: CSV文件（最大100MB）
    """
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

    return {
        "success": True,
        "message": "文件上传成功",
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