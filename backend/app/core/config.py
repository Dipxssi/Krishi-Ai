from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'krishiai.db'}"
    knowledge_dir: str = str(BACKEND_DIR / "data" / "knowledge")

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.6-flash"
    gemini_embedding_model: str = "gemini-embedding-001"

    router_mode: str = "hybrid"  # keyword | embedding | hybrid
    router_threshold: float = 0.60
    router_cost_lambda: float = 0.05

    agronomic_weight: float = 0.6
    economic_weight: float = 0.4
    max_revisions: int = 2

    weather_api_key: str | None = None
    market_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
