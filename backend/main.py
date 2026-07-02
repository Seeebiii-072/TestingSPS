import logging
import os
import sys
import traceback
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy import select

import models  # noqa: F401
from database import AsyncSessionLocal, Base, DATABASE_URL, engine
from middleware.security_middleware import check_security_threats
from models.user import User, UserRole
from routes import approvals_router, attachments_router, auth_router, events_feed_router, events_router, notifications_router, reports_router, tickets_router, users_router
from services.auth_service import hash_password

logging.basicConfig(level=logging.INFO, stream=sys.stdout, force=True)
logger = logging.getLogger("sps.main")

load_dotenv()


def _seed_email(local_part: str) -> str:
    """Build a seeded demo user's email address.

    By default, seeded users get placeholder @sps.com addresses (never
    real, never deliverable — safe for anyone cloning this repo).

    If SEED_EMAIL_BASE is set (e.g. in a developer's local, gitignored
    .env as "yourname@gmail.com"), seeded users instead get real
    Gmail "+alias" addresses like "yourname+intern@gmail.com" — all of
    which land in the same real inbox, so outbound emails sent via a
    real SMTP provider (instead of Mailhog) can actually be received
    and inspected during local testing.
    """
    override_base = os.getenv("SEED_EMAIL_BASE", "").strip()
    if override_base and "@" in override_base:
        user, domain = override_base.split("@", 1)
        return f"{user}+{local_part}@{domain}"
    return f"{local_part}@sps.com"


DEFAULT_USERS = [
    {"email": _seed_email("intern"), "full_name": "Intern User", "password": "Test1234!", "role": UserRole.INTERN},
    {"email": _seed_email("employee"), "full_name": "Employee User", "password": "Test1234!", "role": UserRole.EMPLOYEE},
    {"email": _seed_email("agent"), "full_name": "Agent User", "password": "Test1234!", "role": UserRole.AGENT},
    {"email": _seed_email("secadmin"), "full_name": "Security Admin", "password": "Test1234!", "role": UserRole.SECURITY_ADMIN},
    {"email": _seed_email("manager"), "full_name": "Manager User", "password": "Test1234!", "role": UserRole.MANAGER},
    {"email": _seed_email("admin"), "full_name": "Administrator", "password": "Test1234!", "role": UserRole.ADMINISTRATOR},
]


def _cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


def _seed_default_users_enabled() -> bool:
    return os.getenv("SEED_DEFAULT_USERS", "false").strip().lower() in {"1", "true", "yes", "on"}


async def _seed_default_users(session) -> int:
    seeded_count = 0
    for user_data in DEFAULT_USERS:
        existing = await session.scalar(select(User).where(User.email == user_data["email"]))
        if existing:
            continue
        user = User(
            email=user_data["email"],
            full_name=user_data["full_name"],
            hashed_password=hash_password(user_data["password"]),
            role=user_data["role"],
        )
        session.add(user)
        seeded_count += 1
    await session.commit()
    return seeded_count


app = FastAPI(
    title="SPS SecureDesk AI API",
    openapi_tags=[
        {"name": "auth", "description": "Registration and JWT login"},
        {"name": "tickets", "description": "Unified helpdesk ticket workflow"},
        {"name": "events", "description": "Ticket timeline entries"},
        {"name": "attachments", "description": "Ticket file uploads"},
        {"name": "approvals", "description": "High-risk ticket approval workflow"},
        {"name": "reports", "description": "Operational summary reports"},
        {"name": "users", "description": "Admin user management"},
        {"name": "notifications", "description": "In-app notifications"},
        {"name": "health", "description": "Service health checks"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(check_security_threats)

app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(events_router)
app.include_router(events_feed_router)
app.include_router(attachments_router)
app.include_router(approvals_router)
app.include_router(reports_router)
app.include_router(notifications_router)
app.include_router(users_router)


@app.on_event("startup")
async def on_startup() -> None:
    Path(os.getenv("UPLOAD_DIR", "./uploads")).mkdir(parents=True, exist_ok=True)

    if not _seed_default_users_enabled():
        logger.info("Default test user seeding disabled; set SEED_DEFAULT_USERS=true to enable it")
        return

    # Tables are created by alembic via the docker-compose command, so we only seed data here.
    try:
        async with AsyncSessionLocal() as session:
            try:
                await session.execute(text("SELECT 1 FROM users LIMIT 1"))
            except Exception:
                logger.warning("Users table not accessible yet (alembic may still be running), skipping seed")
                return

            seeded_count = await _seed_default_users(session)
            if seeded_count > 0:
                logger.info("Seeded %d default test users", seeded_count)
            else:
                logger.info("Default test users already exist, skipping")
    except Exception:
        logger.exception("Failed to seed default test users")
        traceback.print_exc()


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "SPS SecureDesk AI"}