"""
graph_rag.py — Graph RAG: builds a knowledge graph with NetworkX,
traverses relationships to find contextually related information.
No Neo4j needed — pure Python + NetworkX.
"""
from typing import List, Dict, Optional
from backend.data_loader import (get_customers, get_appliances, get_warranty_data,
                                  get_tickets, get_technicians)

_graph = None

def _build_graph():
    """Build NetworkX knowledge graph from CRM data."""
    try:
        import networkx as nx
    except ImportError:
        return None

    G = nx.DiGraph()

    # Add nodes
    for c in get_customers():
        G.add_node(c["customer_id"], type="customer", **c)
    for a in get_appliances():
        G.add_node(a["appliance_id"], type="appliance", **a)
    for t in get_technicians():
        G.add_node(t["technician_id"], type="technician", **t)
    for w in get_warranty_data():
        G.add_node(w["warranty_id"], type="warranty", **w)
    for tk in get_tickets():
        G.add_node(tk["ticket_id"], type="ticket", **tk)

    # Add edges
    for w in get_warranty_data():
        G.add_edge(w["customer_id"], w["warranty_id"],  relation="has_warranty")
        G.add_edge(w["warranty_id"], w["appliance_id"], relation="covers")

    for tk in get_tickets():
        G.add_edge(tk["customer_id"], tk["ticket_id"],  relation="raised")
        if tk.get("warranty_id"):
            G.add_edge(tk["ticket_id"], tk["warranty_id"], relation="under_warranty")
        if tk.get("technician_id"):
            G.add_edge(tk["technician_id"], tk["ticket_id"], relation="assigned_to")
        if tk.get("appliance_id"):
            G.add_edge(tk["ticket_id"], tk["appliance_id"], relation="about")

    return G

def _get_graph():
    global _graph
    if _graph is None:
        _graph = _build_graph()
    return _graph

def retrieve_by_customer(customer_id: str, depth: int = 2) -> List[Dict]:
    """
    Traverse the graph from a customer node to retrieve related entities.
    Returns a list of context dicts.
    """
    G = _get_graph()
    if G is None or customer_id not in G:
        return _fallback(customer_id)

    try:
        import networkx as nx
        nodes = nx.ego_graph(G, customer_id, radius=depth).nodes(data=True)
    except Exception:
        return _fallback(customer_id)

    results = []
    for node_id, data in nodes:
        ntype = data.get("type", "unknown")
        if ntype == "ticket":
            results.append({
                "text": f"Ticket {node_id}: {data.get('issue','?')} — Status: {data.get('status','?')} Priority: {data.get('priority','?')}",
                "score": 0.85, "source_type": "ticket"
            })
        elif ntype == "warranty":
            results.append({
                "text": f"Warranty {node_id}: {data.get('status','?')} for appliance {data.get('appliance_id','?')}, expires {data.get('expiry_date','?')}",
                "score": 0.80, "source_type": "warranty"
            })
        elif ntype == "appliance":
            results.append({
                "text": f"Appliance {node_id}: {data.get('brand','')} {data.get('model','')} — {data.get('description','')}",
                "score": 0.75, "source_type": "appliance"
            })
    return results[:6]

def _fallback(customer_id: str) -> List[Dict]:
    """Return plain data when NetworkX is unavailable."""
    from backend.data_loader import get_warranty_by_customer, get_tickets_by_customer
    results = []
    for w in get_warranty_by_customer(customer_id):
        results.append({"text": f"Warranty {w['warranty_id']}: {w['status']}, expires {w['expiry_date']}",
                        "score": 0.80, "source_type": "warranty"})
    for t in get_tickets_by_customer(customer_id)[:3]:
        results.append({"text": f"Ticket {t['ticket_id']}: {t['issue']} [{t['status']}]",
                        "score": 0.75, "source_type": "ticket"})
    return results

def reset_graph():
    global _graph
    _graph = None


# ── Delay Analysis via Knowledge Graph ────────────────────────────────────────

def analyse_delays(top_n: int = 15) -> Dict:
    """
    Traverse the knowledge graph to explain WHY tickets are delayed.

    Root cause categories:
      NO_TECHNICIAN    — ticket has no technician assigned
      TECH_OVERLOADED  — assigned tech has 4+ active tickets
      WARRANTY_ISSUE   — warranty expired / missing, blocking free repair
      ESCALATION_NEEDED— critical/high open > 7 days
      IN_PROGRESS      — being actively worked on
    """
    from datetime import date, datetime
    from collections import Counter
    from backend.data_loader import (get_tickets, get_customers, get_technicians,
                                      get_warranty_data)

    all_tickets   = get_tickets()
    all_customers = get_customers()
    all_techs     = get_technicians()
    all_warranties = get_warranty_data()

    cust_map     = {c["customer_id"]: c for c in all_customers}
    tech_map     = {t["technician_id"]: t for t in all_techs}
    warranty_map = {w["warranty_id"]: w for w in all_warranties}

    tech_load: Counter = Counter(
        t["technician_id"] for t in all_tickets
        if t.get("technician_id") and t.get("status") in ("Open", "In Progress")
    )

    def _days(ds: str) -> int:
        if not ds:
            return 0
        try:
            return (date.today() - datetime.strptime(ds.strip(), "%Y-%m-%d").date()).days
        except Exception:
            return 0

    EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    SEVERITY = {"NO_TECHNICIAN": 0, "TECH_OVERLOADED": 1,
                "ESCALATION_NEEDED": 2, "WARRANTY_ISSUE": 3, "IN_PROGRESS": 4}

    open_tickets = [t for t in all_tickets if t.get("status") in ("Open", "In Progress")]
    delay_rows = []

    for t in open_tickets:
        days     = _days(t.get("created_date", ""))
        priority = t.get("priority", "medium").lower()
        tech_id  = t.get("technician_id", "")
        wrn_id   = t.get("warranty_id", "")
        cust     = cust_map.get(t["customer_id"], {})

        if not tech_id:
            root_cause   = "NO_TECHNICIAN"
            cause_detail = "No technician assigned yet"
        elif tech_load.get(tech_id, 0) >= 4:
            tech = tech_map.get(tech_id, {})
            root_cause   = "TECH_OVERLOADED"
            cause_detail = f"{tech.get('name','?')} has {tech_load[tech_id]} active tickets"
        elif wrn_id and warranty_map.get(wrn_id, {}).get("status") == "Expired":
            root_cause   = "WARRANTY_ISSUE"
            cause_detail = f"Warranty {wrn_id} expired — manager approval needed"
        elif priority in ("critical", "high") and days > 7:
            root_cause   = "ESCALATION_NEEDED"
            cause_detail = f"Open {days} days without resolution — escalate now"
        else:
            tech = tech_map.get(tech_id, {})
            root_cause   = "IN_PROGRESS"
            cause_detail = f"Being handled by {tech.get('name','?')}"

        delay_rows.append({
            "ticket_id":    t["ticket_id"],
            "customer_id":  t["customer_id"],
            "name":         cust.get("name", "Unknown"),
            "city":         cust.get("city", "—"),
            "issue":        t.get("issue", "—"),
            "priority":     priority,
            "emoji":        EMOJI.get(priority, "⚪"),
            "days_open":    days,
            "root_cause":   root_cause,
            "cause_detail": cause_detail,
            "technician_id": tech_id,
        })

    delay_rows.sort(key=lambda r: (SEVERITY.get(r["root_cause"], 5), -r["days_open"]))
    delay_rows = delay_rows[:top_n]

    cause_counts = Counter(r["root_cause"] for r in delay_rows)

    # Graph-level bottleneck detection
    graph_insight = ""
    try:
        import networkx as nx
        G = _get_graph()
        if G:
            tech_nodes = [(n, G.degree(n)) for n, d in G.nodes(data=True)
                          if d.get("type") == "technician"]
            if tech_nodes:
                busiest_id, busiest_deg = max(tech_nodes, key=lambda x: x[1])
                bname = tech_map.get(busiest_id, {}).get("name", busiest_id)
                graph_insight = (f"Graph bottleneck: {bname} is the most connected node "
                                 f"({busiest_deg} edges). ")
            open_nodes = sum(1 for _, d in G.nodes(data=True)
                             if d.get("type") == "ticket" and d.get("status") in ("Open","In Progress"))
            graph_insight += f"{open_nodes} open ticket nodes in knowledge graph."
    except Exception:
        pass

    return {
        "rows":          delay_rows,
        "total":         len(delay_rows),
        "cause_counts":  dict(cause_counts),
        "graph_insight": graph_insight,
    }


# ── Delay Analysis via Knowledge Graph ────────────────────────────────────────

def analyse_delays(top_n: int = 15) -> dict:
    """
    Traverse the knowledge graph to explain WHY tickets are delayed.

    Root cause categories:
      NO_TECHNICIAN    — ticket has no technician assigned
      TECH_OVERLOADED  — assigned tech has 4+ active tickets
      WARRANTY_ISSUE   — warranty expired / missing, blocking free repair
      ESCALATION_NEEDED— critical/high open > 7 days
      IN_PROGRESS      — being actively worked on
    """
    from datetime import date, datetime
    from collections import Counter
    from backend.data_loader import (get_tickets, get_customers, get_technicians,
                                      get_warranty_data)

    all_tickets    = get_tickets()
    all_customers  = get_customers()
    all_techs      = get_technicians()
    all_warranties = get_warranty_data()

    cust_map     = {c["customer_id"]: c for c in all_customers}
    tech_map     = {t["technician_id"]: t for t in all_techs}
    warranty_map = {w["warranty_id"]: w for w in all_warranties}

    tech_load: Counter = Counter(
        t["technician_id"] for t in all_tickets
        if t.get("technician_id") and t.get("status") in ("Open", "In Progress")
    )

    def _days(ds: str) -> int:
        if not ds:
            return 0
        try:
            return (date.today() - datetime.strptime(ds.strip(), "%Y-%m-%d").date()).days
        except Exception:
            return 0

    EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
    SEVERITY = {"NO_TECHNICIAN": 0, "TECH_OVERLOADED": 1,
                "ESCALATION_NEEDED": 2, "WARRANTY_ISSUE": 3, "IN_PROGRESS": 4}

    open_tickets = [t for t in all_tickets if t.get("status") in ("Open", "In Progress")]
    delay_rows = []

    for t in open_tickets:
        days     = _days(t.get("created_date", ""))
        priority = t.get("priority", "medium").lower()
        tech_id  = t.get("technician_id", "")
        wrn_id   = t.get("warranty_id", "")
        cust     = cust_map.get(t["customer_id"], {})

        if not tech_id:
            root_cause   = "NO_TECHNICIAN"
            cause_detail = "No technician assigned yet"
        elif tech_load.get(tech_id, 0) >= 4:
            tech = tech_map.get(tech_id, {})
            root_cause   = "TECH_OVERLOADED"
            cause_detail = f"{tech.get('name','?')} has {tech_load[tech_id]} active tickets"
        elif wrn_id and warranty_map.get(wrn_id, {}).get("status") == "Expired":
            root_cause   = "WARRANTY_ISSUE"
            cause_detail = f"Warranty {wrn_id} expired — manager approval needed"
        elif priority in ("critical", "high") and days > 7:
            root_cause   = "ESCALATION_NEEDED"
            cause_detail = f"Open {days} days without resolution — escalate now"
        else:
            tech = tech_map.get(tech_id, {})
            root_cause   = "IN_PROGRESS"
            cause_detail = f"Being handled by {tech.get('name','?')}"

        delay_rows.append({
            "ticket_id":    t["ticket_id"],
            "customer_id":  t["customer_id"],
            "name":         cust.get("name", "Unknown"),
            "city":         cust.get("city", "—"),
            "issue":        t.get("issue", "—"),
            "priority":     priority,
            "emoji":        EMOJI.get(priority, "⚪"),
            "days_open":    days,
            "root_cause":   root_cause,
            "cause_detail": cause_detail,
            "technician_id": tech_id,
        })

    delay_rows.sort(key=lambda r: (SEVERITY.get(r["root_cause"], 5), -r["days_open"]))
    delay_rows = delay_rows[:top_n]

    cause_counts = Counter(r["root_cause"] for r in delay_rows)

    # Graph-level bottleneck detection
    graph_insight = ""
    try:
        import networkx as nx
        G = _get_graph()
        if G:
            tech_nodes = [(n, G.degree(n)) for n, d in G.nodes(data=True)
                          if d.get("type") == "technician"]
            if tech_nodes:
                busiest_id, busiest_deg = max(tech_nodes, key=lambda x: x[1])
                bname = tech_map.get(busiest_id, {}).get("name", busiest_id)
                graph_insight = (f"Graph bottleneck: {bname} is the most connected node "
                                 f"({busiest_deg} edges). ")
            open_nodes = sum(1 for _, d in G.nodes(data=True)
                             if d.get("type") == "ticket" and d.get("status") in ("Open","In Progress"))
            graph_insight += f"{open_nodes} open ticket nodes in knowledge graph."
    except Exception:
        pass

    return {
        "rows":          delay_rows,
        "total":         len(delay_rows),
        "cause_counts":  dict(cause_counts),
        "graph_insight": graph_insight,
    }
