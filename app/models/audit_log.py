from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey
from app.db import Base
from datetime import datetime

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, index=True)
    resource_type = Column(String(20), nullable=False)  # "model", "dataset", "workflow"
    resource_id = Column(BigInteger, nullable=False)
    admin_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    
    old_status = Column(String(50))
    new_status = Column(String(50))
    
    action = Column(String(50))
    reason = Column(String(255))
    
    created_at = Column(DateTime, default=datetime.utcnow)
