"""Settings routes for API key management and configuration."""

import logging
import os

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SettingResponse, SettingUpdate
from app.db.engine import get_session
from app.db.models import AppSetting

logger = logging.getLogger(__name__)

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

    # Also set as environment variable so LiteLLM can pick it up
    env_map = {
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "google_api_key": "GEMINI_API_KEY",
        "openai_base_url": "OPENAI_API_BASE",
        "anthropic_base_url": "ANTHROPIC_API_BASE",
    }
    if body.key in env_map:
        os.environ[env_map[body.key]] = body.value

    val = mask_value(body.value) if body.is_sensitive else body.value
    return SettingResponse(key=body.key, value=val, is_encrypted=body.is_sensitive)


@router.delete("")
async def delete_setting(key: str, db: AsyncSession = Depends(get_session)):
    """Delete a setting by key (passed as query parameter)."""
    setting = await db.get(AppSetting, key)
    if not setting:
        return {"ok": True}
    await db.delete(setting)
    await db.commit()
    return {"ok": True}


# Separate router for validate to avoid path parameter conflicts
validate_router = APIRouter(prefix="/validate-key", tags=["settings"])


class ValidateKeyRequest(BaseModel):
    key: str  # e.g. "openai_api_key"
    value: str  # the actual key value


class ValidateKeyResponse(BaseModel):
    valid: bool
    message: str


@validate_router.post("", response_model=ValidateKeyResponse)
async def validate_api_key(body: ValidateKeyRequest):
    """Test if an API key is valid by making a minimal API call."""
    import litellm

    key_model_map = {
        "openai_api_key": ("gpt-4o-mini", "OPENAI_API_KEY"),
        "anthropic_api_key": ("claude-haiku-4-5-20251001", "ANTHROPIC_API_KEY"),
        "google_api_key": ("gemini/gemini-2.0-flash", "GEMINI_API_KEY"),
    }

    if body.key not in key_model_map:
        return ValidateKeyResponse(valid=False, message=f"Validation not supported for {body.key}")

    model, env_var = key_model_map[body.key]
    old_val = os.environ.get(env_var, "")
    os.environ[env_var] = body.value
    try:
        await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        return ValidateKeyResponse(valid=True, message="API key is valid")
    except Exception as e:
        err = str(e)
        if "auth" in err.lower() or "key" in err.lower() or "401" in err or "403" in err:
            return ValidateKeyResponse(valid=False, message="Invalid API key")
        return ValidateKeyResponse(valid=False, message=f"Validation error: {err[:200]}")
    finally:
        if old_val:
            os.environ[env_var] = old_val
        elif env_var in os.environ:
            del os.environ[env_var]
