"""
approval_queue.py — PowerPlex Admin Approval System
Manages all approval items: emails, technician assignments, escalations.
RULE: Nothing executes without an explicit admin approve/reject decision.
"""
import uuid
from datetime import datetime
from typing import Dict, List, Optional

# In-memory store (replace with Supabase in production)
_QUEUE: Dict[str, Dict] = {}

APPROVAL_TYPES = {
    "email_ticket_confirmation": "Ticket Confirmation Email",
    "email_technician_assignment": "Technician Assignment Email",
    "email_warranty_decision": "Warranty Decision Email",
    "email_repair_completion": "Repair Completion Email",
    "email_escalation": "Escalation Notice Email",
    "email_apology": "Apology Email",
    "email_warranty_expiry": "Warranty Expiry Notice",
    "email_purchase_welcome": "Purchase Welcome Email",
    "email_recommendation": "Product Recommendation Email",
    "technician_assignment": "Technician Assignment Action",
    "warranty_override": "Warranty Override Decision",
    "escalation_action": "Escalation Action",
    "refund_approval": "Refund / Compensation",
}


def queue_email_for_approval(
    email_type: str,
    to_email: str,
    customer_id: str,
    ticket_id: Optional[str],
    draft: Dict,
    metadata: Optional[Dict] = None,
) -> Dict:
    """
    Add an email draft to the approval queue.
    Returns the approval item with its ID.
    """
    approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
    item = {
        "approval_id":   approval_id,
        "item_type":     email_type,
        "description":   APPROVAL_TYPES.get(email_type, email_type),
        "to_email":      to_email,
        "customer_id":   customer_id,
        "ticket_id":     ticket_id,
        "subject":       draft.get("subject", ""),
        "body":          draft.get("body", ""),
        "email_type":    draft.get("email_type", email_type),
        "ai_enhanced":   draft.get("ai_enhanced", False),
        "status":        "pending",
        "created_at":    datetime.utcnow().isoformat(),
        "decided_by":    None,
        "decided_at":    None,
        "metadata":      metadata or {},
    }
    _QUEUE[approval_id] = item
    return item


def queue_action_for_approval(
    action_type: str,
    description: str,
    customer_id: str,
    ticket_id: Optional[str],
    action_data: Dict,
    amount: float = 0.0,
) -> Dict:
    """Add a non-email action (technician assignment, refund, etc.) to approval queue."""
    approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
    item = {
        "approval_id":  approval_id,
        "item_type":    action_type,
        "description":  description,
        "customer_id":  customer_id,
        "ticket_id":    ticket_id,
        "amount":       amount,
        "action_data":  action_data,
        "status":       "pending",
        "created_at":   datetime.utcnow().isoformat(),
        "decided_by":   None,
        "decided_at":   None,
    }
    _QUEUE[approval_id] = item
    return item


def get_pending_approvals(approval_type: Optional[str] = None) -> List[Dict]:
    """Return all pending approval items, optionally filtered by type."""
    items = [v for v in _QUEUE.values() if v["status"] == "pending"]
    if approval_type:
        items = [i for i in items if i["item_type"] == approval_type]
    return sorted(items, key=lambda x: x["created_at"], reverse=True)


def get_all_approvals(limit: int = 50) -> List[Dict]:
    """Return all approval items (any status)."""
    return sorted(_QUEUE.values(), key=lambda x: x["created_at"], reverse=True)[:limit]


def process_approval(approval_id: str, decision: str,
                     decided_by: str = "admin") -> Dict:
    """
    Approve or reject an item.
    For emails: approved items are ready to send via Gmail/SMTP.
    For actions: approved items trigger their downstream workflow.
    """
    if approval_id not in _QUEUE:
        return {"error": f"Approval {approval_id} not found"}

    item = _QUEUE[approval_id]
    if item["status"] != "pending":
        return {"error": f"Already {item['status']}"}

    item["status"]     = decision  # "approved" | "rejected"
    item["decided_by"] = decided_by
    item["decided_at"] = datetime.utcnow().isoformat()
    return item


def get_approval(approval_id: str) -> Optional[Dict]:
    return _QUEUE.get(approval_id)


def get_approved_emails_ready_to_send() -> List[Dict]:
    """Returns approved email items that haven't been sent yet."""
    return [
        v for v in _QUEUE.values()
        if v["status"] == "approved"
        and v.get("item_type", "").startswith("email_")
        and not v.get("sent", False)
    ]


def mark_email_sent(approval_id: str) -> bool:
    if approval_id in _QUEUE:
        _QUEUE[approval_id]["sent"] = True
        _QUEUE[approval_id]["sent_at"] = datetime.utcnow().isoformat()
        return True
    return False
