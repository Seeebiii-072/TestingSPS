import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai.classifier.classify import classify_ticket
from ai.llm.router import GenerationResult, LLMGenerationError
from ai.main import app
from ai.schemas.classifier import ClassifierRequest, ClassifierResponse
from ai.schemas.summariser import SummariserRequest, SummariserResponse
from ai.summariser.summarise import summarise_text


class ClassifierTests(unittest.TestCase):
    def test_invalid_json_retries_once(self) -> None:
        responses = iter(
            [
                GenerationResult(text="not-json", provider="test"),
                GenerationResult(
                    text=(
                        '{"category":"general_it","priority":"medium",'
                        '"risk_level":"standard","team":"it",'
                        '"reasoning":"General support request."}'
                    ),
                    provider="test",
                ),
            ]
        )
        calls = 0

        def generator(system: str, user: str) -> GenerationResult:
            nonlocal calls
            del system, user
            calls += 1
            return next(responses)

        result = classify_ticket(
            ClassifierRequest(subject="Printer issue", description="Cannot print."),
            generator=generator,
        )

        self.assertEqual(calls, 2)
        self.assertEqual(result.category, "general_it")

    def test_two_invalid_responses_use_rule_based_fallback(self) -> None:
        calls = 0

        def generator(system: str, user: str) -> GenerationResult:
            nonlocal calls
            del system, user
            calls += 1
            return GenerationResult(text="invalid", provider="test")

        result = classify_ticket(
            ClassifierRequest(
                subject="Production server is down",
                description="Revenue impact from unreachable VMs.",
            ),
            generator=generator,
        )

        self.assertEqual(calls, 2)
        self.assertEqual(result.category, "cloud")
        self.assertEqual(result.priority, "critical")

    def test_phishing_rule_overrides_valid_but_wrong_llm_output(self) -> None:
        result = classify_ticket(
            ClassifierRequest(
                subject="Phishing email",
                description="User entered credentials on a phishing page.",
            ),
            generator=lambda system, user: GenerationResult(
                text=(
                    '{"category":"general_it","priority":"low",'
                    '"risk_level":"standard","team":"it",'
                    '"reasoning":"Routine issue."}'
                ),
                provider="test",
            ),
        )

        self.assertEqual(result.category, "cybersecurity")
        self.assertEqual(result.priority, "critical")
        self.assertEqual(result.risk_level, "high")
        self.assertEqual(result.team, "security")

    def test_production_outage_fallback_is_critical(self) -> None:
        result = classify_ticket(
            ClassifierRequest(
                subject="Production server is down",
                description="All VMs unreachable since 9am. Revenue impact.",
            ),
            generator=self._unavailable_generator,
        )

        self.assertEqual(result.category, "cloud")
        self.assertEqual(result.priority, "critical")
        self.assertEqual(result.team, "devops")

    def test_privileged_password_reset_fallback_is_high_risk(self) -> None:
        result = classify_ticket(
            ClassifierRequest(
                subject="Password reset",
                description="Reset the privileged admin account password.",
            ),
            generator=self._unavailable_generator,
        )

        self.assertEqual(result.category, "identity_access")
        self.assertEqual(result.risk_level, "high")

    @staticmethod
    def _unavailable_generator(system: str, user: str) -> GenerationResult:
        del system, user
        raise LLMGenerationError("No providers available.")


class SummariserTests(unittest.TestCase):
    def test_valid_agent_summary_is_returned(self) -> None:
        result = summarise_text(
            SummariserRequest(
                subject="VPN issue",
                description="User cannot connect to VPN since morning.",
                messages=[],
            ),
            generator=lambda system, user: GenerationResult(
                text=(
                    "The user cannot connect to the VPN since morning. "
                    "IT support is requested to investigate the reported issue."
                ),
                provider="test",
            ),
        )

        self.assertIn("cannot connect", result.summary)

    def test_provider_failure_uses_ticket_only_fallback(self) -> None:
        request = SummariserRequest(
            subject="VPN issue",
            description="User cannot connect to VPN since morning.",
            messages=[],
        )

        result = summarise_text(
            request,
            generator=lambda system, user: (_ for _ in ()).throw(
                LLMGenerationError("No providers available.")
            ),
        )

        self.assertIn(request.description, result.summary)
        self.assertIn(request.subject, result.summary)

    def test_invented_factual_markers_trigger_fallback(self) -> None:
        request = SummariserRequest(
            subject="VPN issue",
            description="User cannot connect to VPN.",
            messages=[],
        )

        result = summarise_text(
            request,
            generator=lambda system, user: GenerationResult(
                text=(
                    "The VPN outage affects 500 users. "
                    "Support should investigate the incident."
                ),
                provider="test",
            ),
        )

        self.assertNotIn("500", result.summary)
        self.assertIn(request.description, result.summary)


class AiEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    @patch("ai.services.classifier_service.classify_ticket")
    def test_classify_endpoint_contract(self, classify) -> None:
        classify.return_value = ClassifierResponse(
            category="cloud",
            priority="critical",
            risk_level="standard",
            team="devops",
            reasoning=(
                "Production outage with revenue impact - critical priority, "
                "DevOps team."
            ),
        )

        response = self.client.post(
            "/ai/classify",
            json={
                "subject": "Production server is down",
                "description": "All VMs unreachable since 9am. Revenue impact.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {"category", "priority", "risk_level", "team", "reasoning"},
        )

    @patch("ai.services.summariser_service.summarise_text")
    def test_summarise_endpoint_contract(self, summarise) -> None:
        summarise.return_value = SummariserResponse(
            summary=(
                "The user cannot connect to VPN since morning. "
                "IT support is requested."
            )
        )

        response = self.client.post(
            "/ai/summarise",
            json={
                "subject": "VPN issue",
                "description": "User cannot connect to VPN since morning.",
                "messages": [],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"summary"})


if __name__ == "__main__":
    unittest.main()
