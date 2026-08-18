"""Application settings, loaded from environment / .env.

Everything configurable lives here. No module reads os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    APP_NAME: str = "SmartBuy AI"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "dev-secret-change-me"
    ADMIN_TOKEN: str = "dev-admin-token"

    # --- Database ---
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'smartbuy.db'}"
    DB_ECHO: bool = False

    # --- CORS ---
    FRONTEND_URL: str = "http://localhost:5173"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- LLM ---
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_TIMEOUT_SECONDS: float = 12.0
    LLM_MAX_RETRIES: int = 1
    LLM_TEMPERATURE: float = 0.2

    # --- Feature flags ---
    ENABLE_LLM_REQUIREMENT_AUGMENT: bool = False
    ENABLE_COLLABORATIVE_FILTERING: bool = False
    USE_DETERMINISTIC_FALLBACK: bool = True

    # --- Agent behaviour ---
    MAX_FOLLOWUP_QUESTIONS: int = 3
    DEFAULT_CANDIDATES_PER_REQUIREMENT: int = 5

    # --- Rate limiting ---
    RATE_LIMIT_PER_MINUTE: int = 60

    # --- Paths ---
    RANKING_CONFIG_PATH: str = str(BACKEND_DIR / "app" / "config" / "ranking.yaml")
    SLOT_POLICY_PATH: str = str(BACKEND_DIR / "app" / "config" / "slot_policy.yaml")
    KB_GOALS_DIR: str = str(BACKEND_DIR / "app" / "kb" / "goals")
    CATALOG_PATH: str = str(PROJECT_ROOT / "data" / "products" / "catalog.json")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        """True only when we actually have credentials. Drives the degraded path."""
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
