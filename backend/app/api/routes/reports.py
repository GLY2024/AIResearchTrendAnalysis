"""Report routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import ReportGenerateRequest, ReportResponse
from app.db.engine import get_session
from app.db.models import Report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=list[ReportResponse])
async def list_reports(session_id: int, db: AsyncSession = Depends(get_session)):
    result = await db.execute(
        select(Report)
        .where(Report.session_id == session_id)
        .order_by(Report.created_at.desc())
    )
    return [ReportResponse.model_validate(r) for r in result.scalars().all()]


@router.post("/generate", response_model=ReportResponse, status_code=201)
async def generate_report(body: ReportGenerateRequest, db: AsyncSession = Depends(get_session)):
    version = 1
    if body.parent_report_id:
        parent = await db.get(Report, body.parent_report_id)
        if parent:
            version = parent.version + 1

    report = Report(
        session_id=body.session_id,
        parent_report_id=body.parent_report_id,
        title="Generating...",
        version=version,
        status="generating",
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    # TODO: Trigger publisher agent via task_manager
    return ReportResponse.model_validate(report)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_session)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return ReportResponse.model_validate(report)
