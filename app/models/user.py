from sqlalchemy import Column, BigInteger, String, Integer, DateTime
from app.db import Base
from datetime import datetime

class User(Base):
    __tablename__ = "sys_user"

    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    role = Column(String(20), nullable=False, default="ZERO_BASIS")
    api_token_limit = Column(Integer, default=1000000)
    api_token_used = Column(Integer, default=0)

    status = Column(Integer, default=1)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

from pydantic import BaseModel
from datetime import datetime

class UserOut(BaseModel):
    id: int
    username: str
    role: str
    status: int
    created_at: datetime

    class Config:
        orm_mode = True