from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey
from app.db import Base
from datetime import datetime

class QuotaLog(Base):
    __tablename__ = "quota_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    
    tokens_consumed = Column(Integer, nullable=False)
    action = Column(String(50))  # e.g., "task_execution", "upload", "manual_adjustment"
    task_id = Column(String(50), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
