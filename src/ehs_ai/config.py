from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global application settings sourced from environment variables or a .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "staging", "prod"] = Field(default="dev")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(default="INFO")

    # LLM configuration (pydantic-ai / OpenAI)
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini")

    # Vector memory configuration
    vector_db_path: Path = Field(default=Path("./storage/vector_db"))
    vector_collection: str = Field(default="ehs_policies")
    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")

    # FastAPI server
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()

