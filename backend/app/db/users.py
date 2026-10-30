from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlmodel import Field, SQLModel, select

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


def create_user_with_farm(
    *,
    email: str,
    name: str,
    password_hash: str,
    farmer_id: str,
    location: str,
) -> UserRow | None:
    """Insert the account and its farm row in one transaction.

    Returns None when the email is already registered. One connection checkout
    matters on Neon: signup used to open four separate sessions before the
    client could show the farm form.
    """
    from app.db.session import FarmContextRow

    normalized_email = email.lower().strip()
    with get_session() as session:
        existing = session.exec(select(UserRow).where(UserRow.email == normalized_email)).first()
        if existing:
            return None
        row = UserRow(
            email=normalized_email,
            name=name.strip(),
            password_hash=password_hash,
            farmer_id=farmer_id,
        )
        session.add(row)
        session.add(
            FarmContextRow(
                farmer_id=farmer_id,
                location=location,
                farm_area_acres=1.0,
                preferred_language="en",
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return None
        session.refresh(row)
        return UserRow(
            id=row.id,
            email=row.email,
            name=row.name,
            password_hash=row.password_hash,
            farmer_id=row.farmer_id,
            created_at=row.created_at,
        )
