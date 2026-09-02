"""Persist query runs for Phase 5 audit API."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Field, Session, SQLModel, select

from app.db.session import get_engine
from app.schemas.models import QueryResponse


class QueryRunRow(SQLModel, table=True):
    __tablename__ = "query_runs"

    request_id: str = Field(primary_key=True)
    farmer_id: str
    query: str
    response_json: str
    created_at: str


class FeedbackRow(SQLModel, table=True):
    __tablename__ = "feedback"

    id: int | None = Field(default=None, primary_key=True)
    request_id: str
    rating: int
    comment: str | None = None
    expert_verdict: str | None = None
    created_at: str


def new_request_id() -> str:
    return str(uuid.uuid4())


def save_query_run(request_id: str, farmer_id: str, query: str, response: QueryResponse) -> None:
    with Session(get_engine()) as session:
        row = QueryRunRow(
            request_id=request_id,
            farmer_id=farmer_id,
            query=query,
            response_json=response.model_dump_json(),
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        session.add(row)
        session.commit()


def get_query_run(request_id: str) -> dict[str, Any] | None:
    with Session(get_engine()) as session:
        row = session.get(QueryRunRow, request_id)
        if not row:
            return None
        payload = json.loads(row.response_json)
        return {
            "request_id": row.request_id,
            "farmer_id": row.farmer_id,
            "query": row.query,
            "created_at": row.created_at,
            "response": payload,
        }


def save_feedback(request_id: str, rating: int, comment: str | None, expert_verdict: str | None) -> None:
    with Session(get_engine()) as session:
        row = FeedbackRow(
            request_id=request_id,
            rating=rating,
            comment=comment,
            expert_verdict=expert_verdict,
            created_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        )
        session.add(row)
        session.commit()


def list_feedback(limit: int = 100) -> list[dict[str, Any]]:
    with Session(get_engine()) as session:
        rows = session.exec(select(FeedbackRow).order_by(FeedbackRow.id.desc()).limit(limit)).all()
        return [
            {
                "id": r.id,
                "request_id": r.request_id,
                "rating": r.rating,
                "comment": r.comment,
                "expert_verdict": r.expert_verdict,
                "created_at": r.created_at,
            }
            for r in rows
        ]
