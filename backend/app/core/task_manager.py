"""Async background task management."""

import asyncio
import logging
from typing import Any, Callable, Coroutine
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages async background tasks with tracking."""

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    def submit(
        self,
        coro: Coroutine,
        task_id: str | None = None,
    ) -> str:
        task_id = task_id or uuid4().hex[:12]
        task = asyncio.create_task(self._run(task_id, coro))
        self._tasks[task_id] = task
        return task_id

    async def _run(self, task_id: str, coro: Coroutine):
        try:
            return await coro
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            raise
        finally:
            self._tasks.pop(task_id, None)

    def cancel(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, task_id: str) -> bool:
        task = self._tasks.get(task_id)
        return task is not None and not task.done()

    @property
    def active_count(self) -> int:
        return sum(1 for t in self._tasks.values() if not t.done())


task_manager = TaskManager()
