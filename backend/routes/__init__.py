from routes.approvals import router as approvals_router
from routes.attachments import router as attachments_router
from routes.auth import router as auth_router
from routes.events import router as events_router
from routes.reports import router as reports_router
from routes.tickets import router as tickets_router

__all__ = [
    "approvals_router",
    "attachments_router",
    "auth_router",
    "events_router",
    "reports_router",
    "tickets_router",
]
