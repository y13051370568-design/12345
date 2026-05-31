from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional, Any, Dict
from datetime import datetime

from app.models.dataset import Dataset
from app.models.ai_model import AIModel
from app.models.agent import AgentWorkflow
from app.models.comment import Comment
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentOut
from app.core.exceptions import BusinessException

class CommunityService:
    """社区资源中心服务类"""

    @staticmethod
    def list_resources(
        db: Session,
        resource_type: str,  # DATASET, MODEL, WORKFLOW
        category: Optional[str] = None,
        sort_by: str = "created_at",  # created_at, heat (view_count + fork_count/rating)
        page: int = 1,
        page_size: int = 10,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """展示与检索社区资源"""
        if resource_type == "DATASET":
            model_class = Dataset
        elif resource_type == "MODEL":
            model_class = AIModel
        elif resource_type == "WORKFLOW":
            model_class = AgentWorkflow
        else:
            raise BusinessException("无效的资源类型")

        query = db.query(model_class).filter(
            model_class.is_public == 1,
            (model_class.status == 1 if resource_type != "WORKFLOW" else model_class.audit_status == "APPROVED")
        )

        if category:
            query = query.filter(model_class.category == category)
        
        if search:
            if resource_type == "WORKFLOW":
                query = query.filter(model_class.title.contains(search) | model_class.description.contains(search))
            else:
                query = query.filter(model_class.name.contains(search) | model_class.description.contains(search))

        # 排序逻辑
        if sort_by == "heat":
            if resource_type == "WORKFLOW":
                query = query.order_by(desc(model_class.view_count + model_class.fork_count))
            else:
                query = query.order_by(desc(model_class.view_count))
        elif sort_by == "recommended":
            if hasattr(model_class, "is_recommended"):
                query = query.order_by(desc(model_class.is_recommended), desc(model_class.created_at))
            else:
                query = query.order_by(desc(model_class.created_at))
        else:
            query = query.order_by(desc(model_class.created_at))

        total = query.count()
        items = query.offset((page - 1) * page_size).limit(page_size).all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items
        }

    @staticmethod
    def get_resource_detail(db: Session, resource_type: str, resource_id: int) -> Any:
        """获取资源详情并增加浏览量"""
        if resource_type == "DATASET":
            resource = db.query(Dataset).filter(Dataset.id == resource_id).first()
        elif resource_type == "MODEL":
            resource = db.query(AIModel).filter(AIModel.id == resource_id).first()
        elif resource_type == "WORKFLOW":
            resource = db.query(AgentWorkflow).filter(AgentWorkflow.id == resource_id).first()
        else:
            raise BusinessException("无效的资源类型")

        if not resource:
            raise BusinessException("资源不存在")
        
        # 增加浏览量
        resource.view_count += 1
        db.commit()
        db.refresh(resource)
        return resource

    @staticmethod
    def add_comment(db: Session, comment_in: CommentCreate, user_id: int) -> Comment:
        """发表评论与评分"""
        new_comment = Comment(
            user_id=user_id,
            resource_id=comment_in.resource_id,
            resource_type=comment_in.resource_type,
            rating=comment_in.rating,
            content=comment_in.content
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)
        return new_comment

    @staticmethod
    def list_comments(db: Session, resource_type: str, resource_id: int) -> List[CommentOut]:
        """获取资源的评论列表"""
        comments = db.query(Comment).filter(
            Comment.resource_type == resource_type,
            Comment.resource_id == resource_id
        ).order_by(desc(Comment.created_at)).all()
        
        # 转换并填充用户名
        result = []
        for c in comments:
            user = db.query(User).filter(User.id == c.user_id).first()
            out = CommentOut.from_orm(c)
            out.username = user.username if user else "未知用户"
            result.append(out)
        return result

    @staticmethod
    def delete_comment(db: Session, comment_id: int, user_id: int, is_admin: bool = False) -> bool:
        """删除评论 (本人或管理员)"""
        comment = db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            raise BusinessException("评论不存在")
        
        if not is_admin and comment.user_id != user_id:
            raise BusinessException("无权删除此评论")
        
        db.delete(comment)
        db.commit()
        return True

community_service = CommunityService()
