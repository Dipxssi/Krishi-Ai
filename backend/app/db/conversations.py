"""Persisted chat threads so history follows the farmer across devices."""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Field, SQLModel, col, select

from app.db.session import get_session


class ConversationRow(SQLModel, table=True):
    __tablename__ = "conversations"

    id: str = Field(primary_key=True)
    farmer_id: str = Field(index=True)
    title: str = ""
    updated_at: int = Field(default=0, index=True)
    messages_json: str = "[]"


def _row_to_dict(row: ConversationRow) -> dict[str, Any]:
    try:
        messages = json.loads(row.messages_json or "[]")
    except json.JSONDecodeError:
        messages = []
    if not isinstance(messages, list):
        messages = []
    return {
        "id": row.id,
        "title": row.title,
        "updatedAt": row.updated_at,
        "messages": messages,
    }


def list_conversations(farmer_id: str) -> list[dict[str, Any]]:
    with get_session() as session:
        rows = session.exec(
            select(ConversationRow)
            .where(ConversationRow.farmer_id == farmer_id)
            .order_by(col(ConversationRow.updated_at).desc())
        ).all()
        return [_row_to_dict(row) for row in rows]


def upsert_conversation(farmer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    conversation_id = str(payload.get("id") or "").strip()
    if not conversation_id:
        raise ValueError("Conversation id is required")

    title = str(payload.get("title") or "Chat").strip() or "Chat"
    updated_at = int(payload.get("updatedAt") or 0)
    messages = payload.get("messages")
    if not isinstance(messages, list):
        messages = []

    with get_session() as session:
        row = session.get(ConversationRow, conversation_id)
        if row and row.farmer_id != farmer_id:
            raise PermissionError("Conversation belongs to another farmer")

        if row is None:
            row = ConversationRow(
                id=conversation_id,
                farmer_id=farmer_id,
                title=title,
                updated_at=updated_at,
                messages_json=json.dumps(messages),
            )
        else:
            # Last-write-wins by updatedAt so an older device cannot clobber newer history.
            if updated_at < row.updated_at:
                return _row_to_dict(row)
            row.title = title
            row.updated_at = updated_at
            row.messages_json = json.dumps(messages)

        session.add(row)
        session.commit()
        session.refresh(row)
        return _row_to_dict(row)


def replace_conversations(farmer_id: str, conversations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upsert a batch; does not delete remote threads missing from the payload."""
    for item in conversations:
        if not isinstance(item, dict):
            continue
        upsert_conversation(farmer_id, item)
    return list_conversations(farmer_id)


def delete_conversation(farmer_id: str, conversation_id: str) -> bool:
    with get_session() as session:
        row = session.get(ConversationRow, conversation_id)
        if not row or row.farmer_id != farmer_id:
            return False
        session.delete(row)
        session.commit()
        return True


def delete_all_conversations(farmer_id: str) -> int:
    with get_session() as session:
        rows = session.exec(
            select(ConversationRow).where(ConversationRow.farmer_id == farmer_id)
        ).all()
        count = len(rows)
        for row in rows:
            session.delete(row)
        session.commit()
        return count
