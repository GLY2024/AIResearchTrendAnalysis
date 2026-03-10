"""Research session CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SessionCreate, SessionResponse, SessionUpdate
from app.db.engine import get_session
from app.db.models import Paper, ResearchSession

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_session)):
    stmt = (
        select(
            ResearchSession,
            func.count(Paper.id).label("paper_count"),
        )
        .outerjoin(Paper, Paper.session_id == ResearchSession.id)
        .group_by(ResearchSession.id)
        .order_by(ResearchSession.updated_at.desc())
    )
    result = await db.execute(stmt)
    sessions = []
    for row in result.all():
        session_obj = row[0]
        resp = SessionResponse.model_validate(session_obj)
        resp.paper_count = row[1]
        sessions.append(resp)
    return sessions


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_session)):
    session = ResearchSession(title=body.title, description=body.description)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session_detail(session_id: int, db: AsyncSession = Depends(get_session)):
    session = await db.get(ResearchSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    # Get paper count
    count_result = await db.execute(
        select(func.count()).where(Paper.session_id == session_id)
    )
    resp = SessionResponse.model_validate(session)
    resp.paper_count = count_result.scalar() or 0
    return resp


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(session_id: int, body: SessionUpdate, db: AsyncSession = Depends(get_session)):
    session = await db.get(ResearchSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(session, field, value)
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_session)):
    session = await db.get(ResearchSession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.commit()
