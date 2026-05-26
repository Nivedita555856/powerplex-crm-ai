"""
ticket_classifier.py — PowerPlex Ticket Classification Agent
Detects severity, product type, urgency, warranty relevance from raw text/email.
"""
import re
from typing import Dict, Optional
from backend.utils.llm import call_llm, _get_client

SEVERITY_KEYWORDS = {
    "critical": ["fire","smoke","electrical","shock","not turning on","completely dead","water leak","flooding","gas"],
    "high":     ["not working","broken","stopped","no power","error","fault","freezing","overheating"],
    "medium":   ["slow","noise","vibration","intermittent","sometimes","occasional","reduced"],
    "low":      ["cosmetic","minor","question","inquiry","schedule","information","when"],
}

# Order matters — more specific products first to avoid false AC matches
PRODUCT_KEYWORDS = {
    "Refrigerator":     ["fridge","refrigerator","freezer","ice maker"],
    "Washing Machine":  ["washing machine","washer","laundry","spin","drum"],
    "Microwave":        ["microwave","oven","cooking appliance"],
    "Television":       ["tv","television","screen","display","remote control"],
    "AC":               ["air conditioner","aircon","hvac","ac unit","split ac",
                         " ac ","ac not","ac is","ac repair","ac cooling",
                         "outdoor unit","indoor unit","compressor","condenser"],
}

WARRANTY_KEYWORDS = ["warranty","under warranty","covered","claim","replacement","repair","eligible"]


def classify_ticket(text: str, session_id: str = "") -> Dict:
    """
    Classify a support request or email body.
    Returns: severity, product_type, urgency_score, warranty_relevant, summary
    """
    t = text.lower()

    # Rule-based severity
    severity = "medium"
    for level in ["critical", "high", "medium", "low"]:
        if any(kw in t for kw in SEVERITY_KEYWORDS[level]):
            severity = level
            break

    # Product type
    product_type = "General"
    for prod, keywords in PRODUCT_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            product_type = prod
            break

    # Warranty relevance
    warranty_relevant = any(kw in t for kw in WARRANTY_KEYWORDS)

    # Urgency score 0–10
    urgency_map = {"critical": 9, "high": 7, "medium": 5, "low": 2}
    urgency_score = urgency_map[severity]
    if warranty_relevant:
        urgency_score = min(10, urgency_score + 1)

    # AI summary if Groq available
    summary = text[:120].strip()
    if _get_client() and len(text) > 60:
        prompt = (
            f"Summarise this support request in one sentence (max 15 words):\n{text[:500]}"
        )
        ai_sum = call_llm("You summarise support requests concisely.", prompt, session_id, 60)
        if ai_sum and len(ai_sum) < 200:
            summary = ai_sum.strip()

    return {
        "severity":          severity,
        "product_type":      product_type,
        "urgency_score":     urgency_score,
        "warranty_relevant": warranty_relevant,
        "summary":           summary,
    }
