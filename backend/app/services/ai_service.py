"""AI service - direct OpenAI SDK, no LiteLLM routing issues."""

import logging
import os
from typing import AsyncGenerator

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, AuthenticationError, RateLimitError

from app.config import settings
from app.core.exceptions import AIServiceError

# OpenAI SDK built-in retry count for transient errors (500, 429, etc.)
SDK_MAX_RETRIES = 3

logger = logging.getLogger(__name__)

# Chat system prompt
CHAT_SYSTEM_PROMPT = """You are ARTA (AI Research Trend Analysis), an AI research assistant that helps users explore and analyze academic research trends.

Your capabilities:
1. **Topic Clarification**: Help users refine and define their research topics through conversation
2. **Search Planning**: When the user is ready, suggest generating a search plan (they can trigger this via the UI)
3. **Research Guidance**: Provide context about research fields, suggest related topics, identify key concepts

Guidelines:
- Be concise and focused on research assistance
- Ask clarifying questions to understand the user's research interests
- When the topic is sufficiently defined, suggest the user generate a search plan
- Provide academic context and domain knowledge
- Use markdown formatting for readability
- Reference relevant concepts, methods, and subfields"""


def _status_error_code(status_code: int | None) -> str:
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "authentication_error"
    if status_code == 403:
        return "forbidden"
    if status_code == 404:
        return "model_not_found"
    if status_code == 408:
        return "timeout"
    if status_code == 409:
        return "conflict"
    if status_code == 429:
        return "rate_limited"
    if status_code and status_code >= 500:
        return "provider_error"
    return "ai_error"


class AIService:
    """Unified AI interface with role-based model routing via OpenAI SDK."""

    ROLE_MODEL_MAP = {
        "chat": "ai_chat_model",
        "planner": "ai_planner_model",
        "analyst": "ai_analyst_model",
        "publisher": "ai_publisher_model",
        "executor": "ai_executor_model",
    }

    _MODEL_SETTING_KEYS = {
        "model_chat": "ai_chat_model",
        "model_planner": "ai_planner_model",
        "model_analyst": "ai_analyst_model",
        "model_publisher": "ai_publisher_model",
        "model_executor": "ai_executor_model",
    }

    _PROVIDER_SETTING_KEYS = {
        "model_chat_provider",
        "model_planner_provider",
        "model_analyst_provider",
        "model_publisher_provider",
        "model_executor_provider",
    }

    # Provider defaults - all use OpenAI-compatible protocol
    _PROVIDER_DEFAULTS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "base_url_key": "openai_base_url",
            "api_key_key": "openai_api_key",
        },
        "anthropic": {
            "base_url": "https://api.anthropic.com/v1",
            "base_url_key": "anthropic_base_url",
            "api_key_key": "anthropic_api_key",
        },
        "openrouter": {
            "base_url": "https://openrouter.ai/api/v1",
            "base_url_key": "openrouter_base_url",
            "api_key_key": "openrouter_api_key",
        },
    }

    def __init__(self):
        self._model_overrides: dict[str, str] = {}
        self._provider_overrides: dict[str, str] = {}
        self._db_settings: dict[str, str] = {}
        self._clients: dict[str, AsyncOpenAI] = {}

    async def load_settings_from_db(self):
        """Load API keys and model overrides from the database."""
        from app.db.engine import async_session
        from app.db.models import AppSetting
        from sqlalchemy import select

        try:
            async with async_session() as db:
                result = await db.execute(select(AppSetting))
                self._db_settings.clear()
                self._model_overrides.clear()
                self._provider_overrides.clear()
                self._clients.clear()

                for s in result.scalars().all():
                    if s.value:
                        self._db_settings[s.key] = s.value

                    # API keys → env vars (for backward compat)
                    env_map = {
                        "openai_api_key": "OPENAI_API_KEY",
                        "anthropic_api_key": "ANTHROPIC_API_KEY",
                        "google_api_key": "GEMINI_API_KEY",
                        "scopus_api_key": "SCOPUS_API_KEY",
                        "openrouter_api_key": "OPENROUTER_API_KEY",
                    }
                    if s.key in env_map and s.value:
                        os.environ[env_map[s.key]] = s.value

                    # Model overrides
                    if s.key in self._MODEL_SETTING_KEYS and s.value:
                        attr = self._MODEL_SETTING_KEYS[s.key]
                        self._model_overrides[attr] = s.value
                        logger.info(f"Model override: {attr} = {s.value}")

                    # Provider overrides
                    if s.key in self._PROVIDER_SETTING_KEYS and s.value:
                        model_key = s.key.replace("_provider", "")
                        attr = self._MODEL_SETTING_KEYS.get(model_key)
                        if attr:
                            self._provider_overrides[attr] = s.value
                            logger.info(f"Provider override: {attr} = {s.value}")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to load settings from DB: {e}", exc_info=True)

    def _get_client(self, provider: str) -> AsyncOpenAI:
        """Get or create an AsyncOpenAI client for the given provider."""
        if provider in self._clients:
            return self._clients[provider]

        cfg = self._PROVIDER_DEFAULTS.get(provider)
        if not cfg:
            raise AIServiceError(
                f"Unknown provider: {provider}",
                error_code="unknown_provider",
                retryable=False,
            )

        base_url = (self._db_settings.get(cfg["base_url_key"]) or cfg["base_url"]).rstrip("/")
        api_key = self._db_settings.get(cfg["api_key_key"])
        if not api_key:
            raise AIServiceError(
                f"No API key configured for provider '{provider}'. "
                f"Please go to Settings and configure your API key.",
                error_code="no_api_key",
                status_code=400,
                retryable=False,
            )

        client = AsyncOpenAI(base_url=base_url, api_key=api_key, max_retries=SDK_MAX_RETRIES)
        self._clients[provider] = client
        logger.info(f"Created OpenAI client for provider={provider}, base_url={base_url}")
        return client

    def _wrap_provider_error(self, exc: Exception, *, provider: str, model: str, operation: str) -> AIServiceError:
        if isinstance(exc, AIServiceError):
            return exc

        if isinstance(exc, AuthenticationError):
            return AIServiceError(
                f"{provider} rejected the configured credentials while trying to {operation} with model '{model}'.",
                error_code="authentication_error",
                status_code=401,
                retryable=False,
            )

        if isinstance(exc, RateLimitError):
            return AIServiceError(
                f"{provider} rate-limited the request for model '{model}'. Try again shortly or switch to another model.",
                error_code="rate_limited",
                status_code=429,
                retryable=True,
            )

        if isinstance(exc, APIConnectionError):
            return AIServiceError(
                f"Could not reach {provider} while trying to {operation} with model '{model}'. Check the base URL and network connectivity.",
                error_code="connection_error",
                retryable=True,
            )

        if isinstance(exc, APIStatusError):
            status_code = exc.status_code or getattr(exc.response, "status_code", None)
            return AIServiceError(
                f"{provider} returned HTTP {status_code} while trying to {operation} with model '{model}': {exc}",
                error_code=_status_error_code(status_code),
                status_code=status_code,
                retryable=status_code is None or status_code >= 500 or status_code == 429,
            )

        return AIServiceError(
            f"{provider} failed while trying to {operation} with model '{model}': {exc}",
            error_code="ai_error",
            retryable=True,
        )

    def _get_model_config(self, role: str) -> tuple[AsyncOpenAI, str]:
        """Resolve client + model name for a given role. Returns (client, model_name)."""
        attr = self.ROLE_MODEL_MAP.get(role)
        if not attr:
            raise AIServiceError(
                f"Unknown AI role: '{role}'. Valid: {list(self.ROLE_MODEL_MAP.keys())}",
                error_code="unknown_role",
                retryable=False,
            )
        model = self._model_overrides.get(attr, getattr(settings, attr))
        provider = self._provider_overrides.get(attr, "openai")

        client = self._get_client(provider)
        logger.debug(f"Role={role}: model={model}, provider={provider}")
        return client, model

    async def chat(
        self,
        messages: list[dict],
        role: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Non-streaming chat completion (SDK handles retries via max_retries)."""
        client, model = self._get_model_config(role)
        provider = self._provider_overrides.get(self.ROLE_MODEL_MAP[role], "openai")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI chat error ({model}): {e}")
            raise self._wrap_provider_error(e, provider=provider, model=model, operation="complete the request") from e

    async def chat_stream(
        self,
        messages: list[dict],
        role: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion."""
        client, model = self._get_model_config(role)
        provider = self._provider_overrides.get(self.ROLE_MODEL_MAP[role], "openai")
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"AI stream error ({model}): {e}")
            raise self._wrap_provider_error(e, provider=provider, model=model, operation="stream a response") from e

    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
        role: str = "executor",
        temperature: float = 0.0,
    ) -> dict:
        """Chat completion with function calling / tools."""
        client, model = self._get_model_config(role)
        provider = self._provider_overrides.get(self.ROLE_MODEL_MAP[role], "openai")
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=temperature,
            )
            msg = response.choices[0].message
            return {
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in (msg.tool_calls or [])
                ],
            }
        except Exception as e:
            logger.error(f"AI function call error ({model}): {e}")
            raise self._wrap_provider_error(e, provider=provider, model=model, operation="call tools") from e


ai_service = AIService()
