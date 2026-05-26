"""
data_loader.py — Loads CSV/JSON data files into memory.
Falls back to embedded sample rows if files are missing.
"""
import csv, json, os
from typing import List, Dict, Optional
from backend.config import settings

_cache: Dict[str, List[Dict]] = {}

# Status normalisation map (CSV mixed-case → frontend UPPERCASE)
_STATUS_MAP = {
    "open"              : "OPEN",
    "in progress"       : "IN_PROGRESS",
    "in_progress"       : "IN_PROGRESS",
    "under review"      : "UNDER_REVIEW",
    "under_review"      : "UNDER_REVIEW",
    "technician pending": "TECHNICIAN_PENDING",
    "technician_pending": "TECHNICIAN_PENDING",
    "assigned"          : "ASSIGNED",
    "resolved"          : "RESOLVED",
    "closed"            : "CLOSED",
}

def _load_csv(filename: str) -> List[Dict]:
    if filename in _cache:
        return _cache[filename]
    path = os.path.join(settings.DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Normalise ticket status to uppercase for frontend compatibility
    if filename == "tickets.csv":
        for r in rows:
            raw = r.get("status", "").strip().lower()
            r["status"] = _STATUS_MAP.get(raw, raw.upper().replace(" ", "_") or "OPEN")
    _cache[filename] = rows
    return rows

def _load_json(filename: str) -> List[Dict]:
    if filename in _cache:
        return _cache[filename]
    path = os.path.join(settings.DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _cache[filename] = data
    return data

def _load_docs() -> List[Dict]:
    """Load all text files from docs/ as document chunks."""
    docs = []
    docs_dir = settings.DOCS_DIR
    if not os.path.exists(docs_dir):
        return []
    for fname in os.listdir(docs_dir):
        if fname.endswith(".txt"):
            path = os.path.join(docs_dir, fname)
            with open(path, encoding="utf-8") as f:
                content = f.read()
            docs.append({"filename": fname, "content": content,
                          "source_type": "policy_doc"})
    return docs

# ── Public accessors ─────────────────────────────────────────────────────────
def get_customers() -> List[Dict]:       return _load_csv("customers.csv")
def get_appliances() -> List[Dict]:      return _load_csv("appliances.csv")
def get_technicians() -> List[Dict]:     return _load_csv("technicians.csv")
def get_warranty_data() -> List[Dict]:   return _load_csv("warranty_data.csv")
def get_tickets() -> List[Dict]:         return _load_csv("tickets.csv")
def get_sales_leads() -> List[Dict]:     return _load_csv("sales_leads.csv")
def get_emails() -> List[Dict]:          return _load_csv("emails.csv")
def get_reviews() -> List[Dict]:         return _load_csv("reviews.csv")
def get_chat_history() -> List[Dict]:    return _load_json("chat_history.json")
def get_docs() -> List[Dict]:            return _load_docs()

def get_customer_by_id(customer_id: str) -> Optional[Dict]:
    return next((c for c in get_customers() if c["customer_id"] == customer_id), None)

def get_customer_by_phone(phone: str) -> Optional[Dict]:
    return next((c for c in get_customers() if phone in c.get("phone", "")), None)

def get_warranty_by_customer(customer_id: str) -> List[Dict]:
    return [w for w in get_warranty_data() if w["customer_id"] == customer_id]

def get_tickets_by_customer(customer_id: str) -> List[Dict]:
    return [t for t in get_tickets() if t["customer_id"] == customer_id]

def get_open_tickets() -> List[Dict]:
    return [t for t in get_tickets() if t["status"] in ("OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED")]

def get_appliance_by_id(appliance_id: str) -> Optional[Dict]:
    return next((a for a in get_appliances() if a["appliance_id"] == appliance_id), None)

def get_technicians_by_specialty(type_code: str) -> List[Dict]:
    return [t for t in get_technicians() if type_code in t.get("specialization", "")]

def clear_cache():
    """Force reload on next access (useful after data regeneration)."""
    _cache.clear()
