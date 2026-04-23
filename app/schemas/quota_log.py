from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class QuotaLogOut(BaseModel):
    id: int
    user_id: int
    tokens_consumed: int
    action: Optional[str]
    task_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
