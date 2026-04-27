from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db import get_db_session
from app.schemas.agent import ApiResponse, PredictRequest, ReviewSubmit, TaskCreate, TaskRunRequest, WorkflowShare
from app.service.agent_service import agent_service


# Agent 模块统一挂载在 /api/agent 下，避免与现有任务中心、数据中心接口混淆。
router = APIRouter(prefix="/agent", tags=["Agent 工作流"])


@router.post("/datasets/upload", summary="上传 Agent 数据集")
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    上传用于 Agent 自动建模的 CSV 数据集。

    - **file**: 仅支持 CSV 文件。
    - 上传后会保存到后端本地 `uploads/agent/datasets`。
    - 系统会解析列名、前 10 行预览、总行数和文件大小。
    - 返回的 `id` 用于后续创建 Agent 建模任务。
    """
    dataset = agent_service.upload_dataset(db, file, current_user)
    return ApiResponse(
        message="数据集上传成功",
        data={
            "id": dataset.id,
            "name": dataset.name,
            "file_path": dataset.file_path,
            "file_size_kb": dataset.file_size_kb,
            "row_count": dataset.row_count,
            "preview": dataset.preview_json,
            "audit_status": dataset.audit_status,
            "created_at": dataset.created_at,
        },
    )


@router.get("/datasets/{dataset_id}/preview", summary="获取 Agent 数据集预览")
def get_dataset_preview(
    dataset_id: int,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    获取已上传 CSV 数据集的预览信息。

    - **dataset_id**: 数据集数据库 ID。
    - 普通用户只能查看自己上传的数据集。
    - 管理员可以查看所有 Agent 数据集。
    - 返回列名、样例行、行数和文件大小等信息。
    """
    from app.models.agent import AgentDataset

    record = db.query(AgentDataset).filter(AgentDataset.id == dataset_id).first()
    if not record:
        from app.core.exceptions import ResourceNotFoundException

        raise ResourceNotFoundException("数据集不存在")
    agent_service._assert_owner_or_admin(record.user_id, current_user)
    return ApiResponse(data=record.preview_json)


@router.post("/tasks", summary="创建 Agent 建模任务")
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    基于已上传数据集创建一个 Agent 自动建模任务。

    - **dataset_id**: 已上传数据集 ID。
    - **task_description**: 用户自然语言建模需求。
    - **hitl**: 可选人工审核节点列表，传 `all` 或留空表示启用全部审核节点；传空列表或 `none` 表示关闭人工审核。
    - 创建后任务状态为 `CREATED`，需要调用运行接口才会开始执行工作流。
    """
    task = agent_service.create_task(db, payload, current_user)
    return ApiResponse(message="Agent 任务创建成功", data=agent_service.serialize_task(task))


@router.get("/tasks", summary="查询 Agent 任务列表")
def list_tasks(
    status: str | None = Query(None),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    查询当前用户可见的 Agent 建模任务列表。

    - **status**: 可选任务状态过滤条件。
    - 只返回当前登录用户本人创建的任务。
    - 管理员如需查看全量任务，应使用 `/api/agent/admin/tasks`。
    - 返回任务状态、当前节点、版本、产物索引等摘要信息。
    """
    tasks = agent_service.list_tasks(db, current_user, status=status)
    return ApiResponse(data=[agent_service.serialize_task(task) for task in tasks])


@router.get("/tasks/{task_id}", summary="获取 Agent 任务详情")
def get_task(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    获取指定 Agent 建模任务的完整详情。

    - **task_id**: 对外暴露的任务编号，例如 `task_xxxxxxxx`。
    - 返回完整 `state`、待审核信息、错误信息和运行产物索引。
    - 只能访问自己的任务，管理员除外。
    """
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    return ApiResponse(data=agent_service.serialize_task(task))


@router.post("/tasks/{task_id}/run", summary="运行 Agent 任务")
def run_task(
    task_id: str,
    payload: TaskRunRequest = TaskRunRequest(),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    启动或继续执行一个处于可运行状态的 Agent 建模任务。

    - **offline=true**: 使用本地规则执行，适合自动化测试和无 Key 环境。
    - **offline=false**: 调用真实 LLM，失败时直接报错，不会静默降级。
    - 如果命中 HITL 节点，任务会暂停为 `WAITING_HUMAN`。
    - 如果没有待审核节点或审核全部通过，任务最终进入 `COMPLETED`。
    """
    task = agent_service.run_task(db, task_id, current_user, offline=payload.offline)
    return ApiResponse(message="Agent 任务执行完成或已暂停", data=agent_service.serialize_task(task))


@router.post("/tasks/{task_id}/resume", summary="恢复 Agent 任务")
def resume_task(
    task_id: str,
    payload: TaskRunRequest = TaskRunRequest(),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    从人工审核通过后的节点恢复执行 Agent 工作流。

    - 任务必须处于 `READY_TO_RESUME` 状态。
    - **offline** 参数含义与运行接口一致。
    - 恢复后可能再次暂停在下一个 HITL 节点，也可能直接完成。
    """
    task = agent_service.resume_task(db, task_id, current_user, offline=payload.offline)
    return ApiResponse(message="Agent 任务恢复执行完成或已暂停", data=agent_service.serialize_task(task))


@router.post("/tasks/{task_id}/cancel", summary="取消 Agent 任务")
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    取消尚未结束的 Agent 建模任务。

    - 已完成、已失败或已取消的任务会保持原状态。
    - 取消会把任务状态置为 `CANCELLED`。
    - 当前实现只更新平台任务状态，不强制中断外部进程。
    """
    task = agent_service.cancel_task(db, task_id, current_user)
    return ApiResponse(message="Agent 任务已取消", data=agent_service.serialize_task(task))


@router.get("/tasks/{task_id}/progress", summary="查询 Agent 任务进度")
def get_progress(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    查询 Agent 任务当前执行进度。

    - 返回任务生命周期状态、当前节点、版本号。
    - 如果处于人工审核阶段，会返回 `pending_review`。
    - 如果已有运行产物，会返回 `artifacts` 索引。
    """
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    data = agent_service.serialize_task(task)
    return ApiResponse(
        data={
            "task_id": data["task_id"],
            "status": data["status"],
            "current_node": data["current_node"],
            "version": data["version"],
            "pending_review": data["pending_review"],
            "last_error": data["last_error"],
            "artifacts": data["artifacts"],
        }
    )


@router.get("/tasks/{task_id}/pending-review", summary="获取待人工审核内容")
def get_pending_review(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    获取当前 Agent 任务的待人工审核载荷。

    - 仅当任务状态为 `WAITING_HUMAN` 时通常会有内容。
    - 返回审核阶段、节点名称、可审核 payload 和版本信息。
    - 前端可据此渲染 HITL 审核页面。
    """
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    return ApiResponse(data=task.pending_review_json)


@router.post("/tasks/{task_id}/reviews", summary="提交 Agent 人工审核")
def submit_review(
    task_id: str,
    payload: ReviewSubmit,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    提交 Agent 工作流的人机协同审核结果。

    - 仅 `DEVELOPER` 和 `ADMIN` 可以提交审核。
    - **action** 支持 `approve`、`edit_and_continue`、`reject`。
    - **patch** 用于 `edit_and_continue` 时提交人工修改内容。
    - **auto_resume=true** 时审核通过后立即继续执行后续节点。
    """
    task = agent_service.submit_review(db, task_id, payload, current_user)
    return ApiResponse(message="审核提交成功", data=agent_service.serialize_task(task))


@router.get("/tasks/{task_id}/reviews", summary="查询 Agent 审核历史")
def list_reviews(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    查询指定 Agent 任务的全部人工审核历史。

    - 返回审核阶段、动作、补丁、备注和版本变化。
    - 用于前端展示人工干预轨迹和工作流演进。
    """
    reviews = agent_service.get_reviews(db, task_id, current_user)
    return ApiResponse(
        data=[
            {
                "id": item.id,
                "review_stage": item.review_stage,
                "action": item.action,
                "patch": item.patch_json,
                "comment": item.comment,
                "before_version": item.before_version,
                "after_version": item.after_version,
                "created_at": item.created_at,
            }
            for item in reviews
        ]
    )


@router.get("/tasks/{task_id}/report", summary="获取 Agent 任务报告")
def get_report(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    获取 Agent 建模任务生成的最终分析报告。

    - 任务完成后可用。
    - 返回数据分析摘要、模型规划、训练指标和总结说明。
    - 如果报告尚未生成，会返回资源不存在错误。
    """
    return ApiResponse(data=agent_service.get_report(db, task_id, current_user))


@router.get("/tasks/{task_id}/code", summary="获取 Agent 生成代码")
def get_code(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    获取 Agent 自动生成的 Python 训练代码。

    - 仅 `DEVELOPER` 和 `ADMIN` 可以查看。
    - 返回代码文件路径和完整 Python 源码。
    - 用于开发者审查、修改或下载模型训练逻辑。
    """
    return ApiResponse(data=agent_service.get_code(db, task_id, current_user))


@router.get("/tasks/{task_id}/download", summary="下载 Agent 任务产物")
def download_task(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    下载 Agent 任务生成的本地产物压缩包。

    - 仅 `DEVELOPER` 和 `ADMIN` 可以下载。
    - 压缩包包含生成代码、报告等本地文件产物。
    - 不会打包外部 HTTP 链接。
    """
    zip_path = agent_service.make_download(db, task_id, current_user)
    return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")


@router.get("/tasks/{task_id}/demo", summary="获取 Agent 预测 Demo 地址")
def get_demo(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    获取任务对应的轻量预测 Demo 地址。

    - 当前返回后端预测接口地址。
    - 前端可使用该地址构造单条样本预测页面。
    - 任务完成后通常可用。
    """
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    return ApiResponse(data={"demo_url": task.result_demo_url or agent_service.serialize_task(task)["artifacts"].get("web_demo")})


@router.post("/tasks/{task_id}/predict", summary="调用 Agent 生成模型预测")
def predict(
    task_id: str,
    payload: PredictRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    使用 Agent 生成的训练代码对单条样本进行预测。

    - 任务必须已经 `COMPLETED`。
    - **features** 为单条样本特征字典，键应与训练特征列一致。
    - 返回预测结果和原始输入。
    """
    return ApiResponse(data=agent_service.predict(db, task_id, payload.features, current_user))


@router.post("/workflows/share", summary="分享 Agent 工作流")
def share_workflow(
    payload: WorkflowShare,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    将已完成任务沉淀为可复用工作流并提交审核。

    - 仅 `DEVELOPER` 和 `ADMIN` 可以分享。
    - 系统会从任务状态中提取工作流定义和生成代码。
    - 新分享的工作流默认进入 `PENDING` 审核状态。
    """
    workflow = agent_service.share_workflow(db, payload, current_user)
    return ApiResponse(message="工作流已提交审核", data={"id": workflow.id, "audit_status": workflow.audit_status})


@router.post("/workflows/{workflow_id}/fork", summary="Fork Agent 工作流")
def fork_workflow(
    workflow_id: int,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    Fork 一个已有 Agent 工作流，生成当前用户自己的副本。

    - 可 Fork 公开工作流。
    - 私有工作流仅所有者本人或管理员可 Fork。
    - Fork 后的副本默认进入 `PENDING` 审核状态。
    """
    workflow = agent_service.fork_workflow(db, workflow_id, current_user)
    return ApiResponse(message="工作流 Fork 成功", data={"id": workflow.id, "fork_from_id": workflow.fork_from_id})


@router.get("/workflows", summary="查询 Agent 工作流列表")
def list_workflows(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    查询当前用户可见的 Agent 工作流列表。

    - 普通用户可见公开工作流和自己的私有工作流。
    - 管理员可以查看全部工作流。
    - 返回标题、描述、适用任务类型、审核状态和 Fork 来源。
    """
    workflows = agent_service.list_workflows(db, current_user)
    return ApiResponse(
        data=[
            {
                "id": item.id,
                "task_id": item.task_id,
                "title": item.title,
                "description": item.description,
                "applicable_task_types": item.applicable_task_types,
                "fork_from_id": item.fork_from_id,
                "is_public": item.is_public,
                "audit_status": item.audit_status,
                "created_at": item.created_at,
            }
            for item in workflows
        ]
    )


@router.get("/admin/tasks", summary="管理员查询全部 Agent 任务")
def admin_list_tasks(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    管理员查询平台内全部 Agent 建模任务。

    - 仅 `ADMIN` 可访问。
    - 用于后台任务监控、排障和运营管理。
    - 返回完整任务摘要列表。
    """
    tasks = agent_service.admin_list_tasks(db, current_user)
    return ApiResponse(data=[agent_service.serialize_task(task) for task in tasks])


@router.get("/admin/tasks/{task_id}/logs", summary="管理员查询 Agent 任务日志")
def admin_task_logs(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    管理员查询指定 Agent 任务的运行日志视图。

    - 仅 `ADMIN` 可访问。
    - 返回任务快照、最近错误和审核历史。
    - 用于定位失败原因和审计人工干预记录。
    """
    return ApiResponse(data=agent_service.admin_task_logs(db, task_id, current_user))


@router.get("/admin/resource-summary", summary="管理员查询 Agent 资源摘要")
def admin_resource_summary(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    """
    管理员查询 Agent 模块资源统计摘要。

    - 仅 `ADMIN` 可访问。
    - 返回任务总数、状态分布、数据集数量和工作流数量。
    - 用于后台监控面板展示。
    """
    return ApiResponse(data=agent_service.admin_resource_summary(db, current_user))
