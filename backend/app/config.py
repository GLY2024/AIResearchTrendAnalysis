"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ARTA_",
        case_sensitive=False,
    )

    # App
    app_name: str = "ARTA"
    debug: bool = False
    host: str = "127.0.0.1"
    port: int = 8721

    # Database
    data_dir: Path = Path("data")
    db_name: str = "research.db"

    @property
    def db_url(self) -> str:
        db_path = self.data_dir / self.db_name
        return f"sqlite+aiosqlite:///{db_path}"

    # AI Model Roles (configurable by user)
    ai_planner_model: str = "gpt-4o"
    ai_analyst_model: str = "gpt-4o"
    ai_publisher_model: str = "gpt-4o"
    ai_chat_model: str = "gpt-4o"
    ai_executor_model: str = "gemini/gemini-2.0-flash"

    # API Keys (stored encrypted in DB, these are fallbacks)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    scopus_api_key: str = ""
    zotero_api_key: str = ""
    zotero_library_id: str = ""
    zotero_library_type: str = "user"

    # Rate limiting
    default_rate_limit: int = 10  # requests per second


settings = Settings()
