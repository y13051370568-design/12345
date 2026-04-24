from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON, LONGTEXT, TINYINT
from sqlalchemy.orm import relationship

from app.db import Base


class AgentDataset(Base):
    __tablename__ = "ml_dataset"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    file_path = Column(String(255), nullable=False)
    file_size_kb = Column(Integer, nullable=False)
    row_count = Column(Integer)
    preview_json = Column(JSON)
    is_public = Column(TINYINT, nullable=False, default=0)
    audit_status = Column(String(20), nullable=False, default="PENDING")
    tags = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AgentTask(Base):
    __tablename__ = "ml_task"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    dataset_id = Column(BigInteger, ForeignKey("ml_dataset.id"), nullable=False)
    source_workflow_id = Column(BigInteger)
    task_description = Column(Text, nullable=False)
    task_type = Column(String(20))
    target_column = Column(String(100))
    feature_columns_json = Column(JSON)
    status = Column(String(30), nullable=False, default="CREATED")
    current_node = Column(String(50))
    version = Column(Integer, nullable=False, default=1)
    state_json = Column(JSON)
    pending_review_json = Column(JSON)
    last_error_json = Column(JSON)
    result_demo_url = Column(String(255))
    report_url = Column(String(255))
    generated_code_path = Column(String(255))
    model_artifact_path = Column(String(255))
    fail_reason = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    dataset = relationship("AgentDataset")


class AgentTaskReview(Base):
    __tablename__ = "ml_task_review"

    id = Column(BigInteger, primary_key=True, index=True)
    task_id = Column(BigInteger, ForeignKey("ml_task.id"), nullable=False)
    operator_user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    review_stage = Column(String(50), nullable=False)
    action = Column(String(30), nullable=False)
    patch_json = Column(JSON)
    comment = Column(Text)
    before_version = Column(Integer)
    after_version = Column(Integer)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AgentModel(Base):
    __tablename__ = "ml_model"

    id = Column(BigInteger, primary_key=True, index=True)
    task_id = Column(BigInteger, ForeignKey("ml_task.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    task_type = Column(String(20))
    target_column = Column(String(100))
    feature_columns_json = Column(JSON)
    framework = Column(String(50))
    performance_metrics = Column(JSON)
    model_artifact_path = Column(String(255))
    is_public = Column(TINYINT, nullable=False, default=0)
    audit_status = Column(String(20), nullable=False, default="PENDING")
    is_recommended = Column(TINYINT, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AgentWorkflow(Base):
    __tablename__ = "ml_workflow"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    task_id = Column(BigInteger, ForeignKey("ml_task.id"), nullable=False)
    title = Column(String(100), nullable=False)
    description = Column(Text)
    workflow_spec_json = Column(JSON)
    default_config_json = Column(JSON)
    prompt_template_json = Column(JSON)
    applicable_task_types = Column(String(100))
    code_content = Column(LONGTEXT, nullable=False)
    fork_from_id = Column(BigInteger)
    is_public = Column(TINYINT, nullable=False, default=0)
    audit_status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

