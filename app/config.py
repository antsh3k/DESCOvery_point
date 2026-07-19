"""Application configuration, loaded from environment / .env (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- LLM ---
    llm_provider: str = "anthropic"  # "anthropic" | "openai"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # --- Database ---
    database_url: str = (
        "postgresql+psycopg://thesis:thesis@localhost:5432/thesis_match"
    )

    # --- App ---
    app_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"  # comma-separated

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Scraping ---
    scrape_tier2: str = "off"  # "tavily" | "playwright" | "off"
    scrape_max_pages: int = 6
    tavily_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
