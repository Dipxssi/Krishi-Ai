from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = Path(__file__).resolve().parents[2]


_DEV_JWT_SECRET = "dev-only-change-me-krishiai-jwt-secret-key-32b"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"  # development | production
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )

    database_url: str = f"sqlite:///{BACKEND_DIR / 'data' / 'krishiai.db'}"
    knowledge_dir: str = str(BACKEND_DIR / "data" / "knowledge")

    jwt_secret: str = _DEV_JWT_SECRET
    jwt_expire_minutes: int = 60 * 24 * 7  # 7 days

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: object) -> str:
        if not v or not str(v).strip():
            return _DEV_JWT_SECRET
        return str(v).strip()

    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v: object) -> str:
        if not v or not str(v).strip():
            return f"sqlite:///{BACKEND_DIR / 'data' / 'krishiai.db'}"
        cleaned = str(v).strip().strip('"').strip("'")
        if cleaned.lower().startswith("database_url="):
            cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
        return cleaned

    groq_api_key: str | None = None
    groq_model: str = "qwen/qwen3.8-27b"
    openai_api_key: str | None = None
    openai_tts_model: str = "gpt-4o-mini-tts"

    # Default heuristic so slim/Free deploys work without torch.
    # Set VISION_MODEL=mobilenetv3 only when the vision extra is installed.
    vision_model: str = "heuristic"  # heuristic | mobilenetv3
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

    def cors_origin_list(self) -> list[str]:
        origins: list[str] = []
        for raw in self.cors_origins.split(","):
            origin = raw.strip().strip('"').strip("'").rstrip("/")
            if origin:
                origins.append(origin)
        return origins

    def cors_origin_regex(self) -> str | None:
        """Allow Vercel production + preview URLs without listing every deploy."""
        # Exact origins still come from CORS_ORIGINS; this covers *.vercel.app.
        return r"https://.*\.vercel\.app"

    def ensure_secure_for_production(self) -> None:
        if self.app_env.strip().lower() != "production":
            return
        secret = (self.jwt_secret or "").strip()
        if not secret or secret == _DEV_JWT_SECRET or len(secret) < 32:
            raise RuntimeError(
                "APP_ENV=production requires JWT_SECRET to be a strong random string "
                "(at least 32 characters, not the dev default)."
            )
        if not (self.database_url or "").strip() or self.database_url.startswith("sqlite"):
            raise RuntimeError(
                "APP_ENV=production requires DATABASE_URL pointing at Postgres (e.g. Neon)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
