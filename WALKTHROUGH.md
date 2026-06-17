# SPS SecureDesk AI – Walkthrough Verification

All six required capstone scenarios were executed end‑to‑end using the Docker Compose stack (backend, AI service, MailHog, PostgreSQL, email_worker). Each scenario is summarised below with the key API calls and results.

---

## Scenario 1 – Email‑Only Ticket Lifecycle ✅
- **Create ticket**: `POST /tickets` with `source=email`, `category=general_it` → `SPS-2026-028` created, status `open`.
- **Acknowledgment**: MailHog shows `[SPS-2026-028] Your request has been received` to `intern@sps.com`.
- **Status → in_progress**: `PATCH /tickets/…` as agent → status changed.
- **Agent reply**: `POST /tickets/…/events` with `event_type=agent_reply_email` → MailHog shows reply email.
- **Resolution**: `PATCH /tickets/…` status `resolved` → MailHog shows resolution notification.
- **Timeline**: all events (`ticket_created`, `status_change`, `agent_reply_email`) recorded correctly.

## Scenario 2 – Web Form with Attachment ✅
- **Guest ticket**: `POST /tickets` with `source=portal_form` (no auth) → `SPS-2026-029` created.
- **Attachment upload**: `POST /tickets/…/attachments` (guest) → `test_attachment.txt` stored on disk and in database.
- **File persistence**: confirmed file exists in `/app/uploads/…`.

## Scenario 3 – AI Chat VPN → Escalated Admin Access + Approval ✅
- **VPN question**: `POST /api/chat` → KB‑grounded answer with sources, `escalate: false`.
- **Admin access request**: same session → `escalate: true`, `ticket_prefill` with `category=identity_access`.
- **Ticket creation** (simulated): `POST /tickets` with `category=identity_access` → `SPS-2026-035`, `risk_level=high`, `status=waiting_approval`.
- **Approval block**: agent `PATCH` → **403 Forbidden** *“This ticket is pending approval…”*.
- **Approval**: `POST /tickets/…/approve` as `secadmin` → status `in_progress`, timeline includes `approval_requested`.

## Scenario 4 – Mixed Channel (Email + Portal Upload) ✅
- **Upload to email ticket**: `POST /tickets/…/attachments` (guest) → `mixed_proof.txt` attached to `SPS-2026-028`.
- **Verification**: file on disk and listed in ticket detail `attachments` array.

## Scenario 5 – Phishing → SOC/Security Queue ✅
- **Ticket creation**: `source=email`, `category=cybersecurity`, `team=security` → `SPS-2026-036`.
- **Queue filtering**: `GET /tickets?category=cybersecurity` returns the ticket.
- **Enum note**: team values accepted: `security`, `it`, `devops`, `hr`, `management`.

## Scenario 6 – Manager Report (High‑Risk Requests) ✅
- **Login**: `secadmin@sps.com`.
- **Report endpoint**: `GET /reports/summary` returns JSON with:
  - `high_risk_total: 18`
  - `high_risk_pending_approval: 1`
  - `cybersecurity_tickets: 8`
  - `sla_breached: 16`
- High‑risk pending approvals are visible and countable.

---

**All six walkthroughs passed.** The platform meets the core behavioural requirements of the capstone specification.
