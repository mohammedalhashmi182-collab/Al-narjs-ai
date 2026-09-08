from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import deque

from src.core.model_provider import ModelProvider, ModelRequest
from src.core.agent_registry import AgentRegistry
from src.core.prompt_engine import PromptEngine
from src.core.state_manager import StateManager, StepStatus, WorkflowStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TaskPriority(int, Enum):
    LOW = 0
    NORMAL = 50
    HIGH = 100
    CRITICAL = 200


class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class QueueTask:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_slug: str = ""
    prompt_template: str = "default"
    input_data: dict = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    max_retries: int = 3
    retry_count: int = 0
    timeout_seconds: int = 300
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    callback: Optional[Callable] = None
    metadata: dict = field(default_factory=dict)


class QueueWorker:
    def __init__(
        self,
        agent_registry: AgentRegistry,
        model_provider: ModelProvider,
        state_manager: StateManager,
        concurrency: int = 4,
        max_queue_size: int = 1000,
    ):
        self.agent_registry = agent_registry
        self.model_provider = model_provider
        self.state_manager = state_manager
        self.concurrency = concurrency
        self.max_queue_size = max_queue_size

        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=max_queue_size)
        self._running_tasks: dict[str, QueueTask] = {}
        self._completed_tasks: deque = deque(maxlen=1000)
        self._workers: list[asyncio.Task] = []
        self._running = False
        self._semaphore = asyncio.Semaphore(concurrency)

    async def start(self):
        if self._running:
            return
        self._running = True
        for i in range(self.concurrency):
            worker = asyncio.create_task(self._worker_loop(i))
            self._workers.append(worker)
        logger.info(f"Queue worker started with {self.concurrency} workers")

    async def stop(self, wait: bool = True):
        if not self._running:
            return
        self._running = False

        if wait:
            await self._queue.join()

        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Queue worker stopped")

    async def enqueue(self, task: QueueTask) -> str:
        if self._queue.full():
            raise RuntimeError("Queue is full")

        task.status = TaskStatus.QUEUED
        priority = -task.priority.value
        await self._queue.put((priority, task.created_at, task))
        logger.debug(f"Task {task.id} enqueued with priority {task.priority.name}")
        return task.id

    async def enqueue_agent(
        self,
        agent_slug: str,
        input_data: dict,
        prompt_template: str = "default",
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
        timeout_seconds: int = 300,
        callback: Optional[Callable] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        task = QueueTask(
            agent_slug=agent_slug,
            prompt_template=prompt_template,
            input_data=input_data,
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            callback=callback,
            metadata=metadata or {},
        )
        return await self.enqueue(task)

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        for _, _, task in self._queue._queue:
            if task.id == task_id:
                return task.status

        if task_id in self._running_tasks:
            return self._running_tasks[task_id].status

        for task in self._completed_tasks:
            if task.id == task_id:
                return task.status

        return None

    def get_task_result(self, task_id: str) -> Optional[dict]:
        for _, _, task in self._queue._queue:
            if task.id == task_id:
                return task.result

        if task_id in self._running_tasks:
            return self._running_tasks[task_id].result

        for task in self._completed_tasks:
            if task.id == task_id:
                return task.result

        return None

    async def cancel_task(self, task_id: str) -> bool:
        for i, (_, _, task) in enumerate(self._queue._queue):
            if task.id == task_id:
                task.status = TaskStatus.CANCELLED
                self._queue._queue.pop(i)
                return True

        if task_id in self._running_tasks:
            self._running_tasks[task_id].status = TaskStatus.CANCELLED
            return True

        return False

    def get_queue_stats(self) -> dict:
        queued = sum(1 for _, _, task in self._queue._queue if task.status == TaskStatus.QUEUED)
        running = len(self._running_tasks)
        completed = len([t for t in self._completed_tasks if t.status == TaskStatus.COMPLETED])
        failed = len([t for t in self._completed_tasks if t.status == TaskStatus.FAILED])

        return {
            "queued": queued,
            "running": running,
            "completed": completed,
            "failed": failed,
            "total_processed": completed + failed,
            "queue_size": self._queue.qsize(),
            "max_queue_size": self.max_queue_size,
        }

    async def _worker_loop(self, worker_id: int):
        logger.debug(f"Worker {worker_id} started")
        while self._running:
            try:
                priority, created_at, task = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=1.0,
                )

                if task.status == TaskStatus.CANCELLED:
                    self._queue.task_done()
                    continue

                await self._execute_task(task)

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.exception(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)

    async def _execute_task(self, task: QueueTask):
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        self._running_tasks[task.id] = task

        try:
            agent_def = await self.agent_registry.get_agent(task.agent_slug)
            if not agent_def:
                raise ValueError(f"Agent {task.agent_slug} not found")

            prompt_template = agent_def.prompt_templates.get(task.prompt_template)
            if not prompt_template:
                raise ValueError(f"Prompt template {task.prompt_template} not found")

            prompt_engine = PromptEngine()
            rendered = prompt_engine.render(prompt_template.template_text, task.input_data)

            request = ModelRequest(
                prompt=rendered.user_prompt,
                system_prompt=rendered.system_prompt,
                temperature=agent_def.default_parameters.get("temperature", 0.7),
                max_tokens=agent_def.default_parameters.get("max_tokens", 2000),
                top_p=agent_def.default_parameters.get("top_p", 1.0),
                metadata=task.metadata,
            )

            response = await asyncio.wait_for(
                self.model_provider.complete(agent_def.default_model, request),
                timeout=task.timeout_seconds,
            )

            task.result = {
                "content": response.content,
                "structured_output": response.structured_output.model_dump() if response.structured_output else None,
                "tokens_used": response.tokens_used,
                "latency_ms": response.latency_ms,
                "model": response.model,
            }
            task.status = TaskStatus.COMPLETED

            if task.callback:
                try:
                    await task.callback(task.result)
                except Exception as e:
                    logger.warning(f"Task callback failed: {e}")

        except asyncio.TimeoutError:
            task.error = f"Task timeout after {task.timeout_seconds}s"
            task.status = TaskStatus.FAILED
            logger.warning(f"Task {task.id} timed out")

        except Exception as e:
            task.error = str(e)
            task.retry_count += 1

            if task.retry_count < task.max_retries:
                task.status = TaskStatus.QUEUED
                priority = -task.priority.value
                await asyncio.sleep(2 ** task.retry_count)
                await self._queue.put((priority, time.time(), task))
                logger.info(f"Task {task.id} requeued for retry {task.retry_count}/{task.max_retries}")
            else:
                task.status = TaskStatus.FAILED
                logger.exception(f"Task {task.id} failed after {task.retry_count} retries: {e}")

        finally:
            task.completed_at = time.time()
            self._running_tasks.pop(task.id, None)
            self._completed_tasks.append(task)
            self._queue.task_done()