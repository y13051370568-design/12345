from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class AIModelBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    is_public: bool = False
    resource_url: Optional[str] = None

class ModelCreate(AIModelBase):
    pass

class ModelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    is_public: Optional[bool] = None
    resource_url: Optional[str] = None

class ModelAudit(BaseModel):
    status: int  # 1: Approved, 2: Rejected, 4: Info Missing
    rejection_reason: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    is_recommended: Optional[bool] = None

class ModelOut(AIModelBase):
    id: int
    user_id: int
    status: int
    is_recommended: bool
    rejection_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AuditLogOut(BaseModel):
    id: int
    resource_type: str
    resource_id: int
    admin_id: int
    old_status: Optional[int]
    new_status: int
    action: str
    reason: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
