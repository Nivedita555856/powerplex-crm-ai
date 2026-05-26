"""
gmail_reader.py — PowerPlex Gmail Integration
Reads incoming support emails and auto-creates tickets via the classification pipeline.
Uses Gmail API (OAuth2). Falls back to IMAP if credentials not configured.

Setup:
  1. Go to console.cloud.google.com → Enable Gmail API
  2. Create OAuth2 credentials → download client_secret.json
  3. Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET in .env
  4. Run: python -m backend.automation.gmail_reader --auth (once, to get token)
  5. Set GMAIL_REFRESH_TOKEN in .env
"""
import os
import json
import base64
from typing import List, Dict, Optional
from datetime import datetime

# Gmail API — graceful import
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    _GMAIL_AVAILABLE = True
except ImportError:
    _GMAIL_AVAILABLE = False

SUPPORT_EMAIL = "niveditakothuri0506@gmail.com"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Customer email → customer_id mapping (update with real Supabase lookup)
KNOWN_CUSTOMERS = {
    "arunchabra03@gmail.com":   "CUST_DEMO1",
    "niveditakothuri9@gmail.com": "CUST_DEMO2",
    "knivedita132@gmail.com":   "CUST_DEMO3",
}


def gmail_available() -> bool:
    """Check if Gmail API credentials are configured."""
    if not _GMAIL_AVAILABLE:
        return False
    required = ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"]
    return all(os.getenv(k) for k in required)


def _get_service():
    """Build Gmail API service from environment credentials."""
    if not gmail_available():
        return None
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GMAIL_REFRESH_TOKEN"),
        client_id=os.getenv("GMAIL_CLIENT_ID"),
        client_secret=os.getenv("GMAIL_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


def _decode_body(payload: Dict) -> str:
    """Extract plain text body from Gmail message payload."""
    body = ""
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
    else:
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return body.strip()


def fetch_unread_support_emails(max_results: int = 10) -> List[Dict]:
    """
    Fetch unread emails from the support inbox.
    Returns list of parsed email dicts ready for ticket creation.
    """
    service = _get_service()
    if not service:
        return _get_demo_emails()

    try:
        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=max_results,
        ).execute()

        messages = results.get("messages", [])
        parsed   = []

        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me", id=msg["id"], format="full"
            ).execute()

            headers    = {h["name"]: h["value"] for h in msg_data["payload"]["headers"]}
            from_email = headers.get("From", "")
            subject    = headers.get("Subject", "(No Subject)")
            body       = _decode_body(msg_data["payload"])

            # Extract email address from "Name <email>" format
            import re
            email_match = re.search(r"<(.+?)>", from_email)
            sender_email = email_match.group(1) if email_match else from_email.strip()

            parsed.append({
                "message_id":    msg["id"],
                "from_email":    sender_email,
                "from_name":     from_email.split("<")[0].strip().strip('"'),
                "subject":       subject,
                "body":          body[:2000],
                "customer_id":   KNOWN_CUSTOMERS.get(sender_email.lower()),
                "received_at":   datetime.utcnow().isoformat(),
                "source":        "gmail",
            })

        return parsed

    except Exception as e:
        print(f"[Gmail] Fetch failed: {e}")
        return []


def mark_as_read(message_id: str) -> bool:
    """Mark a Gmail message as read after processing."""
    service = _get_service()
    if not service:
        return False
    try:
        service.users().messages().modify(
            userId="me", id=message_id,
            body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        return True
    except Exception as e:
        print(f"[Gmail] Mark read failed: {e}")
        return False


def _get_demo_emails() -> List[Dict]:
    """Demo emails for when Gmail API is not configured."""
    return [
        {
            "message_id":  "demo_001",
            "from_email":  "arunchabra03@gmail.com",
            "from_name":   "Arun Chabra",
            "subject":     "AC not cooling — urgent help needed",
            "body":        "Hello, my LG air conditioner has completely stopped cooling. It was working fine yesterday but today it is just blowing hot air. I am under warranty. Please help urgently.",
            "customer_id": "CUST_DEMO1",
            "received_at": datetime.utcnow().isoformat(),
            "source":      "demo",
        },
        {
            "message_id":  "demo_002",
            "from_email":  "niveditakothuri9@gmail.com",
            "from_name":   "Nivedita K",
            "subject":     "Washing machine making loud noise",
            "body":        "Hi, my washing machine (FrostKing model) is making a very loud banging noise during the spin cycle. It started 2 days ago. Can you send someone to check?",
            "customer_id": "CUST_DEMO2",
            "received_at": datetime.utcnow().isoformat(),
            "source":      "demo",
        },
        {
            "message_id":  "demo_003",
            "from_email":  "knivedita132@gmail.com",
            "from_name":   "K Nivedita",
            "subject":     "Refrigerator stopped working completely",
            "body":        "My refrigerator has completely stopped working. Nothing is cold, the motor is not running, and I can see water pooling at the bottom. I bought it 8 months ago so it should be under warranty.",
            "customer_id": "CUST_DEMO3",
            "received_at": datetime.utcnow().isoformat(),
            "source":      "demo",
        },
    ]


def process_emails_into_tickets() -> List[Dict]:
    """
    Full pipeline: read emails → classify → create tickets → queue confirmation emails.
    Returns list of created tickets with their approval queue items.
    """
    from backend.agents.ticket_classifier import classify_ticket
    from backend.agents.communication_agent import generate_ticket_confirmation
    from backend.approval.approval_queue import queue_email_for_approval
    from backend.sample_data import add_ticket
    import uuid

    emails = fetch_unread_support_emails()
    results = []

    for email in emails:
        # Classify the email
        classification = classify_ticket(email["body"] + " " + email["subject"])

        # Create ticket
        ticket_id = f"TKT-{uuid.uuid4().hex[:6].upper()}"
        ticket = add_ticket({
            "ticket_id":    ticket_id,
            "customer_id":  email["customer_id"] or "UNKNOWN",
            "issue":        email["subject"] + ": " + email["body"][:100],
            "priority":     classification["severity"],
            "product_type": classification["product_type"],
            "source":       "email",
            "email_id":     email["message_id"],
        })

        # Generate confirmation email draft → queue for approval
        customer = {
            "name":  email["from_name"] or email["from_email"],
            "email": email["from_email"],
        }
        draft    = generate_ticket_confirmation(customer, {**ticket, **classification})
        approval = queue_email_for_approval(
            email_type  = "email_ticket_confirmation",
            to_email    = email["from_email"],
            customer_id = email["customer_id"] or "UNKNOWN",
            ticket_id   = ticket_id,
            draft       = draft,
            metadata    = {"classification": classification},
        )

        results.append({
            "email":      email,
            "ticket":     ticket,
            "classification": classification,
            "approval":   approval,
            "message":    f"Ticket {ticket_id} created. Confirmation email queued for approval ({approval['approval_id']}).",
        })

        # Mark email as read
        if email["source"] == "gmail":
            mark_as_read(email["message_id"])

    return results
