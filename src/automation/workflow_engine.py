from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.core.state_manager import StateManager, WorkflowState, StepState, WorkflowStatus, StepStatus
from src.core.model_provider import ModelProvider, ModelRequest
from src.core.agent_registry import AgentRegistry
from src.core.context_manager import ContextManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class StepCondition(BaseModel):
    type: str = "expression"
    expression: str


class WorkflowStep(BaseModel):
    id: str
    agent_slug: str
    prompt_template: str = "default"
    depends_on: list[str] = Field(default_factory=list)
    condition: Optional[StepCondition] = None
    config: dict = Field(default_factory=dict)
    retry_count: int = 0
    timeout_seconds: int = 300


class WorkflowDefinition(BaseModel):
    version: int = 1
    steps: list[WorkflowStep]
    global_config: dict = Field(default_factory=dict)


@dataclass
class ExecutionResult:
    workflow_id: UUID
    success: bool
    final_context: dict
    error: Optional[str] = None
    steps_completed: int = 0
    steps_failed: int = 0
    total_latency_ms: int = 0


class WorkflowEngine:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        model_provider: ModelProvider,
        state_manager: StateManager,
        context_manager: ContextManager,
        max_concurrent_steps: int = 4,
    ):
        self.agent_registry = agent_registry
        self.model_provider = model_provider
        self.state_manager = state_manager
        self.context_manager = context_manager
        self.max_concurrent_steps = max_concurrent_steps
        self._running_workflows: dict[UUID, asyncio.Task] = {}

    async def execute(
        self,
        workflow_def: WorkflowDefinition,
        initial_context: dict,
        trigger_type: str = "manual",
        trigger_payload: Optional[dict] = None,
    ) -> ExecutionResult:
        workflow_id = self.state_manager.create_workflow(
            workflow_slug=workflow_def.global_config.get("slug", "workflow"),
            steps=[step.model_dump() for step in workflow_def.steps],
            trigger_type=trigger_type,
            trigger_payload=trigger_payload or {},
        ).workflow_id

        state = self.state_manager.get_workflow(workflow_id)
        if not state:
            return ExecutionResult(
                workflow_id=workflow_id,
                success=False,
                final_context={},
                error="Failed to create workflow state",
            )

        self.state_manager.update_workflow_status(workflow_id, WorkflowStatus.RUNNING)

        try:
            await self._execute_workflow(workflow_id, workflow_def, initial_context, state)
            state = self.state_manager.get_workflow(workflow_id)
            return ExecutionResult(
                workflow_id=workflow_id,
                success=state.status == WorkflowStatus.COMPLETED,
                final_context=state.global_context,
                error=state.error,
                steps_completed=len(state.get_completed_steps()),
                steps_failed=len(state.get_failed_steps()),
                total_latency_ms=sum(s.latency_ms for s in state.steps.values()),
            )
        except Exception as e:
            logger.exception(f"Workflow {workflow_id} execution failed: {e}")
            self.state_manager.update_workflow_status(workflow_id, WorkflowStatus.FAILED, str(e))
            return ExecutionResult(
                workflow_id=workflow_id,
                success=False,
                final_context={},
                error=str(e),
            )

    async def _execute_workflow(
        self,
        workflow_id: UUID,
        workflow_def: WorkflowDefinition,
        initial_context: dict,
        state: WorkflowState,
    ):
        state.global_context.update(initial_context)
        step_map = {step.id: step for step in workflow_def.steps}

        while True:
            executable_steps = self.state_manager.get_next_executable_steps(workflow_id, {s.id: s.model_dump() for s in workflow_def.steps})

            if not executable_steps:
                if state.is_complete():
                    self.state_manager.update_workflow_status(workflow_id, WorkflowStatus.COMPLETED)
                else:
                    failed = state.get_failed_steps()
                    if failed:
                        self.state_manager.update_workflow_status(
                            workflow_id,
                            WorkflowStatus.FAILED,
                            f"Steps failed: {[s.step_id for s in failed]}"
                        )
                    else:
                        self.state_manager.update_workflow_status(workflow_id, WorkflowStatus.COMPLETED)
                break

            semaphore = asyncio.Semaphore(self.max_concurrent_steps)

            async def execute_step_with_semaphore(step_id: str):
                async with semaphore:
                    await self._execute_step(workflow_id, step_id, step_map[step_id], state)

            tasks = [execute_step_with_semaphore(step_id) for step_id in executable_steps]
            await asyncio.gather(*tasks, return_exceptions=True)

            await asyncio.sleep(0.1)

    async def _execute_step(
        self,
        workflow_id: UUID,
        step_id: str,
        step_def: WorkflowStep,
        state: WorkflowState,
    ):
        if not self.state_manager.start_step(workflow_id, step_id):
            return

        if step_def.condition and not self._evaluate_condition(step_def.condition, state.global_context):
            self.state_manager.skip_step(workflow_id, step_id)
            logger.info(f"Step {step_id} skipped due to condition")
            return

        input_data = self.state_manager.get_step_input(workflow_id, step_id, step_def.depends_on)
        input_data.update(state.global_context)

        agent_def = await self.agent_registry.get_agent(step_def.agent_slug)
        if not agent_def:
            error = f"Agent {step_def.agent_slug} not found"
            self.state_manager.fail_step(workflow_id, step_id, error)
            logger.error(error)
            return

        prompt_template = agent_def.prompt_templates.get(step_def.prompt_template)
        if not prompt_template:
            error = f"Prompt template {step_def.prompt_template} not found for agent {step_def.agent_slug}"
            self.state_manager.fail_step(workflow_id, step_id, error)
            logger.error(error)
            return

        from src.core.prompt_engine import PromptEngine
        prompt_engine = PromptEngine()
        rendered = prompt_engine.render(prompt_template.template_text, input_data)

        if rendered.missing_variables and prompt_engine.strict:
            error = f"Missing variables for step {step_id}: {rendered.missing_variables}"
            self.state_manager.fail_step(workflow_id, step_id, error)
            return

        request = ModelRequest(
            prompt=rendered.user_prompt,
            system_prompt=rendered.system_prompt,
            temperature=agent_def.default_parameters.get("temperature", 0.7),
            max_tokens=agent_def.default_parameters.get("max_tokens", 2000),
            top_p=agent_def.default_parameters.get("top_p", 1.0),
            metadata={"workflow_id": str(workflow_id), "step_id": step_id},
        )

        try:
            start_time = time.perf_counter()
            response = await self.model_provider.complete(
                agent_def.default_model,
                request,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            output_data = {
                "content": response.content,
                "structured_output": response.structured_output.model_dump() if response.structured_output else None,
                "tokens_used": response.tokens_used,
            }

            self.state_manager.complete_step(
                workflow_id=workflow_id,
                step_id=step_id,
                output_data=output_data,
                model_used=response.model,
                tokens_used=response.tokens_used,
                latency_ms=latency_ms,
            )

            logger.info(f"Step {step_id} completed in {latency_ms}ms")

        except Exception as e:
            logger.exception(f"Step {step_id} failed: {e}")
            self.state_manager.fail_step(workflow_id, step_id, str(e))

    def _evaluate_condition(self, condition: StepCondition, context: dict) -> bool:
        try:
            from jinja2 import Environment, BaseLoader
            env = Environment(loader=BaseLoader())
            template = env.from_string(f"{{% if {condition.expression} %}}true{{% else %}}false{{% endif %}}")
            result = template.render(**context)
            return result.strip().lower() == "true"
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
            return False

    async def cancel_workflow(self, workflow_id: UUID) -> bool:
        state = self.state_manager.get_workflow(workflow_id)
        if not state or state.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED):
            return False

        self.state_manager.update_workflow_status(workflow_id, WorkflowStatus.CANCELLED)
        if workflow_id in self._running_workflows:
            self._running_workflows[workflow_id].cancel()
            del self._running_workflows[workflow_id]
        return True

    def get_workflow_status(self, workflow_id: UUID) -> Optional[dict]:
        state = self.state_manager.get_workflow(workflow_id)
        if not state:
            return None

        return {
            "workflow_id": str(state.workflow_id),
            "workflow_slug": state.workflow_slug,
            "status": state.status.value,
            "current_step": state.current_step,
            "steps": {
                step_id: {
                    "status": step_state.status.value,
                    "agent_slug": step_state.agent_slug,
                    "started_at": step_state.started_at,
                    "completed_at": step_state.completed_at,
                    "error": step_state.error,
                    "latency_ms": step_state.latency_ms,
                }
                for step_id, step_state in state.steps.items()
            },
            "global_context": state.global_context,
            "created_at": state.created_at,
            "started_at": state.started_at,
            "completed_at": state.completed_at,
        }