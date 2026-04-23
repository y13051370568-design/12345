from sqlalchemy.orm import Session
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from app.models.dataset import Dataset
from app.models.audit_log import AuditLog
from app.schemas.dataset import DatasetCreate, DatasetUpdate, DatasetAudit
from app.core.exceptions import BusinessException
from app.core.logger import logger

class DatasetService:
    """数据集管理服务类"""

    @staticmethod
    def create_dataset(db: Session, dataset_in: DatasetCreate, user_id: int) -> Dataset:
        """用户分享数据集"""
        new_dataset = Dataset(
            user_id=user_id,
            name=dataset_in.name,
            description=dataset_in.description,
            category=dataset_in.category,
            tags=dataset_in.tags,
            is_public=dataset_in.is_public,
            file_url=dataset_in.file_url,
            file_size=dataset_in.file_size,
            row_count=dataset_in.row_count,
            status=0  # Pending
        )
        db.add(new_dataset)
        db.commit()
        db.refresh(new_dataset)
        logger.info(f"User {user_id} shared dataset: {new_dataset.name} (ID: {new_dataset.id})")
        return new_dataset

    @staticmethod
    def get_dataset_by_id(db: Session, dataset_id: int) -> Optional[Dataset]:
        """通过ID获取数据集"""
        return db.query(Dataset).filter(Dataset.id == dataset_id).first()

    @staticmethod
    def list_datasets(
        db: Session, 
        status: Optional[int] = None, 
        is_public: Optional[bool] = None,
        user_id: Optional[int] = None,
        category: Optional[str] = None
    ) -> List[Dataset]:
        """获取数据集列表"""
        query = db.query(Dataset)
        if status is not None:
            query = query.filter(Dataset.status == status)
        if is_public is not None:
            query = query.filter(Dataset.is_public == is_public)
        if user_id is not None:
            query = query.filter(Dataset.user_id == user_id)
        if category:
            query = query.filter(Dataset.category == category)
        
        return query.order_by(Dataset.created_at.desc()).all()

    @staticmethod
    def audit_dataset(db: Session, dataset_id: int, audit_in: DatasetAudit, admin_id: int) -> Dataset:
        """管理员审核数据集"""
        dataset = DatasetService.get_dataset_by_id(db, dataset_id)
        if not dataset:
            raise BusinessException("数据集不存在")
        
        old_status = dataset.status
        dataset.status = audit_in.status
        if audit_in.rejection_reason:
            dataset.rejection_reason = audit_in.rejection_reason
        if audit_in.category:
            dataset.category = audit_in.category
        if audit_in.tags:
            dataset.tags = audit_in.tags
            
        action = "audit"
        if audit_in.status == 1:
            action = "approve"
        elif audit_in.status == 2:
            action = "reject"
        elif audit_in.status == 4:
            action = "info_request"
            
        audit_log = AuditLog(
            resource_type="dataset",
            resource_id=dataset_id,
            admin_id=admin_id,
            old_status=old_status,
            new_status=dataset.status,
            action=action,
            reason=audit_in.rejection_reason
        )
        db.add(audit_log)
        
        db.commit()
        db.refresh(dataset)
        logger.info(f"Admin {admin_id} audited dataset {dataset_id}: {old_status} -> {dataset.status}")
        return dataset

    @staticmethod
    def take_down_dataset(db: Session, dataset_id: int, admin_id: int, reason: str) -> Dataset:
        """数据集下架"""
        dataset = DatasetService.get_dataset_by_id(db, dataset_id)
        if not dataset:
            raise BusinessException("数据集不存在")
            
        old_status = dataset.status
        dataset.status = 3  # Off-shelf
        
        audit_log = AuditLog(
            resource_type="dataset",
            resource_id=dataset_id,
            admin_id=admin_id,
            old_status=old_status,
            new_status=3,
            action="take-down",
            reason=reason
        )
        db.add(audit_log)
        db.commit()
        db.refresh(dataset)
        logger.info(f"Admin {admin_id} took down dataset {dataset_id}")
        return dataset

    @staticmethod
    def get_audit_logs(db: Session, dataset_id: int) -> List[AuditLog]:
        """获取审核记录"""
        return db.query(AuditLog).filter(
            AuditLog.resource_type == "dataset",
            AuditLog.resource_id == dataset_id
        ).order_by(AuditLog.created_at.desc()).all()

# 全局实例
dataset_service = DatasetService()
