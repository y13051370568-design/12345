"""
开发者申请 ORM 模型
"""
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey
from app.db import Base
from datetime import datetime


class DeveloperApplication(Base):
    __tablename__ = "developer_application"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, default=None)
    status = Column(String(20), nullable=False, default="PENDING")
    reviewed_by = Column(BigInteger, ForeignKey("sys_user.id", ondelete="SET NULL"), default=None)
    review_comment = Column(String(255), default=None)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
