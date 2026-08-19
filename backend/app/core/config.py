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

    # --- Feature flags: NOT WIRED UP ---
    # Nothing in the codebase reads any of these three. They describe features
    # that were designed and never built, and toggling them changes nothing.
    # Documented as inert rather than deleted so that an existing .env that
    # sets them keeps parsing -- but do not cite them as capabilities.
    ENABLE_LLM_REQUIREMENT_AUGMENT: bool = False  # no augment_requirements() exists
    ENABLE_COLLABORATIVE_FILTERING: bool = False  # no CF implementation exists
    USE_DETERMINISTIC_FALLBACK: bool = True  # fallback is unconditional; cannot be turned off

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
    def resolved_database_url(self) -> str:
        """DATABASE_URL with a relative SQLite path anchored to the backend dir.

        `sqlite:///./smartbuy.db` means "relative to the process working
        directory", so running a script from the repo root instead of from
        backend/ points SQLAlchemy at a path with no database -- and SQLite
        cheerfully creates an empty one rather than failing. The result is a
        script that reports zero products instead of an error. Anchoring the
        path here makes the URL mean the same thing from every directory.
        """
        url = self.DATABASE_URL
        prefix = "sqlite:///"
        if not url.startswith(prefix):
            return url
        path = url[len(prefix) :]
        if not path or path == ":memory:" or Path(path).is_absolute():
            return url
        return f"{prefix}{(BACKEND_DIR / path).resolve()}"

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
