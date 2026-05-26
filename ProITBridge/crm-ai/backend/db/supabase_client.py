"""
supabase_client.py — Supabase operations with sample data fallback.
If Supabase is not configured or unreachable, all reads return sample data
and writes are silently skipped so the app works immediately.
"""
from backend.config import settings
from datetime import datetime
from typing import Optional, List, Dict, Any
import json

_client = None
_use_sample = False


def _get_client():
    global _client, _use_sample
    if _use_sample:
        return None
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
            _use_sample = True
            return None
        try:
            from supabase import create_client
            _client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        except Exception as e:
            print(f"[Supabase] Could not connect: {e} — using sample data")
            _use_sample = True
    return _client


def _is_sample() -> bool:
    _get_client()
    return _use_sample


# ── LEADS ─────────────────────────────────────────────────────────────────────
def get_all_leads() -> List[Dict]:
    if _is_sample():
        from backend.sample_data import get_leads
        return get_leads()
    try:
        res = _get_client().table("leads").select("*, deals(*)").execute()
        return res.data or []
    except Exception:
        from backend.sample_data import get_leads
        return get_leads()


def get_lead_by_id(lead_id: str) -> Optional[Dict]:
    if _is_sample():
        from backend.sample_data import LEADS
        return next((l for l in LEADS if l["id"] == lead_id), None)
    try:
        res = _get_client().table("leads").select("*, deals(*)").eq("id", lead_id).single().execute()
        return res.data
    except Exception:
        from backend.sample_data import LEADS
        return next((l for l in LEADS if l["id"] == lead_id), None)


def upsert_lead(lead: Dict) -> Dict:
    if _is_sample():
        return lead
    try:
        lead["updated_at"] = datetime.utcnow().isoformat()
        res = _get_client().table("leads").upsert(lead).execute()
        return res.data[0] if res.data else lead
    except Exception:
        return lead


# ── DEALS ─────────────────────────────────────────────────────────────────────
def get_all_deals() -> List[Dict]:
    if _is_sample():
        from backend.sample_data import get_deals_with_leads
        return get_deals_with_leads()
    try:
        res = _get_client().table("deals").select("*, leads(name,company,email,title)").order("expected_close_date", desc=False).execute()
        return res.data or []
    except Exception:
        from backend.sample_data import get_deals_with_leads
        return get_deals_with_leads()


def get_deal_by_id(deal_id: str) -> Optional[Dict]:
    if _is_sample():
        from backend.sample_data import get_deal
        return get_deal(deal_id)
    try:
        res = _get_client().table("deals").select("*, leads(*)").eq("id", deal_id).single().execute()
        return res.data
    except Exception:
        from backend.sample_data import get_deal
        return get_deal(deal_id)


def update_deal(deal_id: str, updates: Dict) -> Dict:
    if _is_sample():
        # Update in-memory sample data
        from backend import sample_data
        for deal in sample_data.DEALS:
            if deal["id"] == deal_id:
                deal.update(updates)
                return deal
        return updates
    try:
        updates["updated_at"] = datetime.utcnow().isoformat()
        res = _get_client().table("deals").update(updates).eq("id", deal_id).execute()
        return res.data[0] if res.data else updates
    except Exception:
        return updates


def upsert_deal(deal: Dict) -> Dict:
    if _is_sample():
        return deal
    try:
        deal["updated_at"] = datetime.utcnow().isoformat()
        res = _get_client().table("deals").upsert(deal).execute()
        return res.data[0] if res.data else deal
    except Exception:
        return deal


# ── ACTIVITIES ────────────────────────────────────────────────────────────────
def get_activities(deal_id: Optional[str] = None, limit: int = 20) -> List[Dict]:
    if _is_sample():
        from backend.sample_data import get_activities as sa
        return sa(deal_id=deal_id, limit=limit)
    try:
        query = _get_client().table("activities").select("*").order("created_at", desc=True).limit(limit)
        if deal_id:
            query = query.eq("deal_id", deal_id)
        res = query.execute()
        return res.data or []
    except Exception:
        from backend.sample_data import get_activities as sa
        return sa(deal_id=deal_id, limit=limit)


def insert_activity(activity: Dict) -> Dict:
    if _is_sample():
        from backend import sample_data
        activity["id"] = f"act-{len(sample_data.ACTIVITIES)+1:03d}"
        activity["created_at"] = datetime.utcnow().isoformat()
        sample_data.ACTIVITIES.append(activity)
        return activity
    try:
        activity["created_at"] = datetime.utcnow().isoformat()
        res = _get_client().table("activities").insert(activity).execute()
        return res.data[0] if res.data else activity
    except Exception:
        return activity


# ── FOLLOW-UPS ────────────────────────────────────────────────────────────────
def get_follow_ups(rep_id: Optional[str] = None) -> List[Dict]:
    if _is_sample():
        from backend.sample_data import get_follow_ups as sfu
        return sfu()
    try:
        query = _get_client().table("follow_ups").select("*, deals(title)").eq("status", "pending")
        if rep_id:
            query = query.eq("rep_id", rep_id)
        res = query.execute()
        return res.data or []
    except Exception:
        from backend.sample_data import get_follow_ups as sfu
        return sfu()


def insert_follow_up(follow_up: Dict) -> Dict:
    if _is_sample():
        from backend import sample_data
        follow_up["id"] = f"fu-{len(sample_data.FOLLOW_UPS)+1:03d}"
        follow_up["created_at"] = datetime.utcnow().isoformat()
        sample_data.FOLLOW_UPS.append(follow_up)
        return follow_up
    try:
        follow_up["created_at"] = datetime.utcnow().isoformat()
        res = _get_client().table("follow_ups").insert(follow_up).execute()
        return res.data[0] if res.data else follow_up
    except Exception:
        return follow_up


# ── EMAIL DRAFTS ──────────────────────────────────────────────────────────────
_draft_store: List[Dict] = []

def save_email_draft(draft: Dict) -> Dict:
    draft["id"] = f"draft-{len(_draft_store)+1:03d}"
    draft["created_at"] = datetime.utcnow().isoformat()
    draft["status"] = "pending_approval"
    if not _is_sample():
        try:
            res = _get_client().table("email_drafts").insert(draft).execute()
            return res.data[0] if res.data else draft
        except Exception:
            pass
    _draft_store.append(draft)
    return draft


def approve_email_draft(draft_id: str) -> Dict:
    for d in _draft_store:
        if d["id"] == draft_id:
            d["status"] = "approved"
            return d
    if not _is_sample():
        try:
            res = _get_client().table("email_drafts").update({"status": "approved"}).eq("id", draft_id).execute()
            return res.data[0] if res.data else {}
        except Exception:
            pass
    return {}


def get_pending_drafts(deal_id: Optional[str] = None) -> List[Dict]:
    local = [d for d in _draft_store if d.get("status") == "pending_approval"]
    if deal_id:
        local = [d for d in local if d.get("deal_id") == deal_id]
    if local or _is_sample():
        return local
    try:
        query = _get_client().table("email_drafts").select("*").eq("status", "pending_approval")
        if deal_id:
            query = query.eq("deal_id", deal_id)
        res = query.execute()
        return res.data or []
    except Exception:
        return local


# ── MCP CONTEXT ───────────────────────────────────────────────────────────────
_context_store: Dict[str, List[Dict]] = {}

def save_context(session_id: str, context: List[Dict]) -> None:
    _context_store[session_id] = context
    if _is_sample():
        return
    try:
        _get_client().table("agent_context").upsert({
            "session_id": session_id,
            "context": json.dumps(context),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        pass


def load_context(session_id: str) -> List[Dict]:
    if session_id in _context_store:
        return _context_store[session_id]
    if _is_sample():
        return []
    try:
        res = _get_client().table("agent_context").select("context").eq("session_id", session_id).execute()
        if res.data:
            return json.loads(res.data[0]["context"])
    except Exception:
        pass
    return []


# ── INGESTION LOGS ────────────────────────────────────────────────────────────
def log_ingestion(source: str, count: int, status: str = "success") -> None:
    if _is_sample():
        return
    try:
        _get_client().table("ingestion_logs").insert({
            "source": source, "chunk_count": count,
            "status": status, "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception:
        pass
