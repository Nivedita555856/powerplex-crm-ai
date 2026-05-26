"""
sample_data.py — In-memory demo state for Appliance CRM.
Stores runtime mutations (new tickets, approvals) during a session.
Also used by tests and as fallback when CSV is unavailable.
"""
from typing import List, Dict
from datetime import datetime

# Runtime in-memory ticket log (new tickets created via API go here)
RUNTIME_TICKETS: List[Dict] = []

# Approval queue for human-in-the-loop decisions
APPROVAL_QUEUE: List[Dict] = []

# Agent context store (session_id → context list)
CONTEXT_STORE: Dict[str, List[Dict]] = {}


def add_ticket(ticket: Dict) -> Dict:
    ticket["ticket_id"] = f"TKT{9000 + len(RUNTIME_TICKETS) + 1:04d}"
    ticket["created_date"] = datetime.utcnow().strftime("%Y-%m-%d")
    ticket["status"] = "Open"
    RUNTIME_TICKETS.append(ticket)
    return ticket


def add_to_approval_queue(item: Dict) -> Dict:
    item["approval_id"] = f"APR{len(APPROVAL_QUEUE)+1:03d}"
    item["queued_at"] = datetime.utcnow().isoformat()
    item["status"] = "pending"
    APPROVAL_QUEUE.append(item)
    return item


def get_pending_approvals() -> List[Dict]:
    return [a for a in APPROVAL_QUEUE if a["status"] == "pending"]


def resolve_approval(approval_id: str, decision: str, reason: str = "") -> Dict:
    for a in APPROVAL_QUEUE:
        if a["approval_id"] == approval_id:
            a["status"] = decision      # "approved" | "rejected"
            a["resolved_at"] = datetime.utcnow().isoformat()
            a["reason"] = reason
            return a
    return {}
