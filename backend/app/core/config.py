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

    jwt_secret: str = "dev-only-change-me-krishiai-jwt"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    openai_api_key: str | None = None
    openai_tts_model: str = "gpt-4o-mini-tts"

    vision_model: str = "mobilenetv3"  # mobilenetv3 | heuristic
    vision_confidence_threshold: float = 0.60
    hf_model_repo: str = "Ishan2702/krishiai-mobilenetv3"
    hf_model_filename: str = "mobilenetv3_plantdisease_best.pth"
    hf_token: str | None = None

    router_mode: str = "keyword"  # keyword | embedding | hybrid | supervised
    router_threshold: float = 0.60
    router_cost_lambda: float = 0.05

    agronomic_weight: float = 0.6
    economic_weight: float = 0.4
    max_revisions: int = 2

    weather_api_key: str | None = None
    market_api_key: str | None = None
    data_gov_api_key: str | None = None
    weather_cache_ttl_seconds: int = 3600
    market_cache_ttl_seconds: int = 21600

    upag_api_username: str | None = None
    upag_api_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
