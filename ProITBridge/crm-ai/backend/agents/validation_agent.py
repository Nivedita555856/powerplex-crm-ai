"""
validation_agent.py — Validates claims, warranty requests, refund eligibility.
Uses Hybrid RAG to cross-check against policy documents.
"""
from typing import Dict
from backend.rag.hybrid_rag import retrieve, format_context
from backend.guardrails.guardrails import validate_warranty_claim, check_refund_authority
from backend.data_loader import get_warranty_by_customer, get_customer_by_id
from backend.utils.llm import call_llm

def validate_claim(customer_id: str, claim_type: str, claim_details: str,
                   amount: int = 0, session_id: str = "") -> Dict:
    """
    Validates a warranty or refund claim against policy.
    Returns validation result + whether human approval is required.
    """
    customer   = get_customer_by_id(customer_id)
    warranties = get_warranty_by_customer(customer_id)
    active_w   = next((w for w in warranties if w.get("status") == "Active"), None)

    # Guardrail checks
    warranty_valid, warranty_msg = validate_warranty_claim(customer_id, active_w)

    needs_human = False
    auth_msg    = ""
    if claim_type == "refund" and amount > 0:
        can_approve, auth_msg = check_refund_authority(amount, "bot")
        needs_human = not can_approve

    # Hybrid RAG for policy context
    policy_query = f"{claim_type} policy {claim_details}"
    chunks = retrieve(policy_query, top_k=3)
    ctx    = format_context(chunks)

    system_prompt = "You are a strict claim validation agent. Evaluate based on policy only."
    user_prompt   = f"""Claim type: {claim_type}
Claim details: {claim_details}
Amount: ₹{amount:,} (if applicable)
Warranty status: {warranty_msg}
Authority check: {auth_msg}

Policy context:
{ctx}

Assess: Is this claim valid? What action should be taken? 
Keep response under 3 sentences."""

    answer = call_llm(system_prompt, user_prompt, session_id)

    return {
        "answer": answer,
        "warranty_valid": warranty_valid,
        "needs_human_approval": needs_human,
        "authority_message": auth_msg,
        "context_used": "hybrid_rag",
    }
