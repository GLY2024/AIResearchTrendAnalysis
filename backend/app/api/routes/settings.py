"""Settings routes for API key management and configuration."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SettingResponse, SettingUpdate
from app.db.engine import get_session
from app.db.models import AppSetting

router = APIRouter(prefix="/settings", tags=["settings"])

# Keys that should be masked in responses
SENSITIVE_KEYS = {"openai_api_key", "anthropic_api_key", "google_api_key", "scopus_api_key", "zotero_api_key"}


def mask_value(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


@router.get("", response_model=list[SettingResponse])
async def list_settings(db: AsyncSession = Depends(get_session)):
    result = await db.execute(select(AppSetting))
    settings = []
    for s in result.scalars().all():
        val = mask_value(s.value) if s.is_encrypted else s.value
        settings.append(SettingResponse(key=s.key, value=val, is_encrypted=s.is_encrypted))
    return settings


@router.put("")
async def update_setting(body: SettingUpdate, db: AsyncSession = Depends(get_session)):
    setting = await db.get(AppSetting, body.key)
    if setting:
        setting.value = body.value
        setting.is_encrypted = body.is_sensitive
    else:
        setting = AppSetting(
            key=body.key,
            value=body.value,
            is_encrypted=body.is_sensitive,
        )
        db.add(setting)
    await db.commit()
    val = mask_value(body.value) if body.is_sensitive else body.value
    return SettingResponse(key=body.key, value=val, is_encrypted=body.is_sensitive)


@router.delete("/{key}", status_code=204)
async def delete_setting(key: str, db: AsyncSession = Depends(get_session)):
    setting = await db.get(AppSetting, key)
    if setting:
        await db.delete(setting)
        await db.commit()
