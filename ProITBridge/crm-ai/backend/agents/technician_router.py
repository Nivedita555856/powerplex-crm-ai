"""
technician_router.py — PowerPlex Technician Routing Agent
Selects the best technician based on specialization, workload, and ticket severity.
Assignment requires admin approval before it takes effect.
"""
from typing import Dict, List, Optional
from backend.data_loader import get_technicians
from backend.agents.ticket_classifier import classify_ticket

PRODUCT_TO_SPECIALIZATION = {
    "AC":              ["AC","Air Conditioner","HVAC","Cooling"],
    "Refrigerator":    ["Refrigerator","Fridge","Cooling","Appliances"],
    "Washing Machine": ["Washing Machine","Laundry","Appliances"],
    "Microwave":       ["Microwave","Kitchen Appliances","Appliances"],
    "Television":      ["Television","Electronics","Display"],
    "General":         ["Appliances","General"],
}


def _specialization_score(tech: Dict, product_type: str) -> int:
    spec = tech.get("specialization", "").lower()
    targets = [s.lower() for s in PRODUCT_TO_SPECIALIZATION.get(product_type, ["appliances"])]
    if spec in targets:
        return 3
    if any(t in spec for t in targets):
        return 2
    if "appliance" in spec or "general" in spec:
        return 1
    return 0


def route_technician(ticket_issue: str, product_type: Optional[str] = None,
                     severity: Optional[str] = None) -> Dict:
    """
    Suggest the best technician for a ticket.
    Returns: suggested technician + reasoning + requires_approval=True always.
    """
    techs = get_technicians()
    if not techs:
        return {"answer": "No technicians available.", "requires_approval": True}

    # Auto-classify if not provided
    if not product_type or not severity:
        cls = classify_ticket(ticket_issue)
        product_type = product_type or cls["product_type"]
        severity     = severity     or cls["severity"]

    # Score each technician
    scored = []
    for t in techs:
        score  = _specialization_score(t, product_type)
        rating = float(t.get("rating", 3.0))
        # Weight: specialization 60%, rating 40%
        total  = score * 0.6 + (rating / 5.0) * 4 * 0.4
        scored.append({**t, "_score": round(total, 2), "_spec_match": score})

    scored.sort(key=lambda x: x["_score"], reverse=True)
    best   = scored[0]
    others = scored[1:3]

    reasoning = (
        f"Recommended: {best['name']} ({best['specialization']}) — "
        f"City: {best['city']}, Rating: {best['rating']}/5, "
        f"Specialization match: {'Direct' if best['_spec_match'] == 3 else 'Partial' if best['_spec_match'] > 0 else 'General'}.\n"
        f"Severity: {severity} | Product: {product_type}\n"
        f"Alternatives: " + ", ".join(f"{t['name']} ({t['specialization']})" for t in others)
    )

    max_score   = 3 * 0.6 + 4 * 0.4   # 3.4
    match_score = round(best["_score"] / max_score, 3)  # 0.0 – 1.0
    match_pct   = round(match_score * 100)

    spec_label = (
        "Direct match"   if best["_spec_match"] == 3 else
        "Partial match"  if best["_spec_match"] > 0  else
        "General"
    )

    return {
        "recommended_technician": best,
        "alternatives":           others,
        "reasoning":              reasoning,
        "severity":               severity,
        "product_type":           product_type,
        "score":                  match_score,
        "match_pct":              match_pct,
        "match_label":            spec_label,
        "requires_approval":      True,
        "answer":                 f"Technician suggested: {best['name']}. Awaiting admin approval before assignment.",
    }
