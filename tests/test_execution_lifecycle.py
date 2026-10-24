"""Regressions for shutdown accounting and honest workflow outcomes."""
import asyncio
from unittest.mock import AsyncMock

import pytest

from src.automation.queue_worker import QueueTask, QueueWorker, TaskStatus
from src.automation.workflow_engine import WorkflowDefinition, WorkflowEngine, WorkflowStep
from src.core.state_manager import StateManager


async def test_graceful_shutdown_drains_cancelled_and_pending_tasks():
    worker = QueueWorker(AsyncMock(), AsyncMock(), StateManager(), concurrency=1)
    seen = []

    async def execute(task):
        seen.append(task.id)
        worker._queue.task_done()

    worker._execute_task = execute
    cancelled = QueueTask(created_at=1)
    remaining = QueueTask(created_at=1)
    await worker.enqueue(cancelled)
    await worker.enqueue(remaining)
    assert await worker.cancel_task(cancelled.id)
    await worker.start()
    await asyncio.wait_for(worker.stop(), timeout=2)
    assert seen == [remaining.id]
    assert cancelled.status == TaskStatus.CANCELLED
    assert worker._queue.qsize() == 0
    with pytest.raises(RuntimeError, match='stopping'):
        await worker.enqueue(QueueTask())


@pytest.mark.parametrize('failure', ['missing_agent', 'registry_error', 'cycle'])
async def test_failed_or_blocked_workflow_never_reports_success(failure):
    registry = AsyncMock()
    registry.get_agent.return_value = None
    if failure == 'registry_error':
        registry.get_agent.side_effect = RuntimeError('Registry unavailable')
    step = WorkflowStep(id='one', agent_slug='test', depends_on=['one'] if failure == 'cycle' else [])
    engine = WorkflowEngine(registry, AsyncMock(), StateManager(), None)
    result = await engine.execute(WorkflowDefinition(steps=[step]), {})
    assert not result.success
    assert result.error
    assert engine.get_workflow_status(result.workflow_id)['status'] == 'failed'


async def test_full_retry_queue_does_not_deadlock_worker(monkeypatch):
    registry = AsyncMock()
    registry.get_agent.side_effect = RuntimeError('Temporary failure')
    worker = QueueWorker(registry, AsyncMock(), StateManager(), max_queue_size=1)
    task = QueueTask()
    await worker.enqueue(task)
    await worker._queue.get()
    await worker.enqueue(QueueTask())
    # Skip only the retry backoff; the queue accounting remains real.
    monkeypatch.setattr('src.automation.queue_worker.asyncio.sleep', AsyncMock())
    await asyncio.wait_for(worker._execute_task(task), timeout=1)
    assert task.status == TaskStatus.FAILED
    assert task.error == 'Retry queue is full'
    await worker._queue.get()
    worker._queue.task_done()
    await asyncio.wait_for(worker._queue.join(), timeout=1)


async def test_successful_empty_workflow_still_completes():
    engine = WorkflowEngine(AsyncMock(), AsyncMock(), StateManager(), None)
    result = await engine.execute(WorkflowDefinition(steps=[]), {})
    assert result.success
    assert result.error is None
