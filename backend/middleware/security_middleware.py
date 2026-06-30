import logging
import json
import re
import traceback
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, Response

from database import AsyncSessionLocal
from services.audit_service import write_audit_log

logger = logging.getLogger("sps.security_middleware")

INJECTION_KEYWORDS = ("SELECT", "DROP", "INSERT", "DELETE", "UNION", "XP_")
FREE_TEXT_FIELDS = {"subject", "description", "message", "body", "content", "ai_summary"}
SQLISH_INJECTION_PATTERN = re.compile(
    r"(?:['\";]|--|/\*|\*/).{0,80}\b(SELECT|DROP|INSERT|DELETE|UNION|XP_)\b"
    r"|\b(SELECT|DROP|INSERT|DELETE|UNION|XP_)\b.{0,80}(?:['\";]|--|/\*|\*/)",
    re.IGNORECASE | re.DOTALL,
)
SECRET_PATTERNS = (
    ("api_key", re.compile(r"(api[_-]?key|secret[_-]?key|access[_-]?token|anthropic_api_key)\s*[:=]\s*[\"']?[A-Za-z0-9_.\-]{8,}", re.IGNORECASE)),
    ("bearer_token", re.compile(r"bearer\s+[A-Za-z0-9_.\-]{20,}", re.IGNORECASE)),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("password_assignment", re.compile(r"password\s*=\s*[^&\s]{4,}", re.IGNORECASE)),
)


def _client_ip(request: Request | None) -> str | None:
    if not request or not request.client:
        return None
    return request.client.host


def _should_scan_body(request: Request) -> bool:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return False

    content_type = request.headers.get("content-type", "").lower()
    if content_type.startswith("multipart/form-data"):
        return False
    if content_type.startswith("application/octet-stream"):
        return False
    return True


async def log_security_event(
    *,
    action: str,
    details: dict[str, Any],
    request: Request | None = None,
    db: AsyncSession | None = None,
    actor_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> None:
    log_ip = ip_address or _client_ip(request)
    log_details = {
        "path": str(request.url.path) if request else None,
        **details,
    }

    try:
        if db:
            await write_audit_log(
                db,
                action=action,
                channel="security",
                actor_id=actor_id,
                details=log_details,
                ip_address=log_ip,
            )
            await db.commit()
            return

        async with AsyncSessionLocal() as session:
            await write_audit_log(
                session,
                action=action,
                channel="security",
                actor_id=actor_id,
                details=log_details,
                ip_address=log_ip,
            )
            await session.commit()
    except Exception:
        if db:
            await db.rollback()


def _normalize_path(path: Iterable[str]) -> str:
    return ".".join(path)


def _find_sqlish_injection(value: str) -> str | None:
    match = SQLISH_INJECTION_PATTERN.search(value)
    if not match:
        return None
    keyword = next((group for group in match.groups() if group), None)
    return keyword.upper() if keyword else "SQL_SYNTAX"


def _scan_json_value(value: Any, path: tuple[str, ...] = ()) -> dict[str, str] | None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            if key_text.lower() in FREE_TEXT_FIELDS:
                continue
            detected = _scan_json_value(child, (*path, key_text))
            if detected:
                return detected
        return None

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for index, child in enumerate(value):
            detected = _scan_json_value(child, (*path, str(index)))
            if detected:
                return detected
        return None

    if not isinstance(value, str):
        return None

    pattern = _find_sqlish_injection(value)
    if not pattern:
        return None
    return {"pattern": pattern, "field": _normalize_path(path)}


def _detect_injection(body_text: str, content_type: str) -> dict[str, str] | None:
    if "application/json" in content_type.lower():
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            payload = None
        if payload is not None:
            return _scan_json_value(payload)

    pattern = _find_sqlish_injection(body_text)
    if pattern:
        return {"pattern": pattern, "field": "raw_body"}
    return None


def _detect_secret(body_text: str, path: str) -> str | None:
    for name, pattern in SECRET_PATTERNS:
        if name == "password_assignment" and path.startswith("/auth/"):
            continue
        if pattern.search(body_text):
            return name
    return None


async def check_security_threats(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    try:
        if not _should_scan_body(request):
            return await call_next(request)

        body = await request.body()
        body_text = body.decode("utf-8", errors="ignore")

        injection = _detect_injection(body_text, request.headers.get("content-type", ""))
        if injection:
            await log_security_event(
                action="security.injection_attempt",
                request=request,
                details={**injection, "method": request.method},
            )
            return JSONResponse(status_code=400, content={"detail": "Invalid request"})

        secret_pattern = _detect_secret(body_text, request.url.path)
        if secret_pattern:
            await log_security_event(
                action="security.secret_detected",
                request=request,
                details={"pattern": secret_pattern, "method": request.method},
            )
            return JSONResponse(status_code=400, content={"detail": "Sensitive values are not allowed in request body"})

        return await call_next(request)
    except Exception:
        logging.exception("Unhandled exception in security_middleware.check_security_threats")
        traceback.print_exc()
        return await call_next(request)
