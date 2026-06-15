import json
import re
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from ai.llm.router import GenerationResult, LLMGenerationError, generate_response_with_provider
from ai.schemas.classifier import ClassifierRequest, ClassifierResponse


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "classifier.txt"
Generator = Callable[[str, str], GenerationResult]

SECURITY_PATTERN = re.compile(
    r"\b(phish(?:ing|ed)?|malware|ransomware|security threat|"
    r"cyber(?:\s|-)?attack|data (?:breach|leak)|compromised|"
    r"unauthori[sz]ed access|stolen credentials?)\b",
    re.IGNORECASE,
)
IDENTITY_PATTERN = re.compile(
    r"\b(identity|access|admin(?:istrator)?|root|privilege[ds]?|"
    r"permission|role assignment|account unlock|password reset)\b",
    re.IGNORECASE,
)
PRODUCTION_PATTERN = re.compile(
    r"\b(production|prod|outage|server (?:is )?down|service (?:is )?down|"
    r"unreachable|revenue impact|business critical)\b",
    re.IGNORECASE,
)
DEVOPS_PATTERN = re.compile(
    r"\b(ci/?cd|pipeline|deployment|deploy|container|docker|kubernetes|"
    r"terraform|devops)\b",
    re.IGNORECASE,
)
CLOUD_PATTERN = re.compile(
    r"\b(cloud|vm|vms|virtual machine|aws|azure|gcp|server|infrastructure)\b",
    re.IGNORECASE,
)
HR_PATTERN = re.compile(
    r"\b(intern|internship|onboarding|offboarding|hr|human resources)\b",
    re.IGNORECASE,
)
LOW_PRIORITY_PATTERN = re.compile(
    r"\b(how do i|information|question|request when convenient)\b",
    re.IGNORECASE,
)


def _ticket_text(request: ClassifierRequest) -> str:
    return f"{request.subject}\n{request.description}".strip()


def _user_prompt(request: ClassifierRequest, *, retry: bool = False) -> str:
    retry_note = (
        "\nYour previous response was invalid. Return only the exact JSON object."
        if retry
        else ""
    )
    return (
        f"Subject: {request.subject}\n"
        f"Description: {request.description}"
        f"{retry_note}"
    )


def _parse_response(text: str) -> ClassifierResponse:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Classifier response must be a JSON object.")
    return ClassifierResponse.model_validate(payload)


def _fallback_classifier(request: ClassifierRequest) -> ClassifierResponse:
    text = _ticket_text(request)

    if SECURITY_PATTERN.search(text):
        return ClassifierResponse(
            category="cybersecurity",
            priority="critical",
            risk_level="high",
            team="security",
            reasoning=(
                "Security threat detected - critical priority for the Security team."
            ),
        )

    identity_match = IDENTITY_PATTERN.search(text)
    production_match = PRODUCTION_PATTERN.search(text)
    if identity_match:
        return ClassifierResponse(
            category="identity_access",
            priority="critical" if production_match else "high",
            risk_level="high",
            team="it",
            reasoning=(
                "Identity or privileged access request detected - high risk for IT."
            ),
        )

    if production_match:
        category = "devops" if DEVOPS_PATTERN.search(text) else "cloud"
        return ClassifierResponse(
            category=category,
            priority="critical",
            risk_level="standard",
            team="devops",
            reasoning=(
                "Production outage or revenue impact detected - critical priority "
                "for the DevOps team."
            ),
        )

    if DEVOPS_PATTERN.search(text):
        return ClassifierResponse(
            category="devops",
            priority="high",
            risk_level="standard",
            team="devops",
            reasoning="DevOps tooling or deployment issue detected.",
        )

    if CLOUD_PATTERN.search(text):
        return ClassifierResponse(
            category="cloud",
            priority="high",
            risk_level="standard",
            team="devops",
            reasoning="Cloud or infrastructure issue detected.",
        )

    if HR_PATTERN.search(text):
        return ClassifierResponse(
            category="internship_hr",
            priority="medium",
            risk_level="standard",
            team="hr",
            reasoning="Internship or HR support request detected.",
        )

    priority = "low" if LOW_PRIORITY_PATTERN.search(text) else "medium"
    return ClassifierResponse(
        category="general_it",
        priority=priority,
        risk_level="standard",
        team="it",
        reasoning="General IT support request detected.",
    )


def _enforce_mandatory_rules(
    request: ClassifierRequest,
    response: ClassifierResponse,
) -> ClassifierResponse:
    text = _ticket_text(request)
    if SECURITY_PATTERN.search(text):
        return ClassifierResponse.model_validate(
            {
                **response.model_dump(mode="json"),
                "category": "cybersecurity",
                "priority": "critical",
                "risk_level": "high",
                "team": "security",
                "reasoning": (
                    "Security threat detected - critical priority for the "
                    "Security team."
                ),
            }
        )

    updates: dict[str, str] = {}
    reasons: list[str] = []
    if IDENTITY_PATTERN.search(text):
        updates.update(
            category="identity_access",
            risk_level="high",
        )
        reasons.append("identity or privileged access request")
    if PRODUCTION_PATTERN.search(text):
        updates["priority"] = "critical"
        reasons.append("production outage or revenue impact")
    if not updates:
        return response

    updates["reasoning"] = (
        f"Mandatory classification applied for {' and '.join(reasons)}."
    )
    return ClassifierResponse.model_validate(
        {**response.model_dump(mode="json"), **updates}
    )


def classify_ticket(
    request: ClassifierRequest,
    *,
    generator: Generator = generate_response_with_provider,
) -> ClassifierResponse:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()

    for attempt in range(2):
        try:
            generated = generator(
                system_prompt,
                _user_prompt(request, retry=attempt == 1),
            )
            return _enforce_mandatory_rules(
                request,
                _parse_response(generated.text),
            )
        except (json.JSONDecodeError, ValidationError, ValueError):
            continue
        except LLMGenerationError:
            break

    return _fallback_classifier(request)
