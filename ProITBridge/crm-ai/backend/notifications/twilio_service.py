"""
twilio_service.py — Twilio SMS notifications.
Used for: follow-up reminders, deal alerts, pipeline digests.
"""
from typing import Dict, Optional
from backend.config import settings


_client = None


def _get_client():
    global _client
    if _client is None:
        from twilio.rest import Client
        _client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    return _client


def send_sms(to_number: str, message: str) -> Dict:
    """Send an SMS notification via Twilio."""
    try:
        client = _get_client()
        msg = client.messages.create(
            body=message,
            from_=settings.TWILIO_FROM_NUMBER,
            to=to_number
        )
        return {"status": "sent", "sid": msg.sid, "to": to_number}
    except Exception as e:
        print(f"[Twilio] SMS error: {e}")
        return {"status": "error", "error": str(e)}


def send_follow_up_alert(to_number: str, deal_title: str, lead_name: str, days_since: int) -> Dict:
    message = (
        f"CRM Alert: '{deal_title}' with {lead_name} "
        f"has had no contact for {days_since} days. Time to follow up!"
    )
    return send_sms(to_number, message)


def send_deal_stage_alert(to_number: str, deal_title: str, old_stage: str, new_stage: str) -> Dict:
    message = f"Deal Update: '{deal_title}' moved from '{old_stage}' to '{new_stage}'"
    return send_sms(to_number, message)


def send_pipeline_digest(to_number: str, total_deals: int, hot_deals: int, pipeline_value: float) -> Dict:
    message = (
        f"Weekly Pipeline: {total_deals} active deals | "
        f"{hot_deals} hot | ${pipeline_value:,.0f} total value"
    )
    return send_sms(to_number, message)
