"""
guardrails.py — LLM output validation layer.
Prevents unauthorized refunds, hallucinated warranties, unsafe responses.
"""
import re
from typing import Dict, Tuple

# ── Rules ─────────────────────────────────────────────────────────────────────
BLOCKED_PHRASES = [
    r"refund.{0,30}approved",
    r"warranty.{0,30}extended.{0,30}free",
    r"free.{0,30}replacement",
    r"no.{0,20}charge",
    r"complimentary",
    r"at no cost",
    r"₹\d{5,}",           # blocks any amount ≥ ₹10,000 in raw output
]

REQUIRED_DISCLAIMERS = {
    "refund": "Subject to management approval.",
    "warranty": "Warranty terms as per purchase agreement.",
}

MAX_OUTPUT_LENGTH = 1200


def validate_response(response: str, intent: str = "") -> Tuple[str, bool, str]:
    """
    Returns (cleaned_response, is_safe, reason).
    is_safe=False means the response was blocked or modified.
    """
    if len(response) > MAX_OUTPUT_LENGTH:
        response = response[:MAX_OUTPUT_LENGTH] + "...\n[Response truncated for safety.]"

    flagged_patterns = []
    for pattern in BLOCKED_PHRASES:
        if re.search(pattern, response, re.IGNORECASE):
            flagged_patterns.append(pattern)

    if flagged_patterns:
        safe_response = (
            "I'm unable to confirm this directly. Please contact our support team "
            "for authorised approvals. Our team will review and respond within 24 hours."
        )
        return safe_response, False, f"Blocked patterns: {flagged_patterns}"

    # Add disclaimers when relevant
    for keyword, disclaimer in REQUIRED_DISCLAIMERS.items():
        if keyword in response.lower() and disclaimer not in response:
            response = response.rstrip() + f"\n\n*Note: {disclaimer}*"

    return response, True, "OK"


def validate_warranty_claim(customer_id: str, warranty_data: Dict) -> Tuple[bool, str]:
    """Check if a warranty claim is valid before acting on it."""
    if not warranty_data:
        return False, "No warranty record found for this customer."
    if warranty_data.get("status") == "Expired":
        return False, f"Warranty expired on {warranty_data.get('expiry_date')}. Out-of-warranty charges apply."
    return True, "Warranty is active."


def check_refund_authority(amount: int, agent_level: str = "bot") -> Tuple[bool, str]:
    """
    Determine if the agent can approve a refund.
    bot: up to ₹0 (no auto-approval)
    support: up to ₹2,000
    manager: up to ₹10,000
    director: unlimited
    """
    authority = {"bot": 0, "support": 2000, "manager": 10000, "director": 999999}
    limit = authority.get(agent_level, 0)
    if amount > limit:
        return False, f"Refund of ₹{amount:,} requires approval above {agent_level} level."
    return True, f"Refund of ₹{amount:,} approved at {agent_level} level."


def sanitize_input(text: str) -> str:
    """Basic input sanitization — remove control chars, limit length."""
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return text[:2000].strip()
