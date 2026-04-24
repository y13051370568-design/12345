from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agent.schemas import ApiResponse, PredictRequest, ReviewSubmit, TaskCreate, TaskRunRequest, WorkflowShare
from app.agent.service import agent_service
from app.core.auth import get_current_user
from app.db import get_db_session


router = APIRouter(prefix="/agent", tags=["Agent 工作流"])


@router.post("/datasets/upload")
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
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


@router.get("/datasets/{dataset_id}/preview")
def get_dataset_preview(
    dataset_id: int,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    from app.agent.models import AgentDataset

    record = db.query(AgentDataset).filter(AgentDataset.id == dataset_id).first()
    if not record:
        from app.core.exceptions import ResourceNotFoundException

        raise ResourceNotFoundException("数据集不存在")
    agent_service._assert_owner_or_admin(record.user_id, current_user)
    return ApiResponse(data=record.preview_json)


@router.post("/tasks")
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.create_task(db, payload, current_user)
    return ApiResponse(message="Agent 任务创建成功", data=agent_service.serialize_task(task))


@router.get("/tasks")
def list_tasks(
    status: str | None = Query(None),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    tasks = agent_service.list_tasks(db, current_user, status=status)
    return ApiResponse(data=[agent_service.serialize_task(task) for task in tasks])


@router.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    return ApiResponse(data=agent_service.serialize_task(task))


@router.post("/tasks/{task_id}/run")
def run_task(
    task_id: str,
    payload: TaskRunRequest = TaskRunRequest(),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.run_task(db, task_id, current_user, offline=payload.offline)
    return ApiResponse(message="Agent 任务执行完成或已暂停", data=agent_service.serialize_task(task))


@router.post("/tasks/{task_id}/resume")
def resume_task(
    task_id: str,
    payload: TaskRunRequest = TaskRunRequest(),
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.resume_task(db, task_id, current_user, offline=payload.offline)
    return ApiResponse(message="Agent 任务恢复执行完成或已暂停", data=agent_service.serialize_task(task))


@router.post("/tasks/{task_id}/cancel")
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.cancel_task(db, task_id, current_user)
    return ApiResponse(message="Agent 任务已取消", data=agent_service.serialize_task(task))


@router.get("/tasks/{task_id}/progress")
def get_progress(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
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


@router.get("/tasks/{task_id}/pending-review")
def get_pending_review(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    return ApiResponse(data=task.pending_review_json)


@router.post("/tasks/{task_id}/reviews")
def submit_review(
    task_id: str,
    payload: ReviewSubmit,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.submit_review(db, task_id, payload, current_user)
    return ApiResponse(message="审核提交成功", data=agent_service.serialize_task(task))


@router.get("/tasks/{task_id}/reviews")
def list_reviews(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
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


@router.get("/tasks/{task_id}/report")
def get_report(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    return ApiResponse(data=agent_service.get_report(db, task_id, current_user))


@router.get("/tasks/{task_id}/code")
def get_code(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    return ApiResponse(data=agent_service.get_code(db, task_id, current_user))


@router.get("/tasks/{task_id}/download")
def download_task(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    zip_path = agent_service.make_download(db, task_id, current_user)
    return FileResponse(zip_path, filename=zip_path.name, media_type="application/zip")


@router.get("/tasks/{task_id}/demo")
def get_demo(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    task = agent_service.get_task_by_public_id(db, task_id, current_user)
    return ApiResponse(data={"demo_url": task.result_demo_url or agent_service.serialize_task(task)["artifacts"].get("web_demo")})


@router.post("/tasks/{task_id}/predict")
def predict(
    task_id: str,
    payload: PredictRequest,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    return ApiResponse(data=agent_service.predict(db, task_id, payload.features, current_user))


@router.post("/workflows/share")
def share_workflow(
    payload: WorkflowShare,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    workflow = agent_service.share_workflow(db, payload, current_user)
    return ApiResponse(message="工作流已提交审核", data={"id": workflow.id, "audit_status": workflow.audit_status})


@router.post("/workflows/{workflow_id}/fork")
def fork_workflow(
    workflow_id: int,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    workflow = agent_service.fork_workflow(db, workflow_id, current_user)
    return ApiResponse(message="工作流 Fork 成功", data={"id": workflow.id, "fork_from_id": workflow.fork_from_id})


@router.get("/workflows")
def list_workflows(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
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


@router.get("/admin/tasks")
def admin_list_tasks(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    tasks = agent_service.admin_list_tasks(db, current_user)
    return ApiResponse(data=[agent_service.serialize_task(task) for task in tasks])


@router.get("/admin/tasks/{task_id}/logs")
def admin_task_logs(
    task_id: str,
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    return ApiResponse(data=agent_service.admin_task_logs(db, task_id, current_user))


@router.get("/admin/resource-summary")
def admin_resource_summary(
    db: Session = Depends(get_db_session),
    current_user=Depends(get_current_user),
):
    return ApiResponse(data=agent_service.admin_resource_summary(db, current_user))
