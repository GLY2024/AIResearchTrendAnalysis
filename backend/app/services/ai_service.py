"""AI service with LiteLLM - role-based model routing."""

import logging
from typing import AsyncGenerator

import litellm

from app.config import settings
from app.core.exceptions import AIServiceError

logger = logging.getLogger(__name__)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True


class AIService:
    """Unified AI interface with role-based model routing."""

    ROLE_MODEL_MAP = {
        "chat": "ai_chat_model",
        "planner": "ai_planner_model",
        "analyst": "ai_analyst_model",
        "publisher": "ai_publisher_model",
        "executor": "ai_executor_model",
    }

    def _get_model(self, role: str) -> str:
        attr = self.ROLE_MODEL_MAP.get(role, "ai_chat_model")
        return getattr(settings, attr)

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
