from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DatasetBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    is_public: bool = False
    file_url: Optional[str] = None

class DatasetCreate(DatasetBase):
    file_size: Optional[int] = None
    row_count: Optional[int] = None

class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    is_public: Optional[bool] = None
    file_url: Optional[str] = None

class DatasetAudit(BaseModel):
    status: int  # 1: Approved, 2: Rejected, 4: Info Missing
    rejection_reason: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None

class DatasetOut(DatasetBase):
    id: int
    user_id: int
    status: int
    rejection_reason: Optional[str] = None
    file_size: Optional[int]
    row_count: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
