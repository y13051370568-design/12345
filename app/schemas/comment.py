from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class CommentBase(BaseModel):
    resource_id: int
    resource_type: str  # DATASET, MODEL, WORKFLOW
    rating: int
    content: Optional[str] = None

class CommentCreate(CommentBase):
    pass

class CommentOut(CommentBase):
    id: int
    user_id: int
    username: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
