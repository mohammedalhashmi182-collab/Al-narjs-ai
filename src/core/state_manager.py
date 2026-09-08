from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from src.utils.logger import get_logger

logger = get_logger(__name__)


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepState:
    step_id: str
    agent_slug: str
    status: StepStatus = StepStatus.PENDING
    input_data: dict = field(default_factory=dict)
    output_data: dict = field(default_factory=dict)
    error: str | None = None
    retry_count: int = 0
    started_at: float | None = None
    completed_at: float | None = None
    model_used: str | None = None
    tokens_used: int = 0
    latency_ms: int = 0


@dataclass
class WorkflowState:
    workflow_id: UUID
    workflow_slug: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    steps: dict[str, StepState] = field(default_factory=dict)
    global_context: dict = field(default_factory=dict)
    current_step: str | None = None
    trigger_type: str = "manual"
    trigger_payload: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    completed_at: float | None = None
    error: str | None = None

    def get_step(self, step_id: str) -> StepState | None:
        return self.steps.get(step_id)

    def get_completed_steps(self) -> list[StepState]:
        return [s for s in self.steps.values() if s.status == StepStatus.COMPLETED]

    def get_failed_steps(self) -> list[StepState]:
        return [s for s in self.steps.values() if s.status == StepStatus.FAILED]

    def is_complete(self) -> bool:
        if not self.steps:
            return True
        return all(
            s.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.FAILED)
            for s in self.steps.values()
        )


class StateManager:
    def __init__(self, db_session_factory=None):
        self._db_session_factory = db_session_factory
        self._states: dict[UUID, WorkflowState] = {}
        self._step_results: dict[UUID, dict[str, Any]] = defaultdict(dict)

    def create_workflow(
        self,
        workflow_slug: str,
        steps: list[dict],
        trigger_type: str = "manual",
        trigger_payload: dict | None = None,
    ) -> WorkflowState:
        workflow_id = uuid4()
        state = WorkflowState(
            workflow_id=workflow_id,
            workflow_slug=workflow_slug,
            trigger_type=trigger_type,
            trigger_payload=trigger_payload or {},
        )
        for step_def in steps:
            step_id = step_def.get("id", step_def.get("agent_slug"))
            state.steps[step_id] = StepState(
                step_id=step_id,
                agent_slug=step_def.get("agent_slug", step_id),
            )
        self._states[workflow_id] = state
        return state

    def get_workflow(self, workflow_id: UUID) -> WorkflowState | None:
        return self._states.get(workflow_id)

    def update_workflow_status(self, workflow_id: UUID, status: WorkflowStatus, error: str | None = None):
        state = self._states.get(workflow_id)
        if state:
            state.status = status
            if error:
                state.error = error
            if status == WorkflowStatus.RUNNING and not state.started_at:
                state.started_at = time.time()
            elif status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
                state.completed_at = time.time()

    def start_step(self, workflow_id: UUID, step_id: str) -> bool:
        state = self._states.get(workflow_id)
        if not state:
            return False
        step = state.steps.get(step_id)
        if not step:
            return False
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        state.current_step = step_id
        return True

    def complete_step(
        self,
        workflow_id: UUID,
        step_id: str,
        output_data: dict,
        model_used: str | None = None,
        tokens_used: int = 0,
        latency_ms: int = 0,
    ) -> bool:
        state = self._states.get(workflow_id)
        if not state:
            return False
        step = state.steps.get(step_id)
        if not step:
            return False
        step.status = StepStatus.COMPLETED
        step.output_data = output_data
        step.completed_at = time.time()
        step.model_used = model_used
        step.tokens_used = tokens_used
        step.latency_ms = latency_ms
        self._step_results[workflow_id][step_id] = output_data
        state.global_context[step_id] = output_data
        return True

    def fail_step(self, workflow_id: UUID, step_id: str, error: str) -> bool:
        state = self._states.get(workflow_id)
        if not state:
            return False
        step = state.steps.get(step_id)
        if not step:
            return False
        step.status = StepStatus.FAILED
        step.error = error
        step.completed_at = time.time()
        return True

    def skip_step(self, workflow_id: UUID, step_id: str) -> bool:
        state = self._states.get(workflow_id)
        if not state:
            return False
        step = state.steps.get(step_id)
        if not step:
            return False
        step.status = StepStatus.SKIPPED
        step.completed_at = time.time()
        return True

    def get_step_input(self, workflow_id: UUID, step_id: str, depends_on: list[str]) -> dict:
        input_data = {}
        for dep_id in depends_on:
            if dep_id in self._step_results[workflow_id]:
                input_data[dep_id] = self._step_results[workflow_id][dep_id]
        return input_data

    def get_global_context(self, workflow_id: UUID) -> dict:
        state = self._states.get(workflow_id)
        return state.global_context if state else {}

    def set_global_context(self, workflow_id: UUID, key: str, value: Any):
        state = self._states.get(workflow_id)
        if state:
            state.global_context[key] = value

    def can_execute_step(self, workflow_id: UUID, step_id: str, depends_on: list[str]) -> bool:
        state = self._states.get(workflow_id)
        if not state:
            return False
        step = state.steps.get(step_id)
        if not step or step.status != StepStatus.PENDING:
            return False
        for dep_id in depends_on:
            dep_step = state.steps.get(dep_id)
            if not dep_step or dep_step.status != StepStatus.COMPLETED:
                return False
        return True

    def get_next_executable_steps(self, workflow_id: UUID, all_steps: dict[str, dict]) -> list[str]:
        state = self._states.get(workflow_id)
        if not state:
            return []
        executable = []
        for step_id, step_def in all_steps.items():
            step_state = state.steps.get(step_id)
            if not step_state or step_state.status != StepStatus.PENDING:
                continue
            depends_on = step_def.get("depends_on", [])
            if self.can_execute_step(workflow_id, step_id, depends_on):
                executable.append(step_id)
        return executable

    def persist(self, workflow_id: UUID) -> None:
        if not self._db_session_factory:
            return
        state = self._states.get(workflow_id)
        if not state:
            return
        try:
            asyncio.create_task(self._persist_async(workflow_id, state))
        except Exception as e:
            logger.exception(f"Failed to persist workflow state: {e}")

    async def _persist_async(self, workflow_id: UUID, state: WorkflowState) -> None:
        if not self._db_session_factory:
            return
        async with self._db_session_factory() as session:
            from src.models import StepExecution, WorkflowExecution

            exec_result = await session.execute(
                select(WorkflowExecution).where(WorkflowExecution.id == workflow_id)
            )
            execution = exec_result.scalar_one_or_none()

            if execution is None:
                execution = WorkflowExecution(
                    id=workflow_id,
                    workflow_id=state.workflow_slug,
                    trigger_type=state.trigger_type,
                    trigger_payload=state.trigger_payload,
                    status=state.status.value,
                    current_step=state.current_step,
                    context=state.global_context,
                    started_at=state.started_at,
                    completed_at=state.completed_at,
                    error=state.error,
                )
                session.add(execution)
            else:
                execution.status = state.status.value
                execution.current_step = state.current_step
                execution.context = state.global_context
                execution.completed_at = state.completed_at
                execution.error = state.error

            for step_id, step_state in state.steps.items():
                step_result = await session.execute(
                    select(StepExecution).where(
                        StepExecution.workflow_execution_id == workflow_id,
                        StepExecution.step_id == step_id,
                    )
                )
                step_exec = step_result.scalar_one_or_none()

                if step_exec is None:
                    step_exec = StepExecution(
                        workflow_execution_id=workflow_id,
                        step_id=step_id,
                        agent_slug=step_state.agent_slug,
                        input_data=step_state.input_data,
                        output_data=step_state.output_data,
                        model_used=step_state.model_used,
                        tokens_used=step_state.tokens_used,
                        latency_ms=step_state.latency_ms,
                        status=step_state.status.value,
                        error=step_state.error,
                        retry_count=step_state.retry_count,
                        started_at=step_state.started_at,
                        completed_at=step_state.completed_at,
                    )
                    session.add(step_exec)
                else:
                    step_exec.status = step_state.status.value
                    step_exec.output_data = step_state.output_data
                    step_exec.model_used = step_state.model_used
                    step_exec.tokens_used = step_state.tokens_used
                    step_exec.latency_ms = step_state.latency_ms
                    step_exec.error = step_state.error
                    step_exec.retry_count = step_state.retry_count
                    step_exec.completed_at = step_state.completed_at

            await session.commit()

    def cleanup(self, workflow_id: UUID) -> bool:
        if workflow_id in self._states:
            del self._states[workflow_id]
        if workflow_id in self._step_results:
            del self._step_results[workflow_id]
        return True

    def get_stats(self) -> dict:
        return {
            "active_workflows": len(self._states),
            "status_counts": {
                status.value: sum(1 for s in self._states.values() if s.status == status)
                for status in WorkflowStatus
            },
        }
