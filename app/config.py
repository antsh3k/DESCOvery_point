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
        "postgresql+psycopg://descovery:descovery@localhost:5432/descovery_point"
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
    scrape_tier2: str = "claude"  # "claude" | "off"
    scrape_max_pages: int = 6

    # --- Enrichment (supplemental firmographics via web search) ---
    enrich_source: str = "claude"  # "claude" | "off"

    # --- EDGAR fund ingestion (Form ADV / Form D bulk data) ---
    # SEC requires a declared contact in the User-Agent on every request or it
    # returns 403/429 (its "fair access" policy) — set a real contact.
    edgar_user_agent: str = "DESCOvery Point antsh3k@gmail.com"
    edgar_data_dir: str = "data/edgar"
    edgar_ingest_limit: int = 100

    # --- Fund embeddings (semantic pre-filter, pgvector) ---
    # Anthropic has no embeddings API; OpenAI's is used regardless of
    # llm_provider — set openai_api_key even when using Claude for everything else.
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
