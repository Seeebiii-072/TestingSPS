import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import models  # noqa: F401
from database import Base, DATABASE_URL, engine
from routes import approvals_router, attachments_router, auth_router, events_router, reports_router, tickets_router

load_dotenv()


def _cors_origins() -> list[str]:
    origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app = FastAPI(
    title="SPS SecureDesk AI API",
    openapi_tags=[
        {"name": "auth", "description": "Registration and JWT login"},
        {"name": "tickets", "description": "Unified helpdesk ticket workflow"},
        {"name": "events", "description": "Ticket timeline entries"},
        {"name": "attachments", "description": "Ticket file uploads"},
        {"name": "approvals", "description": "High-risk ticket approval workflow"},
        {"name": "reports", "description": "Operational summary reports"},
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

app.include_router(auth_router)
app.include_router(tickets_router)
app.include_router(events_router)
app.include_router(attachments_router)
app.include_router(approvals_router)
app.include_router(reports_router)


@app.on_event("startup")
async def on_startup() -> None:
    Path(os.getenv("UPLOAD_DIR", "./uploads")).mkdir(parents=True, exist_ok=True)
    if os.getenv("ENVIRONMENT", "development") == "development" and DATABASE_URL.startswith("sqlite"):
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "SPS SecureDesk AI"}
