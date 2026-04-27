from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import json
import shutil
import zipfile

import pandas as pd
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import DataValidationException, FileUploadException, ResourceNotFoundException


UPLOAD_DIR = Path("uploads/agent/datasets")
DOWNLOAD_DIR = Path("uploads/agent/downloads")


def save_csv_upload(file: UploadFile, user_id: int) -> Dict[str, Any]:
    # 保存 CSV 并生成预览信息，供任务创建和前端数据预览复用。
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise FileUploadException("仅支持上传 CSV 文件")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename).name
    target_dir = UPLOAD_DIR / str(user_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    if target_path.exists():
        target_path = target_dir / f"{target_path.stem}_{pd.Timestamp.utcnow().strftime('%Y%m%d%H%M%S')}.csv"

    with target_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    file_size = target_path.stat().st_size
    if file_size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        target_path.unlink(missing_ok=True)
        raise FileUploadException(f"文件大小超过 {settings.MAX_UPLOAD_SIZE_MB}MB 限制")

    try:
        frame = pd.read_csv(target_path)
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise DataValidationException("CSV 文件解析失败，请检查编码、分隔符和表头", {"error": str(exc)})

    if frame.empty or not list(frame.columns):
        target_path.unlink(missing_ok=True)
        raise DataValidationException("CSV 文件为空或缺少表头")
    if len(frame) > settings.MAX_ROWS_PER_CSV:
        target_path.unlink(missing_ok=True)
        raise DataValidationException(f"CSV 行数超过 {settings.MAX_ROWS_PER_CSV} 行限制")

    preview = {
        "columns": [str(column) for column in frame.columns],
        "rows": json.loads(frame.head(10).to_json(orient="records", force_ascii=False)),
        "row_count": int(len(frame)),
        "file_size_kb": max(1, int(file_size / 1024)),
    }
    return {
        "name": safe_name,
        "file_path": str(target_path),
        "file_size_kb": preview["file_size_kb"],
        "row_count": preview["row_count"],
        "preview": preview,
    }


def read_json_artifact(path: str) -> Dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.exists():
        raise ResourceNotFoundException("报告文件不存在")
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def read_text_artifact(path: str) -> str:
    artifact_path = Path(path)
    if not artifact_path.exists():
        raise ResourceNotFoundException("代码文件不存在")
    return artifact_path.read_text(encoding="utf-8")


def make_task_zip(task_id: str, artifacts: Dict[str, Any]) -> Path:
    # 将当前任务的代码、报告等可读产物打包给开发者下载。
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DOWNLOAD_DIR / f"{task_id}_artifacts.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for key, value in artifacts.items():
            if not value or str(value).startswith("http"):
                continue
            artifact_path = Path(str(value))
            if artifact_path.exists() and artifact_path.is_file():
                archive.write(artifact_path, arcname=f"{key}_{artifact_path.name}")
    return zip_path
