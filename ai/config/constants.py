from enum import Enum


class TicketCategory(str, Enum):
    ACCESS_AND_IDENTITY = "access_and_identity"
    HARDWARE = "hardware"
    SOFTWARE = "software"
    NETWORK = "network"
    EMAIL = "email"
    SECURITY = "security"
    OTHER = "other"


class TicketPrefillCategory(str, Enum):
    CLOUD = "cloud"
    CYBERSECURITY = "cybersecurity"
    IDENTITY_ACCESS = "identity_access"
    DEVOPS = "devops"
    INTERNSHIP_HR = "internship_hr"
    GENERAL_IT = "general_it"


class TicketPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SupportTeam(str, Enum):
    SERVICE_DESK = "service_desk"
    IDENTITY_AND_ACCESS = "identity_and_access"
    INFRASTRUCTURE = "infrastructure"
    APPLICATION_SUPPORT = "application_support"
    NETWORK_OPERATIONS = "network_operations"
    SECURITY_OPERATIONS = "security_operations"


class TicketSource(str, Enum):
    EMAIL = "email"
    PORTAL_FORM = "portal_form"
    CHAT = "chat"


class TicketStatus(str, Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    CLOSED = "closed"


class SLAStatus(str, Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BREACHED = "breached"
    MET = "met"


class TimelineEventType(str, Enum):
    TICKET_CREATED = "ticket_created"
    COMMENT = "comment"
    EMAIL_EVENT = "email_event"
    FORM_SUBMISSION = "form_submission"
    CHAT_MESSAGE = "chat_message"
    ASSIGNMENT = "assignment"
    REASSIGNMENT = "reassignment"
    ESCALATION = "escalation"
    STATUS_CHANGE = "status_change"
    EMAIL_REPLY = "email_reply"
    PORTAL_REPLY = "portal_reply"
    AI_SUMMARY_EDITED = "ai_summary_edited"


ALLOWED_CATEGORIES = tuple(item.value for item in TicketCategory)
ALLOWED_TICKET_PREFILL_CATEGORIES = tuple(
    item.value for item in TicketPrefillCategory
)
ALLOWED_PRIORITIES = tuple(item.value for item in TicketPriority)
ALLOWED_RISKS = tuple(item.value for item in RiskLevel)
ALLOWED_TEAMS = tuple(item.value for item in SupportTeam)

RISK_KEYWORDS = frozenset(
    {
        "breach",
        "compromised",
        "data leak",
        "exfiltration",
        "malware",
        "phishing",
        "ransomware",
        "stolen credentials",
        "unauthorized access",
        "zero-day",
    }
)
