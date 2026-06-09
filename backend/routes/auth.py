from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.user import User
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, TokenUser
from schemas.user import UserPublic
from services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_ATTEMPTS: dict[str, deque[datetime]] = defaultdict(deque)
LOGIN_LIMIT = 10
LOGIN_WINDOW = timedelta(minutes=1)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enforce_login_rate_limit(request: Request) -> None:
    client_ip = _client_ip(request)
    now = datetime.now(timezone.utc)
    attempts = LOGIN_ATTEMPTS[client_ip]
    while attempts and attempts[0] <= now - LOGIN_WINDOW:
        attempts.popleft()
    if len(attempts) >= LOGIN_LIMIT:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts")
    attempts.append(now)


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    existing_user = await db.scalar(select(User).where(User.email == payload.email))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    _enforce_login_rate_limit(request)
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    try:
        token = create_access_token(user.id, user.role)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    return TokenResponse(
        access_token=token,
        user=TokenUser(id=user.id, email=user.email, role=user.role),
    )
