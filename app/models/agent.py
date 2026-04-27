from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.mysql import JSON, LONGTEXT, TINYINT
from sqlalchemy.orm import relationship

from app.db import Base


# Agent 上传数据集表，对应需求中“上传 CSV 数据并预览”的持久化记录。
class AgentDataset(Base):
    __tablename__ = "ml_dataset"

    # 基础归属和文件信息字段。
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    file_path = Column(String(255), nullable=False)
    file_size_kb = Column(Integer, nullable=False)
    # 预览字段用于前端在不重新读取 CSV 的情况下展示列名、样例行和总行数。
    row_count = Column(Integer)
    preview_json = Column(JSON)
    # 审核字段与平台资源审核逻辑保持一致，Agent 上传默认先进入待审核状态。
    is_public = Column(TINYINT, nullable=False, default=0)
    audit_status = Column(String(20), nullable=False, default="PENDING")
    tags = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


# Agent 建模任务主表，承载工作流状态机、HITL 暂停点和运行产物索引。
class AgentTask(Base):
    __tablename__ = "ml_task"

    # 任务归属、数据集引用和工作流复用来源。
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    dataset_id = Column(BigInteger, ForeignKey("ml_dataset.id"), nullable=False)
    source_workflow_id = Column(BigInteger)
    # 用户自然语言需求和 Agent 自动解析出的建模元信息。
    task_description = Column(Text, nullable=False)
    task_type = Column(String(20))
    target_column = Column(String(100))
    feature_columns_json = Column(JSON)
    # 工作流生命周期状态和当前节点，对齐原型状态机。
    status = Column(String(30), nullable=False, default="CREATED")
    current_node = Column(String(50))
    version = Column(Integer, nullable=False, default=1)
    # JSON 快照保存完整工作流上下文、待审核内容和错误详情。
    state_json = Column(JSON)
    pending_review_json = Column(JSON)
    last_error_json = Column(JSON)
    # 运行产物字段供报告、代码、模型包和 Web Demo 接口读取。
    result_demo_url = Column(String(255))
    report_url = Column(String(255))
    generated_code_path = Column(String(255))
    model_artifact_path = Column(String(255))
    fail_reason = Column(Text)
    # 时间字段用于任务中心排序、耗时统计和管理端排障。
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = Column(DateTime)
    finished_at = Column(DateTime)

    dataset = relationship("AgentDataset")


# HITL 人工审核历史表，记录每一次审核动作、补丁和版本变化。
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


# Agent 训练产出的模型沉淀表，后续可对接模型广场审核和推荐。
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


# 可复用工作流表，用于开发者分享、Fork 和平台审核。
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
