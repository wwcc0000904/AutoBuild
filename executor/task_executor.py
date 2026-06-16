from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import ai
from builder.build_service import BuildService
from config.logging_setup import get_logger
from customer_project.project_manager import CustomerProjectManager
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
    ) -> None:
        self._project_manager = project_manager
        self._review_service = review_service
        self._build_service = build_service
        self._logger = get_logger()

    def run(self, analysis: ai.AnalysisResult) -> TaskRecord:
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
