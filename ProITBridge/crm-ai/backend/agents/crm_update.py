"""
crm_update.py — CRM Update Agent.
Updates deal records in Supabase and logs all changes as activities.
Syncs back to HubSpot/Zoho if API keys are configured.
"""
from backend.db import supabase_client
from backend.config import settings
from datetime import datetime
from typing import Dict, Optional, List


def update_deal_stage(deal_id: str, new_stage: str, notes: str = "", rep_id: str = "") -> Dict:
    """Update a deal's pipeline stage and log the change."""
    updates = {
        "stage": new_stage,
        "last_contact_date": datetime.utcnow().date().isoformat()
    }
    if notes:
        updates["notes"] = notes

    result = supabase_client.update_deal(deal_id, updates)

    # Log activity
    supabase_client.insert_activity({
        "deal_id": deal_id,
        "type": "stage_change",
        "summary": f"Deal moved to '{new_stage}'. {notes}",
        "rep_id": rep_id
    })

    return result


def update_last_contact(deal_id: str, contact_type: str = "email", summary: str = "", rep_id: str = "") -> Dict:
    """Update last contact date and log the activity."""
    today = datetime.utcnow().date().isoformat()

    result = supabase_client.update_deal(deal_id, {
        "last_contact_date": today
    })

    supabase_client.insert_activity({
        "deal_id": deal_id,
        "type": contact_type,
        "summary": summary or f"Contact made via {contact_type}",
        "rep_id": rep_id
    })

    return result


def add_follow_up(
    deal_id: str,
    task: str,
    due_date: str,
    rep_id: str = "",
    priority: str = "medium"
) -> Dict:
    """Create a follow-up task for a deal."""
    return supabase_client.insert_follow_up({
        "deal_id": deal_id,
        "task": task,
        "due_date": due_date,
        "rep_id": rep_id,
        "priority": priority,
        "status": "pending"
    })


def update_deal_value(deal_id: str, new_value: float, reason: str = "", rep_id: str = "") -> Dict:
    """Update deal value with audit trail."""
    old_deal = supabase_client.get_deal_by_id(deal_id)
    old_value = old_deal.get("value", 0) if old_deal else 0

    result = supabase_client.update_deal(deal_id, {"value": new_value})

    supabase_client.insert_activity({
        "deal_id": deal_id,
        "type": "deal_update",
        "summary": f"Deal value updated: ${old_value:,.0f} → ${new_value:,.0f}. Reason: {reason}",
        "rep_id": rep_id
    })

    return result


def add_deal_notes(deal_id: str, notes: str, rep_id: str = "") -> Dict:
    """Append notes to a deal."""
    deal = supabase_client.get_deal_by_id(deal_id)
    existing_notes = deal.get("notes", "") if deal else ""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    updated_notes = f"{existing_notes}\n\n[{timestamp}] {notes}".strip()

    result = supabase_client.update_deal(deal_id, {"notes": updated_notes})

    supabase_client.insert_activity({
        "deal_id": deal_id,
        "type": "note",
        "summary": notes[:200],
        "rep_id": rep_id
    })

    return result


def bulk_update_deals(updates: List[Dict]) -> List[Dict]:
    """Update multiple deals at once. Each item: { deal_id, ...fields }"""
    results = []
    for upd in updates:
        deal_id = upd.pop("deal_id", None)
        if deal_id:
            results.append(supabase_client.update_deal(deal_id, upd))
    return results
