from sqlalchemy.orm import Session
from typing import List, Optional, Tuple, Dict
from datetime import datetime

from app.models.user import User
from app.models.quota_log import QuotaLog
from app.core.exceptions import BusinessException
from app.core.logger import logger

class QuotaService:
    """API 额度管理服务类"""

    @staticmethod
    def get_user_quota_info(db: Session, user_id: int) -> Dict:
        """获取用户额度详情"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessException("用户不存在")
        
        return {
            "api_token_limit": user.api_token_limit,
            "api_token_used": user.api_token_used,
            "api_token_warning_threshold": user.api_token_warning_threshold,
            "remaining": max(0, user.api_token_limit - user.api_token_used),
            "is_near_limit": user.api_token_used >= user.api_token_warning_threshold
        }

    @staticmethod
    def adjust_user_quota(
        db: Session, 
        user_id: int, 
        limit: Optional[int] = None, 
        threshold: Optional[int] = None
    ) -> User:
        """管理员调整用户额度配置"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessException("用户不存在")
        
        if limit is not None:
            user.api_token_limit = limit
        if threshold is not None:
            user.api_token_warning_threshold = threshold
            
        db.commit()
        db.refresh(user)
        logger.info(f"Quota adjusted for user {user_id}: limit={limit}, threshold={threshold}")
        return user

    @staticmethod
    def check_quota(db: Session, user_id: int, required_tokens: int = 0) -> Dict:
        """
        检查额度是否足够
        返回: {"allowed": bool, "warning": bool, "message": str}
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessException("用户不存在")
            
        if user.api_token_used + required_tokens > user.api_token_limit:
            return {
                "allowed": False, 
                "warning": True, 
                "message": f"API 额度不足。当前已用: {user.api_token_used}, 上限: {user.api_token_limit}"
            }
            
        is_near_limit = (user.api_token_used + required_tokens) >= user.api_token_warning_threshold
        
        return {
            "allowed": True, 
            "warning": is_near_limit, 
            "message": "预警：API 额度即将耗尽" if is_near_limit else "额度充足"
        }

    @staticmethod
    def consume_quota(
        db: Session, 
        user_id: int, 
        tokens: int, 
        action: str, 
        task_id: Optional[str] = None
    ) -> Dict:
        """消耗额度并记录日志"""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise BusinessException("用户不存在")
            
        # 即使超过限制也允许扣费（产生负数或超出），但通常在 check_quota 拦截
        user.api_token_used += tokens
        
        # 记录日志
        log = QuotaLog(
            user_id=user_id,
            tokens_consumed=tokens,
            action=action,
            task_id=task_id
        )
        db.add(log)
        db.commit()
        
        is_near_limit = user.api_token_used >= user.api_token_warning_threshold
        
        logger.info(f"User {user_id} consumed {tokens} tokens for {action}. Total used: {user.api_token_used}")
        
        return {
            "success": True,
            "tokens_consumed": tokens,
            "total_used": user.api_token_used,
            "warning": is_near_limit
        }

    @staticmethod
    def get_quota_logs(
        db: Session, 
        user_id: Optional[int] = None, 
        page: int = 1, 
        page_size: int = 20
    ) -> Tuple[int, List[QuotaLog]]:
        """查询消耗明细"""
        query = db.query(QuotaLog)
        if user_id:
            query = query.filter(QuotaLog.user_id == user_id)
            
        total = query.count()
        logs = query.order_by(QuotaLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
        
        return total, logs

# 全局实例
quota_service = QuotaService()
