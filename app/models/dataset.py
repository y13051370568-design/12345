from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db import Base
from datetime import datetime

class Dataset(Base):
    __tablename__ = "ml_datasets"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    category = Column(String(50))
    tags = Column(String(255))
    
    # Status: 0: Pending, 1: Approved, 2: Rejected, 3: Off-shelf, 4: Info Missing
    status = Column(Integer, default=0)
    
    is_public = Column(Boolean, default=False)
    
    rejection_reason = Column(String(255))
    file_url = Column(String(255))
    file_size = Column(BigInteger)  # in bytes
    row_count = Column(Integer)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", backref="datasets")
