from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"
    data: Any = None


class DatasetPreview(BaseModel):
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    file_size_kb: int


class DatasetOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    file_path: str
    file_size_kb: int
    row_count: Optional[int] = None
    preview: Optional[DatasetPreview] = None
    audit_status: str
    created_at: datetime


class TaskCreate(BaseModel):
    dataset_id: int = Field(..., description="已上传的数据集 ID")
    task_description: str = Field(..., min_length=3, description="自然语言建模需求")
    hitl: Optional[List[str]] = Field(
        default=None,
        description="启用的人工审核节点；传 all 或留空时默认开启全部节点",
    )
    source_workflow_id: Optional[int] = Field(None, description="Fork 后复用的工作流 ID")


class TaskRunRequest(BaseModel):
    offline: bool = Field(True, description="是否使用离线规则 LLM，测试和无 Key 环境建议为 true")


class ReviewSubmit(BaseModel):
    action: str = Field(..., description="approve、edit_and_continue 或 reject")
    patch: Optional[Dict[str, Any]] = Field(None, description="edit_and_continue 时提交的补丁")
    comment: str = ""
    auto_resume: bool = Field(False, description="审核通过后是否立即恢复执行")
    offline: bool = Field(True, description="恢复执行时是否使用离线规则 LLM")


class TaskSummary(BaseModel):
    id: int
    task_id: str
    dataset_id: int
    task_description: str
    task_type: Optional[str] = None
    target_column: Optional[str] = None
    status: str
    current_node: Optional[str] = None
    version: int
    result_demo_url: Optional[str] = None
    report_url: Optional[str] = None
    generated_code_path: Optional[str] = None
    fail_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class TaskDetail(TaskSummary):
    state: Optional[Dict[str, Any]] = None
    pending_review: Optional[Dict[str, Any]] = None
    last_error: Optional[Dict[str, Any]] = None
    artifacts: Dict[str, Any] = {}


class ReviewOut(BaseModel):
    id: int
    review_stage: str
    action: str
    patch: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
    before_version: Optional[int] = None
    after_version: Optional[int] = None
    created_at: datetime


class WorkflowShare(BaseModel):
    task_id: str
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    applicable_task_types: Optional[str] = None
    tags: Optional[str] = None


class PredictRequest(BaseModel):
    features: Dict[str, Any] = Field(..., description="单条预测输入，键为特征列名")


class WorkflowOut(BaseModel):
    id: int
    task_id: int
    title: str
    description: Optional[str] = None
    applicable_task_types: Optional[str] = None
    fork_from_id: Optional[int] = None
    is_public: int
    audit_status: str
    created_at: datetime
