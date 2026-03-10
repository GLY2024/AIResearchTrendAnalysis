"""WebSocket manager for real-time communication."""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.events import event_bus
from app.core.exceptions import AIServiceError
from app.db.engine import async_session
from app.db.models import ChatMessage, ResearchSession, SearchPlan
from app.services.ai_service import ai_service, CHAT_SYSTEM_PROMPT
from app.agents.planner import planner_agent

logger = logging.getLogger(__name__)
router = APIRouter()


async def _handle_chat_send(websocket: WebSocket, session_id: str, data: dict):
    """Handle streaming chat message via WebSocket."""
    content = data.get("content", "").strip()
    if not content:
        return

    sid = int(session_id)
    async with async_session() as db:
        session = await db.get(ResearchSession, sid)
        if not session:
            await websocket.send_text(json.dumps({
                "event": "error", "data": {"message": "Session not found"}
            }))
            return

        # Save user message
        user_msg = ChatMessage(session_id=sid, role="user", content=content)
        db.add(user_msg)
        await db.commit()

        # Get conversation history
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sid)
            .order_by(ChatMessage.created_at)
        )
        history = [
            {"role": m.role, "content": m.content}
            for m in result.scalars().all()
        ]

        # Stream AI response with system prompt
        messages_with_system = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT},
            *history,
        ]
        full_response = ""
        try:
            async for token in ai_service.chat_stream(messages_with_system, role="chat"):
                full_response += token
                await websocket.send_text(json.dumps({
                    "event": "chat_token",
                    "data": {"token": token},
                }))
        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            full_response = "Sorry, something went wrong. Please try again."
            error_data: dict = {"message": str(e)}
            if isinstance(e, AIServiceError) and e.error_code:
                error_data["error_code"] = e.error_code
            await websocket.send_text(json.dumps({
                "event": "error",
                "data": error_data,
            }))

        # Save assistant message
        assistant_msg = ChatMessage(
            session_id=sid, role="assistant", content=full_response,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        await websocket.send_text(json.dumps({
            "event": "chat_complete",
            "data": {
                "message": {
                    "id": assistant_msg.id,
                    "session_id": sid,
                    "role": "assistant",
                    "content": full_response,
                    "created_at": assistant_msg.created_at.isoformat(),
                },
            },
        }))


async def _handle_generate_plan(websocket: WebSocket, session_id: str, data: dict):
    """Handle search plan generation request via WebSocket."""
    topic = data.get("topic", "").strip()
    if not topic:
        return

    sid = int(session_id)
    async with async_session() as db:
        # Get chat history for context
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == sid)
            .order_by(ChatMessage.created_at)
        )
        chat_history = [
            {"role": m.role, "content": m.content}
            for m in result.scalars().all()
        ]

        await websocket.send_text(json.dumps({
            "event": "plan_generating",
            "data": {"topic": topic},
        }))

        try:
            plan_data = await planner_agent.generate_plan(topic, chat_history)

            plan = SearchPlan(
                session_id=sid,
                plan_data=plan_data,
                status="draft",
            )
            db.add(plan)
            await db.commit()
            await db.refresh(plan)

            await websocket.send_text(json.dumps({
                "event": "plan_generated",
                "data": {
                    "plan_id": plan.id,
                    "plan_data": plan_data,
                    "status": "draft",
                },
            }))

        except Exception as e:
            logger.error(f"Plan generation error: {e}")
            error_data: dict = {"message": f"Plan generation failed: {e}"}
            if isinstance(e, AIServiceError) and e.error_code:
                error_data["error_code"] = e.error_code
            await websocket.send_text(json.dumps({
                "event": "error",
                "data": error_data,
            }))


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
                payload = msg.get("data", {})

                if event_type == "ping":
                    await websocket.send_text(json.dumps({"event": "pong"}))
                elif event_type == "chat_send":
                    await _handle_chat_send(websocket, session_id, payload)
                elif event_type == "generate_plan":
                    await _handle_generate_plan(websocket, session_id, payload)
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: session {session_id}")
    finally:
        event_bus.unregister_ws(session_id)
