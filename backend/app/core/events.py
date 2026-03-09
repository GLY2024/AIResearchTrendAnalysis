"""EventBus for WebSocket event distribution."""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


class EventBus:
    """Simple pub/sub event bus for distributing events to WebSocket clients."""

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}
        self._ws_connections: dict[str, Any] = {}  # session_id -> websocket

    def subscribe(self, event_type: str, handler: Callable[..., Coroutine]):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                h for h in self._subscribers[event_type] if h != handler
            ]

    async def emit(self, event_type: str, data: dict | None = None, session_id: str | None = None):
        """Emit event to subscribers and connected WebSocket clients."""
        payload = {"event": event_type, "data": data or {}}
        if session_id:
            payload["session_id"] = session_id

        # Notify in-process subscribers
        handlers = self._subscribers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(payload)
            except Exception as e:
                logger.error(f"Event handler error for {event_type}: {e}")

        # Send to WebSocket clients
        await self._broadcast_ws(payload, session_id)

    def register_ws(self, session_id: str, websocket):
        self._ws_connections[session_id] = websocket

    def unregister_ws(self, session_id: str):
        self._ws_connections.pop(session_id, None)

    async def _broadcast_ws(self, payload: dict, session_id: str | None):
        message = json.dumps(payload, ensure_ascii=False)
        targets = (
            {session_id: self._ws_connections[session_id]}
            if session_id and session_id in self._ws_connections
            else self._ws_connections
        )
        disconnected = []
        for sid, ws in targets.items():
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(sid)
        for sid in disconnected:
            self._ws_connections.pop(sid, None)


# Global event bus instance
event_bus = EventBus()
