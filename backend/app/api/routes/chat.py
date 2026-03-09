"""Chat routes for AI conversation."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import ChatMessageRequest, ChatMessageResponse
from app.db.engine import get_session
from app.db.models import ChatMessage, ResearchSession
from app.services.ai_service import ai_service
from app.core.events import event_bus

router = APIRouter(prefix="/chat", tags=["chat"])


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

    # Get conversation history
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == body.session_id)
        .order_by(ChatMessage.created_at)
    )
    history = [
        {"role": m.role, "content": m.content}
        for m in result.scalars().all()
    ]

    # Get AI response
    ai_response = await ai_service.chat(history, role="chat")

    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=body.session_id,
        role="assistant",
        content=ai_response,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    return ChatMessageResponse.model_validate(assistant_msg)
