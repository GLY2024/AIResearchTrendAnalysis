"""Report routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import ReportGenerateRequest, ReportResponse
from app.db.engine import async_session, get_session
from app.db.models import Report
from app.core.task_manager import task_manager
from app.agents.publisher import publisher_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


async def _generate_report(report_id: int):
    """Background task: generate report."""
    async with async_session() as db:
        report = await db.get(Report, report_id)
        if not report:
            return
        try:
            await publisher_agent.generate_report(db, report)
            logger.info(f"Report {report_id} completed")
        except Exception as e:
            logger.error(f"Report {report_id} failed: {e}")
            report.status = "failed"
            report.content_markdown = f"Report generation failed: {e}"
            await db.commit()


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
    task_manager.submit(_generate_report(report.id), task_id=f"report-{report.id}")
    return ReportResponse.model_validate(report)


@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(report_id: int, db: AsyncSession = Depends(get_session)):
    report = await db.get(Report, report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    return ReportResponse.model_validate(report)
