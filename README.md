# SPS SecureDesk AI

**Multi-Channel IT Helpdesk Platform** — Users can create tickets via Email, Web Form, or AI Chat.

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
|----------|---------|-------------|
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
|---------|---------------|
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
|---------|-------------|
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
|---------|-------------|-----------|
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
|----------|----------|---------------------|
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
|------|----------|----------------|---------|
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
|------------|-------------|--------------|
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
|--------|-------------|
| `save_message_mapping(message_id, ticket_id)` | Persist a mapping |
| `lookup_message_id(message_id)` | Retrieve ticket ID by Message-ID (returns `None` if not found) |
| `delete_mapping(message_id)` | Remove a mapping |
| `count` | Return number of stored mappings |

#### Duplicate Prevention

The message store acts as a dedup layer — if the same Message-ID arrives again (e.g., due to IMAP re-fetch), the lookup returns the existing mapping and the email can be skipped. In-memory UID tracking (`_processed_uids` set) provides a second layer of dedup within the same session.

---

### 12. Resiliency & Error Handling

| Scenario | Handling |
|----------|----------|
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
|-----------|------------|
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

### 15. Quick Start Guide

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
pip install -r email_worker/requirements.txt

# 4. Configure environment
copy email_worker\.env.example email_worker\.env
# Edit email_worker/.env with your settings

# 5. Start Mailhog (dev SMTP server)
docker run -d -p 1025:1025 -p 8025:8025 --name mailhog mailhog/mailhog

# 6. Run tests
python -m pytest email_worker/tests/ -v

# 7. Start the email worker
cd email_worker
python main.py
```

#### Viewing Emails

Open [http://localhost:8025](http://localhost:8025) to view all sent emails in Mailhog's web interface.

#### Docker Deployment

```powershell
# Build the image
cd e:\sps-securedesk-ai
docker build -t sps-email-worker -f Dockerfile .

# Run the container
docker run --rm --env-file email_worker/.env sps-email-worker
```

---

### 16. Testing

**45 tests** across 5 test files:

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_parser.py` | 8 | MIME parsing, header decoding, empty/missing fields |
| `test_thread_resolver.py` | 10 | Subject tag regex, In-Reply-To lookup, priority ordering |
| `test_sender.py` | 6 | All 4 email types, Message-ID format, persistence mapping |
| `test_message_store.py` | 8 | CRUD, cross-instance persistence, corrupted file recovery |
| `test_soc_routing.py` | 8 | SOC rules, case insensitivity, non-matching categories, duplicate detection |

```powershell
# Run all tests
python -m pytest email_worker/tests/ -v

# Run specific test file
python -m pytest email_worker/tests/test_parser.py -v

# Run with coverage report
pip install pytest-cov
python -m pytest email_worker/tests/ --cov=email_worker
```

---

### 17. Development & Integration Notes

- The email worker is **completely independent** — it does not modify `backend/`, `frontend/`, or `ai/` code
- It communicates with the backend solely through HTTP endpoints defined in **Section 14**
- The worker must be running alongside the backend for full functionality
- Configure `BACKEND_API_URL` in `.env` to point to your running backend instance
- Approval emails link to the portal URL configured in `PORTAL_URL`

---

### 18. License

Proprietary — SPS SecureDesk AI. All rights reserved.