"""
orchestrator.py — Pure Python multi-agent orchestrator.
Handles: name lookups, context-aware follow-ups, data queries, all agent routing.
"""
import re
from typing import Dict, Optional
from backend.mcp.context_manager import get_entity, set_entity, save_turn
from backend.guardrails.guardrails import sanitize_input

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

INTENT_RULES = [
    # early-catch: specific policy questions that share keywords with data_query/warranty
    ("policy_query",
     r"how many days|days.*return|return.*within|days.*to return|return.*days|void.*warrant|warrant.*void|warrant.*condition|condition.*warrant|standard.*repair|repair.*turnaround|turnaround.*time|repair.*time.*polic"),

    # early-catch: list/show queries that should be pure data lookups — must come BEFORE global_analysis
    ("data_query",
     r"list all customer.*name|list all customer.*id|customer.*name.*and.*id|"
     r"list all customers who|list all customers that|customers who have|customers who own|"
     r"show.*all tickets.*last|tickets.*raised.*last|tickets.*in the last|"
     r"last \d+ days|past \d+ days|show all customer"),

    # ── delay / knowledge-graph analysis (highest specificity) ──────────────
    ("delay_analysis",
     r"why.*delay|delay.*reason|why.*pending|why.*not.*resolved|why.*stuck|"
     r"knowledge graph|graph.*analysis|delay.*analysis|what.*causing.*delay|"
     r"bottleneck|overload|escalat.*needed|unassigned.*ticket|no.*technician|"
     r"pending.*long|open.*too long|days.*open|taking.*long"),

    # ── global cross-customer analysis ────────────────────────────────────────
    ("global_analysis",
     r"who.*having|who.*facing|who.*problem|who has.*ticket|who.*issue|"
     r"all.*customer.*issue|all.*open.*issue|all.*complaint|"
     r"show.*all.*problem|list.*problem|which customer|customers.*having|"
     r"people.*facing|anyone.*having|how.*people.*problem|"
     r"most.*common.*issue|most.*common.*problem|common.*appliance|top.*issue|common.*complaint|"
     r"breaking.*down|break.*down|appliance.*fail|fail.*appliance|most.*fail|"
     r"which.*appliance.*problem|which.*appliance.*break|appliance.*breakdown|"
     r"critical.*ticket|critical.*customer|"
     r"urgent.*attention|need.*attention|need.*urgent|customers.*urgent|"
     r"high.*priority.*customer|all.*ticket|across.*customer|"
     r"overall.*issue|overview.*problem|everyone.*having|problems.*across|"
     r"percentage.*ticket|ticket.*percentage|percent.*open|open.*percent|"
     r"ratio.*ticket|ticket.*ratio|open.*vs.*resolv|resolv.*vs.*open|"
     r"ticket.*breakdown|breakdown.*ticket|how many.*open.*ticket|"
     r"unresolved.*ticket|open.*across|list.*all.*customer|which.*customer.*severe|"
     r"severe.*issue|severity.*issue|most.*severe"),

    ("data_query",
     r"how many|total number|give me all|show all|list all|count of|"
     r"all appliance|all customer|appliance name|appliance type|appliance list|"
     r"customer list|lead list|technician list|show technician|"
     r"customers.*from|from.*city|how many.*city|city.*customer|"
     r"customer.*name.*id|list.*customer.*name|all customer.*id|"
     r"customers.*have.*|customers.*own|who.*own.*appliance|have.*refrigerator|"
     r"have.*washing|have.*microwave|have.*television|have.*\bac\b|"
     r"last.*days|past.*days|raised.*last|tickets.*last|recent.*ticket|"
     r"multiple.*issue|multiple.*ticket|active.*issue|active.*technician|"
     r"technician.*active|currently.*active.*tech|high.*priority.*ticket|"
     r"low.*priority.*ticket|critical.*ticket.*open|open.*critical"),

    ("warranty",       r"my warranty|check warranty|warranty status|warranty.*expire|coverage check|warranty active|warranty claim|is.*under warranty|warranty.*on|warranty.*for|what.*warranty|tell.*warranty|show.*warranty|warranty.*left|warranty.*valid|warranty.*cover"),
    ("recommendation", r"recommend|suggest|best product|which appliance|buy|upgrade|looking for"),
    ("validation",     r"validate|valid claim|refund eligib|reject claim"),
    ("approval",       r"pending approval|manager review|approval queue"),
    ("crm_lookup",     r"pipeline|lead status|crm stats|total leads|total revenue"),

    ("email",
     r"draft.*email|write.*email|compose.*email|send.*email|email.*for|email.*to|"
     r"generate.*email|create.*email|prepare.*email|ticket.*confirmation.*email|"
     r"apology.*email|escalation.*email|technician.*email|welcome.*email|"
     r"warranty.*email|repair.*email|send.*update|send.*message|send.*notification|"
     r"notify.*customer|message.*customer|update.*customer.*email|email.*customer"),

    ("customer_lookup",
     r"status of|details of|info on|who is|tickets of|warranty of|appliances of|"
     r"customer profile|tell me.*about|everything about|what problem|what issue|"
     r"what.*having|problem.*having|complaints.*of|history of|what is.*facing|"
     r"facing.*issue|what.*experiencing|experiencing.*with|what.*going on with|"
     r"what.*trouble|trouble.*with|what.*wrong with|show me.*customer|"
     r"give me.*info|profile of|overview of|.*'s problem|.*'s issue|"
     r".*'s ticket|.*'s warranty|what.*arun|what.*priya|what.*rahul|"
     r"tell.*arun|tell.*priya|arun.*problem|priya.*problem|"
     r"arun.*issue|priya.*issue|about.*customer"),

    ("policy_query",
     r"policy|return policy|refund|warranty policy|what.*covered|"
     r"how.*claim|claim process|repair cost|eligible|installation|manual|"
     r"troubleshoot|faq|frequently asked|how.*work|what.*happen|procedure|"
     r"step.*by.*step|what.*include|what.*exclude|how long|within.*days|"
     r"do.*charge|is.*free|cost.*repair|"
     r"void.*warranty|warranty.*void|warrant.*condition|condition.*warrant|"
     r"second.*visit|service.*charge|charge.*service|visit.*charge|"
     r"policy.*if|if.*policy|repair.*incorrectly|incorrect.*repair|"
     r"technician.*cannot|cannot.*assign|escalation.*process|escalat.*work|"
     r"replacement.*policy|product.*replace|return.*product|days.*return|"
     r"how many days|refund.*process|what happens"),

    ("support",
     r"not working|broken|fault|noise|leak|flickering|heating"),
]


def classify_intent(query: str) -> str:
    q = query.lower()
    for intent, pattern in INTENT_RULES:
        if re.search(pattern, q):
            return intent
    return "general"


def extract_customer_id(query: str, session_id: str) -> Optional[str]:
    """Resolve customer from: CUST### in query > name in query > session context."""
    match = re.search(r"CUST\d{3}", query, re.IGNORECASE)
    if match:
        return match.group(0).upper()
    name_id = _lookup_by_name(query)
    if name_id:
        return name_id
    ctx_id = get_entity(session_id, "customer_id")
    if ctx_id:
        return ctx_id
    return None


def _lookup_by_name(query: str) -> Optional[str]:
    try:
        from backend.data_loader import get_customers
        customers = get_customers()
        q = query.lower()
        for c in customers:
            if c["name"].lower() in q:
                return c["customer_id"]
        for c in customers:
            parts = c["name"].lower().split()
            if len(parts) >= 2 and parts[0] in q and parts[-1] in q:
                return c["customer_id"]
        for c in customers:
            parts = c["name"].lower().split()
            if len(parts) >= 2:
                if parts[-1] in q and parts[0] in q:
                    return c["customer_id"]
    except Exception:
        pass
    return None


def _suggest_similar_names(query: str) -> str:
    try:
        from backend.data_loader import get_customers
        customers = get_customers()
        q = query.lower()
        hits = [c["name"] for c in customers
                if any(p in q for p in c["name"].lower().split() if len(p) > 3)]
        if hits:
            return "Did you mean: " + ", ".join(hits[:3]) + "?"
    except Exception:
        pass
    return ""


def _load_policy_docs(query: str = "") -> str:
    """
    Load policy docs/ txt files, prioritising those most relevant to the query.
    Always includes return_policy.txt and warranty_policy.txt first, then faq.txt,
    then any other docs whose filename matches a keyword in the query.
    """
    try:
        from backend.data_loader import get_docs
        docs = get_docs()
        if not docs:
            return ""

        q = query.lower()

        # Tier 1 — always include: core policy docs
        CORE = {"return_policy.txt", "warranty_policy.txt", "faq.txt"}
        # Tier 2 — query-keyword matched docs
        KW_MAP = {
            "ac": "ac_manual.txt", "air conditioner": "ac_manual.txt",
            "fridge": "fridge_manual.txt", "refrigerator": "fridge_manual.txt",
            "washing": "washing_machine_manual.txt",
            "microwave": "microwave_manual.txt",
            "tv": "tv_manual.txt", "television": "tv_manual.txt",
            "install": "installation_guide.txt", "installation": "installation_guide.txt",
            "troubleshoot": "troubleshooting_guide.txt", "error": "troubleshooting_guide.txt",
        }

        tier1, tier2, rest = [], [], []
        for d in docs:
            fname = d.get("filename", "")
            body  = d.get("content", "")
            entry = f"[{fname}]\n{body[:1500]}"  # increased cap to 1500 chars
            if fname in CORE:
                tier1.append(entry)
            elif any(kw in q for kw, fn in KW_MAP.items() if fn == fname):
                tier2.append(entry)
            else:
                rest.append(entry)

        # Return core first, then relevant, then others — cap total at 8 docs
        ordered = tier1 + tier2 + rest
        return "\n\n".join(ordered[:8])
    except Exception:
        return ""


def _get_topic_context(session_id: str) -> str:
    try:
        from backend.mcp.context_manager import get_context
        ctx = get_context(session_id)
        for turn in reversed(ctx):
            if turn.get("role") == "user":
                return turn.get("content", "")
    except Exception:
        pass
    return ""


def _handle_data_query(query: str, customer_id: Optional[str], session_id: str = "") -> Optional[str]:
    """Answer factual questions directly from CSV — no LLM needed."""
    from backend.data_loader import (get_appliances, get_customers, get_tickets,
                                      get_open_tickets, get_sales_leads, get_technicians,
                                      get_warranty_by_customer, get_tickets_by_customer)
    q = query.lower()

    if re.search(r"^(give me the count|total|count|how many|number)$", q.strip()):
        last = _get_topic_context(session_id).lower()
        if "appliance" in last:
            q = "how many appliances"
        elif "ticket" in last or "issue" in last:
            q = "how many tickets"
        elif "customer" in last:
            q = "how many customers"
        elif "lead" in last:
            q = "how many leads"

    bought_match = re.search(r"bought\s+([\w ]+?)(?:\?|$)", q)
    if bought_match:
        cat_query = bought_match.group(1).strip().lower()
        from backend.data_loader import get_warranty_data
        appliances = get_appliances()
        warranties = get_warranty_data()
        matching_appl = [a["appliance_id"] for a in appliances
                         if cat_query in a.get("category","").lower()
                         or cat_query in a.get("brand","").lower()
                         or cat_query in a.get("model","").lower()
                         or cat_query in a.get("type_code","").lower()]
        buyers = {w["customer_id"] for w in warranties if w["appliance_id"] in matching_appl}
        if matching_appl:
            return f"Customers who bought {bought_match.group(1).strip()}: {len(buyers)}"

    # ── Customers who have/own a specific appliance ───────────────────────────
    have_match = re.search(r"customers?.*(have|own|with|registered|using)\s+(?:a\s+)?([\w\s]+?)(?:\?|$|\.|in the)", q)
    if have_match and re.search(r"customer", q):
        cat_q = have_match.group(2).strip().lower()
        # Skip if matched text is about issues/tickets, not appliances
        if re.search(r"issue|ticket|problem|complaint|multiple|active|open", cat_q):
            have_match = None
    if have_match and re.search(r"customer", q):
        cat_q = have_match.group(2).strip().lower()
        appliance_cats = {"refrigerator":"Refrigerator","fridge":"Refrigerator",
                          "ac":"Air Conditioner","air conditioner":"Air Conditioner",
                          "washing machine":"Washing Machine","washer":"Washing Machine",
                          "microwave":"Microwave","tv":"TV","television":"TV"}
        matched_cat = None
        for kw, cat in appliance_cats.items():
            if kw in cat_q:
                matched_cat = cat
                break
        if matched_cat:
            from backend.data_loader import get_warranty_data
            appliances = get_appliances()
            warranties = get_warranty_data()
            customers  = get_customers()
            cat_appls  = {a["appliance_id"] for a in appliances if a.get("category","") == matched_cat}
            cust_ids   = {w["customer_id"] for w in warranties if w["appliance_id"] in cat_appls}
            cust_map   = {c["customer_id"]: c for c in customers}
            lines = [f"Customers with a {matched_cat}: {len(cust_ids)}\n"]
            for cid in sorted(cust_ids):
                c = cust_map.get(cid, {})
                lines.append(f"  {cid} | {c.get('name',cid)} | {c.get('segment','')} | {c.get('city','')}")
            return "\n".join(lines)

    # ── List all customer names and IDs ───────────────────────────────────────
    if re.search(r"customer.*name.*id|list.*customer.*name|all customer.*id|customer.*id.*name", q):
        customers = get_customers()
        lines = [f"All {len(customers)} customers:\n"]
        for c in customers:
            lines.append(f"  {c['customer_id']} | {c['name']} | {c.get('segment','')} | {c.get('city','')}")
        return "\n".join(lines)

    # ── Customers with multiple active issues ─────────────────────────────────
    if re.search(r"multiple.*issue|multiple.*ticket|more than one.*ticket|several.*issue|active.*issue", q):
        from backend.data_loader import get_tickets
        all_tickets = get_tickets()
        open_statuses = {"OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED"}
        cust_open = {}
        for t in all_tickets:
            if t.get("status","") in open_statuses:
                cid = t["customer_id"]
                cust_open[cid] = cust_open.get(cid, 0) + 1
        multi = {cid: cnt for cid, cnt in cust_open.items() if cnt > 1}
        customers = {c["customer_id"]: c for c in get_customers()}
        lines = [f"Customers with multiple active issues: {len(multi)}\n"]
        for cid, cnt in sorted(multi.items(), key=lambda x: -x[1]):
            c = customers.get(cid, {})
            lines.append(f"  {cid} | {c.get('name', cid)} | {cnt} open tickets | {c.get('segment','')} | {c.get('city','')}")
        if not multi:
            lines = ["No customers currently have more than one active/open ticket."]
        return "\n".join(lines)

    # ── Active technicians ────────────────────────────────────────────────────
    if re.search(r"active.*technician|technician.*active|currently.*active|how many.*tech", q):
        techs = get_technicians()
        active = [t for t in techs if str(t.get("available","")).lower() in ("true","yes","1","available")]
        lines = [f"Active/Available technicians: {len(active)} of {len(techs)} total\n"]
        for t in active:
            lines.append(f"  {t['name']} | {t.get('specialization','')} | {t.get('city','')} | Rating: {t.get('rating','')}")
        if not active:
            lines = [f"All {len(techs)} technicians (no availability data):\n"]
            for t in techs:
                lines.append(f"  {t['name']} | {t.get('specialization','')} | {t.get('city','')} | Rating: {t.get('rating','')}")
        return "\n".join(lines)

    # ── Tickets in last N days ────────────────────────────────────────────────
    days_match = re.search(r"last\s+(\d+)\s+days?|past\s+(\d+)\s+days?|recent\s+(\d+)\s+days?", q)
    if days_match and re.search(r"ticket|issue|complaint", q):
        from backend.data_loader import get_tickets
        import datetime
        n_days = int(next(g for g in days_match.groups() if g))
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=n_days)).strftime("%Y-%m-%d")
        all_t  = get_tickets()
        recent = [t for t in all_t if t.get("created_at","") >= cutoff]
        if not recent:
            recent = all_t  # fallback: return all if no date field
            note = " (no date filter — showing all tickets)"
        else:
            note = ""
        lines = [f"Tickets in the last {n_days} days{note}: {len(recent)}\n"]
        for t in sorted(recent, key=lambda x: x.get("created_at",""), reverse=True)[:15]:
            lines.append(f"  [{t.get('priority','?').upper():8}] {t['ticket_id']} | {t['customer_id']} | {t['issue'][:50]} | {t.get('status','')} | {t.get('created_at','')}")
        return "\n".join(lines)

    # ── High/low/critical priority open tickets ───────────────────────────────
    pri_match = re.search(r"(critical|high|medium|low)\s*[\-\s]*priority", q)
    if pri_match and re.search(r"ticket|issue", q):
        from backend.data_loader import get_tickets
        pri = pri_match.group(1).lower()
        all_t  = get_tickets()
        open_s = {"OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED"}
        matched = [t for t in all_t if t.get("priority","").lower() == pri
                   and (t.get("status","") in open_s if re.search(r"open|active|unresolved", q) else True)]
        customers = {c["customer_id"]: c["name"] for c in get_customers()}
        lines = [f"{pri.capitalize()}-priority {'open ' if re.search(r'open|active', q) else ''}tickets: {len(matched)}\n"]
        for t in matched[:15]:
            lines.append(f"  {t['ticket_id']} | {customers.get(t['customer_id'], t['customer_id'])} | {t['issue'][:55]} | {t.get('status','')}")
        return "\n".join(lines)

    if re.search(r"appliance|product|refrigerator|fridge|\bac\b|washing machine|microwave|television|\btv\b|coolbreeze|frostking|washpro|microchef|visionx", q):
        appliances = get_appliances()
        by_cat = {}
        for a in appliances:
            by_cat.setdefault(a.get("category","?"), []).append(f"{a['brand']} {a['model']}")
        if re.search(r"how many|total|count|number", q):
            lines = [f"Total appliances: {len(appliances)} across {len(by_cat)} categories\n"]
            for cat, models in by_cat.items():
                lines.append(f"  {cat}: {len(models)} model(s) — {', '.join(models)}")
            return "\n".join(lines)
        else:
            lines = [f"All {len(appliances)} appliances:\n"]
            for cat, models in by_cat.items():
                lines.append(f"  {cat}: {', '.join(models)}")
            return "\n".join(lines)

    if re.search(r"ticket|issue|complaint|open|pending", q):
        if customer_id:
            tickets = get_tickets_by_customer(customer_id)
            tickets_sorted = sorted(tickets, key=lambda t: PRIORITY_ORDER.get(t.get("priority","medium").lower(), 2))
            open_t   = [t for t in tickets_sorted if t["status"] in ("OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED")]
            closed_t = [t for t in tickets_sorted if t["status"] in ("RESOLVED","CLOSED")]
            lines = [f"Tickets for {customer_id}: {len(tickets)} total\n",
                     f"  Open/In Progress: {len(open_t)}",
                     f"  Resolved/Closed:  {len(closed_t)}"]
            if open_t:
                lines.append("\nOpen issues (priority order):")
                for t in open_t:
                    lines.append(f"  [{t['priority'].upper():8}] {t['issue'][:55]}  ({t['ticket_id']})")
            return "\n".join(lines)
        else:
            from backend.data_loader import get_tickets
            all_t = get_tickets()
            open_statuses   = {"OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED"}
            closed_statuses = {"RESOLVED","CLOSED"}
            open_t   = [t for t in all_t if t.get("status","") in open_statuses]
            closed_t = [t for t in all_t if t.get("status","") in closed_statuses]
            total = len(all_t)
            open_pct   = round(len(open_t)   / total * 100) if total else 0
            closed_pct = round(len(closed_t) / total * 100) if total else 0

            # Percentage / ratio question
            if re.search(r"percentage|percent|ratio|%|vs|versus|open.*resolv|resolv.*open", q):
                by_status = {}
                for t in all_t:
                    s = t.get("status","?")
                    by_status[s] = by_status.get(s, 0) + 1
                lines = [f"Ticket status breakdown ({total} total):\n",
                         f"  Open/Active : {len(open_t)} ({open_pct}%)",
                         f"  Resolved    : {len(closed_t)} ({closed_pct}%)",
                         "\nBy status:"]
                for s in ["OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED","RESOLVED","CLOSED"]:
                    if s in by_status:
                        lines.append(f"  {s}: {by_status[s]}")
                return "\n".join(lines)

            sorted_t = sorted(open_t, key=lambda t: PRIORITY_ORDER.get(t.get("priority","medium").lower(), 2))
            by_pri = {}
            for t in open_t:
                p = t.get("priority","?")
                by_pri[p] = by_pri.get(p, 0) + 1
            lines = [f"Open tickets: {len(open_t)} of {total} total ({open_pct}% open)\n"]
            for p in ["critical","high","medium","low"]:
                if p in by_pri:
                    lines.append(f"  {p.capitalize()}: {by_pri[p]}")
            if sorted_t:
                lines.append("\nTop critical/high priority:")
                for t in sorted_t[:5]:
                    lines.append(f"  [{t['priority'].upper():8}] {t['issue'][:50]}  {t['customer_id']}")
            return "\n".join(lines)

    if re.search(r"customer", q):
        customers = get_customers()
        # City filter — "how many customers from Hyderabad?"
        city_match = re.search(
            r"from\s+([a-z]+)|in\s+([a-z]+)|([a-z]+)\s+customer",
            q
        )
        KNOWN_CITIES = {"mumbai","delhi","bangalore","chennai","hyderabad",
                        "pune","kolkata","ahmedabad","jaipur","lucknow"}
        city_filter = None
        if city_match:
            candidate = next(g for g in city_match.groups() if g)
            if candidate in KNOWN_CITIES:
                city_filter = candidate
        # Also scan the whole query for a city name
        if not city_filter:
            for city in KNOWN_CITIES:
                if city in q:
                    city_filter = city
                    break

        if city_filter:
            # Use substring match so "Delhi - Sector 5" matches "delhi"
            matched = [c for c in customers if city_filter in c.get("city","").lower()]
            lines = ["Customers from " + city_filter.capitalize() + ": " + str(len(matched)) + "\n"]
            for c in matched:
                lines.append("  " + c["customer_id"] + " | " + c["name"] + " | " + c.get("segment","") + " | " + c.get("city",""))
            return "\n".join(lines)

        by_seg = {}
        for c in customers:
            by_seg[c.get("segment","?")] = by_seg.get(c.get("segment","?"), 0) + 1
        lines = [f"Total customers: {len(customers)}\n"]
        for s in ["Premium","Standard","Basic"]:
            if s in by_seg:
                lines.append(f"  {s}: {by_seg[s]}")
        # City breakdown
        by_city = {}
        for c in customers:
            by_city[c.get("city","?")] = by_city.get(c.get("city","?"), 0) + 1
        lines.append("\nBy city:")
        for city, cnt in sorted(by_city.items(), key=lambda x: -x[1]):
            lines.append(f"  {city}: {cnt}")
        return "\n".join(lines)

    if re.search(r"technician|tech", q):
        techs = get_technicians()
        lines = [f"Technicians ({len(techs)}):\n"]
        for t in techs:
            lines.append(f"  {t['name']} | {t['specialization']} | {t['city']} | Rating: {t['rating']}")
        return "\n".join(lines)

    if re.search(r"lead", q):
        leads = get_sales_leads()
        by_stage = {}
        for l in leads:
            by_stage[l.get("stage","?")] = by_stage.get(l.get("stage","?"), 0) + 1
        lines = [f"Sales leads: {len(leads)} total\n"]
        for s, cnt in by_stage.items():
            lines.append(f"  {s}: {cnt}")
        return "\n".join(lines)

    return None


def _handle_customer_lookup(query: str, customer_id: Optional[str], session_id: str) -> Dict:
    from backend.data_loader import (get_customer_by_id, get_warranty_by_customer,
                                      get_tickets_by_customer, get_appliance_by_id)
    if not customer_id:
        hint = _suggest_similar_names(query)
        msg  = "I could not find that customer."
        if hint:
            msg += f" {hint}"
        else:
            msg += " Please check the name or select from the sidebar."
        return {"answer": msg}

    customer   = get_customer_by_id(customer_id)
    if not customer:
        return {"answer": f"No customer found with ID {customer_id}."}

    warranties = get_warranty_by_customer(customer_id)
    tickets    = get_tickets_by_customer(customer_id)
    open_t     = [t for t in tickets if t["status"] in ("OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED")]
    active_w   = [w for w in warranties if w["status"] == "Active"]

    owned = []
    for w in warranties:
        a = get_appliance_by_id(w["appliance_id"])
        if a:
            owned.append(f"{a['brand']} {a['model']} ({a['category']}) — warranty {w['status']} till {w['expiry_date']}")

    lines = [
        f"Customer: {customer['name']}",
        f"  ID       : {customer['customer_id']}",
        f"  Email    : {customer['email']}",
        f"  Phone    : {customer['phone']}",
        f"  City     : {customer['city']}",
        f"  Segment  : {customer['segment']}",
        f"  Since    : {customer['since']}",
        "",
        f"Appliances Owned ({len(owned)}):",
    ]
    if owned:
        for o in owned:
            lines.append(f"  - {o}")
    else:
        lines.append("  None on record")

    lines += [
        "",
        f"Tickets: {len(tickets)} total  |  Open: {len(open_t)}  |  Active Warranties: {len(active_w)}",
    ]
    if open_t:
        sorted_open = sorted(open_t, key=lambda t: PRIORITY_ORDER.get(t.get("priority","medium").lower(), 2))
        lines.append("\nOpen issues (by priority):")
        for t in sorted_open:
            lines.append(f"  [{t['priority'].upper():8}] {t['issue'][:55]}  ({t['ticket_id']})")

    base_answer = "\n".join(lines)

    # Enhance with LLM natural language summary if available
    from backend.utils.llm import call_llm, _get_client
    if _get_client():
        llm_ans = call_llm(
            "You are a CRM assistant. Give a concise, natural-language summary of this customer profile. "
"Include their name, key appliances, open issues, and warranty status. Under 150 words.",
            f"Query: {query}\n\nProfile data:\n{base_answer}",
            session_id, 250
        )
        if llm_ans and len(llm_ans) > 50 and "error" not in llm_ans.lower():
            return {"answer": llm_ans, "customer": customer}

    return {"answer": base_answer, "customer": customer}


def _handle_delay_analysis(query: str, session_id: str) -> Dict:
    """Use the knowledge graph to explain why tickets are delayed."""
    from backend.rag.graph_rag import analyse_delays
    from backend.utils.llm import call_llm, _get_client

    data         = analyse_delays(top_n=15)
    rows         = data["rows"]
    cause_counts = data["cause_counts"]
    graph_insight = data.get("graph_insight", "")

    if not rows:
        return {"answer": "No open tickets found to analyse.", "intent": "delay_analysis"}

    CAUSE_LABELS = {
        "NO_TECHNICIAN":    "No Technician Assigned",
        "TECH_OVERLOADED":  "Technician Overloaded",
        "ESCALATION_NEEDED":"Escalation Needed",
        "WARRANTY_ISSUE":   "Warranty / Approval Blocked",
        "IN_PROGRESS":      "In Progress",
    }

    groups: Dict = {}
    for r in rows:
        groups.setdefault(r["root_cause"], []).append(r)

    lines = ["DELAY_ANALYSIS_START"]
    lines.append(f"graph_insight:{graph_insight}")

    for cause, label in CAUSE_LABELS.items():
        if cause not in groups:
            continue
        count = len(groups[cause])
        icon = {"NO_TECHNICIAN":"WARN","TECH_OVERLOADED":"LOOP",
                "ESCALATION_NEEDED":"ALERT","WARRANTY_ISSUE":"DOC","IN_PROGRESS":"TOOL"}.get(cause,"")
        lines.append(f"CAUSE_GROUP:{icon}|{label} ({count})")
        for r in groups[cause]:
            lines.append(
                f"  {r['emoji']} {r['customer_id']} | {r['name']:<18} | "
                f"{r['issue'][:45]:<45} | {r['priority'].upper():<8} | "
                f"{r['days_open']}d | {r['cause_detail']}"
            )

    lines.append("DELAY_ANALYSIS_END")

    order = ["NO_TECHNICIAN","TECH_OVERLOADED","ESCALATION_NEEDED","WARRANTY_ISSUE","IN_PROGRESS"]
    summary_parts = []
    for k in order:
        if k in cause_counts:
            summary_parts.append(f"{CAUSE_LABELS[k]}: {cause_counts[k]}")
    lines.append(f"summary:{' | '.join(summary_parts)}")

    llm_narrative = ""
    if _get_client():
        system = (
            "You are a CRM operations analyst. Given delay data, explain in 3 sentences "
"the systemic root causes and the single most important fix to make right now."
        )
        table_snippet = "\n".join(
            f"{r['root_cause']}: {r['name']} — {r['issue'][:40]} ({r['days_open']}d)"
            for r in rows[:8]
        )
        llm_narrative = call_llm(
            system,
            f"Delay data:\n{table_snippet}\n\nCause distribution: {cause_counts}\n\n"
            f"Graph: {graph_insight}\n\nExplain root causes and best fix.",
            session_id, max_tokens=200
        )

    if llm_narrative:
        lines.append(f"llm_narrative:{llm_narrative}")

    return {
        "answer":     "\n".join(lines),
        "delay_data": data,
        "intent":     "delay_analysis",
        "agent_used": "graph_rag + knowledge_graph",
    }


def _handle_email_draft(query: str, customer_id: Optional[str], session_id: str) -> Dict:
    """Generate a fully RAG-driven personalised email draft and queue for approval."""
    from backend.data_loader import (
        get_customer_by_id, get_tickets_by_customer,
        get_technicians, get_appliances, get_warranty_by_customer,
    )
    from backend.agents.communication_agent import generate_rag_email
    from backend.approval.approval_queue import queue_email_for_approval

    q = query.lower()

    if not customer_id:
        return {"answer": (
            "To draft an email I need a customer selected.\n"
"Pick one from the sidebar or mention their name — e.g.\n"
            '"Draft an apology email for Arun Kumar"'
        )}

    customer = get_customer_by_id(customer_id)
    if not customer:
        return {"answer": f"Customer {customer_id} not found. Please select a valid customer."}

    # ── RAG: load all context ─────────────────────────────────────────────────
    tickets     = get_tickets_by_customer(customer_id)
    appliances  = get_appliances()
    warranties  = get_warranty_by_customer(customer_id)
    technicians = get_technicians()

    # Detect email type from query
    if any(x in q for x in ["apolog", "sorry", "inconvenience", "delay"]):
        email_type = "email_apology"
        label      = "Apology Email"
    elif any(x in q for x in ["escalat", "senior", "specialist"]):
        email_type = "email_escalation"
        label      = "Escalation Notice"
    elif any(x in q for x in ["technician", "tech", "engineer", "visit"]):
        email_type = "email_technician_assignment"
        label      = "Technician Assignment Email"
    elif any(x in q for x in ["warranty expir", "renew", "extend warranty"]):
        email_type = "email_warranty_expiry"
        label      = "Warranty Expiry Notice"
    else:
        email_type = "email_ticket_confirmation"
        label      = "Service Update Email"

    # ── Generate fully RAG-driven email via Groq ──────────────────────────────
    draft = generate_rag_email(
        email_type  = email_type,
        customer    = customer,
        tickets     = tickets,
        appliances  = appliances,
        warranties  = warranties,
        technicians = technicians,
        query       = query,
        session_id  = session_id,
    )

    # Get primary ticket for approval queue reference
    open_t = [t for t in tickets
              if str(t.get("status","")).lower().replace(" ","_")
              in {"open","in_progress","under_review","technician_pending","assigned"}]
    ref_ticket = open_t[0] if open_t else (tickets[0] if tickets else {})

    approval_id = ""
    try:
        approval = queue_email_for_approval(
            email_type  = email_type,
            to_email    = customer.get("email", ""),
            customer_id = customer_id,
            ticket_id   = ref_ticket.get("ticket_id", ""),
            draft       = draft,
        )
        approval_id = approval.get("approval_id", "")
    except Exception as exc:
        print(f"[Email] Approval queue error: {exc}")

    sep    = "─" * 52
    answer = (
        f"EMAIL_DRAFT_START\n"
        f"label:{label}\n"
        f"to:{customer.get('email','')}\n"
        f"subject:{draft['subject']}\n"
        f"approval:{approval_id}\n"
        f"{sep}\n"
        f"{draft['body']}\n"
        f"{sep}\n"
        f"EMAIL_DRAFT_END"
    )

    return {
        "answer":      answer,
        "email_draft": draft,
        "approval_id": approval_id,
        "intent":      "email",
        "agent_used":  "communication_agent_rag",
    }


def run(query: str, session_id: str, customer_id: Optional[str] = None,
        extra: Dict = None) -> Dict:
    """Main orchestrator entry point."""
    extra = extra or {}
    query = sanitize_input(query)

    cid = customer_id or extract_customer_id(query, session_id)
    if cid:
        set_entity(session_id, "customer_id", cid)

    save_turn(session_id, "user", query)

    intent = classify_intent(query)

    try:
        # ── Data queries (no LLM) ─────────────────────────────────────────────
        if intent == "data_query":
            answer = _handle_data_query(query, cid, session_id)
            if answer:
                save_turn(session_id, "assistant", answer[:300])
                return {"answer": answer, "intent": intent, "agent_used": "data_query"}
            intent = "general"

        # ── Delay analysis (knowledge graph) ──────────────────────────────────
        if intent == "delay_analysis":
            result = _handle_delay_analysis(query, session_id)
            save_turn(session_id, "assistant", result["answer"][:300])
            return result

        # ── Global cross-customer analysis ────────────────────────────────────
        if intent == "global_analysis":
            from backend.agents.global_analysis_agent import run as global_run
            result = global_run(query, session_id)
            save_turn(session_id, "assistant", result["answer"][:300])
            return result

        # ── Email draft ───────────────────────────────────────────────────────
        if intent == "email":
            result = _handle_email_draft(query, cid, session_id)
            save_turn(session_id, "assistant", result["answer"][:300])
            result["intent"] = intent
            return result

        # ── Customer lookup by name ───────────────────────────────────────────
        if intent == "customer_lookup":
            result = _handle_customer_lookup(query, cid, session_id)
            save_turn(session_id, "assistant", result["answer"][:300])
            result["intent"] = intent
            result["agent_used"] = intent
            return result

        # ── Warranty ──────────────────────────────────────────────────────────
        if intent == "warranty":
            from backend.data_loader import get_warranty_by_customer
            from backend.agents.crm_agent import check_warranty
            from backend.rag.graph_rag import retrieve_by_customer
            if not cid:
                return {"answer": "Please select a customer or mention their name.",
                        "intent": intent, "agent_used": intent}
            warranties    = get_warranty_by_customer(cid)
            warranty_check = check_warranty(cid)
            graph_ctx     = retrieve_by_customer(cid)
            if not warranties:
                answer = f"No warranty records found for {cid}."
            else:
                active = [w for w in warranties if w["status"] == "Active"]
                lines  = [f"Warranty status for {cid} — Active: {len(active)} / Total: {len(warranties)}\n"]
                for w in warranties:
                    status_txt = "ACTIVE" if w["status"] == "Active" else "EXPIRED"
                    lines.append(f"[{status_txt}] {w['warranty_id']} — {w['appliance_id']}")
                    lines.append(f"  Purchased: {w['purchase_date']}  |  Expires: {w['expiry_date']}")
                    lines.append(f"  Serial: {w['serial_number']}  |  Amount: Rs.{int(float(w['purchase_amount'])):,}\n")
                answer = "\n".join(lines)
                from backend.utils.llm import call_llm, _get_client
                if _get_client():
                    llm_ans = call_llm(
                        "You are a warranty support agent. Be concise and helpful.",
                        f"Query: {query}\nWarranty data:\n{answer}", session_id, 200)
                    if llm_ans and "data-only" not in llm_ans:
                        answer = llm_ans
            result = {"answer": answer, **warranty_check}

        # ── Recommendations ───────────────────────────────────────────────────
        elif intent == "recommendation":
            from backend.agents.recommendation_agent import recommend
            result = recommend(cid or "CUST001", query, session_id)

        # ── Validation ────────────────────────────────────────────────────────
        elif intent == "validation":
            from backend.agents.validation_agent import validate_claim
            result = validate_claim(cid or "", extra.get("claim_type","warranty"),
                                    query, int(extra.get("amount",0)), session_id)

        # ── Approvals ─────────────────────────────────────────────────────────
        elif intent == "approval":
            from backend.agents.human_approval_agent import get_queue, process_approval
            if "process" in query.lower():
                result = {"answer": str(process_approval(
                    extra.get("approval_id", ""),
                    extra.get("decision", "approved")))}
            else:
                queue  = get_queue()
                result = {"answer": f"{len(queue)} item(s) pending approval.", "queue": queue}

        # ── CRM pipeline stats ────────────────────────────────────────────────
        elif intent == "crm_lookup":
            from backend.agents.crm_agent import get_crm_stats
            result = get_crm_stats(session_id)

        # ── Policy / document queries ─────────────────────────────────────────
        elif intent == "policy_query":
            from backend.utils.llm import call_llm, _get_client
            policy_ctx = _load_policy_docs(query)
            customer_info = ""
            if cid:
                try:
                    from backend.data_loader import (get_customer_by_id,
                        get_tickets_by_customer, get_warranty_by_customer)
                    c = get_customer_by_id(cid)
                    if c:
                        c_tix  = get_tickets_by_customer(cid)
                        c_warr = get_warranty_by_customer(cid)
                        open_t = [t for t in c_tix if t["status"] in
                                  ("OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED")]
                        customer_info = (
                            "Customer: " + c["name"] +
                            " | Segment: " + c.get("segment","") +
                            " | Open tickets: " + str(len(open_t)) +
                            " | Warranties: " + str(len(c_warr))
                        )
                except Exception:
                    pass
            if _get_client():
                system = (
                    "You are a PowerPlex customer support specialist with access to all "
"company policy documents, product manuals, FAQs, and guidelines. "
"Answer ONLY from the provided documents. Quote specific clauses, "
"time limits, and conditions where they exist. "
"If a specific number of days, cost, or condition is stated in the "
"docs include it verbatim. Be direct: lead with the answer. "
"For warranty void conditions, escalation, incorrect repairs, "
"second visits answer from faq.txt or warranty_policy.txt. "
"Personalise to the customer if context is provided."
                )
                ctx_prefix = ("Customer context: " + customer_info + "\n\n") if customer_info else ""
                user = (
                    ctx_prefix +
                    "Policy documents (use these to answer):\n" + policy_ctx[:3000] + "\n\n" +
                    "Question: " + query + "\n\n" +
                    "Answer directly and specifically from the documents above."
                )
                answer = call_llm(system, user, session_id, max_tokens=500)
                result = {"answer": answer or "Please refer to our support team for this query.",
                          "intent": intent, "agent_used": "policy_query"}
            else:
                q_words = [w for w in query.lower().split() if len(w) > 3]
                scored = []
                for doc in _load_policy_docs(query).split("\n\n"):
                    score = sum(1 for w in q_words if w in doc.lower())
                    if score > 0:
                        scored.append((score, doc[:500]))
                scored.sort(key=lambda x: -x[0])
                if scored:
                    result = {"answer": "\n\n".join(d for _, d in scored[:2]),
                              "intent": intent, "agent_used": "policy_query"}
                else:
                    result = {"answer": "Please refer to return_policy.txt and warranty_policy.txt.",
                              "intent": intent}

        # -- General / RAG fallback --
        else:
            from backend.utils.llm import call_llm, _get_client
            ctx_parts = []
            policy_ctx = _load_policy_docs(query)
            if policy_ctx:
                ctx_parts.append("Service Policies & Manuals:\n" + policy_ctx[:800])
            customer_info = ""
            if cid:
                try:
                    from backend.data_loader import (get_customer_by_id,
                        get_tickets_by_customer, get_warranty_by_customer)
                    c      = get_customer_by_id(cid)
                    c_tix  = get_tickets_by_customer(cid)
                    c_warr = get_warranty_by_customer(cid)
                    if c:
                        open_t = [t for t in c_tix if t["status"] in
                                  ("OPEN","IN_PROGRESS","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED")]
                        customer_info = (
                            "Customer: " + c["name"] +
                            " | Segment: " + c.get("segment","") +
                            " | City: " + c.get("city","") + "\n" +
                            "Open tickets (" + str(len(open_t)) + "): " +
                            "; ".join(t["ticket_id"] + ": " + t["issue"][:40] +
                                      " [" + t["priority"] + "]"
                                      for t in open_t[:3]) +
                            "\nActive warranties: " +
                            str(sum(1 for w in c_warr if w.get("status") == "Active"))
                        )
                        ctx_parts.append("Customer Profile:\n" + customer_info)
                except Exception:
                    pass
            try:
                from backend.rag.hybrid_rag import retrieve as hybrid_retrieve, format_context as hfmt
                h = hybrid_retrieve(query, top_k=3)
                if h:
                    ctx_parts.append("Knowledge Base:\n" + hfmt(h))
            except Exception:
                pass
            full_ctx = "\n\n".join(ctx_parts)
            if _get_client():
                system = (
                    "You are PowerPlex CRM assistant. Help support agents answer questions "
"about customers, appliances, policies and tickets. "
"Be helpful, specific and concise."
                )
                user = (full_ctx + "\n\n" if full_ctx else "") + "Question: " + query
                answer = call_llm(system, user, session_id, max_tokens=400)
                result = {"answer": answer or "I could not find a specific answer. Please try rephrasing.",
                          "intent": intent, "agent_used": "general"}
            else:
                result = {"answer": full_ctx[:600] if full_ctx else
                          "Please provide more details or select a customer.",
                          "intent": intent, "agent_used": "general_fallback"}

    except Exception as e:
        import traceback
        result = {"answer": "Sorry, I encountered an error: " + str(e),
                  "error": traceback.format_exc(), "intent": "error"}

    try:
        save_turn(session_id, query, result.get("answer",""))
    except Exception:
        pass

    return result
