"""SMTP outbound email sender with HTML templates, retry logic, and Message-ID tracking."""

from __future__ import annotations

import asyncio
import email.mime.multipart
import email.mime.text
import smtplib
import uuid
from datetime import datetime
from email.utils import formataddr, formatdate
from typing import Optional

from jinja2 import Environment, FileSystemLoader

from email_worker.config.settings import settings
from email_worker.models.email_models import EmailTemplateData
from email_worker.storage.message_store import message_store
from email_worker.utils.logger import logger
from email_worker.utils.retry import async_retry


class EmailSender:
    """Outbound email sender with template rendering and SMTP delivery."""

    def __init__(self) -> None:
        self._template_env = Environment(
            loader=FileSystemLoader(
                searchpath=settings.message_store_path.replace("data", "templates")
            ),
            autoescape=True,
        )
        # Fallback: try relative to this file
        import os
        template_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "templates"
        )
        if os.path.isdir(template_dir):
            self._template_env = Environment(
                loader=FileSystemLoader(searchpath=template_dir),
                autoescape=True,
            )

    def _generate_message_id(self, ticket_id: Optional[str] = None) -> str:
        """Generate a unique Message-ID for outbound emails.

        Args:
            ticket_id: Optional ticket ID to include in the Message-ID.

        Returns:
            A unique Message-ID string.
        """
        unique = uuid.uuid4().hex[:12]
        domain = settings.email_from_address.split("@")[-1]
        if ticket_id:
            return f"<{ticket_id}.{unique}@{domain}>"
        return f"<{unique}.{datetime.utcnow().timestamp()}@{domain}>"

    def _build_message(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_text_body: str,
        message_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> email.mime.multipart.MIMEMultipart:
        """Build a MIME multipart email message with HTML and plain text alternatives.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML version of the email body.
            plain_text_body: Plain text version of the email body.
            message_id: Optional pre-generated Message-ID. A new one is created if not provided.
            in_reply_to: Optional In-Reply-To header value for threading.

        Returns:
            A fully constructed MIMEMultipart message ready to send.
        """
        msg = email.mime.multipart.MIMEMultipart("alternative")
        msg["From"] = formataddr(
            (settings.email_from_name, settings.email_from_address)
        )
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)

        # Message-ID
        mid = message_id or self._generate_message_id()
        msg["Message-ID"] = mid

        # In-Reply-To (for threading)
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to

        # Attach plain text and HTML parts
        part_text = email.mime.text.MIMEText(plain_text_body, "plain", "utf-8")
        part_html = email.mime.text.MIMEText(html_body, "html", "utf-8")
        msg.attach(part_text)
        msg.attach(part_html)

        return msg, mid

    def _render_template(self, template_name: str, data: EmailTemplateData) -> str:
        """Render a Jinja2 email template with the given data.

        Args:
            template_name: Name of the template file (e.g. ack.html).
            data: Template variables.

        Returns:
            Rendered HTML string.
        """
        template = self._template_env.get_template(template_name)
        return template.render(**data.model_dump())

    @async_retry(max_attempts=3, base_delay=2.0, max_delay=15.0)
    async def _send_smtp(
        self, msg: email.mime.multipart.MIMEMultipart, to_email: str
    ) -> None:
        """Send an email via SMTP with retry logic.

        Args:
            msg: The MIME message to send.
            to_email: The recipient email address.

        Raises:
            smtplib.SMTPException: If sending fails after all retries.
        """
        loop = asyncio.get_event_loop()

        def _send() -> None:
            with smtplib.SMTP(
                host=settings.smtp_host,
                port=settings.smtp_port,
                timeout=30,
            ) as server:
                # Start TLS if not Mailhog (plain text) and port is not 1025
                if settings.smtp_port != 1025:
                    server.starttls()

                # Authenticate if credentials are provided
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)

                server.send_message(msg)
                logger.info(
                    "Email sent to %s: subject=%s",
                    to_email,
                    msg["Subject"],
                )

        await loop.run_in_executor(None, _send)

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_text_body: str,
        ticket_id: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> str:
        """Build and send an email, storing its Message-ID for thread tracking.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML version of the email body.
            plain_text_body: Plain text version.
            ticket_id: Associated ticket ID (for Message-ID generation and storage).
            in_reply_to: Optional In-Reply-To header for threading.

        Returns:
            The generated Message-ID of the sent email.
        """
        # Generate Message-ID
        message_id = self._generate_message_id(ticket_id)

        msg, mid = self._build_message(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            plain_text_body=plain_text_body,
            message_id=message_id,
            in_reply_to=in_reply_to,
        )

        await self._send_smtp(msg, to_email)

        # Persist Message-ID mapping for thread tracking
        if ticket_id:
            message_store.save_message_mapping(mid, ticket_id)

        return mid

    async def send_ack_email(
        self,
        to_email: str,
        ticket_id: str,
        subject: str,
        requester_name: str = "",
    ) -> str:
        """Send a ticket acknowledgment email.

        Args:
            to_email: Recipient email address.
            ticket_id: The ticket ID (e.g. SPS-2026-001).
            subject: Original ticket subject.
            requester_name: Name of the requester.

        Returns:
            The Message-ID of the sent email.
        """
        data = EmailTemplateData(
            ticket_id=ticket_id,
            subject=subject,
            requester_name=requester_name or to_email,
            requester_email=to_email,
            description=subject,
            portal_url=settings.portal_url,
        )

        email_subject = f"[{ticket_id}] Your request has been received"
        html_body = self._render_template("ack.html", data)
        plain_text_body = (
            f"Dear {data.requester_name},\n\n"
            f"Your request has been received and assigned ticket {ticket_id}.\n\n"
            f"Subject: {subject}\n\n"
            f"Track your ticket: {settings.portal_url}/tickets/{ticket_id}\n\n"
            f"Thank you,\n{settings.email_from_name}"
        )

        return await self.send_email(
            to_email=to_email,
            subject=email_subject,
            html_body=html_body,
            plain_text_body=plain_text_body,
            ticket_id=ticket_id,
        )

    async def send_agent_reply_email(
        self,
        to_email: str,
        ticket_id: str,
        original_subject: str,
        agent_name: str,
        reply_content: str,
        requester_name: str = "",
    ) -> str:
        """Send an agent reply notification email.

        Args:
            to_email: Recipient email address.
            ticket_id: The ticket ID.
            original_subject: The original ticket subject.
            agent_name: Name of the agent who replied.
            reply_content: The reply message content.
            requester_name: Name of the requester.

        Returns:
            The Message-ID of the sent email.
        """
        data = EmailTemplateData(
            ticket_id=ticket_id,
            subject=original_subject,
            requester_name=requester_name or to_email,
            requester_email=to_email,
            agent_name=agent_name,
            reply_content=reply_content,
            portal_url=settings.portal_url,
        )

        email_subject = f"[{ticket_id}] Re: {original_subject}"
        html_body = self._render_template("agent_reply.html", data)
        plain_text_body = (
            f"Dear {data.requester_name},\n\n"
            f"Agent {agent_name} has replied to your ticket.\n\n"
            f"---\n{reply_content}\n---\n\n"
            f"View the full conversation: {settings.portal_url}/tickets/{ticket_id}\n\n"
            f"Thank you,\n{settings.email_from_name}"
        )

        return await self.send_email(
            to_email=to_email,
            subject=email_subject,
            html_body=html_body,
            plain_text_body=plain_text_body,
            ticket_id=ticket_id,
        )

    async def send_status_change_email(
        self,
        to_email: str,
        ticket_id: str,
        subject: str,
        new_status: str,
        requester_name: str = "",
    ) -> str:
        """Send a ticket status change notification email.

        Args:
            to_email: Recipient email address.
            ticket_id: The ticket ID.
            subject: Original ticket subject.
            new_status: The new ticket status.
            requester_name: Name of the requester.

        Returns:
            The Message-ID of the sent email.
        """
        data = EmailTemplateData(
            ticket_id=ticket_id,
            subject=subject,
            requester_name=requester_name or to_email,
            requester_email=to_email,
            status=new_status,
            portal_url=settings.portal_url,
        )

        email_subject = f"[{ticket_id}] Status update: {new_status}"
        html_body = self._render_template("status_change.html", data)
        plain_text_body = (
            f"Dear {data.requester_name},\n\n"
            f"The status of your ticket has been updated.\n\n"
            f"Ticket: {ticket_id}\n"
            f"Subject: {subject}\n"
            f"Status: {new_status}\n\n"
            f"View your ticket: {settings.portal_url}/tickets/{ticket_id}\n\n"
            f"Thank you,\n{settings.email_from_name}"
        )

        return await self.send_email(
            to_email=to_email,
            subject=email_subject,
            html_body=html_body,
            plain_text_body=plain_text_body,
            ticket_id=ticket_id,
        )

    async def send_approval_request_email(
        self,
        to_email: str,
        ticket_id: str,
        subject: str,
        requester_name: str = "",
        approval_url: str = "",
    ) -> str:
        """Send an approval request email for high-risk actions.

        Args:
            to_email: Recipient email address (approver).
            ticket_id: The ticket ID requiring approval.
            subject: Original ticket subject.
            requester_name: Name of the requester.
            approval_url: URL for the approval action.

        Returns:
            The Message-ID of the sent email.
        """
        data = EmailTemplateData(
            ticket_id=ticket_id,
            subject=subject,
            requester_name=requester_name or to_email,
            requester_email=to_email,
            approval_url=approval_url or f"{settings.portal_url}/tickets/{ticket_id}/approve",
            portal_url=settings.portal_url,
        )

        email_subject = f"[ACTION REQUIRED] High-Risk Access Request — {ticket_id}"
        html_body = self._render_template("approval_request.html", data)
        plain_text_body = (
            f"ACTION REQUIRED\n\n"
            f"A high-risk access request requires your approval.\n\n"
            f"Ticket: {ticket_id}\n"
            f"Subject: {subject}\n"
            f"Requester: {requester_name}\n\n"
            f"Review and approve: {data.approval_url}\n\n"
            f"Thank you,\n{settings.email_from_name}"
        )

        return await self.send_email(
            to_email=to_email,
            subject=email_subject,
            html_body=html_body,
            plain_text_body=plain_text_body,
            ticket_id=ticket_id,
        )