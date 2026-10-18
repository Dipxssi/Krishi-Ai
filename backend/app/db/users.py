from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlmodel import Field, Session, SQLModel, select

from app.db.session import get_session


class UserRow(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    password_hash: str
    farmer_id: str = Field(index=True, unique=True)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


def get_user_by_email(email: str) -> UserRow | None:
    with get_session() as session:
        statement = select(UserRow).where(UserRow.email == email.lower().strip())
        return session.exec(statement).first()


def get_user_by_id(user_id: str) -> UserRow | None:
    with get_session() as session:
        return session.get(UserRow, user_id)


def create_user(
    *,
    email: str,
    name: str,
    password_hash: str,
    farmer_id: str,
) -> UserRow:
    with get_session() as session:
        row = UserRow(
            email=email.lower().strip(),
            name=name.strip(),
            password_hash=password_hash,
            farmer_id=farmer_id,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        # Detach plain values for return outside session
        return UserRow(
            id=row.id,
            email=row.email,
            name=row.name,
            password_hash=row.password_hash,
            farmer_id=row.farmer_id,
            created_at=row.created_at,
        )
