from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import json
import math
import re
import uuid

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.exceptions import DataValidationException
from app.models.agent import AgentDataset, AgentModel, AgentTask, AgentTaskReview
from app.service.agent_llm_client import AgentLLMClient


# 后端内置工作流主链路，避免运行时依赖 backend/base 之外的草案代码。
WORKFLOW_NODES = [
    "manager_parse",
    "data_analysis",
    "model_plan",
    "model_training",
    "code_generation",
    "operation_report",
]

# 需要人工审核的节点映射，键为审核阶段，值为审核通过后要继续执行的下一个节点。
REVIEW_NEXT_NODE = {
    "parse_review": "data_analysis",
    "feature_review": "model_plan",
    "model_plan_review": "model_training",
    "code_review": "operation_report",
}

# 节点执行完成后进入的审核阶段，保持与需求草案中的 HITL 状态机一致。
NODE_REVIEW_STAGE = {
    "manager_parse": "parse_review",
    "data_analysis": "feature_review",
    "model_plan": "model_plan_review",
    "code_generation": "code_review",
}

# 默认开启全部人工审核节点，前端可在创建任务时传入子集关闭部分节点。
DEFAULT_HITL_CONFIG = {
    "parse_review": True,
    "feature_review": True,
    "model_plan_review": True,
    "code_review": True,
}

ARTIFACTS_DIR = Path("uploads/agent/artifacts")


@dataclass
class WorkflowResult:
    # 兼容旧服务层只关心 task_id 的返回结构。
    task_id: str


def parse_hitl_config(stages: list[str] | None) -> Dict[str, bool]:
    # None 或 all 表示全部审核节点启用；空列表或 none/off 表示关闭人工审核。
    if stages is None or "all" in stages:
        return dict(DEFAULT_HITL_CONFIG)
    if not stages or any(stage in {"none", "off", "false"} for stage in stages):
        return {key: False for key in DEFAULT_HITL_CONFIG}
    enabled = set(stages)
    return {key: key in enabled for key in DEFAULT_HITL_CONFIG}


class AgentWorkflowEngine:
    def __init__(self, db: Session, current_user: Any, offline: bool = True):
        # 每次请求使用 FastAPI 注入的 SQLAlchemy 会话，保证后端可独立部署。
        self.db = db
        self.current_user = current_user
        self.offline = offline
        self.llm_client = None if offline else AgentLLMClient()

    def create_task(self, dataset: AgentDataset, user_request: str, hitl_config: Dict[str, bool]) -> WorkflowResult:
        # 创建任务时只写入初始状态，真正的节点执行由 run/resume 接口触发。
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        state = {
            "task_id": task_id,
            "status": "CREATED",
            "current_node": "manager_parse",
            "context": {
                "user_request": user_request,
                "csv_path": dataset.file_path,
                "hitl_config": hitl_config,
                "artifacts": {},
                "node_outputs": {},
            },
            "artifacts": {},
        }
        task = AgentTask(
            user_id=self.current_user.id,
            dataset_id=dataset.id,
            task_description=user_request,
            status="CREATED",
            current_node="manager_parse",
            version=1,
            state_json=state,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return WorkflowResult(task_id=task_id)

    def run_task(self, task: AgentTask) -> None:
        # 首次运行从 current_node 开始，通常是 manager_parse。
        if task.status == "CANCELLED":
            raise DataValidationException("任务已取消，不能继续执行")
        self._execute_until_pause_or_finish(task)

    def resume_task(self, task: AgentTask) -> None:
        # 恢复执行要求审核已把任务置为 READY_TO_RESUME，并写入下一个节点。
        if task.status != "READY_TO_RESUME":
            raise DataValidationException("任务当前状态不能恢复执行")
        self._execute_until_pause_or_finish(task)

    def submit_review(self, task: AgentTask, action: str, patch: Dict[str, Any] | None, comment: str) -> None:
        # 审核动作只处理当前 pending_review，保证版本演进可追溯。
        pending = task.pending_review_json or {}
        review_stage = pending.get("review_stage")
        if task.status != "WAITING_HUMAN" or not review_stage:
            raise DataValidationException("任务当前没有待审核节点")
        if action not in {"approve", "edit_and_continue", "reject"}:
            raise DataValidationException("不支持的审核动作")

        before_version = task.version
        after_version = before_version + 1
        task.version = after_version
        state = self._state(task)
        if action == "reject":
            task.status = "FAILED"
            task.current_node = None
            task.fail_reason = comment or "人工审核拒绝"
            task.pending_review_json = None
            state["status"] = task.status
            state["current_node"] = None
            state["pending_review"] = None
        else:
            if action == "edit_and_continue" and patch:
                # 补丁合并到上下文，供后续节点读取；当前实现保留原结构便于前端展示。
                state.setdefault("context", {}).setdefault("human_patches", []).append(
                    {"stage": review_stage, "patch": patch, "comment": comment}
                )
            next_node = REVIEW_NEXT_NODE.get(review_stage)
            task.status = "READY_TO_RESUME"
            task.current_node = next_node
            task.pending_review_json = None
            state["status"] = task.status
            state["current_node"] = next_node
            state["pending_review"] = None

        task.state_json = state
        flag_modified(task, "state_json")
        self.db.add(
            AgentTaskReview(
                task_id=task.id,
                operator_user_id=self.current_user.id,
                review_stage=review_stage,
                action=action,
                patch_json=patch,
                comment=comment,
                before_version=before_version,
                after_version=after_version,
            )
        )
        self.db.commit()
        self.db.refresh(task)

    def _execute_until_pause_or_finish(self, task: AgentTask) -> None:
        # 同步执行节点直到遇到启用的 HITL 审核点或工作流完成。
        state = self._state(task)
        task.status = "RUNNING"
        state["status"] = "RUNNING"
        self._sync_task_state(task, state)

        while task.current_node:
            node = task.current_node
            if node not in WORKFLOW_NODES:
                raise DataValidationException(f"未知工作流节点: {node}")
            self._run_node(task, node)
            state = self._state(task)
            review_stage = NODE_REVIEW_STAGE.get(node)
            if review_stage and state.get("context", {}).get("hitl_config", {}).get(review_stage):
                self._pause_for_review(task, review_stage, node)
                return
            task.current_node = self._next_node(node)
            state["current_node"] = task.current_node
            self._sync_task_state(task, state)

        self._complete_task(task)

    def _run_node(self, task: AgentTask, node: str) -> None:
        # 节点调度表让状态机结构清晰，后续替换为真实 LLM/队列执行也更容易。
        handlers = {
            "manager_parse": self._manager_parse,
            "data_analysis": self._data_analysis,
            "model_plan": self._model_plan,
            "model_training": self._model_training,
            "code_generation": self._code_generation,
            "operation_report": self._operation_report,
        }
        handlers[node](task)

    def _manager_parse(self, task: AgentTask) -> None:
        # 解析自然语言需求；offline=false 时必须调用真实 LLM。
        state = self._state(task)
        frame = self._load_frame(state)
        columns = [str(column) for column in frame.columns]
        request = task.task_description or ""
        if self.llm_client:
            parsed = self.llm_client.chat_json(
                system_prompt="你是 AI4ML 平台的 Manager Agent。请把用户自然语言需求解析成稳定的结构化建模意图，只返回 JSON。",
                user_prompt=f"""
用户需求：
{request}

CSV 列名：
{json.dumps(columns, ensure_ascii=False)}

请返回严格 JSON：
{{
  "target_column": "必须是 CSV 列名之一",
  "task_type": "CLASSIFICATION 或 REGRESSION",
  "business_goal": "一句话业务目标",
  "success_criteria": "一句话成功标准",
  "optimization_goal": "accuracy、f1、r2 或 rmse",
  "reason": "选择原因"
}}
""".strip(),
            )
            target_column = self._validate_target_column(parsed.get("target_column"), columns)
            task_type = self._normalize_task_type(parsed.get("task_type"), frame[target_column])
            llm_output = parsed
        else:
            target_column = self._infer_target_column(request, columns)
            task_type = self._infer_task_type(frame[target_column])
            llm_output = None
        feature_columns = [column for column in columns if column != target_column]
        task.task_type = task_type
        task.target_column = target_column
        task.feature_columns_json = feature_columns
        output = {
            "task_type": task_type,
            "target_column": target_column,
            "feature_columns": feature_columns,
            "reason": (llm_output or {}).get("reason", "根据用户描述和 CSV 列结构自动推断"),
            "llm_used": self.llm_client is not None,
            "llm_output": llm_output,
        }
        self._record_node_output(task, "manager_parse", output)

    def _data_analysis(self, task: AgentTask) -> None:
        # 生成数据概览；真实 LLM 模式下让 Data Agent 复核目标列和特征列。
        state = self._state(task)
        frame = self._load_frame(state)
        columns = [str(column) for column in frame.columns]
        output = {
            "row_count": int(len(frame)),
            "column_count": int(len(frame.columns)),
            "columns": columns,
            "missing_values": {str(k): int(v) for k, v in frame.isna().sum().to_dict().items()},
            "numeric_columns": [str(column) for column in frame.select_dtypes(include="number").columns],
            "sample_rows": json.loads(frame.head(5).to_json(orient="records", force_ascii=False)),
        }
        if self.llm_client:
            selection = self.llm_client.chat_json(
                system_prompt="你是 AI4ML 平台的 Data Agent。请根据任务意图和数据概况复核目标列与候选特征列，只返回 JSON。",
                user_prompt=f"""
任务解析：
{json.dumps(self._state(task).get("context", {}).get("node_outputs", {}).get("manager_parse", {}), ensure_ascii=False, indent=2)}

数据概况：
{json.dumps(output, ensure_ascii=False, indent=2)}

请返回严格 JSON：
{{
  "target_column": "必须是 CSV 列名之一",
  "candidate_feature_columns": ["必须是 CSV 列名，且不包含目标列"],
  "selection_reason": "一句话说明"
}}
""".strip(),
            )
            target_column = self._validate_target_column(selection.get("target_column"), columns)
            feature_columns = self._validate_feature_columns(selection.get("candidate_feature_columns"), columns, target_column)
            task.target_column = target_column
            task.feature_columns_json = feature_columns
            output["target_column"] = target_column
            output["feature_columns"] = feature_columns
            output["selection_reason"] = selection.get("selection_reason", "")
            output["llm_used"] = True
            output["llm_output"] = selection
        self._record_node_output(task, "data_analysis", output)

    def _model_plan(self, task: AgentTask) -> None:
        # 规划候选模型、评估指标和切分策略；真实 LLM 模式下由 Model Agent 给出结构化计划。
        state = self._state(task)
        data_analysis = state.get("context", {}).get("node_outputs", {}).get("data_analysis", {})
        row_count = int(data_analysis.get("row_count") or 0)
        allowed_models = self._allowed_models(task.task_type or "REGRESSION")
        default_metric = "accuracy" if task.task_type == "CLASSIFICATION" else "r2_score"
        if self.llm_client:
            plan = self.llm_client.chat_json(
                system_prompt="你是 AI4ML 平台的 Model Agent。请根据任务类型和数据概况规划可执行的 sklearn 表格建模方案，只返回 JSON。",
                user_prompt=f"""
任务解析：
{json.dumps(state.get("context", {}).get("node_outputs", {}).get("manager_parse", {}), ensure_ascii=False, indent=2)}

数据分析：
{json.dumps(data_analysis, ensure_ascii=False, indent=2)}

可选模型只能从以下列表选择：
{json.dumps(allowed_models, ensure_ascii=False)}

请返回严格 JSON：
{{
  "framework": "sklearn",
  "candidate_models": ["从可选模型中选择 1 到 3 个"],
  "primary_metric": "CLASSIFICATION 只能是 accuracy 或 f1；REGRESSION 只能是 r2_score、r2 或 rmse",
  "train_test_split": 0.2,
  "random_state": 42,
  "use_stratify": true,
  "preprocess": "一句话说明预处理策略",
  "reason": "一句话说明为什么这样规划"
}}
""".strip(),
            )
        else:
            plan = {
                "framework": "sklearn",
                "candidate_models": allowed_models,
                "primary_metric": default_metric,
                "train_test_split": 0.2 if row_count >= 10 else 0.25,
                "random_state": 42,
                "use_stratify": task.task_type == "CLASSIFICATION",
                "preprocess": "数值特征填充中位数并标准化，类别特征填充众数并做 OneHot 编码",
                "reason": "根据任务类型选择轻量可解释基线模型和随机森林模型进行对比。",
            }
        output = self._normalize_model_plan(plan, task.task_type or "REGRESSION", allowed_models)
        self._record_node_output(task, "model_plan", output)

    def _model_training(self, task: AgentTask) -> None:
        # 训练多个候选模型并选择最佳结果，只记录可审计摘要，不持久化 pickle。
        state = self._state(task)
        frame = self._load_frame(state)
        target = task.target_column
        if not target or target not in frame.columns:
            raise DataValidationException("目标列不存在，无法训练")

        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
        from sklearn.impute import SimpleImputer
        from sklearn.linear_model import LinearRegression, LogisticRegression
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import OneHotEncoder, StandardScaler

        plan = self._effective_model_plan(task)
        features = [column for column in (task.feature_columns_json or []) if column in frame.columns and column != target]
        if not features:
            features = [column for column in frame.columns if column != target]
        x = frame[features]
        y = frame[target]
        numeric_features = list(x.select_dtypes(include="number").columns)
        categorical_features = [column for column in features if column not in numeric_features]
        preprocess = ColumnTransformer(
            transformers=[
                ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_features),
                ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical_features),
            ]
        )
        random_state = int(plan.get("random_state", 42))
        estimators = {
            "LinearRegression": LinearRegression(),
            "RandomForestRegressor": RandomForestRegressor(n_estimators=120, random_state=random_state),
            "LogisticRegression": LogisticRegression(max_iter=1000, random_state=random_state),
            "RandomForestClassifier": RandomForestClassifier(n_estimators=120, random_state=random_state),
        }
        candidate_names = [name for name in plan.get("candidate_models", []) if name in estimators]
        if not candidate_names:
            candidate_names = self._allowed_models(task.task_type or "REGRESSION")
        primary_metric = self._normalize_metric(plan.get("primary_metric") or plan.get("metric"), task.task_type or "REGRESSION")
        candidate_models = []
        best_model = None
        best_score = float("inf") if primary_metric == "rmse" else float("-inf")
        train_rows = int(len(frame))
        test_rows = 0
        if len(frame) >= 5 and y.nunique(dropna=True) > 1:
            # 小样本分类在测试集容量不足时不能分层抽样，否则 sklearn 会报错。
            split = float(plan.get("train_test_split", 0.2))
            split = min(0.5, max(0.1, split))
            test_rows = max(1, int(round(len(frame) * split)))
            stratify = y if task.task_type == "CLASSIFICATION" and plan.get("use_stratify") and y.value_counts().min() >= 2 and test_rows >= y.nunique(dropna=True) else None
            x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=split, random_state=random_state, stratify=stratify)
            train_rows = int(len(x_train))
            test_rows = int(len(x_test))
            for model_name in candidate_names:
                try:
                    pipeline = Pipeline([("preprocess", preprocess), ("model", estimators[model_name])])
                    pipeline.fit(x_train, y_train)
                    prediction = pipeline.predict(x_test)
                    metrics = self._evaluate_predictions(task.task_type or "REGRESSION", y_test, prediction)
                    summary = {"model_name": model_name, "metrics": metrics}
                except Exception as exc:
                    summary = {"model_name": model_name, "metrics": {}, "error": str(exc)}
                    candidate_models.append(summary)
                    continue
                candidate_models.append(summary)
                comparable = metrics.get(primary_metric)
                if comparable is None:
                    continue
                is_better = comparable < best_score if primary_metric == "rmse" else comparable > best_score
                if is_better:
                    best_score = comparable
                    best_model = summary
        else:
            for model_name in candidate_names:
                try:
                    pipeline = Pipeline([("preprocess", preprocess), ("model", estimators[model_name])])
                    pipeline.fit(x, y)
                    summary = {"model_name": model_name, "metrics": {}}
                except Exception as exc:
                    summary = {"model_name": model_name, "metrics": {}, "error": str(exc)}
                candidate_models.append(summary)
                if best_model is None and "error" not in summary:
                    best_model = summary
        if best_model is None:
            raise DataValidationException("没有可用模型完成训练")
        metrics = {
            "metric": primary_metric,
            "score": best_model.get("metrics", {}).get(primary_metric),
            "train_rows": train_rows,
            "test_rows": test_rows,
            **best_model.get("metrics", {}),
        }
        feature_importance = self._feature_importance(frame, target, features)
        output = {
            "metrics": metrics,
            "best_model": best_model,
            "candidate_models": candidate_models,
            "model_plan": plan,
            "feature_columns": features,
            "feature_importance": feature_importance,
        }
        task.feature_columns_json = features
        self._record_node_output(task, "model_training", output)
        self._upsert_agent_model(task, metrics)

    def _code_generation(self, task: AgentTask) -> None:
        # 生成可独立运行的训练代码，预测接口会调用其中的 train()。
        state = self._state(task)
        csv_path = state["context"]["csv_path"]
        target = task.target_column
        training = state.get("context", {}).get("node_outputs", {}).get("model_training", {})
        best_model = training.get("best_model", {}).get("model_name")
        features = training.get("feature_columns") or task.feature_columns_json or []
        code_path = self._task_artifact_dir(task) / "generated_model.py"
        code = self._render_training_code(csv_path, target or "", task.task_type or "REGRESSION", best_model, features)
        code_path.write_text(code, encoding="utf-8")
        task.generated_code_path = str(code_path)
        artifacts = state.setdefault("artifacts", {})
        artifacts["generated_code"] = str(code_path)
        artifacts["web_demo"] = f"/api/agent/tasks/{state['task_id']}/predict"
        state.setdefault("context", {})["artifacts"] = artifacts
        task.state_json = state
        flag_modified(task, "state_json")
        self._record_node_output(task, "code_generation", {"generated_code": str(code_path)})

    def _operation_report(self, task: AgentTask) -> None:
        # 汇总前面节点的结构化输出；真实 LLM 模式下生成面向用户的解释和建议。
        state = self._state(task)
        report_path = self._task_artifact_dir(task) / "final_report.json"
        node_outputs = state.get("context", {}).get("node_outputs", {})
        summary = "Agent 已完成数据分析、模型规划、训练评估、代码生成和报告汇总。"
        recommendations = []
        if self.llm_client:
            report_text = self.llm_client.chat_json(
                system_prompt="你是 AI4ML 平台的 Operation Agent。请把建模工作流结果解释给非专业用户，只返回 JSON。",
                user_prompt=f"""
用户需求：
{task.task_description}

需求解析：
{json.dumps(node_outputs.get("manager_parse", {}), ensure_ascii=False, indent=2)}

数据分析：
{json.dumps(node_outputs.get("data_analysis", {}), ensure_ascii=False, indent=2)}

模型规划：
{json.dumps(node_outputs.get("model_plan", {}), ensure_ascii=False, indent=2)}

训练结果：
{json.dumps(node_outputs.get("model_training", {}), ensure_ascii=False, indent=2)}

请返回严格 JSON：
{{
  "summary": "用中文 2 到 4 句话说明本次任务做了什么、模型效果如何、能如何使用",
  "recommendations": ["给零基础用户的使用建议或下一步优化建议，2 到 5 条"],
  "risk_notes": ["数据或模型风险提示，1 到 3 条"]
}}
""".strip(),
            )
            summary = str(report_text.get("summary") or summary)
            recommendations = report_text.get("recommendations") if isinstance(report_text.get("recommendations"), list) else []
            risk_notes = report_text.get("risk_notes") if isinstance(report_text.get("risk_notes"), list) else []
        else:
            risk_notes = ["离线模式使用规则化摘要，未调用真实 LLM 解释结果。"]
        report = {
            "task_id": state.get("task_id"),
            "task_description": task.task_description,
            "task_type": task.task_type,
            "target_column": task.target_column,
            "feature_columns": task.feature_columns_json or [],
            "metrics": node_outputs.get("model_training", {}).get("metrics", {}),
            "model_plan": node_outputs.get("model_plan", {}),
            "model_training": node_outputs.get("model_training", {}),
            "data_analysis": node_outputs.get("data_analysis", {}),
            "summary": summary,
            "recommendations": recommendations,
            "risk_notes": risk_notes,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        task.report_url = str(report_path)
        artifacts = state.setdefault("artifacts", {})
        artifacts["final_report"] = str(report_path)
        task.result_demo_url = f"/api/agent/tasks/{state['task_id']}/predict"
        task.state_json = state
        flag_modified(task, "state_json")
        self._record_node_output(task, "operation_report", {"final_report": str(report_path)})

    def _pause_for_review(self, task: AgentTask, review_stage: str, node: str) -> None:
        # 将节点输出转换为待审核内容，前端提交审核后再进入下一个节点。
        state = self._state(task)
        pending = {
            "review_stage": review_stage,
            "node": node,
            "version": task.version,
            "payload": state.get("context", {}).get("node_outputs", {}).get(node, {}),
        }
        task.status = "WAITING_HUMAN"
        task.current_node = review_stage
        task.pending_review_json = pending
        state["status"] = task.status
        state["current_node"] = review_stage
        state["pending_review"] = pending
        self._sync_task_state(task, state)

    def _complete_task(self, task: AgentTask) -> None:
        # 完成态会清空 current_node 和 pending_review，前端据此停止轮询。
        state = self._state(task)
        task.status = "COMPLETED"
        task.current_node = None
        task.pending_review_json = None
        state["status"] = "COMPLETED"
        state["current_node"] = None
        state["pending_review"] = None
        self._sync_task_state(task, state)

    def _record_node_output(self, task: AgentTask, node: str, output: Dict[str, Any]) -> None:
        # 所有节点输出统一写入 state_json.context.node_outputs，方便审计和工作流分享。
        state = self._state(task)
        context = state.setdefault("context", {})
        context.setdefault("node_outputs", {})[node] = output
        task.state_json = state
        flag_modified(task, "state_json")
        self.db.commit()
        self.db.refresh(task)

    def _sync_task_state(self, task: AgentTask, state: Dict[str, Any]) -> None:
        # 同步数据库字段和 JSON 快照，避免列表接口与详情接口状态不一致。
        task.state_json = state
        flag_modified(task, "state_json")
        self.db.commit()
        self.db.refresh(task)

    def _state(self, task: AgentTask) -> Dict[str, Any]:
        # SQLAlchemy/MySQL JSON 字段读出后应为 dict；这里兜底处理空值。
        return dict(task.state_json or {})

    def _load_frame(self, state: Dict[str, Any]) -> pd.DataFrame:
        # 每个节点按路径重新读取 CSV，保证服务重启后仍可恢复执行。
        csv_path = state.get("context", {}).get("csv_path")
        if not csv_path or not Path(csv_path).exists():
            raise DataValidationException("任务数据集文件不存在")
        return pd.read_csv(csv_path)

    def _allowed_models(self, task_type: str) -> List[str]:
        # 限制 LLM 规划只能选择后端已经实现并测试过的 sklearn 模型。
        if task_type == "CLASSIFICATION":
            return ["LogisticRegression", "RandomForestClassifier"]
        return ["LinearRegression", "RandomForestRegressor"]

    def _normalize_metric(self, metric: Any, task_type: str) -> str:
        # 兼容 r2 / r2_score、大小写和空值，保证训练比较时指标合法。
        value = str(metric or "").lower()
        if task_type == "CLASSIFICATION":
            return "accuracy" if value not in {"f1"} else "f1"
        if value in {"rmse"}:
            return "rmse"
        return "r2_score"

    def _normalize_model_plan(self, plan: Dict[str, Any], task_type: str, allowed_models: List[str]) -> Dict[str, Any]:
        # 真实 LLM 的输出必须被压到可执行范围内，不能让模型名或指标幻觉进入训练。
        raw_candidates = plan.get("candidate_models") or [plan.get("model_name")]
        if not isinstance(raw_candidates, list):
            raw_candidates = [raw_candidates]
        candidate_models = [str(name) for name in raw_candidates if str(name) in allowed_models]
        if not candidate_models:
            candidate_models = allowed_models
        split = plan.get("train_test_split", plan.get("test_size", 0.2))
        try:
            split = float(split)
        except (TypeError, ValueError):
            split = 0.2
        split = min(0.5, max(0.1, split))
        return {
            "framework": "sklearn",
            "model_name": candidate_models[0],
            "candidate_models": candidate_models,
            "metric": self._normalize_metric(plan.get("metric") or plan.get("primary_metric"), task_type),
            "primary_metric": self._normalize_metric(plan.get("primary_metric") or plan.get("metric"), task_type),
            "train_test_split": split,
            "random_state": self._safe_int(plan.get("random_state"), 42),
            "use_stratify": bool(plan.get("use_stratify", task_type == "CLASSIFICATION")),
            "preprocess": str(plan.get("preprocess") or "数值特征填充中位数并标准化，类别特征填充众数并做 OneHot 编码"),
            "reason": str(plan.get("reason") or "根据任务类型和数据规模选择可执行的 sklearn 候选模型。"),
            "llm_used": self.llm_client is not None,
        }

    def _effective_model_plan(self, task: AgentTask) -> Dict[str, Any]:
        # 读取模型规划节点输出，并合并人工审核阶段可能提交的局部修改。
        state = self._state(task)
        plan = dict(state.get("context", {}).get("node_outputs", {}).get("model_plan", {}))
        for item in state.get("context", {}).get("human_patches", []):
            if item.get("stage") != "model_plan_review":
                continue
            patch = item.get("patch") or {}
            for key, value in patch.items():
                normalized_key = key.removeprefix("model_plan.")
                plan[normalized_key] = value
        return self._normalize_model_plan(plan, task.task_type or "REGRESSION", self._allowed_models(task.task_type or "REGRESSION"))

    def _safe_int(self, value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def _evaluate_predictions(self, task_type: str, y_true: pd.Series, prediction: Any) -> Dict[str, float]:
        # 根据任务类型计算适合前端报告展示和模型比较的指标。
        from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score

        if task_type == "CLASSIFICATION":
            return {
                "accuracy": round(float(accuracy_score(y_true, prediction)), 6),
                "f1": round(float(f1_score(y_true, prediction, average="weighted", zero_division=0)), 6),
            }
        return {
            "mae": round(float(mean_absolute_error(y_true, prediction)), 6),
            "rmse": round(float(math.sqrt(mean_squared_error(y_true, prediction))), 6),
            "r2_score": round(float(r2_score(y_true, prediction)), 6),
        }

    def _feature_importance(self, frame: pd.DataFrame, target: str, features: List[str]) -> List[Dict[str, Any]]:
        # 用相关系数生成轻量可解释性信息；非数值字段没有可靠系数时跳过。
        if target not in frame.columns or not pd.api.types.is_numeric_dtype(frame[target]):
            return []
        rows = []
        target_series = frame[target]
        for column in features:
            if column not in frame.columns or not pd.api.types.is_numeric_dtype(frame[column]):
                continue
            corr = frame[column].corr(target_series)
            if pd.isna(corr):
                continue
            rows.append({"feature": column, "importance": round(abs(float(corr)), 6), "direction": "positive" if corr >= 0 else "negative"})
        return sorted(rows, key=lambda item: item["importance"], reverse=True)[:10]

    def _infer_target_column(self, request: str, columns: List[str]) -> str:
        # 优先从用户描述中匹配列名，否则默认最后一列为目标列。
        patterns = [
            r"预测\s*([A-Za-z0-9_\u4e00-\u9fa5]+)",
            r"predict\s+([A-Za-z0-9_]+)",
            r"forecast\s+([A-Za-z0-9_]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, request, re.I)
            if match and match.group(1) in columns:
                return match.group(1)
        lowered_request = request.lower()
        for column in columns:
            if str(column).lower() in lowered_request:
                return column
        return columns[-1]

    def _validate_target_column(self, target_column: Any, columns: List[str]) -> str:
        # 真实 LLM 只能选择已有列名，避免幻觉列名进入训练阶段。
        if target_column not in columns:
            raise DataValidationException("真实 LLM 返回的目标列不在 CSV 中", {"target_column": target_column, "columns": columns})
        return str(target_column)

    def _validate_feature_columns(self, feature_columns: Any, columns: List[str], target_column: str) -> List[str]:
        # 特征列必须是非空列表，且不能包含目标列。
        if not isinstance(feature_columns, list) or not feature_columns:
            raise DataValidationException("真实 LLM 返回的特征列为空或格式错误")
        normalized = [str(column) for column in feature_columns]
        illegal = [column for column in normalized if column not in columns or column == target_column]
        if illegal:
            raise DataValidationException("真实 LLM 返回了非法特征列", {"illegal": illegal, "columns": columns, "target_column": target_column})
        return normalized

    def _normalize_task_type(self, task_type: Any, target_series: pd.Series) -> str:
        # 兼容模型返回大小写或中英文描述，不合法时退回基于目标列的确定性推断。
        value = str(task_type or "").upper()
        if "CLASS" in value or "分类" in value:
            return "CLASSIFICATION"
        if "REG" in value or "回归" in value:
            return "REGRESSION"
        return self._infer_task_type(target_series)

    def _infer_task_type(self, target_series: pd.Series) -> str:
        # 小基数、布尔或字符串目标按分类处理，其余数值目标按回归处理。
        non_null = target_series.dropna()
        if not pd.api.types.is_numeric_dtype(non_null):
            return "CLASSIFICATION"
        if pd.api.types.is_float_dtype(non_null) and not (non_null.dropna() % 1 == 0).all():
            return "REGRESSION"
        unique_count = int(non_null.nunique())
        classification_threshold = min(10, max(2, int(len(non_null) * 0.1)))
        if unique_count <= classification_threshold:
            return "CLASSIFICATION"
        return "REGRESSION"

    def _next_node(self, node: str) -> str | None:
        # 根据固定链路找到下一个节点。
        index = WORKFLOW_NODES.index(node)
        if index + 1 >= len(WORKFLOW_NODES):
            return None
        return WORKFLOW_NODES[index + 1]

    def _task_artifact_dir(self, task: AgentTask) -> Path:
        # 每个任务独立产物目录，防止文件覆盖。
        state = self._state(task)
        task_id = state.get("task_id") or str(task.id)
        artifact_dir = ARTIFACTS_DIR / task_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        return artifact_dir

    def _render_training_code(self, csv_path: str, target_column: str, task_type: str, model_name: str | None, feature_columns: List[str]) -> str:
        # 生成代码跟随训练阶段选出的最佳模型和特征列，预测接口会直接执行该 train()。
        fallback = "RandomForestClassifier" if task_type == "CLASSIFICATION" else "RandomForestRegressor"
        model_class = model_name if model_name in self._allowed_models(task_type) else fallback
        feature_literal = json.dumps(feature_columns, ensure_ascii=False)
        estimator_map = {
            "LinearRegression": "LinearRegression()",
            "RandomForestRegressor": "RandomForestRegressor(n_estimators=120, random_state=42)",
            "LogisticRegression": "LogisticRegression(max_iter=1000, random_state=42)",
            "RandomForestClassifier": "RandomForestClassifier(n_estimators=120, random_state=42)",
        }
        return f'''from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


# 后端生成的训练数据路径，部署时应保证该文件仍在服务器本地。
DATA_PATH = Path(r"{csv_path}")
TARGET_COLUMN = "{target_column}"
FEATURE_COLUMNS = {feature_literal}
MODEL_NAME = "{model_class}"


def train():
    # 训练入口供后端预测接口调用，返回模型、特征列和目标列。
    frame = pd.read_csv(DATA_PATH)
    feature_columns = [column for column in FEATURE_COLUMNS if column in frame.columns and column != TARGET_COLUMN]
    if not feature_columns:
        feature_columns = [column for column in frame.columns if column != TARGET_COLUMN]
    x = frame[feature_columns]
    y = frame[TARGET_COLUMN]
    numeric_features = list(x.select_dtypes(include="number").columns)
    categorical_features = [column for column in feature_columns if column not in numeric_features]
    preprocess = ColumnTransformer(
        transformers=[
            ("num", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), numeric_features),
            ("cat", Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore"))]), categorical_features),
        ]
    )
    estimators = {{
        "LinearRegression": LinearRegression(),
        "RandomForestRegressor": RandomForestRegressor(n_estimators=120, random_state=42),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
        "RandomForestClassifier": RandomForestClassifier(n_estimators=120, random_state=42),
    }}
    model = estimators.get(MODEL_NAME, {estimator_map[model_class]})
    pipeline = Pipeline([("preprocess", preprocess), ("model", model)])
    pipeline.fit(x, y)
    return pipeline, feature_columns, TARGET_COLUMN
'''

    def _upsert_agent_model(self, task: AgentTask, metrics: Dict[str, Any]) -> None:
        # 训练完成后沉淀一条模型资源记录，后续可接入模型广场审核流程。
        existing = self.db.query(AgentModel).filter(AgentModel.task_id == task.id).first()
        if existing:
            existing.performance_metrics = metrics
            self.db.commit()
            return
        model = AgentModel(
            task_id=task.id,
            user_id=task.user_id,
            name=f"Agent 模型 {task.id}",
            description="Agent 自动训练生成的基线模型",
            task_type=task.task_type,
            target_column=task.target_column,
            feature_columns_json=task.feature_columns_json,
            framework="sklearn",
            performance_metrics=metrics,
            model_artifact_path=None,
            is_public=0,
            audit_status="PENDING",
            is_recommended=0,
        )
        self.db.add(model)
        self.db.commit()
