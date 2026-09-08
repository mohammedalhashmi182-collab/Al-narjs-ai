from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import UUID

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TriggerConfig:
    name: str
    trigger_type: str
    target_type: str
    target_id: UUID
    config: dict = field(default_factory=dict)
    payload_template: Optional[dict] = None
    is_active: bool = True


class WebhookTriggerHandler:
    def __init__(self, secret: Optional[str] = None):
        self.secret = secret
        self._handlers: dict[str, Callable] = {}

    def register(self, path: str, handler: Callable):
        self._handlers[path] = handler

    async def handle_request(self, path: str, payload: dict, headers: dict) -> dict:
        if path not in self._handlers:
            return {"status": "error", "message": f"No handler for path: {path}"}

        if self.secret:
            signature = headers.get("X-Signature", "")
            if not self._verify_signature(payload, signature):
                return {"status": "error", "message": "Invalid signature"}

        try:
            result = await self._handlers[path](payload)
            return {"status": "success", "result": result}
        except Exception as e:
            logger.exception(f"Webhook handler error: {e}")
            return {"status": "error", "message": str(e)}

    def _verify_signature(self, payload: dict, signature: str) -> bool:
        expected = hmac.new(
            self.secret.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)


class FileWatchHandler(FileSystemEventHandler):
    def __init__(self, callback: Callable, patterns: list[str] = None):
        super().__init__()
        self.callback = callback
        self.patterns = patterns or ["*"]

    def _should_process(self, path: str) -> bool:
        path_obj = Path(path)
        return any(path_obj.match(p) for p in self.patterns)

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            asyncio.create_task(self.callback(event.src_path, "created"))

    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            asyncio.create_task(self.callback(event.src_path, "modified"))

    def on_deleted(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            asyncio.create_task(self.callback(event.src_path, "deleted"))


class DatabasePollTrigger:
    def __init__(self, session_factory, query: str, interval: float = 60.0):
        self.session_factory = session_factory
        self.query = query
        self.interval = interval
        self._last_seen: set = set()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self, callback: Callable):
        self._running = True
        self._task = asyncio.create_task(self._poll_loop(callback))

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _poll_loop(self, callback: Callable):
        while self._running:
            try:
                async with self.session_factory() as session:
                    from sqlalchemy import text
                    result = await session.execute(text(self.query))
                    rows = result.fetchall()

                    current_ids = set()
                    for row in rows:
                        row_id = row[0] if len(row) == 1 else tuple(row)
                        current_ids.add(row_id)
                        if row_id not in self._last_seen:
                            await callback(dict(row._mapping) if hasattr(row, '_mapping') else dict(zip(result.keys(), row)))

                    self._last_seen = current_ids
            except Exception as e:
                logger.exception(f"Database poll error: {e}")

            await asyncio.sleep(self.interval)


class TriggerEngine:
    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.webhook_handler = WebhookTriggerHandler()
        self.file_observer: Optional[Observer] = None
        self.file_watches: dict[str, tuple] = {}
        self.db_polls: dict[str, DatabasePollTrigger] = {}
        self._trigger_callbacks: dict[str, Callable] = {}

    async def start(self):
        self.file_observer = Observer()
        self.file_observer.start()
        await self._load_triggers_from_db()
        logger.info("Trigger engine started")

    async def stop(self):
        if self.file_observer:
            self.file_observer.stop()
            self.file_observer.join()

        for poll in self.db_polls.values():
            await poll.stop()

        logger.info("Trigger engine stopped")

    async def _load_triggers_from_db(self):
        async with self.session_factory() as session:
            from src.models import Trigger
            from sqlalchemy import select
            result = await session.execute(select(Trigger).where(Trigger.is_active == True))
            triggers = result.scalars().all()
            for trigger in triggers:
                await self._setup_trigger(trigger)

    async def _setup_trigger(self, trigger):
        if trigger.trigger_type == "webhook":
            path = trigger.config.get("path", f"/webhook/{trigger.id}")
            self.webhook_handler.register(path, self._create_webhook_callback(trigger))

        elif trigger.trigger_type == "file_watch":
            watch_path = trigger.config.get("path", ".")
            patterns = trigger.config.get("patterns", ["*"])
            handler = FileWatchHandler(
                self._create_file_callback(trigger),
                patterns
            )
            self.file_observer.schedule(handler, watch_path, recursive=trigger.config.get("recursive", False))
            self.file_watches[str(trigger.id)] = (handler, watch_path)

        elif trigger.trigger_type == "db_poll":
            query = trigger.config.get("query")
            interval = trigger.config.get("interval", 60.0)
            if query:
                poll = DatabasePollTrigger(self.session_factory, query, interval)
                await poll.start(self._create_db_callback(trigger))
                self.db_polls[str(trigger.id)] = poll

    def _create_webhook_callback(self, trigger):
        async def callback(payload: dict):
            rendered_payload = self._render_payload(trigger.payload_template, payload)
            await self._execute_target(trigger.target_type, trigger.target_id, rendered_payload)
        return callback

    def _create_file_callback(self, trigger):
        async def callback(file_path: str, event_type: str):
            payload = {
                "file_path": file_path,
                "event_type": event_type,
                "timestamp": datetime.utcnow().isoformat(),
            }
            rendered_payload = self._render_payload(trigger.payload_template, payload)
            await self._execute_target(trigger.target_type, trigger.target_id, rendered_payload)
        return callback

    def _create_db_callback(self, trigger):
        async def callback(row_data: dict):
            rendered_payload = self._render_payload(trigger.payload_template, row_data)
            await self._execute_target(trigger.target_type, trigger.target_id, rendered_payload)
        return callback

    def _render_payload(self, template: Optional[dict], data: dict) -> dict:
        if not template:
            return data

        result = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                var_name = value[2:-2].strip()
                result[key] = data.get(var_name, value)
            else:
                result[key] = value
        return result

    async def _execute_target(self, target_type: str, target_id: UUID, payload: dict):
        async with self.session_factory() as session:
            if target_type == "agent":
                from src.services.agent_service import execute_agent
                await execute_agent(session, target_id, payload)
            elif target_type == "workflow":
                from src.services.workflow_service import execute_workflow
                await execute_workflow(session, target_id, payload)

    async def register_webhook(self, path: str, handler: Callable):
        self.webhook_handler.register(path, handler)

    async def add_file_watch(self, watch_path: str, patterns: list[str], callback: Callable):
        handler = FileWatchHandler(callback, patterns)
        self.file_observer.schedule(handler, watch_path, recursive=True)
        watch_id = hashlib.md5(f"{watch_path}:{patterns}".encode()).hexdigest()[:8]
        self.file_watches[watch_id] = (handler, watch_path)
        return watch_id

    async def remove_file_watch(self, watch_id: str):
        if watch_id in self.file_watches:
            handler, path = self.file_watches[watch_id]
            self.file_observer.unschedule(handler)
            del self.file_watches[watch_id]

    async def add_db_poll(self, name: str, query: str, interval: float, callback: Callable):
        poll = DatabasePollTrigger(self.session_factory, query, interval)
        await poll.start(callback)
        self.db_polls[name] = poll

    async def remove_db_poll(self, name: str):
        if name in self.db_polls:
            await self.db_polls[name].stop()
            del self.db_polls[name]