"""
human_approval_agent.py — Manages human-in-the-loop approval workflow.
Queues decisions requiring human review and processes approvals.
"""
from typing import Dict, List
from backend.sample_data import add_to_approval_queue, get_pending_approvals, resolve_approval
from backend.config import settings

def queue_for_approval(item_type: str, description: str, amount: int = 0,
                        customer_id: str = "", ticket_id: str = "") -> Dict:
    """Add an item to the human approval queue."""
    item = {
        "item_type":    item_type,
        "description":  description,
        "amount":       amount,
        "customer_id":  customer_id,
        "ticket_id":    ticket_id,
        "requires_approval_because": _get_reason(item_type, amount),
    }
    queued = add_to_approval_queue(item)
    return {
        "queued": True,
        "approval_id": queued["approval_id"],
        "message": f"Queued for human approval: {queued['approval_id']}. A manager will review shortly.",
    }

def _get_reason(item_type: str, amount: int) -> str:
    if item_type == "refund" and amount > settings.REFUND_APPROVAL_THRESHOLD:
        return f"Refund amount ₹{amount:,} exceeds bot authority (₹{settings.REFUND_APPROVAL_THRESHOLD:,})"
    if item_type == "warranty_override":
        return "Warranty override requires manager sign-off"
    if item_type == "escalation":
        return "Critical complaint requires senior support"
    return "Requires human review"

def get_queue() -> List[Dict]:
    return get_pending_approvals()

def process_approval(approval_id: str, decision: str, reason: str = "") -> Dict:
    """Process a human approval decision."""
    result = resolve_approval(approval_id, decision, reason)
    if not result:
        return {"error": f"Approval {approval_id} not found"}
    return {
        "approval_id": approval_id,
        "decision":    decision,
        "message":     f"Approval {approval_id} marked as '{decision}'.",
        "item":        result,
    }
