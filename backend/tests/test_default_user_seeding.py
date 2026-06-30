import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models  # noqa: F401, E402
from database import Base  # noqa: E402
from main import DEFAULT_USERS, _seed_default_users, _seed_default_users_enabled  # noqa: E402
from models.user import User  # noqa: E402


def test_default_user_seeding_requires_explicit_env(monkeypatch):
    monkeypatch.delenv("SEED_DEFAULT_USERS", raising=False)
    assert _seed_default_users_enabled() is False

    monkeypatch.setenv("SEED_DEFAULT_USERS", "false")
    assert _seed_default_users_enabled() is False

    monkeypatch.setenv("SEED_DEFAULT_USERS", "true")
    assert _seed_default_users_enabled() is True


def test_default_user_seed_helper_creates_demo_accounts(tmp_path):
    db_path = tmp_path / "default-users.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def run_case():
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            first_count = await _seed_default_users(session)
            second_count = await _seed_default_users(session)
            total_users = await session.scalar(select(func.count()).select_from(User))
            return first_count, second_count, total_users

    try:
        first_count, second_count, total_users = asyncio.run(run_case())
    finally:
        asyncio.run(engine.dispose())

    assert first_count == len(DEFAULT_USERS)
    assert second_count == 0
    assert total_users == len(DEFAULT_USERS)
