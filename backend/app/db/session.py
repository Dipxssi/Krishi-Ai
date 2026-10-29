import json
from typing import Any, Optional

from sqlalchemy.pool import StaticPool
from sqlmodel import Field, Session, SQLModel, create_engine

from app.core.config import get_settings
from app.schemas.models import FarmContext, FarmContextCreate, FarmContextUpdate


class FarmContextRow(SQLModel, table=True):
    __tablename__ = "farm_contexts"

    farmer_id: str = Field(primary_key=True)
    location: str
    farm_area_acres: float
    crop: Optional[str] = None
    growth_stage: Optional[str] = None
    soil_type: Optional[str] = None
    soil_npk_json: Optional[str] = None
    irrigation_available: Optional[bool] = None
    budget: Optional[float] = None
    preferred_language: str = "English"
    season: Optional[str] = None


class ToolTraceRow(SQLModel, table=True):
    __tablename__ = "tool_traces"

    id: Optional[int] = Field(default=None, primary_key=True)
    farmer_id: Optional[str] = None
    agent: str
    tool: str
    arguments_json: str
    status: str
    output_json: Optional[str] = None
    error: Optional[str] = None
    timestamp: str


_engine = None


def reset_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def normalize_database_url(url: str | None) -> str:
    """Accept Neon/postgres URLs and prefer the psycopg3 SQLAlchemy driver. Falls back to default SQLite if unset or empty."""
    cleaned = (url or "").strip().strip('"').strip("'")
    # Common paste mistakes from dashboards / .env copies
    if cleaned.lower().startswith("database_url="):
        cleaned = cleaned.split("=", 1)[1].strip().strip('"').strip("'")
    if not cleaned:
        from app.core.config import BACKEND_DIR
        return f"sqlite:///{BACKEND_DIR / 'data' / 'krishiai.db'}"
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://") and "+psycopg" not in cleaned.split("://", 1)[0]:
        cleaned = cleaned.replace("postgresql://", "postgresql+psycopg://", 1)
    return cleaned


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        url = normalize_database_url(settings.database_url)
        if not (
            url.startswith("sqlite:")
            or url.startswith("postgresql+")
            or url.startswith("postgresql:")
        ):
            raise RuntimeError(
                "DATABASE_URL is invalid. Expected a Neon/Postgres URL starting with "
                "postgresql:// (or postgres://). Check Render env: no quotes, no spaces, "
                "and do not include the DATABASE_URL= prefix."
            )
        if url.startswith("sqlite") and ":memory:" in url:
            _engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        elif url.startswith("sqlite"):
            _engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            # Neon and other hosted Postgres: recycle dropped connections.
            _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def init_db() -> None:
    settings = get_settings()
    url = normalize_database_url(settings.database_url)
    if url.startswith("sqlite") and ":memory:" not in url:
        db_path = url.replace("sqlite:///", "", 1)
        from pathlib import Path

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    # Register tables before create_all (also used from tests without importing main).
    from app.db.conversations import ConversationRow  # noqa: F401
    from app.db.users import UserRow  # noqa: F401
    from app.services.audit import FeedbackRow, QueryRunRow  # noqa: F401

    SQLModel.metadata.create_all(get_engine())


def get_session() -> Session:
    return Session(get_engine())


def _row_to_context(row: FarmContextRow) -> FarmContext:
    soil_npk = json.loads(row.soil_npk_json) if row.soil_npk_json else None
    return FarmContext(
        farmer_id=row.farmer_id,
        location=row.location,
        farm_area_acres=row.farm_area_acres,
        crop=row.crop,
        growth_stage=row.growth_stage,
        soil_type=row.soil_type,
        soil_npk=soil_npk,
        irrigation_available=row.irrigation_available,
        budget=row.budget,
        preferred_language=row.preferred_language,
        season=row.season,
    )


def create_farm_context(payload: FarmContextCreate) -> FarmContext:
    with get_session() as session:
        existing = session.get(FarmContextRow, payload.farmer_id)
        if existing:
            raise ValueError(f"Farmer {payload.farmer_id} already exists")
        row = FarmContextRow(
            farmer_id=payload.farmer_id,
            location=payload.location,
            farm_area_acres=payload.farm_area_acres,
            crop=payload.crop,
            growth_stage=payload.growth_stage,
            soil_type=payload.soil_type,
            soil_npk_json=json.dumps(payload.soil_npk) if payload.soil_npk else None,
            irrigation_available=payload.irrigation_available,
            budget=payload.budget,
            preferred_language=payload.preferred_language,
            season=payload.season,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_context(row)


def get_farm_context(farmer_id: str) -> FarmContext | None:
    with get_session() as session:
        row = session.get(FarmContextRow, farmer_id)
        if not row:
            return None
        return _row_to_context(row)


def update_farm_context(farmer_id: str, payload: FarmContextUpdate) -> FarmContext | None:
    with get_session() as session:
        row = session.get(FarmContextRow, farmer_id)
        if not row:
            return None
        data = payload.model_dump(exclude_unset=True)
        if "soil_npk" in data:
            soil_npk = data.pop("soil_npk")
            row.soil_npk_json = json.dumps(soil_npk) if soil_npk is not None else None
        for key, value in data.items():
            setattr(row, key, value)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_context(row)


def save_tool_trace(
    *,
    farmer_id: str | None,
    agent: str,
    tool: str,
    arguments: dict[str, Any],
    status: str,
    output: Any = None,
    error: str | None = None,
    timestamp: str,
) -> None:
    with get_session() as session:
        row = ToolTraceRow(
            farmer_id=farmer_id,
            agent=agent,
            tool=tool,
            arguments_json=json.dumps(arguments),
            status=status,
            output_json=json.dumps(output) if output is not None else None,
            error=error,
            timestamp=timestamp,
        )
        session.add(row)
        session.commit()
