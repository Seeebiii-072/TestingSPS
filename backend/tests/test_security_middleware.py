import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleware import security_middleware  # noqa: E402


def _test_app(monkeypatch):
    logged_events = []

    async def fake_log_security_event(**kwargs):
        logged_events.append(kwargs)

    monkeypatch.setattr(security_middleware, "log_security_event", fake_log_security_event)

    app = FastAPI()
    app.middleware("http")(security_middleware.check_security_threats)

    @app.post("/tickets")
    async def create_ticket(payload: dict):
        return {"ok": True, "payload": payload}

    return app, logged_events


def test_ticket_free_text_sql_words_are_not_blocked(monkeypatch):
    app, logged_events = _test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/tickets",
            json={
                "source": "portal_form",
                "subject": "VPN profile update",
                "description": "please delete my old VPN profile and select a new region for my account",
                "category": "general_it",
                "requester_email": "employee@sps.com",
            },
        )

    assert response.status_code == 200
    assert logged_events == []


def test_sql_injection_shape_is_blocked_and_logged(monkeypatch):
    app, logged_events = _test_app(monkeypatch)

    with TestClient(app) as client:
        response = client.post(
            "/tickets",
            json={
                "source": "portal_form",
                "subject": "VPN profile update",
                "description": "normal helpdesk text",
                "category": "'; DROP TABLE users; --",
                "requester_email": "employee@sps.com",
            },
        )

    assert response.status_code == 400
    assert len(logged_events) == 1
    assert logged_events[0]["action"] == "security.injection_attempt"
    assert logged_events[0]["details"]["pattern"] == "DROP"
    assert logged_events[0]["details"]["field"] == "category"
