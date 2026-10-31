"""Keyword pre-pass classifier — the free, deterministic canary (ADR-007).

Ported from the supportpilot reference. It is deliberately cheap: it runs on
every ticket at zero cost and its danger tags are trusted even when the LLM
classifier is unavailable. The LLM classifier (provider.classify) refines
category/severity and catches paraphrases the keyword lists miss.
"""

from app.domain import (
    ClassifierResult,
    TicketCategory,
    TicketDifficulty,
    TicketSeverity,
)

_TAG_PHRASES: dict[str, tuple[str, ...]] = {
    "secret_protection": (
        "api key",
        "api secret",
        "access token",
        "private key",
        "secret key",
        "password",
    ),
    "secret_request": (
        "send me the api key",
        "send me the old api key",
        "give me the api key",
        "give me the old api key",
        "show me the api key",
        "retrieve my api key",
        "what is my api key",
        "what is the api key",
        "recover my api key",
        "provide my api key",
        "send me my password",
        "show me my password",
        "give me my password",
    ),
    "prompt_injection": (
        "ignore your instructions",
        "ignore previous instructions",
        "ignore your rules",
        "system prompt",
        "reveal your instructions",
        "show me your prompt",
    ),
    "security_incident": (
        "api key exposed",
        "api key leaked",
        "credential exposed",
        "credentials exposed",
        "hacked",
        "breach",
        "security incident",
        "unauthorized access",
    ),
    "identity_verification": (
        "change account owner",
        "change the account owner",
        "make me owner",
        "transfer ownership",
        "account ownership",
    ),
    "verification_bypass": (
        "without contacting",
        "without verification",
        "without verifying",
        "bypass verification",
        "skip verification",
        "owner is unavailable",
    ),
    "billing_exception": (
        "duplicate charge",
        "charged twice",
        "charged two times",
        "double charged",
    ),
    "refund_exception": (
        "refund exception",
        "chargeback",
        "money back",
    ),
    "outage": (
        "500 errors everywhere",
        "everything is down",
        "production is down",
        "production outage",
        "all requests failing",
        "entire api is down",
    ),
}

_CATEGORY_RULES: list[tuple[TicketCategory, tuple[str, ...]]] = [
    (TicketCategory.BILLING, ("invoice", "billing", "charged", "payment", "subscription")),
    (TicketCategory.TECHNICAL_API, ("api", "401", "403", "404", "500", "endpoint", "request")),
    (
        TicketCategory.ACCOUNT_AUTHENTICATION,
        ("login", "log in", "password", "authentication", "sign in"),
    ),
    (TicketCategory.PERMISSIONS_SECURITY, ("permission", "owner", "admin", "role", "access")),
    (TicketCategory.INTEGRATIONS, ("integration", "webhook", "salesforce", "slack", "zapier")),
    (TicketCategory.FEATURE_REQUEST, ("feature", "support", "add", "would like")),
    (TicketCategory.REFUND_CANCELLATION, ("refund", "cancel", "cancellation")),
]


class KeywordClassifier:
    def classify(self, subject: str, body: str) -> ClassifierResult:
        text = f"{subject}\n{body}".lower()

        tags = [
            tag
            for tag, phrases in _TAG_PHRASES.items()
            if any(phrase in text for phrase in phrases)
        ]

        category = TicketCategory.PRODUCT_HOW_TO
        for candidate, phrases in _CATEGORY_RULES:
            if any(phrase in text for phrase in phrases):
                category = candidate
                break

        if "security_incident" in tags or "outage" in tags:
            severity = TicketSeverity.P1
        elif tags:
            severity = TicketSeverity.P2
        else:
            severity = TicketSeverity.P3

        difficulty = TicketDifficulty.MEDIUM if tags else TicketDifficulty.EASY

        return ClassifierResult(
            category=category,
            severity=severity,
            difficulty=difficulty,
            tags=tags,
            confidence=1.0,  # deterministic pre-pass is certain about its own tags
        )
