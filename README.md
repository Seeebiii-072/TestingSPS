# SPS SecureDesk AI

**Multi-Channel IT Helpdesk Platform** — Users can create tickets via Email, Web Form, or AI Chat.

SPS SecureDesk AI is an AI-assisted enterprise helpdesk platform for managing IT support requests from email, a web portal, and AI chat escalation in one unified ticket queue.

The project replaces a legacy osTicket-style workflow with a modern FastAPI backend, role-based access control, a single ticket lifecycle, approval gates for high-risk requests, SLA tracking, audit logs, and management reporting.

> Current status: Dev 1 backend/ticket engine is implemented. Email worker, AI service, and frontend portal are integration modules owned by separate teammates.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SPS SecureDesk AI                            │
├─────────────────┬─────────────────┬────────────────────────────────┤
│   Frontend      │   Backend API   │    Email Worker (email_worker/) │
│  (React/Vue)    │  (FastAPI/Django)│   ┌──────────────────────────┐ │
│  :5173          │  :8000          │   │  IMAP Poller             │ │
│                 │                 │   │  Event Listener          │ │
│                 │                 │   │  SMTP Sender             │ │
│                 │                 │   │  Thread Resolver         │ │
│                 │                 │   │  Message Store           │ │
│                 │                 │   └──────────────────────────┘ │
└─────────────────┴─────────────────┴────────────────────────────────┘
                         │                      │
                         ▼                      ▼
                   ┌──────────┐          ┌──────────┐
                   │   AI     │          │  Mailhog │
                   │Classifier│          │ / SMTP   │
                   │ :8000/ai │          │ :1025    │
                   └──────────┘          └──────────┘
```

### Intake Pipelines

```text
Email:
User email -> IMAP poller -> thread resolver -> POST /tickets or POST /tickets/{id}/events

Web form:
Portal form -> POST /tickets -> confirmation UI -> ticket appears in queue

AI chat:
Chat question -> KB search -> escalation decision -> POST /tickets with source=chat
```

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Docker Compose](#docker-compose)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Example Requests](#example-requests)
- [Integration Contracts](#integration-contracts)
- [Walkthrough Scenarios](#walkthrough-scenarios)
- [Development Workflow](#development-workflow)
- [Email Pipeline Reference](#email-pipeline-reference)
- [Security Notes](#security-notes)
- [Deployment Plan](#deployment-plan)
- [Team](#team)

---

## Features

- Unified ticket creation for `email`, `portal_form`, and `chat`
- Sequential ticket numbers in `SPS-YYYY-NNN` format
- JWT authentication with six user roles
- Role-based access control for requester, agent, security admin, manager, and admin workflows
- Ticket create, list, detail, update, timeline, attachment, approval, and report endpoints
- Identity access requests automatically marked high risk and blocked for approval
- SLA due date calculation by priority
- Immutable audit logging with channel field
- Security logging for injection attempts, secret leakage, brute force, forbidden role access, and oversized uploads
- File upload validation with size and MIME checks
- PostgreSQL-ready schema with Alembic migrations
- FastAPI `/docs` OpenAPI documentation
- Docker Compose support for local backend, PostgreSQL, and Mailhog

---

## Tech Stack

| Area | Technology |
| --- | --- |
| Backend API | FastAPI |
| Language | Python 3.11 |
| ORM | SQLAlchemy 2.x async |
| Database | PostgreSQL, SQLite for quick local development |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | JWT with `python-jose`, password hashing with `passlib[bcrypt]` |
| File Uploads | FastAPI multipart uploads |
| Local Email Testing | Mailhog |
| Server | Uvicorn |
| Container | Docker |

---

## Project Structure

```text
sps-securedesk-ai/
+-- backend/
|   +-- alembic/              # Database migrations
|   +-- middleware/           # Auth and security middleware
|   +-- models/               # SQLAlchemy models
|   +-- routes/               # FastAPI routers
|   +-- schemas/              # Pydantic schemas
|   +-- services/             # Business logic
|   +-- .env.example          # Backend environment template
|   +-- Dockerfile            # Backend container
|   +-- alembic.ini           # Alembic config
|   +-- database.py           # Async DB setup
|   +-- main.py               # FastAPI app entry
|   +-- requirements.txt      # Python dependencies
+-- email_worker/             # Email pipeline service (Dev 2)
+-- ai/                       # AI service (Dev 3)
+-- docker-compose.yml        # Local DB, Mailhog, backend, email worker, and AI service
+-- README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Git
- PostgreSQL for production-like local testing
- Docker Desktop for Compose-based setup

### Clone

```bash
git clone https://github.com/YOUR_USERNAME/sps-securedesk-ai.git
cd sps-securedesk-ai
```

### Local Python Setup

PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Bash:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

For fast SQLite development, set these values in `backend/.env`:

```env
DATABASE_URL=sqlite+aiosqlite:///./securedesk.db
DATABASE_URL_SYNC=sqlite:///./securedesk.db
SECRET_KEY=replace-with-a-local-development-secret
ENVIRONMENT=development
```

Run the API:

```bash
uvicorn main:app --reload
```

Useful URLs:

- API docs: `http://127.0.0.1:8000/docs`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`
- Health check: `http://127.0.0.1:8000/health`

Expected health response:

```json
{
  "status": "ok",
  "service": "SPS SecureDesk AI"
}
```

---

## Docker Compose

From the repository root:

```bash
docker compose up --build
```

Local service URLs:

- Backend: `http://127.0.0.1:8000`
- Backend docs: `http://127.0.0.1:8000/docs`
- Mailhog UI: `http://127.0.0.1:8025`
- PostgreSQL: `localhost:5432`
- AI service: `http://127.0.0.1:8001`

A plain `docker compose up` starts the full local stack: PostgreSQL, Mailhog, backend, email worker, and AI service. The email worker logs and waits when IMAP credentials are not configured, while the AI service starts without provider keys and only requires an LLM key for endpoints that call a provider.

---

## Environment Variables

Backend variables are documented in `backend/.env.example`.

| Variable | Required | Description |
| --- | --- | --- |
| `DATABASE_URL` | Yes | Async database URL used by FastAPI |
| `DATABASE_URL_SYNC` | Yes for Alembic | Sync database URL used by migrations |
| `SECRET_KEY` | Yes | JWT signing secret |
| `ALGORITHM` | No | JWT algorithm, defaults to `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | JWT token lifetime |
| `UPLOAD_DIR` | No | Attachment storage path |
| `MAX_UPLOAD_SIZE_MB` | No | File upload limit, defaults to `10` |
| `ENVIRONMENT` | No | Use `development` locally and `production` in deployment |
| `SEED_DEFAULT_USERS` | No | Set to `true` only for local/dev demo accounts; leave unset or `false` in production |
| `INTERNAL_API_KEY` | Yes for email worker | Shared secret required for internal backend/email-worker endpoints |
| `CORS_ORIGINS` | No | Comma-separated allowed frontend origins |
| `SMTP_HOST` | Dev 2 | Outbound email host, Mailhog locally |
| `SMTP_PORT` | Dev 2 | Outbound email port |
| `IMAP_HOST` | Dev 2 | Inbound email host |
| `IMAP_USER` | Dev 2 | Inbound mailbox username |
| `IMAP_PASSWORD` | Dev 2 | Inbound mailbox password |
| `ANTHROPIC_API_KEY` | Dev 3 | AI service API key |
| `BACKEND_URL` | Dev 2/3 | Internal backend URL for service-to-service calls |

Never commit real `.env` files, database passwords, API keys, or production secrets.

---

## API Overview

### Public / Auth

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Backend health check |
| `POST` | `/auth/register` | Create a user account |
| `POST` | `/auth/login` | Login and receive a JWT token |
| `POST` | `/tickets` | Create a ticket from email, form, or chat |

### Ticket Operations

| Method | Endpoint | Description | Auth |
| --- | --- | --- | --- |
| `GET` | `/tickets` | List tickets visible to current user | Required |
| `GET` | `/tickets/{ticket_id}` | Get ticket detail with timeline and attachments | Required |
| `PATCH` | `/tickets/{ticket_id}` | Update status, category, priority, team, assignment, summary | Agent+ |
| `POST` | `/tickets/{ticket_id}/events` | Add timeline event | Auth optional for `email`/`chat`, otherwise required |
| `POST` | `/tickets/{ticket_id}/attachments` | Upload attachment | Auth optional |
| `POST` | `/tickets/{ticket_id}/approve` | Approve or reject high-risk ticket | Security Admin / Manager / Admin |
| `GET` | `/reports/summary` | Management report data | Manager / Admin |

### Planned AI Service Contract

The Dev 3 AI service owns this endpoint and the backend can integrate with it later:

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/ai/classify` | Suggest category, priority, risk, and team |

---

## Example Requests

### Register an Agent

```bash
curl -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent@example.com",
    "full_name": "SPS Agent",
    "password": "StrongPassword123",
    "role": "agent"
  }'
```

### Login

```bash
curl -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "agent@example.com",
    "password": "StrongPassword123"
  }'
```

### Create a Portal Ticket

```bash
curl -X POST http://127.0.0.1:8000/tickets \
  -H "Content-Type: application/json" \
  -d '{
    "source": "portal_form",
    "subject": "Cannot access VPN",
    "description": "VPN login fails after password reset.",
    "category": "identity_access",
    "priority": "medium",
    "requester_email": "requester@example.com"
  }'
```

### Add an Email Timeline Event

```bash
curl -X POST http://127.0.0.1:8000/tickets/TICKET_UUID/events \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "email_received",
    "content": "Requester replied with logs.",
    "is_public": true,
    "channel": "email"
  }'
```

---

## Integration Contracts

All intake channels must create tickets through one backend endpoint:

```text
POST /tickets
```

| Developer | Module | Required `source` |
| --- | --- | --- |
| Dev 2 | Email pipeline | `email` |
| Dev 3 | AI chat escalation | `chat` |
| Dev 4 | Submit request form | `portal_form` |

Allowed ticket enums:

| Field | Values |
| --- | --- |
| `source` | `email`, `portal_form`, `chat` |
| `category` | `cloud`, `cybersecurity`, `identity_access`, `devops`, `internship_hr`, `general_it` |
| `priority` | `low`, `medium`, `high`, `critical` |
| `risk_level` | `standard`, `high` |
| `team` | `it`, `security`, `devops`, `hr`, `management` |
| `status` | `open`, `in_progress`, `waiting_approval`, `waiting_user`, `resolved`, `closed` |

Important workflow rules:

- `identity_access` tickets are automatically marked `risk_level=high`.
- High-risk tickets start as `status=waiting_approval`.
- Approved high-risk tickets move to `in_progress`.
- Rejected high-risk tickets move to `closed`.
- `cybersecurity` + `critical` tickets route to the `security` team.
- Timeline events are append-only.
- Audit logs record ticket actions and security events.

---

## Walkthrough Scenarios

Before final submission, the team should verify these scenarios end to end:

| # | Scenario | Reviewer Check |
| --- | --- | --- |
| 1 | Email laptop issue | Email creates `source=email` ticket, ack sent, email replies appear on same timeline, resolved notification sent |
| 2 | Web form VM down | Portal form creates `source=portal_form` ticket, file upload works, ticket appears in agent queue |
| 3 | AI chat VPN/admin access | Chat answers from KB, escalates admin access, creates `source=chat` ticket waiting for approval |
| 4 | Mixed channel | Email ticket later receives portal reply and upload on the same ticket ID |
| 5 | Security email | Phishing email becomes `category=cybersecurity`, `priority=critical`, `team=security` |
| 6 | Manager report | Manager sees high-risk and SLA metrics matching database tickets |

---

## Development Workflow

Recommended branch structure:

```text
main                         # Stable final branch
dev                          # Integration branch
feature/ticket-engine        # Dev 1 backend work
feature/email-pipeline       # Dev 2 email work
feature/ai-chat              # Dev 3 AI work
feature/frontend-portal      # Dev 4 frontend work
```

Daily Dev 1 workflow:

```bash
git checkout feature/ticket-engine
git pull origin dev
```

Before opening a pull request:

```bash
python -m compileall -q backend
git status
```

Pull requests should target `dev`, not `main`.

---

## SPS SecureDesk AI Email Pipeline — Complete Flow & Working Mechanism

### 1. Purpose

The Email Pipeline is a standalone background service responsible for:

- **Receiving** inbound emails via IMAP
- **Creating tickets** from new email inquiries
- **Detecting replies** and appending them to existing tickets
- **Sending outbound notifications** (acknowledgments, agent replies, status changes, approval requests)
- **Tracking email threads** via Message-ID headers for proper conversation threading

It runs as an independent Python async service inside `email_worker/` and communicates with the backend API via HTTP — it never touches the frontend or database directly.

---

### 2. Directory Structure

```
email_worker/
├── main.py                          # Entry point — runs IMAP poller + event listener concurrently
├── requirements.txt                 # Python dependencies
├── .env / .env.example              # Environment configuration
├── config/
│   └── settings.py                  # Dataclass-based config loaded from environment variables
├── models/
│   ├── email_models.py              # Pydantic models: ParsedEmail, OutboundEmail, EmailTemplateData
│   └── event_models.py              # Pydantic models: BackendEvent, TicketCreatePayload, ClassifyResponse
├── api_client/
│   └── ticket_client.py             # Async HTTP client for backend API (httpx with retry)
├── storage/
│   └── message_store.py             # JSON-persisted Message-ID → ticket ID mapping (survives restarts)
├── thread/
│   └── resolver.py                  # Thread resolution: subject tag regex + In-Reply-To lookup
├── imap/
│   ├── parser.py                    # Raw MIME email → structured ParsedEmail model
│   └── poller.py                    # Async IMAP mailbox polling with auto-reconnect
├── smtp/
│   └── sender.py                    # Outbound email sender with Jinja2 templates & Message-ID tracking
├── templates/
│   ├── ack.html                     # Ticket acknowledgment (SPS blue branding)
│   ├── agent_reply.html             # Agent reply notification to requester
│   ├── status_change.html           # Ticket status update notification
│   └── approval_request.html        # High-risk access approval request (red alert header)
├── notifications/
│   └── event_listener.py            # Backend event poller → email dispatch
├── utils/
│   ├── logger.py                    # Structured logging (timestamped, leveled)
│   └── retry.py                     # Async retry decorator with exponential backoff
└── tests/
    ├── test_parser.py               # 8 tests — email parsing, MIME, edge cases
    ├── test_thread_resolver.py      # 10 tests — tag extraction, thread resolution, SOC routing
    ├── test_sender.py               # 6 tests — all 4 email types, Message-ID format, persistence
    ├── test_message_store.py        # 8 tests — CRUD, persistence, file corruption recovery
    └── test_soc_routing.py          # 8 tests — SOC routing rules, duplicate detection
```

---

### 3. Configuration

All configuration is driven by environment variables loaded from `email_worker/.env`:

| Variable | Default | Description |
| --- | --- | --- |
| `IMAP_HOST` | — | IMAP server hostname for inbound email |
| `IMAP_PORT` | `993` | IMAP server port (SSL) |
| `IMAP_USER` | — | IMAP login username |
| `IMAP_PASSWORD` | — | IMAP login password |
| `IMAP_POLL_INTERVAL_SECONDS` | `30` | How often to poll the mailbox |
| `SMTP_HOST` | `localhost` | SMTP server hostname |
| `SMTP_PORT` | `1025` | SMTP server port (1025 = Mailhog default) |
| `SMTP_USER` | — | SMTP login username (empty for Mailhog) |
| `SMTP_PASSWORD` | — | SMTP login password (empty for Mailhog) |
| `EMAIL_FROM_ADDRESS` | `helpdesk@sps.com` | Sender email address |
| `EMAIL_FROM_NAME` | `SPS Helpdesk` | Sender display name |
| `BACKEND_API_URL` | `http://localhost:8000` | Backend API base URL |
| `PORTAL_URL` | `http://localhost:5173` | Frontend portal URL (used in email links) |

The settings are loaded via `python-dotenv` and exposed as a frozen dataclass singleton through `config/settings.py`.

---

### 4. Inbound Email Processing (IMAP Pipeline)

#### 4.1 Polling Cycle

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Connect to  │────▶│ Search for   │────▶│ Fetch raw   │
│ IMAP server │     │ UNSEEN emails│     │ email by UID│
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│ Mark as     │◀────│ Process &    │◀────│ Parse MIME  │
│ SEEN (\\Seen)│     │ Route email  │     │ → ParsedEmail│
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
                           ▼
              ┌──────────────────────┐
              │  Thread Resolution   │
              │  (resolver.py)        │
              └──────────┬───────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
      ┌──────────────┐     ┌──────────────────┐
      │  New Ticket  │     │  Reply to Ticket │
      │  (type: new) │     │  (type: reply)   │
      └──────┬───────┘     └────────┬─────────┘
             │                      │
             ▼                      ▼
      ┌──────────────┐     ┌──────────────────┐
      │  AI Classify │     │ POST /tickets/   │
      │  → category, │     │ {id}/events      │
      │    priority, │     │ (email_reply)    │
      │    team      │     └──────────────────┘
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │  SOC Route?  │
      │ cybersecurity│
      │ + critical?  │
      │ → team=security │
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ POST /tickets│
      │ Create ticket│
      └──────┬───────┘
             │
             ▼
      ┌──────────────┐
      │ Send ACK     │
      │ Email        │
      └──────────────┘
```

#### 4.2 IMAP Connection Management

The `IMAPPoller` in `imap/poller.py` implements:

- **Auto-reconnect** — Checks connection health via `NOOP` before each poll cycle. Reconnects automatically if the connection is lost.
- **Port detection** — Uses `IMAP4_SSL` on port 993, `IMAP4` on non-SSL ports.
- **Error resilience** — Catches `ConnectionRefusedError`, `TimeoutError`, `OSError`, `EOFError`, and `AioimapException`. Resets the client to force a fresh connection on next cycle.
- **In-memory dedup** — Tracks processed UIDs in a `Set[str]` to prevent duplicate processing within a session.

#### 4.3 Email Parsing

The `parse_email()` function in `imap/parser.py` converts raw MIME bytes into a structured `ParsedEmail` model. It handles:

| Feature | Implementation |
| --- | --- |
| **Plain text body** | Extracted from `text/plain` MIME parts |
| **HTML body** | Extracted from `text/html` MIME parts |
| **Attachments** | Parsed from parts with `Content-Disposition: attachment` |
| **Message-ID** | Decoded via `email.header.decode_header()` |
| **In-Reply-To** | Captured for thread resolution |
| **From address** | Cleaned from `"Name <email>"` format to just `email` |
| **Subject** | MIME-decoded (handles `=?utf-8?B?...?=` encoding) |
| **Missing From** | Returns `None` — email is skipped |
| **Empty body** | Returns empty string, not an error |

---

### 5. Thread Resolution (Critical Logic)

The `resolve_thread()` function in `thread/resolver.py` determines whether an incoming email is a new ticket request or a reply to an existing ticket. It uses two methods in priority order:

#### Method 1: Subject Tag Detection (Highest Priority)

Detects ticket tags in the subject line using the regex:

```
r"\[SPS-(\d{4})-(\d{3,})\]"
```

**Examples:**

| Subject | Detected As |
| --- | --- |
| `[SPS-2026-001] VPN Issue` | Reply to SPS-2026-001 |
| `Re: [SPS-2026-025] Password Reset` | Reply to SPS-2026-025 |
| `General Inquiry` | No match → proceed to Method 2 |
| `Issue with [brackets] in text` | No match (no SPS-YYYY-NNN format) |

#### Method 2: In-Reply-To Header Lookup

If no subject tag is found, checks the `In-Reply-To` header against the `MessageStore`. The lookup tries three variations to handle client inconsistencies:

1. Exact value as received
2. Stripped of angle brackets (`< >`)
3. With angle brackets added back

#### Result

| Outcome | Thread Type | Ticket ID |
| --- | --- | --- |
| Subject tag found | `"reply"` | `"SPS-2026-001"` |
| In-Reply-To matches stored mapping | `"reply"` | Resolved ticket ID |
| Neither matches | `"new"` | `None` |

---

### 6. New Email Processing Flow

When `thread_type == "new"`, the pipeline executes 4 steps:

#### Step 1: AI Classification

Calls `POST /ai/classify` with:
```json
{
    "subject": "I cannot connect to VPN",
    "description": "Getting error 800 when connecting..."
}
```

Returns:
```json
{
    "category": "networking",
    "priority": "high",
    "team": "network-team"
}
```

#### Step 2: SOC Routing Rule

If `category == "cybersecurity"` AND `priority == "critical"`, the team is overridden to `"security"` regardless of the AI's classification. This ensures high-priority security incidents are automatically routed to the security team.

| Category | Priority | Team After SOC Rule |
| --- | --- | --- |
| cybersecurity | critical | `security` (override) |
| cybersecurity | high | (AI result, no override) |
| networking | critical | (AI result, no override) |
| hardware | low | (AI result, no override) |

#### Step 3: Ticket Creation

Calls `POST /tickets` with:
```json
{
    "source": "email",
    "subject": "I cannot connect to VPN",
    "description": "Getting error 800...",
    "requester_email": "user@example.com",
    "category": "networking",
    "priority": "high",
    "team": "network-team"
}
```

The original email's `Message-ID` is stored in the `MessageStore` mapped to the new ticket ID, enabling future replies to be threaded.

#### Step 4: Acknowledgment Email

Sends an automated acknowledgment to the requester via SMTP with:
- Subject: `[SPS-2026-001] Your request has been received`
- Ticket summary (ID, subject)
- Link to view the ticket on the portal
- Professional SPS blue branding

---

### 7. Reply Email Processing Flow

When `thread_type == "reply"` and a ticket ID is resolved, the pipeline:

1. **Does NOT create a new ticket**
2. Calls `POST /tickets/{id}/events` with:
   ```json
   {
       "event_type": "email_reply",
       "content": "The reply body text..."
   }
   ```
3. Stores the reply's `Message-ID` in the `MessageStore` for future thread tracking

This ensures the conversation remains in a single ticket thread.

---

### 8. Outbound Email Types

All four email types use Jinja2 templates with responsive HTML and plain text fallback.

| Type | Template | Subject Format | Trigger |
| --- | --- | --- | --- |
| **Acknowledgment** | `ack.html` | `[SPS-2026-001] Your request has been received` | New ticket created from email or backend event |
| **Agent Reply** | `agent_reply.html` | `[SPS-2026-001] Re: Original Subject` | Agent replies via the backend |
| **Status Change** | `status_change.html` | `[SPS-2026-001] Status update: Resolved` | Ticket status changes |
| **Approval Request** | `approval_request.html` | `[ACTION REQUIRED] High-Risk Access Request — SPS-2026-001` | High-risk action requires approval |

Each email includes:
- SPS blue header (#0055a5)
- Professional, responsive layout (works on mobile)
- Ticket summary section with ID, subject, and status
- Clear call-to-action button
- Footer with copyright and automated message notice
- Approval requests use a red header (#c0392b) for urgency

---

### 9. SMTP Sending

The `EmailSender` in `smtp/sender.py` handles all outbound email delivery:

#### Message Construction

- Builds `MIMEMultipart("alternative")` messages with both `text/plain` and `text/html` parts
- Sets proper headers: `From`, `To`, `Subject`, `Date`, `Message-ID`, `In-Reply-To`
- Generates unique Message-IDs in format: `<{ticket_id}.{uuid}@{domain}>`

#### Delivery

- Uses Python's `smtplib.SMTP` inside `run_in_executor` to avoid blocking the async event loop
- **Mailhog detection** — When `SMTP_HOST=localhost` and `SMTP_PORT=1025` with no auth, uses plain SMTP (no STARTTLS)
- **Production mode** — When credentials are provided, uses STARTTLS and authentication
- **Timeout** — 30-second SMTP connection timeout
- **Retry** — 3 attempts with exponential backoff (2s, 4s, 8s)

#### Message-ID Tracking

Every outbound email's Message-ID is stored in the `MessageStore` mapped to its ticket ID. This enables:
- The recipient's reply (which includes `In-Reply-To: <our-message-id>`) to be correctly threaded back to the original ticket
- Thread continuity across the entire conversation

---

### 10. Backend Event Listener

The `EventListener` in `notifications/event_listener.py` polls the backend API for email events and sends appropriate notifications.

#### Event Types Handled

| Event Type | API Endpoint | Action Taken |
| --- | --- | --- |
| `ticket_created` | `GET /events/email` | Sends acknowledgment email to requester |
| `agent_reply` | `GET /events/email` | Sends agent reply notification + logs `agent_reply_email` event to timeline |
| `status_changed` | `GET /events/email` | Sends status change notification |
| `approval_required` | `GET /events/email` | Sends approval request to approver |

#### Polling Behavior

- Polls every 10 seconds
- Tracks `last_event_id` cursor to avoid reprocessing
- Maintains a `Set[str]` of processed event IDs for dedup
- Gracefully handles network failures with retry and logging

---

### 11. Message-ID Tracking (MessageStore)

The `MessageStore` in `storage/message_store.py` provides persistent storage for Message-ID → ticket ID mappings.

#### Storage Mechanism

- **File format:** JSON file at `{data_dir}/message_store.json`
- **Persistence:** Survives service restarts
- **Thread safety:** Uses `threading.Lock` for concurrent access
- **Resilience:** Handles corrupted JSON gracefully — logs the error and starts with an empty store

#### API

| Method | Description |
| --- | --- |
| `save_message_mapping(message_id, ticket_id)` | Persist a mapping |
| `lookup_message_id(message_id)` | Retrieve ticket ID by Message-ID (returns `None` if not found) |
| `delete_mapping(message_id)` | Remove a mapping |
| `count` | Return number of stored mappings |

#### Duplicate Prevention

The message store acts as a dedup layer — if the same Message-ID arrives again (e.g., due to IMAP re-fetch), the lookup returns the existing mapping and the email can be skipped. In-memory UID tracking (`_processed_uids` set) provides a second layer of dedup within the same session.

---

### 12. Resiliency & Error Handling

| Scenario | Handling |
| --- | --- |
| **IMAP disconnect** | Auto-detected via `NOOP`, reconnects with full login cycle |
| **SMTP failure** | 3 retries with exponential backoff (2s, 4s, 8s) |
| **Backend API down** | 3 retries per request, logs warning, continues polling |
| **Invalid MIME email** | Catches parse exceptions, marks email as seen, moves on |
| **Missing sender** | Returns `None` from parser, email is skipped |
| **Empty body** | Uses empty string, not an error |
| **Corrupted message store JSON** | Logs error, starts with empty store |
| **Duplicate email (same UID)** | In-memory `Set[str]` prevents reprocessing within session |
| **Duplicate email (same Message-ID)** | MessageStore returns existing mapping, handled gracefully |
| **Invalid ticket IDs** | HTTP 4xx from backend is caught and logged |

All errors are logged with structured logging including timestamps, log levels, module names, and stack traces for debugging.

---

### 13. Tech Stack

| Component | Technology |
| --- | --- |
| **Language** | Python 3.11+ |
| **Async runtime** | `asyncio` |
| **IMAP client** | `aioimaplib` (async) |
| **HTTP client** | `httpx` (async) |
| **Email templates** | `jinja2` |
| **Data validation** | `pydantic` v2 |
| **SMTP** | `smtplib` (standard library) |
| **Email parsing** | `email` (standard library) |
| **Configuration** | `python-dotenv` |
| **Testing** | `pytest` + `pytest-asyncio` |
| **Containerization** | Docker (`python:3.11-slim`) |

---

### 14. API Contracts

#### Ticket Creation

```
POST /tickets
Content-Type: application/json

{
    "source": "email",
    "subject": "VPN Connection Issue",
    "description": "Cannot connect...",
    "requester_email": "user@example.com",
    "category": "networking",
    "priority": "high",
    "team": "network-team"
}
```

#### Append Timeline Event

```
POST /tickets/{id}/events
Content-Type: application/json

{
    "event_type": "email_reply",
    "content": "Still having issues with the connection."
}
```

#### AI Classification

```
POST /ai/classify
Content-Type: application/json

{
    "subject": "VPN Connection Issue",
    "description": "Cannot connect..."
}

Response 200:
{
    "category": "networking",
    "priority": "high",
    "team": "network-team"
}
```

#### Email Events Feed

```
GET /events/email
Response 200:
[
    {
        "id": "evt_001",
        "event_type": "agent_reply",
        "ticket_id": "SPS-2026-001",
        "data": {
            "requester_email": "user@example.com",
            "subject": "VPN Issue",
            "agent_name": "Agent Smith",
            "content": "We have reset your VPN credentials."
        },
        "occurred_at": "2026-06-15T10:30:00Z"
    }
]
```

Supported event types: `ticket_created`, `agent_reply`, `status_changed`, `approval_required`

---

### 15. Email Worker Quick Start

#### Prerequisites
- Python 3.11+
- Docker (for Mailhog)
- Backend API running on port 8000

#### Setup

```powershell
# 1. Clone the repository
git clone https://github.com/Osamaktk/sps-securedesk-ai.git
cd sps-securedesk-ai

# 2. Create Python virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r email_worker/requirements.txt -r email_worker/requirements-dev.txt

# 4. Configure environment
Copy-Item email_worker\.env.example email_worker\.env
# Edit email_worker/.env with your IMAP/SMTP settings

# 5. Run the worker
python -m email_worker.main
```

---

## Security Notes

- All JWT secrets must be rotated in production
- Never expose `.env` files or real API keys in version control
- Use HTTPS in production
- Restrict CORS to known origins
- Validate and sanitize all file uploads
- Rate-limit auth endpoints in production

---

## Deployment Plan

1. Merge all feature branches into `dev`
2. Run full integration test suite
3. Tag release candidate
4. Deploy backend + database to staging
5. Run smoke tests
6. Merge `dev` → `main`
7. Deploy to production

---

## Team

| Developer | Module |
| --- | --- |
| Dev 1 | Backend API, ticket engine, auth, database |
| Dev 2 | Email pipeline worker (IMAP → tickets) |
| Dev 3 | AI chat escalation service |
| Dev 4 | Frontend portal |
