"""Settings routes for API key management and configuration."""

import logging
import os

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SettingResponse, SettingUpdate
from app.db.engine import get_session
from app.db.models import AppSetting

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])

# Keys that should be masked in responses
SENSITIVE_KEYS = {"openai_api_key", "anthropic_api_key", "google_api_key", "scopus_api_key", "zotero_api_key", "openrouter_api_key"}


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

    # Also set as environment variable for backward compat
    env_map = {
        "openai_api_key": "OPENAI_API_KEY",
        "anthropic_api_key": "ANTHROPIC_API_KEY",
        "google_api_key": "GEMINI_API_KEY",
        "openai_base_url": "OPENAI_API_BASE",
        "anthropic_base_url": "ANTHROPIC_API_BASE",
        "openrouter_api_key": "OPENROUTER_API_KEY",
    }
    if body.key in env_map:
        os.environ[env_map[body.key]] = body.value

    # Reload AI service settings so model routing picks up changes immediately
    from app.services.ai_service import ai_service
    await ai_service.load_settings_from_db()

    # Sync scopus key to pybliometrics config
    if body.key == "scopus_api_key" and body.value:
        from app.sources.scopus_source import _write_pybliometrics_key
        _write_pybliometrics_key(body.value)

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


class ModelItem(BaseModel):
    id: str
    name: str


class ModelsResponse(BaseModel):
    models: list[ModelItem]
    error: str | None = None


@router.get("/models", response_model=ModelsResponse)
async def list_provider_models(
    provider: str = Query(..., description="Provider id: openai or anthropic"),
    db: AsyncSession = Depends(get_session),
):
    """Fetch available models from a provider's /models endpoint."""
    # Read api_key and base_url from DB
    key_map = {
        "openai": ("openai_api_key", "openai_base_url", "https://api.openai.com/v1"),
        "anthropic": ("anthropic_api_key", "anthropic_base_url", "https://api.anthropic.com/v1"),
        "openrouter": ("openrouter_api_key", "openrouter_base_url", "https://openrouter.ai/api/v1"),
    }
    if provider not in key_map:
        return ModelsResponse(models=[], error=f"Unknown provider: {provider}")

    api_key_field, base_url_field, default_base = key_map[provider]

    result = await db.execute(
        select(AppSetting).where(AppSetting.key.in_([api_key_field, base_url_field]))
    )
    db_map = {s.key: s.value for s in result.scalars().all()}

    api_key = db_map.get(api_key_field)
    base_url = (db_map.get(base_url_field) or default_base).rstrip("/")

    if not api_key:
        return ModelsResponse(models=[], error=f"No API key configured for {provider}")

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # All providers use OpenAI-compatible /models endpoint
            resp = await client.get(
                f"{base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()

            models: list[ModelItem] = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if not mid:
                    continue
                name = m.get("display_name") or m.get("name") or mid
                models.append(ModelItem(id=mid, name=name))

            models.sort(key=lambda x: x.id)
            if not models:
                return ModelsResponse(models=[], error="No models returned by provider")
            return ModelsResponse(models=models)

    except httpx.HTTPStatusError as e:
        logger.warning(f"Failed to fetch models from {provider}: HTTP {e.response.status_code}")
        return ModelsResponse(models=[], error=f"HTTP {e.response.status_code} from {provider}")
    except Exception as e:
        logger.warning(f"Failed to fetch models from {provider}: {e}")
        return ModelsResponse(models=[], error=str(e)[:200])


# Separate router for validate to avoid path parameter conflicts
validate_router = APIRouter(prefix="/validate-key", tags=["settings"])


class ValidateKeyRequest(BaseModel):
    key: str  # e.g. "openai_api_key"
    value: str  # the actual key value
    base_url: str | None = None


class ValidateKeyResponse(BaseModel):
    valid: bool
    message: str


async def _validate_api_key(body: ValidateKeyRequest):
    """Test if an API key is valid by making a minimal API call."""
    from openai import AsyncOpenAI, AuthenticationError, APIConnectionError, RateLimitError

    # Map key type → (default_base_url, test_model)
    key_config = {
        "openai_api_key": ("https://api.openai.com/v1", "gpt-4o-mini"),
        "anthropic_api_key": ("https://api.anthropic.com/v1", "claude-haiku-4-5-20251001"),
        "openrouter_api_key": ("https://openrouter.ai/api/v1", "openai/gpt-4o-mini"),
    }

    if body.key not in key_config:
        return ValidateKeyResponse(valid=False, message=f"Validation not supported for {body.key}")

    default_base, test_model = key_config[body.key]
    base_url = (body.base_url or default_base).rstrip("/")

    client = AsyncOpenAI(base_url=base_url, api_key=body.value)
    try:
        await client.chat.completions.create(
            model=test_model,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=5,
        )
        return ValidateKeyResponse(valid=True, message="API key is valid")
    except AuthenticationError:
        return ValidateKeyResponse(valid=False, message="Invalid API key")
    except APIConnectionError as e:
        return ValidateKeyResponse(valid=False, message=f"Could not connect to {base_url}: {e}")
    except RateLimitError:
        return ValidateKeyResponse(valid=False, message="Key appears valid but is rate-limited. Try again shortly.")
    except Exception as e:
        logger.warning(f"Unexpected validation error for {body.key}: {e}", exc_info=True)
        return ValidateKeyResponse(valid=False, message=f"Validation error: {str(e)[:200]}")
    finally:
        await client.close()


@validate_router.post("", response_model=ValidateKeyResponse)
async def validate_api_key(body: ValidateKeyRequest):
    return await _validate_api_key(body)


@router.post("/validate-key", response_model=ValidateKeyResponse)
async def validate_api_key_compat(body: ValidateKeyRequest):
    """Compatibility endpoint for older callers that still hit /api/settings/validate-key."""
    return await _validate_api_key(body)
