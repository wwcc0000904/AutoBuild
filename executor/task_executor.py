from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import ai
from builder.build_service import BuildService
from config.logging_setup import get_logger
from customer_project.project_manager import CustomerProjectManager
from executor.build_queue import BuildQueue, QueueItemStatus
from executor.validators import validate_user_app, validate_product_model
from patcher.rule_patcher import RulePatcher
from review.review_service import ReviewService
from rules.rule_matcher import build_rule_registry


@dataclass
class TaskRecord:
    task_id: str
    analysis: ai.AnalysisResult
    review_approved: bool
    project_path: str
    build_status: str
    modified_files: list[str]
    validation_warnings: list[str]


class TaskExecutor:
    def __init__(
        self,
        project_manager: CustomerProjectManager,
        review_service: ReviewService,
        build_service: BuildService,
        build_queue: Optional[BuildQueue] = None,
    ) -> None:
        self._project_manager = project_manager
        self._review_service = review_service
        self._build_service = build_service
        self._build_queue = build_queue or BuildQueue()
        self._logger = get_logger()

    def run(self, analysis: ai.AnalysisResult) -> TaskRecord:
        """执行完整流程（审核 → 准备 → 校验 → 规则 → 编译）。"""
        # 等待审核结果（已被 UI 注入）
        review = self._review_service.wait_for_decision()

        if not review.approved:
            raise RuntimeError(f"审核未通过: {review.reason}")

        project = self._project_manager.resolve_target(
            analysis.target_customer_dir, analysis.operation
        )
        target_path = self._project_manager.prepare_target(project)

        # 校验阶段
        validation_warnings: list[str] = []
        validator_modified: list[str] = []

        # 校验并修正 ro.product.model = SMART_TV
        model_result = validate_product_model(target_path)
        if model_result.warnings:
            validation_warnings.extend(model_result.warnings)
            if not model_result.passed:
                self._logger.warning("校验: product model 问题: %s", "; ".join(model_result.warnings))
            else:
                # passed=True 但有 warnings = 自动修正了
                validator_modified.append(str(target_path / "ctvbuild.prop"))
                self._logger.info("校验: %s", model_result.warnings[0])

        # 校验 userApp.xml
        user_app_result = validate_user_app(target_path)
        if not user_app_result.passed:
            validation_warnings.extend(user_app_result.warnings)
            self._logger.warning("校验: userApp.xml 问题: %s", "; ".join(user_app_result.warnings))

        # 规则执行
        rule_registry = build_rule_registry(analysis.modifications)
        patcher = RulePatcher(rule_registry, target_path)
        changed = patcher.apply_all()

        # 合并校验器修改的文件和规则修改的文件
        all_modified = validator_modified + [str(f) for f in changed]

        build_job = self._build_service.submit(str(target_path))

        self._logger.info(
            "任务完成: dir=%s rules=%d changed=%d build=%s",
            target_path, len(rule_registry.rules), len(all_modified), build_job.status,
        )

        return TaskRecord(
            task_id=f"task-{uuid.uuid4().hex[:12]}",
            analysis=analysis,
            review_approved=review.approved,
            project_path=str(target_path),
            build_status=build_job.status,
            modified_files=all_modified,
            validation_warnings=validation_warnings,
        )

    def run_to_queue(self, analysis: ai.AnalysisResult) -> TaskRecord:
        """执行到编译队列（审核 → 准备 → 校验 → 规则 → 加入队列，不编译）。"""
        # 等待审核结果（已被 UI 注入）
        review = self._review_service.wait_for_decision()

        if not review.approved:
            raise RuntimeError(f"审核未通过: {review.reason}")

        project = self._project_manager.resolve_target(
            analysis.target_customer_dir, analysis.operation
        )
        target_path = self._project_manager.prepare_target(project)

        # 校验阶段
        validation_warnings: list[str] = []
        validator_modified: list[str] = []

        # 校验并修正 ro.product.model = SMART_TV
        model_result = validate_product_model(target_path)
        if model_result.warnings:
            validation_warnings.extend(model_result.warnings)
            if not model_result.passed:
                self._logger.warning("校验: product model 问题: %s", "; ".join(model_result.warnings))
            else:
                validator_modified.append(str(target_path / "ctvbuild.prop"))
                self._logger.info("校验: %s", model_result.warnings[0])

        # 校验 userApp.xml
        user_app_result = validate_user_app(target_path)
        if not user_app_result.passed:
            validation_warnings.extend(user_app_result.warnings)
            self._logger.warning("校验: userApp.xml 问题: %s", "; ".join(user_app_result.warnings))

        # 规则执行
        rule_registry = build_rule_registry(analysis.modifications)
        patcher = RulePatcher(rule_registry, target_path)
        changed = patcher.apply_all()

        # 合并校验器修改的文件和规则修改的文件
        all_modified = validator_modified + [str(f) for f in changed]

        # 添加到编译队列（不立即编译）
        queue_item = self._build_queue.add(
            customer_name=analysis.customer or analysis.target_customer_dir,
            project_path=str(target_path),
            modified_files=all_modified,
            analysis_summary=analysis.notes[:200] if analysis.notes else "",
        )

        self._logger.info(
            "任务已加入编译队列: dir=%s rules=%d changed=%d queue_id=%s",
            target_path, len(rule_registry.rules), len(all_modified), queue_item.id,
        )

        return TaskRecord(
            task_id=f"task-{uuid.uuid4().hex[:12]}",
            analysis=analysis,
            review_approved=review.approved,
            project_path=str(target_path),
            build_status="queued",
            modified_files=all_modified,
            validation_warnings=validation_warnings,
        )

    def build_from_queue(self, queue_id: str) -> bool:
        """从队列中取出一个项并开始编译。"""
        item = self._build_queue.get_by_id(queue_id)
        if not item or item.status != QueueItemStatus.PENDING:
            return False

        # 更新状态为编译中
        self._build_queue.update_status(queue_id, QueueItemStatus.BUILDING)

        # 注册编译完成回调：编译结束后自动更新队列状态
        def _on_finished(status: str, exit_code: int) -> None:
            if status == "succeeded":
                self._build_queue.update_status(
                    queue_id, QueueItemStatus.SUCCEEDED, exit_code=exit_code
                )
            elif status == "failed":
                self._build_queue.update_status(
                    queue_id, QueueItemStatus.FAILED, exit_code=exit_code
                )
            self._logger.info(
                "队列编译完成: %s -> status=%s exit=%s", queue_id, status, exit_code
            )

        self._build_service.set_callbacks(on_finished=_on_finished)

        # 提交编译任务
        build_job = self._build_service.submit(item.project_path)

        # 更新任务ID
        self._build_queue.update_status(queue_id, QueueItemStatus.BUILDING, task_id=build_job.task_id)

        self._logger.info("从队列开始编译: %s -> %s", queue_id, build_job.task_id)
        return True
