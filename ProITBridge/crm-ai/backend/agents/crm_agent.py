"""
crm_agent.py — CRM operations: customer lookup, ticket management, warranty checks.
"""
from typing import Dict, Optional
from backend.data_loader import (get_customer_by_id, get_customer_by_phone,
                                   get_warranty_by_customer, get_tickets_by_customer,
                                   get_open_tickets)
from backend.guardrails.guardrails import validate_warranty_claim

def lookup_customer(identifier: str) -> Dict:
    """Look up customer by ID or phone number."""
    customer = get_customer_by_id(identifier)
    if not customer:
        customer = get_customer_by_phone(identifier)
    if not customer:
        return {"error": f"No customer found for: {identifier}"}

    cid = customer["customer_id"]
    warranties = get_warranty_by_customer(cid)
    tickets    = get_tickets_by_customer(cid)
    active_w   = [w for w in warranties if w.get("status") == "Active"]
    open_t     = [t for t in tickets    if t.get("status") in ("Open","In Progress")]

    return {
        "customer": customer,
        "warranties": warranties,
        "active_warranties": len(active_w),
        "tickets": tickets,
        "open_tickets": len(open_t),
        "summary": (f"{customer['name']} | {customer['city']} | Segment: {customer['segment']} | "
                    f"{len(active_w)} active warranty(ies) | {len(open_t)} open ticket(s)"),
    }

def check_warranty(customer_id: str, warranty_id: Optional[str] = None) -> Dict:
    """Return warranty status with validity check."""
    warranties = get_warranty_by_customer(customer_id)
    if not warranties:
        return {"valid": False, "message": "No warranty records found."}

    if warranty_id:
        w = next((w for w in warranties if w["warranty_id"] == warranty_id), None)
    else:
        w = next((w for w in warranties if w.get("status") == "Active"), warranties[0])

    valid, msg = validate_warranty_claim(customer_id, w)
    return {"valid": valid, "message": msg, "warranty": w}

def get_ticket_summary(customer_id: str) -> Dict:
    """Summarize all tickets for a customer."""
    tickets = get_tickets_by_customer(customer_id)
    by_status = {}
    for t in tickets:
        s = t.get("status", "Unknown")
        by_status[s] = by_status.get(s, 0) + 1

    return {
        "total": len(tickets),
        "by_status": by_status,
        "open": [t for t in tickets if t.get("status") in ("Open","In Progress")],
        "resolved": [t for t in tickets if t.get("status") in ("Resolved","Closed")],
    }

def get_pipeline_stats() -> Dict:
    """Return CRM pipeline overview."""
    from backend.data_loader import get_sales_leads, get_customers
    leads    = get_sales_leads()
    customers= get_customers()
    open_t   = get_open_tickets()

    stages = {}
    for l in leads:
        s = l.get("stage","Unknown")
        stages[s] = stages.get(s,0)+1

    total_value = sum(int(l.get("estimated_value",0)) for l in leads
                      if l.get("stage") not in ("Closed Lost",))

    return {
        "total_customers": len(customers),
        "total_leads": len(leads),
        "lead_by_stage": stages,
        "pipeline_value": total_value,
        "open_tickets": len(open_t),
    }
