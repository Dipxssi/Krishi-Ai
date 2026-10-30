"""Persisted Agmarknet mandi price snapshots for weekly refresh + fast lookups."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, Session, SQLModel, col, select

from app.db.session import get_session


class MandiPriceSnapshotRow(SQLModel, table=True):
    __tablename__ = "mandi_price_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "crop",
            "market",
            "district",
            "arrival_date",
            name="uq_mandi_crop_market_district_arrival",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    crop: str = Field(index=True)
    market: str = Field(default="")
    district: str = Field(default="")
    state: str = Field(default="")
    modal_price_per_kg: float
    modal_price_quintal: float = 0.0
    arrival_date: str = Field(default="")
    scraped_at: str = Field(index=True)


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _crop_key(crop: str) -> str:
    return crop.strip().lower()


def upsert_mandi_records(
    records: list[dict[str, Any]],
    *,
    crop: str,
    scraped_at: str | None = None,
    session: Session | None = None,
) -> int:
    """Insert or update normalized Agmarknet-style records. Returns rows touched."""
    crop_key = _crop_key(crop)
    when = scraped_at or datetime.now(timezone.utc).isoformat()
    owns = session is None
    db = session or get_session()
    touched = 0
    try:
        for r in records:
            market = _norm(r.get("market"))
            district = _norm(r.get("district"))
            arrival = _norm(r.get("arrival_date"))
            try:
                price_kg = float(r.get("modal_price_per_kg") or 0)
            except (TypeError, ValueError):
                continue
            if price_kg <= 0 or not market:
                continue
            try:
                price_q = float(r.get("modal_price_quintal") or price_kg * 100.0)
            except (TypeError, ValueError):
                price_q = price_kg * 100.0

            existing = db.exec(
                select(MandiPriceSnapshotRow).where(
                    MandiPriceSnapshotRow.crop == crop_key,
                    MandiPriceSnapshotRow.market == market,
                    MandiPriceSnapshotRow.district == district,
                    MandiPriceSnapshotRow.arrival_date == arrival,
                )
            ).first()
            if existing:
                existing.state = _norm(r.get("state"))
                existing.modal_price_per_kg = price_kg
                existing.modal_price_quintal = price_q
                existing.scraped_at = when
                db.add(existing)
            else:
                db.add(
                    MandiPriceSnapshotRow(
                        crop=crop_key,
                        market=market,
                        district=district,
                        state=_norm(r.get("state")),
                        modal_price_per_kg=price_kg,
                        modal_price_quintal=price_q,
                        arrival_date=arrival,
                        scraped_at=when,
                    )
                )
            touched += 1
        db.commit()
    finally:
        if owns:
            db.close()
    return touched


def list_fresh_records_for_crop(
    crop: str,
    *,
    max_age_days: int = 7,
    session: Session | None = None,
) -> list[dict[str, Any]]:
    """Return normalized record dicts for crop if scraped within max_age_days."""
    crop_key = _crop_key(crop)
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(0, max_age_days))
    owns = session is None
    db = session or get_session()
    try:
        rows = list(
            db.exec(
                select(MandiPriceSnapshotRow).where(col(MandiPriceSnapshotRow.crop) == crop_key)
            ).all()
        )
    finally:
        if owns:
            db.close()

    fresh: list[dict[str, Any]] = []
    for row in rows:
        try:
            scraped = datetime.fromisoformat(row.scraped_at)
            if scraped.tzinfo is None:
                scraped = scraped.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if scraped < cutoff:
            continue
        fresh.append(
            {
                "commodity": crop_key,
                "market": row.market or None,
                "district": row.district or None,
                "state": row.state or None,
                "modal_price_per_kg": float(row.modal_price_per_kg),
                "modal_price_quintal": float(row.modal_price_quintal),
                "arrival_date": row.arrival_date or None,
                "source": "agmarknet_db_snapshot",
            }
        )
    return fresh
