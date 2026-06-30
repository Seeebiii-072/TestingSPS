import asyncio
import importlib.util
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models  # noqa: F401, E402
from database import Base, get_db  # noqa: E402

AUTH_ROUTE_PATH = Path(__file__).resolve().parents[1] / "routes" / "auth.py"
auth_spec = importlib.util.spec_from_file_location("auth_route_under_test", AUTH_ROUTE_PATH)
assert auth_spec and auth_spec.loader
auth_module = importlib.util.module_from_spec(auth_spec)
auth_spec.loader.exec_module(auth_module)
auth_router = auth_module.router


def test_public_register_forces_employee_role(tmp_path):
    db_path = tmp_path / "auth-register.db"
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
    app.include_router(auth_router)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/auth/register",
                json={
                    "email": "new-admin@sps.com",
                    "full_name": "New Admin",
                    "password": "Test1234!",
                    "role": "administrator",
                },
            )
        assert response.status_code == 201
        assert response.json()["role"] == "employee"
    finally:
        asyncio.run(engine.dispose())
