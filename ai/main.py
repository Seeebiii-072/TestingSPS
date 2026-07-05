from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai.api import chat, classifier, kb, summariser, ticket_reply
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(classifier.router, prefix="/api")
app.include_router(summariser.router, prefix="/api")
app.include_router(kb.router, prefix="/api")
app.include_router(ticket_reply.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": settings.service_name,
        "llm_provider": settings.llm_provider,
    }