"""
开发者申请服务层：申请提交、审核、查询等业务逻辑
"""
from sqlalchemy.orm import Session
from typing import Tuple, List, Optional

from app.models.developer_application import DeveloperApplication
from app.models.user import User
from app.core.exceptions import (
    BusinessException,
    ResourceNotFoundException,
    DataValidationException,
)
from app.core.logger import logger


class DeveloperApplicationService:
    """开发者申请服务类"""

    VALID_ACTIONS = {"APPROVED", "REJECTED"}
    VALID_STATUSES = {"PENDING", "APPROVED", "REJECTED"}

    @staticmethod
    def submit_application(db: Session, user_id: int, reason: Optional[str] = None) -> DeveloperApplication:
        """
        零基础用户提交开发者申请

        Args:
            db: 数据库会话
            user_id: 申请人用户ID
            reason: 申请理由

        Returns:
            创建的申请记录

        Raises:
            DataValidationException: 用户已提交过待审核的申请
        """
        # 检查是否已有待审核的申请
        existing = (
            db.query(DeveloperApplication)
            .filter(DeveloperApplication.user_id == user_id)
            .filter(DeveloperApplication.status == "PENDING")
            .first()
        )
        if existing:
            raise DataValidationException("您已提交过开发者申请，请等待审核结果")

        application = DeveloperApplication(
            user_id=user_id,
            reason=reason,
            status="PENDING",
        )
        db.add(application)
        db.commit()
        db.refresh(application)

        logger.info(f"User {user_id} submitted developer application (id={application.id})")
        return application

    @staticmethod
    def get_user_application(db: Session, user_id: int) -> Optional[DeveloperApplication]:
        """
        查询用户最近的申请记录

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            最近的申请记录或None
        """
        return (
            db.query(DeveloperApplication)
            .filter(DeveloperApplication.user_id == user_id)
            .order_by(DeveloperApplication.created_at.desc())
            .first()
        )

    @staticmethod
    def get_application_list(
        db: Session,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None,
    ) -> Tuple[int, List[dict]]:
        """
        管理员获取申请列表

        Args:
            db: 数据库会话
            page: 页码
            page_size: 每页数量
            status: 筛选状态

        Returns:
            (总数, 列表)
        """
        query = (
            db.query(DeveloperApplication, User.username)
            .join(User, DeveloperApplication.user_id == User.id)
        )

        if status and status in DeveloperApplicationService.VALID_STATUSES:
            query = query.filter(DeveloperApplication.status == status)

        total = query.count()
        results = (
            query
            .order_by(DeveloperApplication.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = []
        for app, username in results:
            items.append({
                "id": app.id,
                "user_id": app.user_id,
                "username": username,
                "reason": app.reason,
                "status": app.status,
                "reviewed_by": app.reviewed_by,
                "review_comment": app.review_comment,
                "created_at": app.created_at,
                "updated_at": app.updated_at,
            })

        return total, items

    @staticmethod
    def review_application(
        db: Session,
        application_id: int,
        action: str,
        reviewer_id: int,
        review_comment: Optional[str] = None,
    ) -> DeveloperApplication:
        """
        管理员审核开发者申请

        Args:
            db: 数据库会话
            application_id: 申请ID
            action: 审核动作 (APPROVED/REJECTED)
            reviewer_id: 审核人ID
            review_comment: 审核意见

        Returns:
            更新后的申请记录

        Raises:
            ResourceNotFoundException: 申请不存在
            DataValidationException: 无效的审核动作或申请状态不正确
        """
        if action not in DeveloperApplicationService.VALID_ACTIONS:
            raise DataValidationException(f"无效的审核动作，允许: {', '.join(DeveloperApplicationService.VALID_ACTIONS)}")

        application = db.query(DeveloperApplication).filter(DeveloperApplication.id == application_id).first()
        if not application:
            raise ResourceNotFoundException("申请记录不存在")

        if application.status != "PENDING":
            raise DataValidationException("该申请已被审核，无法重复操作")

        # 更新申请状态
        application.status = action
        application.reviewed_by = reviewer_id
        if review_comment:
            application.review_comment = review_comment

        # 如果审核通过，更新用户角色为 DEVELOPER
        if action == "APPROVED":
            user = db.query(User).filter(User.id == application.user_id).first()
            if user:
                user.role = "DEVELOPER"
                logger.info(f"User {user.username} role changed from ZERO_BASIS to DEVELOPER")

        db.commit()
        db.refresh(application)

        logger.info(
            f"Application {application_id} reviewed by {reviewer_id}: {action}"
            + (f" (comment: {review_comment})" if review_comment else "")
        )
        return application


# 单例
developer_application_service = DeveloperApplicationService()
