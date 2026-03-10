"""Chat routes for AI conversation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import ChatMessageRequest, ChatMessageResponse
from app.core.exceptions import AIServiceError
from app.db.engine import get_session
from app.db.models import ChatMessage, ResearchSession
from app.services.ai_service import CHAT_SYSTEM_PROMPT, ai_service
from app.core.events import event_bus

router = APIRouter(prefix="/chat", tags=["chat"])


def _build_chat_error_payload(exc: Exception) -> dict:
    error_code = ""
    status_code = getattr(exc, "status_code", None)
    retryable = True
    if isinstance(exc, AIServiceError):
        error_code = exc.error_code
        status_code = exc.status_code
        retryable = exc.retryable if exc.retryable is not None else retryable
    message = str(exc).strip() or "Unknown chat error"
    label = error_code or (f"http_{status_code}" if status_code else "chat_error")
    prefix = f"Request failed ({label})"
    if status_code:
        prefix += f", HTTP {status_code}"
    return {
        "message": message,
        "error_code": error_code or "chat_error",
        "status_code": status_code,
        "retryable": retryable,
        "summary": f"{prefix}\n{message}",
    }


async def _build_history(db: AsyncSession, session_id: int) -> list[dict]:
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    history = []
    for message in result.scalars().all():
        metadata = message.metadata_ or {}
        if message.role == "assistant" and metadata.get("status") == "failed":
            continue
        history.append({"role": message.role, "content": message.content})
    return history


async def _create_assistant_reply(
    db: AsyncSession,
    *,
    session_id: int,
    user_message_id: int,
    history: list[dict],
) -> ChatMessage:
    messages_with_system = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}, *history]

    content = ""
    metadata: dict = {}
    try:
        content = await ai_service.chat(messages_with_system, role="chat")
    except Exception as exc:
        error_payload = _build_chat_error_payload(exc)
        content = error_payload["summary"]
        metadata = {
            "status": "failed",
            "error_code": error_payload["error_code"],
            "status_code": error_payload["status_code"],
            "error_detail": error_payload["message"],
            "retryable": error_payload["retryable"],
            "reply_to_user_message_id": user_message_id,
        }

    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=content,
        metadata_=metadata,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg


@router.get("/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_messages(session_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    return [ChatMessageResponse.model_validate(m) for m in result.scalars().all()]


@router.post("/send", response_model=ChatMessageResponse)
async def send_message(body: ChatMessageRequest, db: AsyncSession = Depends(get_session)):
    """Send a message and get AI response. For streaming, use WebSocket."""
    session = await db.get(ResearchSession, body.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    # Save user message
    user_msg = ChatMessage(
        session_id=body.session_id,
        role="user",
        content=body.content,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    history = await _build_history(db, body.session_id)
    assistant_msg = await _create_assistant_reply(
        db,
        session_id=body.session_id,
        user_message_id=user_msg.id,
        history=history,
    )
    return ChatMessageResponse.model_validate(assistant_msg)


@router.post("/messages/{message_id}/retry", response_model=ChatMessageResponse)
async def retry_message(message_id: int, db: AsyncSession = Depends(get_session)):
    failed_message = await db.get(ChatMessage, message_id)
    if not failed_message:
        raise HTTPException(404, "Chat message not found")
    if failed_message.role != "assistant":
        raise HTTPException(400, "Only assistant messages can be retried")

    metadata = dict(failed_message.metadata_ or {})
    if metadata.get("status") != "failed":
        raise HTTPException(400, "Only failed assistant messages can be retried")

    reply_to_user_message_id = metadata.get("reply_to_user_message_id")
    if not isinstance(reply_to_user_message_id, int):
        raise HTTPException(400, "Retry metadata is missing the linked user message")

    user_msg = await db.get(ChatMessage, reply_to_user_message_id)
    if not user_msg:
        raise HTTPException(404, "Linked user message not found")

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == failed_message.session_id)
        .where(ChatMessage.created_at <= user_msg.created_at)
        .order_by(ChatMessage.created_at)
    )
    history = []
    for message in history_result.scalars().all():
        if message.id == failed_message.id:
            continue
        message_metadata = message.metadata_ or {}
        if message.role == "assistant" and message_metadata.get("status") == "failed":
            continue
        history.append({"role": message.role, "content": message.content})

    metadata["retried"] = True
    failed_message.metadata_ = metadata
    await db.commit()

    assistant_msg = await _create_assistant_reply(
        db,
        session_id=failed_message.session_id,
        user_message_id=user_msg.id,
        history=history,
    )
    return ChatMessageResponse.model_validate(assistant_msg)


@router.delete("/messages/{message_id}", status_code=204)
async def delete_message(message_id: int, db: AsyncSession = Depends(get_session)):
    message = await db.get(ChatMessage, message_id)
    if not message:
        raise HTTPException(404, "Chat message not found")
    await db.delete(message)
    await db.commit()
