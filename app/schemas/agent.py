from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Agent 接口统一响应结构，保持与现有后端 success/message/data 风格一致。
class ApiResponse(BaseModel):
    success: bool = True
    message: str = "操作成功"
    data: Any = None


# 数据集预览结构，用于展示 CSV 列名、样例行、总行数和文件大小。
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
    # 创建任务只引用已上传数据集，避免在建模接口中重复传输大文件。
    dataset_id: int = Field(..., description="已上传的数据集 ID")
    task_description: str = Field(..., min_length=3, description="自然语言建模需求")
    hitl: Optional[List[str]] = Field(
        default=None,
        description="启用的人工审核节点；留空或传 all 默认开启全部节点；传空列表或 none 表示关闭人工审核",
    )
    source_workflow_id: Optional[int] = Field(None, description="Fork 后复用的工作流 ID")


class TaskRunRequest(BaseModel):
    # offline=True 时使用离线规则 LLM，适合测试环境和无 API Key 环境。
    offline: bool = Field(True, description="是否使用离线规则 LLM，测试和无 Key 环境建议为 true")


class ReviewSubmit(BaseModel):
    # 审核动作直接映射原型工作流的 approve/edit_and_continue/reject。
    action: str = Field(..., description="approve、edit_and_continue 或 reject")
    patch: Optional[Dict[str, Any]] = Field(None, description="edit_and_continue 时提交的补丁")
    comment: str = ""
    auto_resume: bool = Field(False, description="审核通过后是否立即恢复执行")
    offline: bool = Field(True, description="恢复执行时是否使用离线规则 LLM")


class TaskSummary(BaseModel):
    # 任务列表只返回前端任务中心需要的摘要字段。
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
    # 详情额外返回完整状态、待审核内容、错误信息和产物索引。
    state: Optional[Dict[str, Any]] = None
    pending_review: Optional[Dict[str, Any]] = None
    last_error: Optional[Dict[str, Any]] = None
    artifacts: Dict[str, Any] = {}


class ReviewOut(BaseModel):
    # 审核历史用于展示人工干预轨迹和版本变化。
    id: int
    review_stage: str
    action: str
    patch: Optional[Dict[str, Any]] = None
    comment: Optional[str] = None
    before_version: Optional[int] = None
    after_version: Optional[int] = None
    created_at: datetime


class WorkflowShare(BaseModel):
    # 分享工作流时只提交展示信息，核心工作流内容从任务状态中提取。
    task_id: str
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    applicable_task_types: Optional[str] = None
    tags: Optional[str] = None


class PredictRequest(BaseModel):
    # 预测输入为样本数组，用于前端表格化批量预测。
    features: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="批量预测输入，数组元素为样本对象，键为特征列名",
    )


class WorkflowOut(BaseModel):
    # 工作流列表返回可复用、可 Fork 的元信息。
    id: int
    task_id: int
    title: str
    description: Optional[str] = None
    applicable_task_types: Optional[str] = None
    fork_from_id: Optional[int] = None
    is_public: int
    audit_status: str
    created_at: datetime
