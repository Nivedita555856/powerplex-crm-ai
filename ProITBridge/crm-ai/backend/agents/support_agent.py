"""
support_agent.py — Handles customer support queries, ticket creation, status checks.
Uses Corrective RAG + Graph RAG + MCTS for decision optimisation.
Optionally escalates to AutoGen for complex multi-step reasoning.
"""
from typing import Dict, Optional
from backend.rag.corrective_rag import retrieve, format_context
from backend.rag.graph_rag import retrieve_by_customer
from backend.mcts.mcts import mcts_decide, build_state
from backend.data_loader import (get_customer_by_id, get_warranty_by_customer,
                                   get_tickets_by_customer, get_appliance_by_id)
from backend.guardrails.guardrails import validate_response
from backend.sample_data import add_ticket
from backend.utils.llm import call_llm, _get_client

# ── AutoGen optional integration ──────────────────────────────────────────────
try:
    import autogen
    _AUTOGEN = True
except ImportError:
    _AUTOGEN = False

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _data_fallback(query: str, customer, past_tickets, warranties, mcts_decision: str) -> str:
    """Structured ticket/customer data response when Groq is unavailable."""
    q = query.lower()
    open_tickets = [t for t in past_tickets if t["status"] in ("Open", "In Progress")]
    active_w = [w for w in warranties if w.get("status") == "Active"]

    lines = []

    if any(x in q for x in ["problem", "issue", "having", "complaint", "what", "broken", "not working"]):
        if not open_tickets:
            lines.append(f"{customer['name']} has no open issues currently.")
            lines.append(f"All {len(past_tickets)} ticket(s) are resolved/closed.")
        else:
            lines.append(f"{customer['name']} has {len(open_tickets)} open issue(s):\n")
            sorted_t = sorted(open_tickets,
                              key=lambda t: PRIORITY_ORDER.get(t.get("priority", "medium").lower(), 2))
            for t in sorted_t:
                lines.append(f"  [{t['priority'].upper():8}] {t['issue'][:70]}")
                lines.append(f"              Ticket: {t['ticket_id']} | Status: {t['status']}")
    elif "repair" in q or "service" in q or "book" in q:
        lines += [
            "To book a service visit:",
            "  1. Go to the Tickets tab",
            "  2. Click '+ Create Ticket' and describe the issue",
            "  A technician will be assigned based on location and specialisation.",
        ]
    else:
        if open_tickets:
            lines.append(f"{customer['name']} | {len(open_tickets)} open issue(s):")
            lines.append(f"  Top: [{open_tickets[0]['priority'].upper()}] {open_tickets[0]['issue'][:60]}")
        else:
            lines.append(f"No active issues for {customer['name']}.")

    lines.append(f"\nMCTS recommendation: {mcts_decision}")
    if active_w:
        lines.append(f"Active warranty: {active_w[0]['warranty_id']} — expires {active_w[0]['expiry_date']}")

    return "\n".join(lines)


def _run_autogen(query: str, customer_ctx: str, doc_ctx: str,
                 mcts_decision: str, session_id: str) -> Optional[str]:
    """AutoGen UserProxy + SupportAssistant for complex multi-step reasoning."""
    if not _AUTOGEN:
        return None
    from backend.config import settings
    if not settings.GROQ_API_KEY:
        return None
    try:
        config_list = [{
            "model": settings.LLM_MODEL,
            "api_key": settings.GROQ_API_KEY,
            "base_url": "https://api.groq.com/openai/v1",
            "api_type": "openai",
        }]
        llm_cfg = {"config_list": config_list, "max_tokens": 350, "temperature": 0.3}

        assistant = autogen.AssistantAgent(
            name="SupportAgent",
            system_message=(
                f"You are an appliance support agent. "
                f"MCTS recommended action: {mcts_decision}. "
                f"Customer context: {customer_ctx[:200]}. "
                "Be concise (3-4 sentences). Do not promise refunds without approval."
            ),
            llm_config=llm_cfg,
        )
        user_proxy = autogen.UserProxyAgent(
            name="CustomerProxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=1,
            code_execution_config=False,
        )
        result = user_proxy.initiate_chat(
            assistant,
            message=f"Knowledge base:\n{doc_ctx[:400]}\n\nCustomer query: {query}",
            max_turns=2,
            silent=True,
        )
        for msg in reversed(result.chat_history):
            if msg.get("role") == "assistant" and msg.get("content"):
                return msg["content"].strip()
    except Exception as e:
        print(f"[AutoGen] Error: {e}")
    return None


def run(query: str, session_id: str, customer_id: str = None) -> Dict:
    """
    Main support agent entry point.
    Pipeline: Graph RAG → Corrective RAG → MCTS → AutoGen (if available) → Groq LLM → data fallback
    """
    customer    = get_customer_by_id(customer_id) if customer_id else None
    warranties  = get_warranty_by_customer(customer_id) if customer_id else []
    past_tickets = get_tickets_by_customer(customer_id) if customer_id else []

    # ── Graph RAG: customer relationship context ───────────────────────────────
    graph_context = retrieve_by_customer(customer_id) if customer_id else []

    # ── Corrective RAG: policy/knowledge docs ─────────────────────────────────
    doc_chunks = retrieve(query, top_k=3)

    # ── MCTS decision ─────────────────────────────────────────────────────────
    mcts_decision = "auto_resolve"
    mcts_scores   = {}
    active_warranty = next((w for w in warranties if w.get("status") == "Active"), None)
    if past_tickets or active_warranty:
        state = build_state(
            ticket={"priority": "medium", "created_date": "", "issue": query},
            warranty=active_warranty,
            customer_tickets=past_tickets,
        )
        mcts_decision, mcts_scores = mcts_decide(state)

    # ── Build context strings ─────────────────────────────────────────────────
    customer_ctx = ""
    if customer:
        w_info = f"Warranty: {active_warranty['status'] if active_warranty else 'None/Expired'}"
        customer_ctx = (
            f"Customer: {customer['name']} ({customer['city']}) | "
            f"Segment: {customer['segment']} | {w_info} | "
            f"Past tickets: {len(past_tickets)}"
        )

    graph_ctx = "\n".join(c["text"] for c in graph_context[:3]) if graph_context else ""
    doc_ctx   = format_context(doc_chunks)

    # ── If Groq is unavailable, return structured data directly ───────────────
    if not _get_client():
        if customer:
            answer = _data_fallback(query, customer, past_tickets, warranties, mcts_decision)
        else:
            answer = (
                "[Data-only mode — Groq not connected]\n\n"
                "Ask about a specific customer by name (e.g., 'What problem is Divya Joshi having?')\n"
                "or use the chat hints below."
            )
        _, safe, _ = validate_response(answer, intent="support")
        return {
            "answer": answer,
            "mcts_decision": mcts_decision,
            "mcts_scores": mcts_scores,
            "ticket_created": None,
            "context_used": "data_fallback",
            "agent_engine": "data_fallback",
        }

    # ── Try AutoGen multi-agent first for complex queries ─────────────────────
    agent_engine = "groq_llm"
    system_prompt = (
        "You are a helpful appliance support agent. "
        "Answer only based on the provided context. "
        "Do not promise refunds or replacements without approval. "
        "Be concise (max 3-4 sentences)."
    )
    user_prompt = (
        f"Customer context: {customer_ctx}\n\n"
        f"Related records:\n{graph_ctx}\n\n"
        f"Policy/Knowledge:\n{doc_ctx}\n\n"
        f"MCTS recommended action: {mcts_decision}\n\n"
        f"Customer query: {query}\n\n"
        "Provide a helpful, accurate response."
    )

    autogen_ans = _run_autogen(query, customer_ctx, doc_ctx, mcts_decision, session_id)
    if autogen_ans:
        raw_answer  = autogen_ans
        agent_engine = "autogen"
    else:
        raw_answer = call_llm(system_prompt, user_prompt, session_id)

    answer, safe, _ = validate_response(raw_answer, intent="support")

    # ── Auto-create ticket for complaints/service requests ────────────────────
    ticket_created = None
    keywords = ["not working", "broken", "issue", "problem", "complaint", "repair", "service"]
    if any(k in query.lower() for k in keywords) and customer_id:
        ticket_created = add_ticket({
            "customer_id": customer_id,
            "issue": query[:100],
            "priority": "medium",
            "warranty_id": active_warranty["warranty_id"] if active_warranty else "",
            "appliance_id": active_warranty["appliance_id"] if active_warranty else "",
        })

    return {
        "answer": answer,
        "mcts_decision": mcts_decision,
        "mcts_scores": mcts_scores,
        "ticket_created": ticket_created,
        "context_used": "graph_rag + corrective_rag",
        "agent_engine": agent_engine,
    }
