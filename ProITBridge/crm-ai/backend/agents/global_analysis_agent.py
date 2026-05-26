"""
global_analysis_agent.py — Cross-customer AI analysis agent.

Answers global queries WITHOUT requiring a customer selection:
  "Who is having problems?"
  "Show all open critical issues"
  "Which customers have unresolved complaints?"
  "What are the most common appliance issues?"

Pipeline:
  1. Pull structured data (tickets + customers + appliances)
  2. Hybrid RAG  → relevant policy/doc context
  3. Agentic RAG → multi-step reasoning context
  4. Groq LLM   → narrative insight layer
  5. Return formatted table + LLM insight
"""
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple
from backend.data_loader import (
    get_tickets, get_customers, get_appliances,
    get_technicians, get_warranty_data, get_appliance_by_id,
)
from backend.utils.llm import call_llm, _get_client

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
PRIORITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _days_open(created_date_str: str) -> int:
    """Return how many days a ticket has been open."""
    if not created_date_str:
        return 0
    try:
        created = datetime.strptime(created_date_str.strip(), "%Y-%m-%d").date()
        return (date.today() - created).days
    except Exception:
        return 0


def _build_ticket_table(tickets: List[Dict], customers_map: Dict,
                        appliances_map: Dict, max_rows: int = 20) -> Tuple[List[Dict], str]:
    """
    Build rich ticket rows and a formatted text table.
    Returns (rows_list, formatted_text).
    """
    rows = []
    for t in tickets[:max_rows]:
        cust  = customers_map.get(t["customer_id"], {})
        appl  = appliances_map.get(t.get("appliance_id", ""), {})
        days  = _days_open(t.get("created_date", ""))
        pri   = t.get("priority", "medium").lower()
        rows.append({
            "ticket_id":   t["ticket_id"],
            "customer_id": t["customer_id"],
            "name":        cust.get("name", "Unknown"),
            "city":        cust.get("city", "—"),
            "segment":     cust.get("segment", "—"),
            "issue":       t.get("issue", "—"),
            "status":      t.get("status", "—"),
            "priority":    pri,
            "days_open":   days,
            "appliance":   f"{appl.get('brand','')} {appl.get('model','')}".strip() or "—",
            "technician_id": t.get("technician_id", ""),
            "emoji":       PRIORITY_EMOJI.get(pri, "⚪"),
        })

    # Sort by priority then days open (most urgent first)
    rows.sort(key=lambda r: (PRIORITY_ORDER.get(r["priority"], 2), -r["days_open"]))

    # Build text table
    lines = []
    for r in rows:
        tech_flag = "" if r["technician_id"] else " ⚠ no tech"
        lines.append(
            f"{r['emoji']} {r['customer_id']} | {r['name']:<18} | "
            f"{r['issue'][:50]:<50} | {r['priority'].upper():<8} | "
            f"{r['days_open']}d open{tech_flag}"
        )
    return rows, "\n".join(lines)


def _pattern_summary(rows: List[Dict]) -> str:
    """Derive patterns from open ticket data."""
    if not rows:
        return ""

    # Issue word frequency
    from collections import Counter
    words = []
    for r in rows:
        words += [w.lower() for w in r["issue"].split()
                  if len(w) > 3 and w.lower() not in
                  {"with", "from", "that", "this", "have", "been", "when", "your", "unit"}]
    top_words = [w for w, _ in Counter(words).most_common(5)]

    # City breakdown
    city_counts = Counter(r["city"] for r in rows if r["city"] != "—")
    top_cities  = [f"{c} ({n})" for c, n in city_counts.most_common(3)]

    # No-technician count
    unassigned = sum(1 for r in rows if not r["technician_id"])

    # Priority breakdown
    pri_counts = Counter(r["priority"] for r in rows)

    lines = [
        f"📊 Pattern summary ({len(rows)} tickets):",
        f"  Top issue keywords : {', '.join(top_words)}",
        f"  Cities most affected: {', '.join(top_cities)}",
        f"  Unassigned tickets  : {unassigned}/{len(rows)} have no technician yet",
        f"  By priority         : " +
        " | ".join(f"{p.capitalize()}: {pri_counts.get(p,0)}"
                   for p in ["critical","high","medium","low"]
                   if pri_counts.get(p, 0) > 0),
    ]
    return "\n".join(lines)


# ── query classifier ──────────────────────────────────────────────────────────

def _resolve_filter(query: str) -> Dict:
    """Return filter params from query keywords."""
    q = query.lower()
    filters = {}

    # Priority filter
    for p in ["critical", "high", "medium", "low"]:
        if p in q:
            filters["priority"] = p
            break

    # Status filter — must match data_loader normalised uppercase values
    if any(x in q for x in ["resolved", "closed", "done", "fixed", "completed"]):
        filters["status"] = ["RESOLVED", "CLOSED"]
    elif any(x in q for x in ["all", "every", "total", "across", "percentage", "percent", "ratio", "%"]):
        filters["status"] = ["OPEN", "IN_PROGRESS", "UNDER_REVIEW", "TECHNICIAN_PENDING",
                              "ASSIGNED", "RESOLVED", "CLOSED"]   # include all for stats queries
    else:
        filters["status"] = ["OPEN", "IN_PROGRESS", "UNDER_REVIEW", "TECHNICIAN_PENDING", "ASSIGNED"]

    # City filter
    cities = ["mumbai", "delhi", "bangalore", "chennai", "hyderabad",
              "pune", "kolkata", "ahmedabad", "jaipur", "lucknow"]
    for city in cities:
        if city in q:
            filters["city"] = city.capitalize()
            break

    # Appliance category filter
    categories = {
        "ac": "Air Conditioner", "air conditioner": "Air Conditioner",
        "refrigerator": "Refrigerator", "fridge": "Refrigerator",
        "washing machine": "Washing Machine",
        "microwave": "Microwave",
        "television": "Television", "tv": "Television",
    }
    for kw, cat in categories.items():
        if kw in q:
            filters["appliance_category"] = cat
            break

    return filters


def _apply_filters(tickets: List[Dict], customers_map: Dict,
                   appliances_map: Dict, filters: Dict) -> List[Dict]:
    """Filter ticket list by resolved filter dict."""
    result = []
    status_set = set(filters.get("status", ["OPEN", "IN_PROGRESS", "UNDER_REVIEW",
                                             "TECHNICIAN_PENDING", "ASSIGNED"]))
    for t in tickets:
        if t.get("status") not in status_set:
            continue
        if "priority" in filters and t.get("priority", "").lower() != filters["priority"]:
            continue
        if "city" in filters:
            cust = customers_map.get(t["customer_id"], {})
            # substring match: "Delhi - Sector 5" matches filter "Delhi"
            if filters["city"].lower() not in cust.get("city", "").lower():
                continue
        if "appliance_category" in filters:
            appl = appliances_map.get(t.get("appliance_id", ""), {})
            if appl.get("category", "") != filters["appliance_category"]:
                continue
        result.append(t)
    return result


# ── RAG context helpers ───────────────────────────────────────────────────────

def _rag_context(query: str) -> str:
    """Pull multi-RAG context: hybrid + agentic (gracefully degrades)."""
    ctx_parts = []
    try:
        from backend.rag.hybrid_rag import retrieve as hybrid_retrieve, format_context as hfmt
        h = hybrid_retrieve(query, top_k=3)
        if h:
            ctx_parts.append("Hybrid RAG:\n" + hfmt(h))
    except Exception:
        pass
    try:
        from backend.rag.agentic_rag import retrieve as ag_retrieve, format_context as afmt
        a = ag_retrieve(query, top_k=3)
        if a:
            ctx_parts.append("Agentic RAG:\n" + afmt(a))
    except Exception:
        pass
    return "\n\n".join(ctx_parts) if ctx_parts else ""


# ── main entry ────────────────────────────────────────────────────────────────

def run(query: str, session_id: str = "") -> Dict:
    """
    Answer a global cross-customer query.
    Returns answer text + structured rows for the frontend table card.
    """
    # ── Load data ─────────────────────────────────────────────────────────────
    all_tickets   = get_tickets()
    all_customers = get_customers()
    all_appliances = get_appliances()

    customers_map  = {c["customer_id"]: c for c in all_customers}
    appliances_map = {a["appliance_id"]: a for a in all_appliances}

    # ── Filter ────────────────────────────────────────────────────────────────
    filters = _resolve_filter(query)
    filtered = _apply_filters(all_tickets, customers_map, appliances_map, filters)

    # ── Build table ───────────────────────────────────────────────────────────
    rows, table_text = _build_ticket_table(filtered, customers_map, appliances_map)
    pattern_text     = _pattern_summary(rows)

    if not rows:
        # Tell the user what IS in the data instead of a dead-end message
        all_open  = [t for t in all_tickets if t.get("status") in
                     ("OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED")]
        all_closed = [t for t in all_tickets if t.get("status") in ("RESOLVED","CLOSED")]
        filter_desc = ""
        if filters.get("priority"):
            filter_desc = f" with {filters['priority']} priority"
        if filters.get("city"):
            filter_desc += f" in {filters['city']}"
        return {
            "answer": (
                f"No tickets found{filter_desc} matching those exact filters.\n\n"
                f"Current overview: {len(all_open)} open tickets, {len(all_closed)} resolved. "
                f"Try asking 'Who has open tickets?' or 'Who has critical tickets?'"
            ),
            "rows": [],
            "intent": "global_analysis",
            "agent_used": "global_analysis_agent",
        }

    # ── RAG context ───────────────────────────────────────────────────────────
    rag_ctx = _rag_context(query)

    # ── Groq LLM narrative ────────────────────────────────────────────────────
    llm_insight = ""
    if _get_client():
        system = (
            "You are a senior CRM analyst. Given ticket data, provide a crisp 2-3 sentence "
            "insight about patterns, root causes, and the most urgent action to take. "
            "Do NOT repeat the table — add new insight only."
        )
        user = (
            "Query: " + query + "\n\n" +
            "Ticket summary:\n" + table_text[:800] + "\n\n" +
            pattern_text + "\n\n" +
            "Knowledge base:\n" + rag_ctx[:400] + "\n\n" +
            "Give a short analyst insight."
        )
        llm_insight = call_llm(system, user, session_id, max_tokens=200)

    # Compose final answer
    statuses = filters.get("status", [])
    if "RESOLVED" in statuses and "OPEN" not in statuses:
        status_label = "resolved"
    elif "OPEN" in statuses and "RESOLVED" in statuses:
        status_label = "all"
    else:
        status_label = "open"
    pri_label = filters.get("priority", "all priorities").upper()
    pri_icon = "\U0001f534 " if pri_label == "CRITICAL" else ""
    pri_suffix = " - " + pri_label if pri_label != "ALL PRIORITIES" else ""
    header = (
        "GLOBAL_TABLE_START\n"
        "title:" + pri_icon + "Customers with " + status_label + " issues" + pri_suffix + "\n"
        "count:" + str(len(rows)) + "\n"
    )

    answer = header + table_text + "\nGLOBAL_TABLE_END\n" + pattern_text + "\n"
    if llm_insight:
        answer += "\n\U0001f4a1 AI Insight: " + llm_insight

    return {
        "answer":     answer,
        "rows":       rows,
        "row_count":  len(rows),
        "filters":    filters,
        "intent":     "global_analysis",
        "agent_used": "global_analysis_agent",
    }
