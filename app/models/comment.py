from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base
from datetime import datetime

class Comment(Base):
    __tablename__ = "community_comment"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    resource_id = Column(BigInteger, nullable=False)
    resource_type = Column(String(20), nullable=False)  # DATASET, MODEL, WORKFLOW
    rating = Column(Integer, nullable=False)  # 1-5
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", backref="comments")
