import unittest
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from ai.config.constants import TicketSource
from ai.main import app
from ai.schemas.ticket import ReplyRequest
from ai.services.ticket_service import TicketService, ticket_repository


class TicketApiTests(unittest.TestCase):
    def setUp(self) -> None:
        ticket_repository.clear()
        self.client = TestClient(app)

    def create_ticket(self, source: str = "email") -> dict:
        response = self.client.post(
            "/api/v1/tickets",
            json={
                "source": source,
                "requester": {
                    "account_id": "acct-42",
                    "email": "requester@example.com",
                },
                "subject": "VPN access is unavailable",
                "description": "The requester cannot connect to the VPN.",
                "category": "network",
                "priority": "high",
                "risk": "medium",
                "team": "network_operations",
                "ai_summary": "VPN connection failure.",
                "source_snapshot": {
                    "external_id": "message-123",
                    "content": "Original requester message.",
                    "metadata": {"mailbox": "support@example.com"},
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_all_sources_use_same_ticket_contract(self) -> None:
        for source in ("email", "portal_form", "chat"):
            with self.subTest(source=source):
                ticket = self.create_ticket(source)
                self.assertRegex(ticket["ticket_id"], r"^SPS-\d{4}-\d{3}$")
                self.assertEqual(ticket["source"], source)
                self.assertEqual(ticket["status"], "open")
                self.assertEqual(ticket["requester"]["account_id"], "acct-42")
                self.assertEqual(len(ticket["timeline"]), 2)

    def test_agent_can_assign_escalate_reply_and_resolve(self) -> None:
        ticket = self.create_ticket()
        ticket_id = ticket["ticket_id"]

        assigned = self.client.post(
            f"/api/v1/tickets/{ticket_id}/assign",
            json={"agent_id": "agent-1", "actor_id": "lead-1"},
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.json()["assigned_agent_id"], "agent-1")

        escalated = self.client.post(
            f"/api/v1/tickets/{ticket_id}/escalate",
            json={
                "actor_id": "agent-1",
                "note": "Security review required.",
                "team": "security_operations",
            },
        )
        self.assertEqual(escalated.json()["status"], "escalated")

        reply = self.client.post(
            f"/api/v1/tickets/{ticket_id}/replies/portal",
            json={"actor_id": "agent-1", "message": "We are investigating."},
        )
        visible_events = [
            event for event in reply.json()["timeline"]
            if event["visible_to_requester"]
        ]
        self.assertTrue(
            any(event["event_type"] == "portal_reply" for event in visible_events)
        )

        resolved = self.client.post(
            f"/api/v1/tickets/{ticket_id}/resolve",
            json={"actor_id": "agent-1", "resolution": "VPN profile was repaired."},
        )
        self.assertEqual(resolved.json()["status"], "resolved")
        self.assertIsNotNone(resolved.json()["sla"]["resolved_at"])

    def test_ai_summary_is_agent_editable_and_audited(self) -> None:
        ticket = self.create_ticket()
        response = self.client.patch(
            f"/api/v1/tickets/{ticket['ticket_id']}",
            headers={"X-Actor-ID": "agent-2"},
            json={"ai_summary": "Agent corrected the AI summary."},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["ai_summary"],
            "Agent corrected the AI summary.",
        )
        self.assertEqual(
            response.json()["timeline"][-1]["event_type"],
            "ai_summary_edited",
        )

    def test_ticket_patch_rejects_null_classification_fields(self) -> None:
        ticket = self.create_ticket()

        response = self.client.patch(
            f"/api/v1/tickets/{ticket['ticket_id']}",
            headers={"X-Actor-ID": "agent-2"},
            json={"priority": None},
        )

        self.assertEqual(response.status_code, 422)

    def test_concurrent_replies_preserve_all_timeline_events(self) -> None:
        ticket = self.create_ticket()
        service = TicketService()

        def reply(index: int) -> None:
            service.reply(
                ticket["ticket_id"],
                ReplyRequest(
                    actor_id=f"agent-{index}",
                    message=f"Update {index}",
                ),
                TicketSource.PORTAL_FORM,
            )

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(reply, range(10)))

        saved = service.get(ticket["ticket_id"])
        replies = [
            event
            for event in saved.timeline
            if event.event_type == "portal_reply"
        ]
        self.assertEqual(len(replies), 10)


if __name__ == "__main__":
    unittest.main()
