import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi.testclient import TestClient

from ai.chat.session import session_store
from ai.config.settings import get_settings
from ai.main import app


class ChatEscalationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        session_store.clear()
        get_settings.cache_clear()
        self.client = TestClient(app)

    @staticmethod
    def request_payload(**prefill_overrides) -> dict:
        prefill = {
            "source": "chat",
            "subject": "Unsupported device",
            "description": "The knowledge base did not contain an answer.",
            "category": "general_it",
            "ai_summary": "The AI could not answer from the knowledge base.",
            "timeline_note": "Chat escalation note: user requested support.",
        }
        prefill.update(prefill_overrides)
        return {
            "session_id": "abc123",
            "user_id": "u1",
            "requester": "user@example.com",
            "ticket_prefill": prefill,
        }

    @patch("ai.services.chat_escalation_service.httpx.post")
    def test_posts_core_ticket_payload_and_returns_backend_id(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=Mock(return_value={"ticket_id": "SPS-2026-001"}),
            raise_for_status=Mock(),
        )

        response = self.client.post(
            "/chat/escalate",
            json=self.request_payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        self.assertEqual(response.json()["ticket_id"], "SPS-2026-001")
        url = post.call_args.args[0]
        payload = post.call_args.kwargs["json"]
        self.assertEqual(url, "http://localhost:8000/tickets")
        self.assertNotIn("ticket_id", payload)
        self.assertEqual(payload["source"], "chat")
        self.assertEqual(payload["requester"], "user@example.com")
        self.assertEqual(payload["priority"], "medium")
        self.assertEqual(payload["risk_level"], "standard")
        self.assertEqual(payload["team"], "it")
        self.assertEqual(payload["status"], "open")
        self.assertEqual(payload["sla"], "standard")
        self.assertEqual(payload["timeline"][0]["session_id"], "abc123")
        self.assertIn(
            "The knowledge base did not contain an answer.",
            payload["timeline"][0]["message"],
        )

    @patch("ai.services.chat_escalation_service.httpx.post")
    def test_requester_falls_back_to_user_id_and_ticket_number_is_supported(
        self,
        post: Mock,
    ) -> None:
        post.return_value = Mock(
            json=Mock(return_value={"ticket_number": "SPS-2026-002"}),
            raise_for_status=Mock(),
        )
        request = self.request_payload(priority="high", risk_level="high")
        del request["requester"]

        response = self.client.post("/chat/escalate", json=request)

        self.assertEqual(response.json()["ticket_id"], "SPS-2026-002")
        self.assertEqual(post.call_args.kwargs["json"]["requester"], "u1")

    @patch("ai.services.chat_escalation_service.httpx.post")
    def test_backend_failure_is_graceful_and_preserves_session(
        self,
        post: Mock,
    ) -> None:
        session = session_store.get_or_create("abc123", "u1")
        session.add_message("user", "Please create a ticket.")
        original_messages = list(session.messages)
        post.side_effect = httpx.ConnectError("Connection refused")

        response = self.client.post(
            "/chat/escalate",
            json=self.request_payload(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertNotIn("backend_response", response.json())
        self.assertIn("backend service is unavailable", response.json()["message"])
        preserved = session_store.get_or_create("abc123", "u1")
        self.assertEqual(preserved.messages, original_messages)

    def test_rejects_invalid_source_and_classification_values(self) -> None:
        invalid_values = (
            {"source": "email"},
            {"category": "hardware"},
            {"priority": "urgent"},
            {"risk_level": "critical"},
            {"team": "finance"},
        )
        for override in invalid_values:
            with self.subTest(override=override):
                response = self.client.post(
                    "/chat/escalate",
                    json=self.request_payload(**override),
                )
                self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
