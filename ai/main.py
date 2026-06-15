from contextlib import asynccontextmanager

from fastapi import FastAPI

from ai.api import chat, classifier, kb, summariser, tickets
from ai.config.settings import get_settings
from ai.services.kb_service import index_all_documents


settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    del application
    index_all_documents()
    yield


app = FastAPI(
    title=settings.service_name,
    version="0.1.0",
    description="AI provider and assistant service for SPS SecureDesk.",
    lifespan=lifespan,
)

app.include_router(chat.router)
app.include_router(chat.router, prefix="/api/v1", include_in_schema=False)
app.include_router(classifier.router, prefix="/api/v1")
app.include_router(summariser.router, prefix="/api/v1")
app.include_router(classifier.ai_router)
app.include_router(summariser.ai_router)
app.include_router(kb.router, prefix="/api/v1")
app.include_router(tickets.router, prefix="/api/v1")


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "llm_provider": settings.llm_provider,
    }
