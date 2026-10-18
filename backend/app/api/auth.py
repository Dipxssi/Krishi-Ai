from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.db.session import create_farm_context, get_farm_context
from app.db.users import create_user, get_user_by_email
from app.schemas.models import FarmContextCreate
from app.services.auth_service import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.users import UserRow

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    location: str | None = Field(default=None, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: str
    email: str
    name: str
    farmer_id: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


def _to_public(user: UserRow) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        name=user.name,
        farmer_id=user.farmer_id,
    )


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(payload: SignupRequest):
    email = str(payload.email).lower().strip()
    if get_user_by_email(email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    from uuid import uuid4

    farmer_id = str(uuid4())

    user = create_user(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        farmer_id=farmer_id,
    )

    if not get_farm_context(farmer_id):
        create_farm_context(
            FarmContextCreate(
                farmer_id=farmer_id,
                location=(payload.location or "India").strip() or "India",
                farm_area_acres=1.0,
                preferred_language="en",
            )
        )

    token = create_access_token(user_id=user.id, email=user.email, farmer_id=user.farmer_id)
    return AuthResponse(access_token=token, user=_to_public(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    email = str(payload.email).lower().strip()
    user = get_user_by_email(email)
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = create_access_token(user_id=user.id, email=user.email, farmer_id=user.farmer_id)
    return AuthResponse(access_token=token, user=_to_public(user))


@router.get("/me", response_model=UserPublic)
def me(user: UserRow = Depends(get_current_user)):
    return _to_public(user)
