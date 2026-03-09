"""Export routes."""

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import get_session
from app.services.export_service import export_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/ris/{session_id}")
async def export_ris(session_id: int, db: AsyncSession = Depends(get_session)):
    content = await export_service.export_ris(db, session_id)
    return PlainTextResponse(
        content,
        media_type="application/x-research-info-systems",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.ris"},
    )


@router.get("/bibtex/{session_id}")
async def export_bibtex(session_id: int, db: AsyncSession = Depends(get_session)):
    content = await export_service.export_bibtex(db, session_id)
    return PlainTextResponse(
        content,
        media_type="application/x-bibtex",
        headers={"Content-Disposition": f"attachment; filename=session_{session_id}.bib"},
    )


@router.post("/zotero/{session_id}")
async def export_zotero(
    session_id: int,
    api_key: str,
    library_id: str,
    library_type: str = "user",
    db: AsyncSession = Depends(get_session),
):
    result = await export_service.export_zotero(
        db, session_id, api_key, library_id, library_type
    )
    return result
