import logging
import os
import smtplib
import traceback
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.security_middleware import log_security_event
from models.user import User, UserRole
from schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    TokenUser,
)
from schemas.user import UserPublic
from services.auth_service import (
    create_access_token,
    create_password_reset_token,
    decode_password_reset_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger("sps.auth_routes")

LOGIN_ATTEMPTS: dict[str, deque[datetime]] = defaultdict(deque)
LOGIN_LIMIT = 10
LOGIN_WINDOW = timedelta(minutes=1)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def _enforce_login_rate_limit(request: Request, db: AsyncSession) -> None:
    client_ip = _client_ip(request)
    now = datetime.now(timezone.utc)
    attempts = LOGIN_ATTEMPTS[client_ip]
    while attempts and attempts[0] <= now - LOGIN_WINDOW:
        attempts.popleft()
    if len(attempts) >= LOGIN_LIMIT:
        await log_security_event(
            action="security.brute_force",
            request=request,
            db=db,
            details={
                "attempts": len(attempts),
                "limit": LOGIN_LIMIT,
                "window_seconds": int(LOGIN_WINDOW.total_seconds()),
            },
        )
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
        role=UserRole.EMPLOYEE,
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
    try:
        await _enforce_login_rate_limit(request, db)
        user = await db.scalar(select(User).where(User.email == payload.email))
        if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

        try:
            token = create_access_token(user.id, user.role)
        except RuntimeError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

        return TokenResponse(
            access_token=token,
            user=TokenUser(
                id=user.id,
                email=user.email,
                full_name=user.full_name,
                role=user.role,
            ),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unhandled exception in /auth/login endpoint")
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")


def _send_reset_email(to_email: str, reset_link: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    from_address = os.getenv("EMAIL_FROM_ADDRESS", "helpdesk@sps.com")
    from_name = os.getenv("EMAIL_FROM_NAME", "SPS SecureDesk")

    html_body = f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 40px 24px;">
      <div style="text-align: center; margin-bottom: 32px;">
        <h2 style="color: #1a237e; margin: 0;">Password Reset</h2>
      </div>
      <p style="color: #475569; font-size: 14px; line-height: 1.7;">
        You requested a password reset for your SPS SecureDesk account. Click the button below to set a new password.
      </p>
      <div style="text-align: center; margin: 32px 0;">
        <a href="{reset_link}" style="display: inline-block; padding: 14px 36px; background: #1565c0; color: #ffffff; text-decoration: none; border-radius: 8px; font-weight: 600; font-size: 14px;">
          Reset Password
        </a>
      </div>
      <p style="color: #94a3b8; font-size: 12px; line-height: 1.6;">
        This link expires in 30 minutes. If you didn't request this, ignore this email.
      </p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, from_address))
    msg["To"] = to_email
    msg["Subject"] = "SPS SecureDesk - Password Reset"
    msg.attach(MIMEText(f"Reset your password: {reset_link}", "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        if smtp_port != 1025 and smtp_user:
            server.starttls()
            server.login(smtp_user, smtp_password)
        server.sendmail(from_address, to_email, msg.as_string())


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user and user.is_active:
        token = create_password_reset_token(user.email)
        portal_url = os.getenv("PORTAL_URL", "http://localhost:5173")
        reset_link = f"{portal_url}/reset-password?token={token}"
        try:
            _send_reset_email(user.email, reset_link)
        except Exception:
            logger.exception("Failed to send password reset email to %s", user.email)
    return {"message": "If an account exists with that email, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    try:
        email = decode_password_reset_token(payload.token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = await db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user.hashed_password = hash_password(payload.password)
    await db.commit()
    return {"message": "Password has been reset successfully."}