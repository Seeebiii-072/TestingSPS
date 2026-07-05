"""Tests for the internal POST /tickets/{ticket_id}/ai-resolve endpoint."""

import asyncio
import importlib.util
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models  # noqa: F401, E402
from database import Base, get_db  # noqa: E402
from models.ticket import RiskLevel, Ticket, TicketCategory, TicketPriority, TicketSource, TicketStatus, TicketTeam  # noqa: E402
from models.user import User, UserRole  # noqa: E402
from services.auth_service import hash_password  # noqa: E402

AI_RESOLVE_PATH = Path(__file__).resolve().parents[1] / "routes" / "ai_resolve.py"
ai_resolve_spec = importlib.util.spec_from_file_location("ai_resolve_route_under_test", AI_RESOLVE_PATH)
assert ai_resolve_spec and ai_resolve_spec.loader
ai_resolve_module = importlib.util.module_from_spec(ai_resolve_spec)
ai_resolve_spec.loader.exec_module(ai_resolve_module)


def _create_ticket_in_db(session, ticket_id: uuid.UUID, status: TicketStatus) -> Ticket:
    ticket = Ticket(
        id=ticket_id,
        ticket_number="SPS-2026-999",
        source=TicketSource.EMAIL,
        requester_email="user@example.com",
        subject="Test ticket",
        description="Test description",
        category=TicketCategory.GENERAL_IT,
        priority=TicketPriority.MEDIUM,
        risk_level=RiskLevel.STANDARD,
        team=TicketTeam.IT,
        status=status,
    )
    session.add(ticket)
    return ticket


def test_ai_resolve_requires_internal_api_key(tmp_path, monkeypatch):
    """Without a valid X-Internal-Api-Key, the endpoint should return 401."""
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")

    db_path = tmp_path / "ai-resolve.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    asyncio.run(create_schema())

    app = FastAPI()
    app.include_router(ai_resolve_module.router)
    app.dependency_overrides[get_db] = override_get_db

    ticket_id = uuid.uuid4()

    try:
        with TestClient(app) as client:
            # No API key
            resp_no_key = client.post(
                f"/tickets/{ticket_id}/ai-resolve",
                json={"answer": "Test answer"},
            )
            # Wrong API key
            resp_wrong_key = client.post(
                f"/tickets/{ticket_id}/ai-resolve",
                json={"answer": "Test answer"},
                headers={"X-Internal-Api-Key": "wrong-key"},
            )
    finally:
        asyncio.run(engine.dispose())

    assert resp_no_key.status_code == 401
    assert resp_wrong_key.status_code == 401


def test_ai_resolve_rejects_waiting_approval(tmp_path, monkeypatch):
    """A WAITING_APPROVAL ticket should be rejected with 403."""
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")

    db_path = tmp_path / "ai-resolve-waiting.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def seed_data():
        async with session_factory() as session:
            # Create the AI agent user
            ai_agent = User(
                email="ai-agent@sps.com",
                full_name="AI Support Agent",
                hashed_password=hash_password("test"),
                role=UserRole.AGENT,
            )
            session.add(ai_agent)
            # Create a WAITING_APPROVAL ticket
            ticket_id = uuid.uuid4()
            _create_ticket_in_db(session, ticket_id, TicketStatus.WAITING_APPROVAL)
            await session.commit()
            return ticket_id

    async def override_get_db():
        async with session_factory() as session:
            yield session

    asyncio.run(create_schema())
    ticket_id = asyncio.run(seed_data())

    app = FastAPI()
    app.include_router(ai_resolve_module.router)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/tickets/{ticket_id}/ai-resolve",
                json={"answer": "Test answer"},
                headers={"X-Internal-Api-Key": "test-internal-key"},
            )
    finally:
        asyncio.run(engine.dispose())

    assert resp.status_code == 403
    assert "pending human approval" in resp.json()["detail"].lower()


def test_ai_resolve_successfully_resolves_open_ticket(tmp_path, monkeypatch):
    """An OPEN ticket should be resolved successfully."""
    monkeypatch.setenv("INTERNAL_API_KEY", "test-internal-key")

    db_path = tmp_path / "ai-resolve-open.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def create_schema():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def seed_data():
        async with session_factory() as session:
            ai_agent = User(
                email="ai-agent@sps.com",
                full_name="AI Support Agent",
                hashed_password=hash_password("test"),
                role=UserRole.AGENT,
            )
            session.add(ai_agent)
            ticket_id = uuid.uuid4()
            _create_ticket_in_db(session, ticket_id, TicketStatus.OPEN)
            await session.commit()
            return ticket_id

    async def override_get_db():
        async with session_factory() as session:
            yield session

    asyncio.run(create_schema())
    ticket_id = asyncio.run(seed_data())

    app = FastAPI()
    app.include_router(ai_resolve_module.router)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/tickets/{ticket_id}/ai-resolve",
                json={
                    "answer": "Here is the solution to your problem.",
                    "sources": ["faq, Password Reset"],
                },
                headers={"X-Internal-Api-Key": "test-internal-key"},
            )
    finally:
        asyncio.run(engine.dispose())

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resolved"
    assert data["ticket_id"] == str(ticket_id)
    assert data["ticket_number"] == "SPS-2026-999"