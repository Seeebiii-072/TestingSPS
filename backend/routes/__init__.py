from routes.ai_resolve import router as ai_resolve_router
from routes.approvals import router as approvals_router
from routes.attachments import router as attachments_router
from routes.auth import router as auth_router
from routes.events import router as events_router
from routes.events_feed import router as events_feed_router
from routes.notifications import router as notifications_router
from routes.reports import router as reports_router
from routes.tickets import router as tickets_router
from routes.users import router as users_router

__all__ = [
    "ai_resolve_router",
    "approvals_router",
    "attachments_router",
    "auth_router",
    "events_router",
    "events_feed_router",
    "notifications_router",
    "reports_router",
    "tickets_router",
    "users_router",
]
