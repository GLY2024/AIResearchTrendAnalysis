"""AI service with LiteLLM - role-based model routing."""

import logging
import os
from typing import AsyncGenerator

import litellm

from app.config import settings
from app.core.exceptions import AIServiceError

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True

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


class AIService:
    """Unified AI interface with role-based model routing."""

    ROLE_MODEL_MAP = {
        "chat": "ai_chat_model",
        "planner": "ai_planner_model",
        "analyst": "ai_analyst_model",
        "publisher": "ai_publisher_model",
        "executor": "ai_executor_model",
    }

    # DB setting keys that override config defaults
    _MODEL_SETTING_KEYS = {
        "model_chat": "ai_chat_model",
        "model_planner": "ai_planner_model",
        "model_analyst": "ai_analyst_model",
        "model_publisher": "ai_publisher_model",
        "model_executor": "ai_executor_model",
    }

    def __init__(self):
        self._model_overrides: dict[str, str] = {}

    async def load_settings_from_db(self):
        """Load API keys and model overrides from the database."""
        from app.db.engine import async_session
        from app.db.models import AppSetting
        from sqlalchemy import select

        try:
            async with async_session() as db:
                result = await db.execute(select(AppSetting))
                for s in result.scalars().all():
                    # API keys → environment variables
                    env_map = {
                        "openai_api_key": "OPENAI_API_KEY",
                        "anthropic_api_key": "ANTHROPIC_API_KEY",
                        "google_api_key": "GEMINI_API_KEY",
                        "scopus_api_key": "SCOPUS_API_KEY",
                    }
                    if s.key in env_map and s.value:
                        os.environ[env_map[s.key]] = s.value
                    # Model overrides
                    if s.key in self._MODEL_SETTING_KEYS and s.value:
                        attr = self._MODEL_SETTING_KEYS[s.key]
                        self._model_overrides[attr] = s.value
                        logger.info(f"Model override: {attr} = {s.value}")
        except Exception as e:
            logger.warning(f"Failed to load settings from DB: {e}")

    def _get_model(self, role: str) -> str:
        attr = self.ROLE_MODEL_MAP.get(role, "ai_chat_model")
        # Check DB overrides first, then config
        return self._model_overrides.get(attr, getattr(settings, attr))

    async def chat(
        self,
        messages: list[dict],
        role: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> str:
        """Non-streaming chat completion."""
        model = self._get_model(role)
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"AI chat error ({model}): {e}")
            raise AIServiceError(f"AI request failed: {e}")

    async def chat_stream(
        self,
        messages: list[dict],
        role: str = "chat",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion."""
        model = self._get_model(role)
        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta.content:
                    yield delta.content
        except Exception as e:
            logger.error(f"AI stream error ({model}): {e}")
            raise AIServiceError(f"AI stream failed: {e}")

    async def function_call(
        self,
        messages: list[dict],
        tools: list[dict],
        role: str = "executor",
        temperature: float = 0.0,
    ) -> dict:
        """Chat completion with function calling / tools."""
        model = self._get_model(role)
        try:
            response = await litellm.acompletion(
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
            raise AIServiceError(f"AI function call failed: {e}")


ai_service = AIService()
