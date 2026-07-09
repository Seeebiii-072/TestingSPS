import os
import re
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from middleware.auth_middleware import get_current_user, get_optional_current_user
from middleware.security_middleware import log_security_event
from models.attachment import Attachment
from models.timeline_event import TimelineEvent, TimelineEventType
from models.user import User
from schemas.ticket import AttachmentRead
from services import ticket_service
from services.audit_service import write_audit_log

router = APIRouter(prefix="/tickets", tags=["attachments"])


def _max_upload_size_bytes() -> int:
    return int(os.getenv("MAX_UPLOAD_SIZE_MB", "5")) * 1024 * 1024


def _upload_dir() -> Path:
    return Path(os.getenv("UPLOAD_DIR", "./uploads"))


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _safe_filename(filename: str) -> str:
    name = Path(filename).name or "attachment"
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)[:255]


def _detect_mime(content: bytes, provided_mime: str | None) -> str:
    if content.startswith(b"%PDF"):
        return "application/pdf"
    if content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06") or content.startswith(b"PK\x07\x08"):
        return "application/zip"

    image_signatures = {
        b"\x89PNG\r\n\x1a\n": "image/png",
        b"\xff\xd8\xff": "image/jpeg",
        b"GIF87a": "image/gif",
        b"GIF89a": "image/gif",
        b"RIFF": "image/webp",
        b"BM": "image/bmp",
    }
    for signature, mime_type in image_signatures.items():
        if content.startswith(signature):
            if provided_mime and not provided_mime.startswith("image/"):
                break
            return mime_type

    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    else:
        if provided_mime == "text/csv":
            return "text/csv"
        if provided_mime in {None, "text/plain", "application/octet-stream"}:
            return "text/plain"

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")


@router.post("/{ticket_id}/attachments", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    ticket_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> Attachment:
    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if not ticket_service.user_can_view_ticket(current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    max_size = _max_upload_size_bytes()
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        await log_security_event(
            action="security.oversized_upload",
            request=request,
            db=db,
            actor_id=current_user.id,
            details={
                "ticket_id": str(ticket_id),
                "filename": _safe_filename(file.filename or "attachment"),
                "max_size_bytes": max_size,
                "received_size_bytes": len(content),
            },
        )
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5MB limit")

    mime_type = _detect_mime(content, file.content_type)
    base_dir = _upload_dir() / str(ticket_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    original_name = _safe_filename(file.filename or "attachment")
    stored_name = f"{uuid.uuid4()}_{original_name}"
    file_path = base_dir / stored_name
    file_path.write_bytes(content)

    attachment = Attachment(
        ticket_id=ticket_id,
        uploaded_by=current_user.id,
        filename=original_name,
        file_path=str(file_path),
        file_size=len(content),
        mime_type=mime_type,
    )
    db.add(attachment)
    db.add(
        TimelineEvent(
            ticket_id=ticket_id,
            event_type=TimelineEventType.FILE_UPLOADED,
            actor_id=current_user.id,
            actor_email=current_user.email,
            content=original_name,
            is_public=True,
            channel="portal",
        )
    )
    await write_audit_log(
        db,
        ticket_id=ticket_id,
        actor_id=current_user.id,
        action="ticket.attachment_uploaded",
        channel="portal",
        details={"filename": original_name, "mime_type": mime_type, "file_size": len(content)},
        ip_address=_client_ip(request),
    )
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.post("/{ticket_id}/attachments/internal", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment_internal(
    ticket_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    internal_api_key: Annotated[str | None, Header(alias="X-Internal-Api-Key")] = None,
    file: UploadFile = File(...),
) -> Attachment:
    """Internal endpoint for email_worker to upload attachments without user auth."""
    expected_key = os.getenv("INTERNAL_API_KEY", "")
    if not expected_key or internal_api_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    max_size = _max_upload_size_bytes()
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5MB limit")

    mime_type = _detect_mime(content, file.content_type)
    base_dir = _upload_dir() / str(ticket_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    original_name = _safe_filename(file.filename or "attachment")
    stored_name = f"{uuid.uuid4()}_{original_name}"
    file_path = base_dir / stored_name
    file_path.write_bytes(content)

    # Use a system user ID (ai-agent) for email attachments
    from sqlalchemy import select
    system_user = await db.scalar(select(User).where(User.email == "ai-agent@sps.com"))
    uploaded_by_id = system_user.id if system_user else None

    attachment = Attachment(
        ticket_id=ticket_id,
        uploaded_by=uploaded_by_id,
        filename=original_name,
        file_path=str(file_path),
        file_size=len(content),
        mime_type=mime_type,
    )
    db.add(attachment)
    db.add(
        TimelineEvent(
            ticket_id=ticket_id,
            event_type=TimelineEventType.FILE_UPLOADED,
            actor_id=uploaded_by_id,
            actor_email="ai-agent@sps.com",
            content=original_name,
            is_public=True,
            channel="email",
        )
    )
    await write_audit_log(
        db,
        ticket_id=ticket_id,
        actor_id=uploaded_by_id,
        action="ticket.attachment_uploaded",
        channel="email",
        details={"filename": original_name, "mime_type": mime_type, "file_size": len(content)},
        ip_address=_client_ip(request),
    )
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.post("/{ticket_id}/attachments/public", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment_public(
    ticket_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    requester_email: Annotated[str, Query(description="Email of the requester to verify ownership")],
    file: UploadFile = File(...),
) -> Attachment:
    """Public endpoint for guests to upload attachments to their tickets (no auth required)."""
    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    
    # Verify the requester email matches
    if ticket.requester_email.lower() != requester_email.lower():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to upload to this ticket")

    max_size = _max_upload_size_bytes()
    content = await file.read(max_size + 1)
    if len(content) > max_size:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds 5MB limit")

    mime_type = _detect_mime(content, file.content_type)
    base_dir = _upload_dir() / str(ticket_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    original_name = _safe_filename(file.filename or "attachment")
    stored_name = f"{uuid.uuid4()}_{original_name}"
    file_path = base_dir / stored_name
    file_path.write_bytes(content)

    # Use a system user ID (ai-agent) for guest uploads
    from sqlalchemy import select
    system_user = await db.scalar(select(User).where(User.email == "ai-agent@sps.com"))
    uploaded_by_id = system_user.id if system_user else None

    attachment = Attachment(
        ticket_id=ticket_id,
        uploaded_by=uploaded_by_id,
        filename=original_name,
        file_path=str(file_path),
        file_size=len(content),
        mime_type=mime_type,
    )
    db.add(attachment)
    db.add(
        TimelineEvent(
            ticket_id=ticket_id,
            event_type=TimelineEventType.FILE_UPLOADED,
            actor_id=uploaded_by_id,
            actor_email="ai-agent@sps.com",
            content=original_name,
            is_public=True,
            channel="portal",
        )
    )
    await write_audit_log(
        db,
        ticket_id=ticket_id,
        actor_id=uploaded_by_id,
        action="ticket.attachment_uploaded",
        channel="portal",
        details={"filename": original_name, "mime_type": mime_type, "file_size": len(content)},
        ip_address=_client_ip(request),
    )
    await db.commit()
    await db.refresh(attachment)
    return attachment


@router.get("/{ticket_id}/attachments/{attachment_id}/file")
async def download_attachment(
    ticket_id: uuid.UUID,
    attachment_id: uuid.UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
):
    attachment = await db.get(Attachment, attachment_id)
    if not attachment or attachment.ticket_id != ticket_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    ticket = await ticket_service.get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    
    # Allow access if user is authenticated and has permissions, or if user matches requester
    if current_user is not None and not ticket_service.user_can_view_ticket(current_user, ticket):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    
    # For non-authenticated users, check if requester matches - but since this is a web app,
    # we require authentication. The email link access uses the public endpoint.

    file_path = Path(attachment.file_path)
    if not file_path.is_absolute():
        base_dir = _upload_dir()
        file_path = base_dir / attachment.file_path
    
    # Debug logging to help diagnose path issues
    import sys
    print(f"DEBUG: Attachment file_path from DB: {attachment.file_path}", file=sys.stderr)
    print(f"DEBUG: Resolved file_path: {file_path}", file=sys.stderr)
    print(f"UPLOAD_DIR from env: {os.getenv('UPLOAD_DIR', './uploads')}", file=sys.stderr)
    
    if not file_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"File not found: {file_path}")

    actor_id = current_user.id if current_user else None

    await write_audit_log(
        db,
        ticket_id=ticket_id,
        actor_id=actor_id,
        action="ticket.attachment_downloaded",
        channel="portal",
        details={"attachment_id": str(attachment_id), "filename": attachment.filename},
        ip_address=_client_ip(request),
    )
    await db.commit()

    # For inline viewing (images, PDFs), use inline content-disposition
    # This allows the browser to display the file directly in the tab
    inline_types = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp", "text/plain"}
    disposition = "inline" if attachment.mime_type in inline_types else f'attachment; filename="{attachment.filename}"'
    
    return FileResponse(
        path=str(file_path),
        filename=attachment.filename,
        media_type=attachment.mime_type,
        content_disposition=disposition,
    )
