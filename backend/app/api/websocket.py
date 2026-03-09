"""WebSocket manager for real-time communication."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.events import event_bus

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    event_bus.register_ws(session_id, websocket)
    logger.info(f"WebSocket connected: session {session_id}")
    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                event_type = msg.get("event", "")
                # Handle client-side events if needed
                if event_type == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session {session_id}")
    finally:
        event_bus.unregister_ws(session_id)
