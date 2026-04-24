from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationException, DataValidationException, ResourceNotFoundException
from app.models.agent import AgentDataset, AgentTask, AgentTaskReview, AgentWorkflow
from app.service.agent_runner_bridge import build_runner_for_user, parse_hitl_config
from app.service.agent_storage import make_task_zip, read_json_artifact, read_text_artifact, save_csv_upload


class AgentService:
    def upload_dataset(self, db: Session, file: UploadFile, current_user: Any) -> AgentDataset:
        # 上传接口负责落盘和写入数据集元信息，后续任务只引用 dataset_id。
        saved = save_csv_upload(file, current_user.id)
        dataset = AgentDataset(
            user_id=current_user.id,
            name=saved["name"],
            description="Agent 建模任务上传数据集",
            file_path=saved["file_path"],
            file_size_kb=saved["file_size_kb"],
            row_count=saved["row_count"],
            preview_json=saved["preview"],
            is_public=0,
            audit_status="PENDING",
            tags="agent,csv",
        )
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset

    def create_task(self, db: Session, payload: Any, current_user: Any) -> AgentTask:
        # 任务创建前先校验数据集归属，防止用户使用他人的私有数据集发起训练。
        dataset = db.query(AgentDataset).filter(AgentDataset.id == payload.dataset_id).first()
        if not dataset:
            raise ResourceNotFoundException("数据集不存在")
        self._assert_owner_or_admin(dataset.user_id, current_user)

        runner, _ = build_runner_for_user(
            offline=True,
            task_owner_username=current_user.username,
            reviewer_username=current_user.username,
        )
        state = runner.create_task(
            user_request=payload.task_description,
            csv_path=dataset.file_path,
            hitl_config=parse_hitl_config(payload.hitl),
        )
        # runner 内部使用独立 PyMySQL 连接写库；结束当前事务后才能看到新任务。
        db.rollback()
        task = self.get_task_by_public_id(db, state.task_id, current_user)
        if payload.source_workflow_id:
            task.source_workflow_id = payload.source_workflow_id
            db.commit()
            db.refresh(task)
        return task

    def list_tasks(self, db: Session, current_user: Any, status: Optional[str] = None) -> List[AgentTask]:
        # 管理员可看全部任务，普通用户和开发者只能看自己的任务。
        query = db.query(AgentTask).order_by(AgentTask.created_at.desc())
        if current_user.role != "ADMIN":
            query = query.filter(AgentTask.user_id == current_user.id)
        if status:
            query = query.filter(AgentTask.status == status)
        return query.all()

    def get_task_by_public_id(self, db: Session, task_id: str, current_user: Any) -> AgentTask:
        # 对外暴露的 task_id 存在 state_json 中，避免把数据库自增主键暴露给前端工作流。
        task = (
            db.query(AgentTask)
            .filter(AgentTask.state_json["task_id"].as_string() == task_id)
            .first()
        )
        if not task:
            raise ResourceNotFoundException("任务不存在")
        self._assert_owner_or_admin(task.user_id, current_user)
        return task

    def run_task(self, db: Session, task_id: str, current_user: Any, offline: bool = True) -> AgentTask:
        # 执行可能在任意节点暂停、完成或失败，最终状态统一从数据库重新读取。
        task = self.get_task_by_public_id(db, task_id, current_user)
        runner, _ = build_runner_for_user(
            offline=offline,
            task_owner_username=current_user.username,
            reviewer_username=current_user.username,
        )
        runner.run_task(task_id)
        db.rollback()
        return self.get_task_by_public_id(db, task_id, current_user)

    def resume_task(self, db: Session, task_id: str, current_user: Any, offline: bool = True) -> AgentTask:
        # 恢复执行只允许 READY_TO_RESUME 状态，具体状态校验由 GraphRunner 保持一致。
        self.get_task_by_public_id(db, task_id, current_user)
        runner, _ = build_runner_for_user(
            offline=offline,
            task_owner_username=current_user.username,
            reviewer_username=current_user.username,
        )
        runner.resume_task(task_id)
        db.rollback()
        return self.get_task_by_public_id(db, task_id, current_user)

    def cancel_task(self, db: Session, task_id: str, current_user: Any) -> AgentTask:
        # 取消只更新平台生命周期状态，不直接中断正在运行的外部进程。
        task = self.get_task_by_public_id(db, task_id, current_user)
        if task.status in {"COMPLETED", "FAILED", "CANCELLED"}:
            return task
        task.status = "CANCELLED"
        task.current_node = None
        task.fail_reason = "用户取消任务"
        state = dict(task.state_json or {})
        state["status"] = "CANCELLED"
        state["current_node"] = None
        task.state_json = state
        db.commit()
        db.refresh(task)
        return task

    def submit_review(self, db: Session, task_id: str, payload: Any, current_user: Any) -> AgentTask:
        # HITL 干预是开发者能力，零基础用户只能查看任务状态和结果。
        if current_user.role not in {"DEVELOPER", "ADMIN"}:
            raise AuthorizationException("只有开发者或管理员可以进行人机协同审核")
        self.get_task_by_public_id(db, task_id, current_user)
        runner, _ = build_runner_for_user(
            offline=payload.offline,
            task_owner_username=current_user.username,
            reviewer_username=current_user.username,
        )
        runner.submit_review(
            task_id=task_id,
            action=payload.action,
            patch=payload.patch,
            comment=payload.comment,
        )
        if payload.auto_resume and payload.action in {"approve", "edit_and_continue"}:
            runner.resume_task(task_id)
        db.rollback()
        return self.get_task_by_public_id(db, task_id, current_user)

    def get_reviews(self, db: Session, task_id: str, current_user: Any) -> List[AgentTaskReview]:
        # 审核历史按插入顺序返回，用于前端展示版本演进和人工干预记录。
        task = self.get_task_by_public_id(db, task_id, current_user)
        return (
            db.query(AgentTaskReview)
            .filter(AgentTaskReview.task_id == task.id)
            .order_by(AgentTaskReview.id.asc())
            .all()
        )

    def get_report(self, db: Session, task_id: str, current_user: Any) -> Dict[str, Any]:
        # 报告文件路径由 Operation Agent 写入 artifacts.final_report。
        task = self.get_task_by_public_id(db, task_id, current_user)
        artifacts = self._artifacts(task)
        report_path = artifacts.get("final_report") or task.report_url
        if not report_path:
            raise ResourceNotFoundException("任务尚未生成报告")
        return read_json_artifact(report_path)

    def get_code(self, db: Session, task_id: str, current_user: Any) -> Dict[str, str]:
        # 代码查看属于开发者能力，避免普通用户误操作或看到过多实现细节。
        if current_user.role not in {"DEVELOPER", "ADMIN"}:
            raise AuthorizationException("只有开发者或管理员可以查看代码")
        task = self.get_task_by_public_id(db, task_id, current_user)
        artifacts = self._artifacts(task)
        code_path = artifacts.get("generated_code") or task.generated_code_path
        if not code_path:
            raise ResourceNotFoundException("任务尚未生成代码")
        return {"path": code_path, "python_code": read_text_artifact(code_path)}

    def predict(self, db: Session, task_id: str, features: Dict[str, Any], current_user: Any) -> Dict[str, Any]:
        # 轻量级 Web Demo 实现：执行生成代码中的 train()，再用提交的单条特征做预测。
        task = self.get_task_by_public_id(db, task_id, current_user)
        if task.status != "COMPLETED":
            raise DataValidationException("任务尚未完成，不能进行预测")
        code_info = self.get_code(db, task_id, current_user if current_user.role in {"DEVELOPER", "ADMIN"} else self._as_developer(current_user))
        namespace: Dict[str, Any] = {}
        exec(code_info["python_code"], namespace)
        train_func = namespace.get("train")
        if not callable(train_func):
            raise DataValidationException("生成代码中缺少 train() 函数，无法执行预测")
        model, _, _ = train_func()
        import pandas as pd

        frame = pd.DataFrame([features])
        prediction = model.predict(frame)
        values = prediction.tolist() if hasattr(prediction, "tolist") else list(prediction)
        return {
            "task_id": task_id,
            "prediction": values[0] if len(values) == 1 else values,
            "input": features,
        }

    def make_download(self, db: Session, task_id: str, current_user: Any):
        # 下载包只包含已生成的本地文件产物，不打包 http 链接。
        if current_user.role not in {"DEVELOPER", "ADMIN"}:
            raise AuthorizationException("只有开发者或管理员可以下载代码包")
        task = self.get_task_by_public_id(db, task_id, current_user)
        return make_task_zip(task_id, self._artifacts(task))

    def share_workflow(self, db: Session, payload: Any, current_user: Any) -> AgentWorkflow:
        # 分享工作流会进入待审核状态，审核通过前不会公开展示。
        if current_user.role not in {"DEVELOPER", "ADMIN"}:
            raise AuthorizationException("只有开发者或管理员可以分享工作流")
        task = self.get_task_by_public_id(db, payload.task_id, current_user)
        code = self.get_code(db, payload.task_id, current_user)["python_code"]
        state = task.state_json or {}
        workflow = AgentWorkflow(
            user_id=current_user.id,
            task_id=task.id,
            title=payload.title,
            description=payload.description,
            workflow_spec_json=state,
            default_config_json=(state.get("context") or {}).get("hitl_config"),
            prompt_template_json=None,
            applicable_task_types=payload.applicable_task_types or task.task_type,
            code_content=code,
            fork_from_id=None,
            is_public=0,
            audit_status="PENDING",
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        return workflow

    def fork_workflow(self, db: Session, workflow_id: int, current_user: Any) -> AgentWorkflow:
        # Fork 会创建独立副本，后续修改不会影响原始工作流。
        source = db.query(AgentWorkflow).filter(AgentWorkflow.id == workflow_id).first()
        if not source:
            raise ResourceNotFoundException("工作流不存在")
        if not source.is_public and source.user_id != current_user.id and current_user.role != "ADMIN":
            raise AuthorizationException("该工作流未公开，不能 Fork")
        forked = AgentWorkflow(
            user_id=current_user.id,
            task_id=source.task_id,
            title=f"{source.title} Fork",
            description=source.description,
            workflow_spec_json=source.workflow_spec_json,
            default_config_json=source.default_config_json,
            prompt_template_json=source.prompt_template_json,
            applicable_task_types=source.applicable_task_types,
            code_content=source.code_content,
            fork_from_id=source.id,
            is_public=0,
            audit_status="PENDING",
        )
        db.add(forked)
        db.commit()
        db.refresh(forked)
        return forked

    def list_workflows(self, db: Session, current_user: Any) -> List[AgentWorkflow]:
        # 普通用户可见公开工作流和自己的私有工作流；管理员可见全部。
        query = db.query(AgentWorkflow).order_by(AgentWorkflow.created_at.desc())
        if current_user.role != "ADMIN":
            query = query.filter((AgentWorkflow.is_public == 1) | (AgentWorkflow.user_id == current_user.id))
        return query.all()

    def admin_list_tasks(self, db: Session, current_user: Any) -> List[AgentTask]:
        # 管理员查看全量 Agent 任务，用于后台监控和排障。
        if current_user.role != "ADMIN":
            raise AuthorizationException("只有管理员可以查看全部 Agent 任务")
        return db.query(AgentTask).order_by(AgentTask.created_at.desc()).all()

    def admin_task_logs(self, db: Session, task_id: str, current_user: Any) -> Dict[str, Any]:
        # 任务日志由状态快照、错误信息和审核历史组合而成，满足一期可观测性需求。
        if current_user.role != "ADMIN":
            raise AuthorizationException("只有管理员可以查看任务日志")
        task = self.get_task_by_public_id(db, task_id, current_user)
        reviews = self.get_reviews(db, task_id, current_user)
        return {
            "task": self.serialize_task(task),
            "last_error": task.last_error_json,
            "reviews": [
                {
                    "stage": item.review_stage,
                    "action": item.action,
                    "comment": item.comment,
                    "created_at": item.created_at,
                }
                for item in reviews
            ],
        }

    def admin_resource_summary(self, db: Session, current_user: Any) -> Dict[str, Any]:
        # 汇总任务数量和状态分布，后续可扩展 CPU、内存、Token 等监控指标。
        if current_user.role != "ADMIN":
            raise AuthorizationException("只有管理员可以查看资源摘要")
        tasks = db.query(AgentTask).all()
        status_count: Dict[str, int] = {}
        for task in tasks:
            status_count[task.status] = status_count.get(task.status, 0) + 1
        return {
            "total_tasks": len(tasks),
            "status_count": status_count,
            "datasets": db.query(AgentDataset).count(),
            "workflows": db.query(AgentWorkflow).count(),
        }

    def _assert_owner_or_admin(self, owner_id: int, current_user: Any) -> None:
        # 所有私有 Agent 资源默认只允许所有者本人或管理员访问。
        if current_user.role != "ADMIN" and owner_id != current_user.id:
            raise AuthorizationException("只能访问自己的 Agent 资源")

    def _artifacts(self, task: AgentTask) -> Dict[str, Any]:
        # artifacts 是原型工作流产物的统一索引，例如代码、报告、Demo URL。
        state = task.state_json or {}
        artifacts = state.get("artifacts") if isinstance(state, dict) else {}
        return artifacts or {}

    def _as_developer(self, current_user: Any) -> Any:
        # 预测接口允许任务所有者使用生成模型，不暴露代码内容给普通用户。
        class CurrentUserProxy:
            pass

        proxy = CurrentUserProxy()
        proxy.id = current_user.id
        proxy.username = current_user.username
        proxy.role = "DEVELOPER"
        return proxy

    def serialize_task(self, task: AgentTask) -> Dict[str, Any]:
        # 统一输出任务结构，避免各接口重复拼装状态和产物字段。
        state = task.state_json or {}
        artifacts = state.get("artifacts") if isinstance(state, dict) else {}
        public_id = state.get("task_id") if isinstance(state, dict) else None
        return {
            "id": task.id,
            "task_id": public_id or str(task.id),
            "dataset_id": task.dataset_id,
            "task_description": task.task_description,
            "task_type": task.task_type,
            "target_column": task.target_column,
            "status": task.status,
            "current_node": task.current_node,
            "version": task.version,
            "result_demo_url": task.result_demo_url,
            "report_url": task.report_url,
            "generated_code_path": task.generated_code_path or (artifacts or {}).get("generated_code"),
            "fail_reason": task.fail_reason,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "started_at": task.started_at,
            "finished_at": task.finished_at,
            "state": state,
            "pending_review": task.pending_review_json,
            "last_error": task.last_error_json,
            "artifacts": artifacts or {},
        }


agent_service = AgentService()
