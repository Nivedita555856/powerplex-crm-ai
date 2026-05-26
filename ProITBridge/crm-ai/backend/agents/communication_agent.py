"""
communication_agent.py — PowerPlex Customer Communication Agent
Generates fully RAG-driven, personalised emails using Groq LLM.
Every output goes to the approval queue — no email sent without admin approval.
"""
from typing import Dict, Optional, List
from datetime import datetime, timezone
from backend.utils.llm import call_llm, _get_client


# ── helpers ───────────────────────────────────────────────────────────────────

def _days_open(ticket: dict) -> int:
    """Return how many days a ticket has been open."""
    raw = ticket.get("created_at") or ticket.get("created_date") or ""
    if not raw:
        return 0
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return 0


def _build_customer_rag_context(customer: dict, tickets: list,
                                 appliances: list, warranties: list,
                                 technicians: list) -> str:
    """Build a rich RAG context string for Groq to use when writing the email."""
    name    = customer.get("name", "Customer")
    segment = customer.get("segment", "Standard")
    city    = customer.get("city", "")
    since   = customer.get("since", "")

    lines = [
        f"CUSTOMER PROFILE",
        f"  Name     : {name}",
        f"  Segment  : {segment}",
        f"  City     : {city}",
        f"  Customer since: {since}",
        "",
        "OPEN / ACTIVE TICKETS",
    ]

    open_statuses = {"open", "in_progress", "in progress", "under_review",
                     "technician_pending", "assigned"}
    open_tickets  = [t for t in tickets
                     if str(t.get("status", "")).lower().replace(" ", "_") in open_statuses]

    if not open_tickets:
        lines.append("  No open tickets.")
    else:
        for t in open_tickets[:5]:
            days  = _days_open(t)
            tid   = t.get("ticket_id", "")
            issue = t.get("issue") or t.get("issue_description") or "unspecified issue"
            pri   = t.get("priority", "medium").upper()
            stat  = t.get("status", "OPEN")
            tid_tech = t.get("assigned_technician") or t.get("technician_id") or ""
            tech_name = ""
            if tid_tech:
                tech = next((x for x in technicians
                             if x.get("technician_id") == tid_tech), None)
                if tech:
                    tech_name = f" | Assigned to: {tech['name']} ({tech.get('specialization','')})"
            appl_id   = t.get("appliance_id", "")
            appl_name = ""
            if appl_id:
                appl = next((a for a in appliances
                             if a.get("appliance_id") == appl_id), None)
                if appl:
                    appl_name = f"{appl.get('brand','')} {appl.get('model','')} ({appl.get('category','')})"
            lines.append(
                f"  [{pri}] {tid}: {issue}"
                f" | Status: {stat}"
                f" | Open {days} days"
                + (f" | Appliance: {appl_name}" if appl_name else "")
                + (tech_name or " | No technician assigned yet")
            )

    lines.append("")
    lines.append("WARRANTY STATUS")
    if warranties:
        for w in warranties[:3]:
            appl = next((a for a in appliances
                         if a.get("appliance_id") == w.get("appliance_id")), {})
            appl_name = f"{appl.get('brand','')} {appl.get('model','')}".strip() or w.get("appliance_id","")
            lines.append(
                f"  {appl_name}: expires {w.get('expiry_date','unknown')}"
                f" | Status: {w.get('status','unknown')}"
            )
    else:
        lines.append("  No warranty records found.")

    return "\n".join(lines)


def generate_rag_email(
    email_type : str,
    customer   : dict,
    tickets    : list,
    appliances : list,
    warranties : list,
    technicians: list,
    query      : str = "",
    session_id : str = "",
) -> dict:
    """
    Fully RAG-driven email generation.
    Groq writes the entire email from scratch using real customer data.
    """
    context = _build_customer_rag_context(
        customer, tickets, appliances, warranties, technicians
    )

    # Determine tone / purpose from query + email_type
    purpose_hints = {
        "email_apology"              : "Write a sincere apology email for the delay in resolving their issue.",
        "email_escalation"           : "Write an escalation notice informing the customer their issue is being escalated to a senior specialist.",
        "email_technician_assignment": "Write an email informing the customer that a technician has been assigned to their ticket.",
        "email_warranty_expiry"      : "Write an email notifying the customer that their warranty is expiring soon and what they can do.",
        "email_ticket_confirmation"  : "Write a professional ticket confirmation email acknowledging their reported issue.",
    }
    purpose = purpose_hints.get(email_type, "Write a helpful, professional support email addressing their current issue.")

    # Load relevant policy docs to keep email accurate and policy-compliant
    policy_snippets = ""
    doc_sources     = []
    try:
        from backend.data_loader import get_docs
        docs = get_docs()
        relevant_docs = []
        q_low = (query + " " + email_type).lower()
        for d in docs:
            fname = d.get("filename", "")
            body  = d.get("content", "")
            # Pick docs relevant to the email type/query
            if any(kw in q_low or kw in fname.lower() for kw in
                   ["warranty","return","refund","repair","install","troubleshoot","faq"]):
                relevant_docs.append(f"[{fname}]\n{body[:400]}")
            if len(relevant_docs) >= 2:
                break
        if not relevant_docs:
            # Default: always include warranty + return policy
            for d in docs:
                if "warranty" in d.get("filename","") or "return" in d.get("filename",""):
                    relevant_docs.append(f"[{d['filename']}]\n{d['content'][:400]}")
                if len(relevant_docs) >= 2:
                    break
        policy_snippets = "\n\n".join(relevant_docs)
        # Track which files were actually used
        for rd in relevant_docs:
            if rd.startswith("["):
                fname_end = rd.find("]")
                if fname_end > 0:
                    doc_sources.append(rd[1:fname_end])
    except Exception:
        pass

    system_prompt = (
        "You are a senior customer support writer for PowerPlex, a premium appliance service company. "
        "Write warm, professional, personalised emails using the customer's real data. "
        "Always follow the company policies provided — especially warranty coverage, repair timelines, "
        "and return/refund eligibility. Address the customer's specific issue. "
        "Mention ticket IDs, technician details, and days open when relevant. "
        "Format: first line is Subject: <subject>, blank line, then the email body. "
        "Sign off as: PowerPlex Support Team. Keep it under 200 words."
    )

    user_prompt = (
        f"{purpose}\n\n"
        f"Customer data:\n{context}\n\n"
        f"Company policies (follow these exactly):\n{policy_snippets}\n\n"
        f"Additional context: {query if query else 'Standard support notification.'}"
    )

    raw = call_llm(system_prompt, user_prompt, session_id, max_tokens=500)

    # Detect LLM failure / fallback responses
    llm_failed = (
        not raw
        or raw.startswith("[Groq")
        or raw.startswith("LLM error")
        or raw.startswith("[Data-only")
        or "not connected" in raw
        or len(raw) < 60
    )

    if llm_failed:
        # Build a professional template-based fallback
        cname  = customer.get("name", "Valued Customer")
        techs  = technicians[:1]
        tech   = techs[0] if techs else {}
        t_name = tech.get("name", "our specialist")
        t_id   = tech.get("technician_id", "")
        t_spec = tech.get("specialization", "appliance repair")
        open_t = [t for t in tickets if str(t.get("status","")).lower() in
                  ("open","in_progress","under_review","technician_pending","assigned")]
        ticket = open_t[0] if open_t else (tickets[0] if tickets else {})
        tid    = ticket.get("ticket_id", "")
        issue  = ticket.get("issue") or ticket.get("issue_description") or "your appliance issue"
        days   = _days_open(ticket)

        subj = f"Technician Assigned for Your Service Request — {tid}" if tid else f"PowerPlex Service Update — {cname}"
        body_lines = [
            f"Dear {cname},",
            "",
            f"Thank you for reaching out to PowerPlex Service.",
        ]
        if tid:
            body_lines += [
                "",
                f"We have reviewed your ticket #{tid} regarding: {issue}.",
                f"This ticket has been open for {days} day(s) and is our top priority.",
            ]
        if t_id:
            body_lines += [
                "",
                f"We are pleased to inform you that a technician has been assigned to your case:",
                f"  Technician : {t_name}  (ID: {t_id})",
                f"  Expertise  : {t_spec}",
                "",
                f"Our technician will contact you shortly to schedule a convenient visit.",
            ]
        body_lines += [
            "",
            "If you have any questions, please reply to this email or call our helpline.",
            "",
            "Warm regards,",
            "PowerPlex Support Team",
        ]
        return {
            "subject"    : subj,
            "body"       : "\n".join(body_lines),
            "ai_enhanced": False,
            "rag_context": True,
            "docs_used"  : doc_sources,
        }

    # Parse subject and body from LLM response
    subject = f"Your PowerPlex Service Update — {customer.get('name', '')}"
    body    = raw
    if raw.startswith("Subject:"):
        parts   = raw.split("\n", 2)
        subject = parts[0].replace("Subject:", "").strip()
        body    = parts[2].strip() if len(parts) > 2 else parts[1].strip()

    return {
        "subject"    : subject,
        "body"       : body,
        "ai_enhanced": True,
        "rag_context": True,
        "docs_used"  : doc_sources if 'doc_sources' in dir() else [],
    }


# ── Legacy wrappers (kept for backward compatibility) ─────────────────────────

def _personalise_with_llm(draft: dict, customer_context: str, session_id: str) -> dict:
    if not _get_client():
        return draft
    prompt = (
        f"Improve this email to be warmer and more personalised, keeping it professional. "
        f"Customer context: {customer_context}\n\nCurrent email body:\n{draft['body']}\n\n"
        f"Return ONLY the improved email body, nothing else."
    )
    improved = call_llm(
        "You are an expert customer communications writer.",
        prompt, session_id, 400
    )
    if improved and len(improved) > 100:
        draft["body"] = improved
        draft["ai_enhanced"] = True
    return draft


def generate_ticket_confirmation(customer, ticket, session_id=""):
    from backend.emails.templates import ticket_confirmation
    draft = ticket_confirmation(
        customer_name=customer["name"],
        ticket_id=ticket["ticket_id"],
        issue_summary=ticket.get("issue", "")[:80],
        severity=ticket.get("priority", "medium"),
        product_type=ticket.get("product_type", "Appliance"),
    )
    ctx = f"Customer: {customer['name']}, Segment: {customer.get('segment','')}, City: {customer.get('city','')}"
    return _personalise_with_llm(draft, ctx, session_id)


def generate_technician_assignment(customer, ticket, technician, session_id=""):
    from backend.emails.templates import technician_assignment
    draft = technician_assignment(
        customer_name=customer["name"],
        ticket_id=ticket["ticket_id"],
        technician_name=technician["name"],
        technician_specialization=technician.get("specialization", ""),
        issue_summary=ticket.get("issue", "")[:80],
    )
    ctx = f"Customer: {customer['name']}, issue: {ticket.get('issue','')[:60]}"
    return _personalise_with_llm(draft, ctx, session_id)


def generate_warranty_decision(customer, ticket, warranty, appliance_name,
                                decision, reason=None, session_id=""):
    from backend.emails.templates import warranty_approval
    return warranty_approval(
        customer_name=customer["name"], ticket_id=ticket["ticket_id"],
        appliance=appliance_name, warranty_id=warranty.get("warranty_id", ""),
        expiry_date=warranty.get("expiry_date", ""), decision=decision, reason=reason,
    )


def generate_repair_completion(customer, ticket, technician,
                                appliance_name, resolution_notes, session_id=""):
    from backend.emails.templates import repair_completion
    draft = repair_completion(
        customer_name=customer["name"], ticket_id=ticket["ticket_id"],
        appliance=appliance_name, technician_name=technician["name"],
        resolution_notes=resolution_notes,
    )
    ctx = f"Customer: {customer['name']}, appliance: {appliance_name}"
    return _personalise_with_llm(draft, ctx, session_id)


def generate_escalation(customer, ticket, reason="complexity of the issue", session_id=""):
    from backend.emails.templates import escalation_notice
    return escalation_notice(
        customer_name=customer["name"], ticket_id=ticket["ticket_id"],
        issue_summary=ticket.get("issue", "")[:80], reason=reason,
    )


def generate_apology(customer, ticket, delay_reason, session_id=""):
    from backend.emails.templates import apology_email
    return apology_email(
        customer_name=customer["name"], ticket_id=ticket["ticket_id"],
        delay_reason=delay_reason,
    )


def generate_warranty_expiry(customer, appliance_name, expiry_date,
                              upgrade_suggestions, session_id=""):
    from backend.emails.templates import warranty_expiry_notice
    return warranty_expiry_notice(
        customer_name=customer["name"], appliance=appliance_name,
        expiry_date=expiry_date, upgrade_suggestions=upgrade_suggestions,
    )


def generate_purchase_welcome(customer, appliance_name, model,
                               warranty_id, expiry_date, session_id=""):
    from backend.emails.templates import purchase_welcome
    draft = purchase_welcome(
        customer_name=customer["name"], appliance=appliance_name,
        model=model, warranty_id=warranty_id, expiry_date=expiry_date,
    )
    ctx = f"New customer: {customer['name']}, product: {appliance_name} {model}"
    return _personalise_with_llm(draft, ctx, session_id)
