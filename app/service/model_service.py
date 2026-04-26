from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import datetime

from app.models.ai_model import AIModel
from app.models.audit_log import AuditLog
from app.schemas.ai_model import ModelCreate, ModelUpdate, ModelAudit
from app.core.exceptions import BusinessException, DataValidationException
from app.core.logger import logger

class ModelService:
    """模型管理服务类"""

    @staticmethod
    def create_model(db: Session, model_in: ModelCreate, user_id: int) -> AIModel:
        """用户发布模型"""
        new_model = AIModel(
            user_id=user_id,
            name=model_in.name,
            description=model_in.description,
            category=model_in.category,
            tags=model_in.tags,
            is_public=model_in.is_public,
            resource_url=model_in.resource_url,
            status=0  # Pending
        )
        db.add(new_model)
        db.commit()
        db.refresh(new_model)
        logger.info(f"User {user_id} published model: {new_model.name} (ID: {new_model.id})")
        return new_model

    @staticmethod
    def get_model_by_id(db: Session, model_id: int) -> Optional[AIModel]:
        """通过ID获取模型"""
        return db.query(AIModel).filter(AIModel.id == model_id).first()

    @staticmethod
    def update_model(db: Session, model_id: int, model_in: ModelUpdate, user_id: int) -> AIModel:
        """用户更新自己的模型"""
        model = ModelService.get_model_by_id(db, model_id)
        if not model:
            raise BusinessException("模型不存在")
        if model.user_id != user_id:
            raise BusinessException("无权修改他人模型")
        
        update_data = model_in.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(model, field, value)
        
        # 如果模型之前被驳回或要求补全，更新后可能需要重新进入待审核状态
        if model.status in [2, 4]:
            model.status = 0
            
        db.commit()
        db.refresh(model)
        return model

    @staticmethod
    def list_models(
        db: Session, 
        status: Optional[int] = None, 
        is_public: Optional[bool] = None,
        user_id: Optional[int] = None,
        category: Optional[str] = None
    ) -> List[AIModel]:
        """获取模型列表"""
        query = db.query(AIModel)
        if status is not None:
            query = query.filter(AIModel.status == status)
        if is_public is not None:
            query = query.filter(AIModel.is_public == is_public)
        if user_id is not None:
            query = query.filter(AIModel.user_id == user_id)
        if category:
            query = query.filter(AIModel.category == category)
        
        return query.order_by(AIModel.created_at.desc()).all()

    @staticmethod
    def audit_model(db: Session, model_id: int, audit_in: ModelAudit, admin_id: int) -> AIModel:
        """管理员审核模型"""
        model = ModelService.get_model_by_id(db, model_id)
        if not model:
            raise BusinessException("模型不存在")
        
        old_status = model.status
        model.status = audit_in.status
        if audit_in.rejection_reason:
            model.rejection_reason = audit_in.rejection_reason
        if audit_in.category:
            model.category = audit_in.category
        if audit_in.tags:
            model.tags = audit_in.tags
        if audit_in.is_recommended is not None:
            model.is_recommended = audit_in.is_recommended
            
        # 记录审计日志
        action = "audit"
        if audit_in.status == 1:
            action = "approve"
        elif audit_in.status == 2:
            action = "reject"
        elif audit_in.status == 4:
            action = "info_request"
            
        audit_log = AuditLog(
            resource_type="model",
            resource_id=model_id,
            admin_id=admin_id,
            old_status=old_status,
            new_status=model.status,
            action=action,
            reason=audit_in.rejection_reason
        )
        db.add(audit_log)
        
        db.commit()
        db.refresh(model)
        logger.info(f"Admin {admin_id} audited model {model_id}: {old_status} -> {model.status}")
        return model

    @staticmethod
    def take_down_model(db: Session, model_id: int, admin_id: int, reason: str) -> AIModel:
        """下架处理"""
        model = ModelService.get_model_by_id(db, model_id)
        if not model:
            raise BusinessException("模型不存在")
            
        old_status = model.status
        model.status = 3  # Off-shelf
        
        audit_log = AuditLog(
            resource_type="model",
            resource_id=model_id,
            admin_id=admin_id,
            old_status=old_status,
            new_status=3,
            action="take-down",
            reason=reason
        )
        db.add(audit_log)
        db.commit()
        db.refresh(model)
        logger.info(f"Admin {admin_id} took down model {model_id}")
        return model

    @staticmethod
    def update_model_admin(db: Session, model_id: int, model_in: ModelUpdate) -> AIModel:
        """管理员更新模型信息（如修改分类、标签）"""
        model = ModelService.get_model_by_id(db, model_id)
        if not model:
            raise BusinessException("模型不存在")
        
        update_data = model_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(model, field, value)
            
        db.commit()
        db.refresh(model)
        logger.info(f"Admin updated model {model_id}")
        return model

    @staticmethod
    def republish_model(db: Session, model_id: int, admin_id: int) -> AIModel:
        """重新上架模型"""
        model = ModelService.get_model_by_id(db, model_id)
        if not model:
            raise BusinessException("模型不存在")
            
        old_status = model.status
        model.status = 1  # Approved/Public
        
        audit_log = AuditLog(
            resource_type="model",
            resource_id=model_id,
            admin_id=admin_id,
            old_status=old_status,
            new_status=1,
            action="re-publish"
        )
        db.add(audit_log)
        db.commit()
        db.refresh(model)
        logger.info(f"Admin {admin_id} re-published model {model_id}")
        return model

    @staticmethod
    def get_audit_logs(db: Session, model_id: int) -> List[AuditLog]:
        """获取审核记录"""
        return db.query(AuditLog).filter(
            AuditLog.resource_type == "model",
            AuditLog.resource_id == model_id
        ).order_by(AuditLog.created_at.desc()).all()

# 全局实例
model_service = ModelService()
