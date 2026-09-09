"""Runtime settings for the Film AD multi-agent system."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(BACKEND_ROOT / ".env"),
            str(REPO_ROOT / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="film_ad", alias="POSTGRES_DB")
    postgres_user: str = Field(default="film_ad_user", alias="POSTGRES_USER")
    postgres_password: str = Field(default="film_ad_pass", alias="POSTGRES_PASSWORD")

    # Gemini / Vertex
    model_name: str = Field(default="gemini-2.5-flash", alias="MODEL_NAME")
    google_genai_use_vertexai: bool = Field(default=True, alias="GOOGLE_GENAI_USE_VERTEXAI")
    google_cloud_project: str | None = Field(default=None, alias="GOOGLE_CLOUD_PROJECT")
    google_cloud_location: str = Field(default="global", alias="GOOGLE_CLOUD_LOCATION")
    google_genai_location: str | None = Field(default=None, alias="GOOGLE_GENAI_LOCATION")

    # Feature toggles
    use_live_weather_mcp: bool = Field(default=False, alias="USE_LIVE_WEATHER_MCP")
    use_live_location_mcp: bool = Field(default=False, alias="USE_LIVE_LOCATION_MCP")
    use_docling_mcp: bool = Field(default=False, alias="USE_DOCLING_MCP")
    use_watsonx_rag: bool = Field(default=False, alias="USE_WATSONX_RAG")
    enable_replan_on_failure: bool = Field(default=True, alias="ENABLE_REPLAN_ON_FAILURE")

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def effective_location(self) -> str:
        return self.google_genai_location or self.google_cloud_location


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
