from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.db import conversations as conversation_store
from app.db.users import UserRow
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/conversations", tags=["conversations"])


class ConversationPayload(BaseModel):
    id: str
    title: str = "Chat"
    updatedAt: int = 0
    messages: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None


class ConversationBatchPayload(BaseModel):
    conversations: list[ConversationPayload] = Field(default_factory=list)


@router.get("")
@router.get("/")
def get_conversations(user: UserRow = Depends(get_current_user)) -> dict[str, Any]:
    items = conversation_store.list_conversations(user.farmer_id)
    return {"conversations": items}


@router.put("")
@router.put("/")
def put_conversations(
    payload: ConversationBatchPayload,
    user: UserRow = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        items = conversation_store.replace_conversations(
            user.farmer_id,
            [c.model_dump() for c in payload.conversations],
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"conversations": items}


@router.put("/{conversation_id}")
def put_conversation(
    conversation_id: str,
    payload: ConversationPayload,
    user: UserRow = Depends(get_current_user),
) -> dict[str, Any]:
    if payload.id != conversation_id:
        raise HTTPException(status_code=400, detail="Conversation id mismatch")
    try:
        item = conversation_store.upsert_conversation(user.farmer_id, payload.model_dump())
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@router.delete("/{conversation_id}", status_code=204)
def remove_conversation(
    conversation_id: str,
    user: UserRow = Depends(get_current_user),
) -> None:
    deleted = conversation_store.delete_conversation(user.farmer_id, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")


@router.delete("", status_code=204)
@router.delete("/", status_code=204)
def remove_all_conversations(user: UserRow = Depends(get_current_user)) -> None:
    conversation_store.delete_all_conversations(user.farmer_id)
