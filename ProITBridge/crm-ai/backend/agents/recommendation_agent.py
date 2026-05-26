"""
recommendation_agent.py — Product recommendations via Semantic RAG + customer history.
Uses CrewAI multi-agent crew (Market Analyst + Product Expert) when available,
falls back to direct Groq LLM call, then to static data response.
"""
from typing import Dict
from backend.rag.semantic_rag import retrieve, format_context
from backend.data_loader import get_appliances, get_warranty_by_customer, get_customer_by_id
from backend.utils.llm import call_llm, _get_client


def recommend(customer_id: str, query: str = "", session_id: str = "") -> Dict:
    """Generate product recommendations for a customer."""
    customer   = get_customer_by_id(customer_id)
    warranties = get_warranty_by_customer(customer_id)
    appliances = get_appliances()

    owned_ids = {w["appliance_id"] for w in warranties}
    owned     = [a for a in appliances if a["appliance_id"] in owned_ids]
    not_owned = [a for a in appliances if a["appliance_id"] not in owned_ids]

    # Semantic RAG for relevant product info
    search_q   = query or f"best appliance for {customer.get('city','home') if customer else 'home'}"
    doc_chunks = retrieve(search_q, top_k=3)
    doc_ctx    = format_context(doc_chunks)

    owned_str    = ", ".join(f"{a['brand']} {a['model']}" for a in owned) or "None"
    products_str = "\n".join(
        f"- {a['appliance_id']}: {a['brand']} {a['model']} ({a['category']}) — Rs.{int(a.get('price',0)):,}"
        for a in not_owned[:6]
    )

    segment = customer.get("segment", "Standard") if customer else "Standard"
    city    = customer.get("city", "") if customer else ""
    name    = customer.get("name", "Customer") if customer else "Customer"

    customer_profile = (
        f"Name: {name} | Segment: {segment} | City: {city} | "
        f"Currently owns: {owned_str}"
    )

    # ── Try CrewAI crew first ──────────────────────────────────────────────────
    agent_engine = "groq_llm"
    answer = None

    try:
        from backend.agents.crewai_agents import run_recommendation_crew, crewai_available
        from backend.config import settings
        if crewai_available() and settings.GROQ_API_KEY:
            crew_ans = run_recommendation_crew(
                customer_profile=customer_profile,
                query=query or "General recommendation",
                appliances_ctx=products_str,
                groq_api_key=settings.GROQ_API_KEY,
                llm_model=f"groq/{settings.LLM_MODEL}",
            )
            if crew_ans:
                answer       = crew_ans
                agent_engine = "crewai"
    except Exception as e:
        print(f"[RecommendAgent] CrewAI skipped: {e}")

    # ── Groq LLM fallback ────────────────────────────────────────────────────
    if not answer:
        if _get_client():
            system_prompt = "You are an expert appliance sales advisor. Recommend products concisely."
            user_prompt = (
                f"Customer profile: {customer_profile}\n"
                f"Customer query: {query or 'General recommendation'}\n\n"
                f"Available products (not yet purchased):\n{products_str}\n\n"
                f"Product knowledge:\n{doc_ctx}\n\n"
                "Recommend 2-3 products with a brief reason for each. Under 150 words."
            )
            answer = call_llm(system_prompt, user_prompt, session_id)
        else:
            # Data-only fallback
            lines = [
                f"Top recommendations for {name} ({segment} segment):\n"
            ]
            for a in not_owned[:3]:
                lines.append(
                    f"  {a['brand']} {a['model']} ({a['category']}) — "
                    f"Rs.{int(a.get('price',0)):,}"
                )
            lines.append(
                "\nNote: Connect Groq or install CrewAI for AI-powered reasoning."
            )
            answer = "\n".join(lines)
            agent_engine = "data_fallback"

    return {
        "answer": answer,
        "recommended_products": not_owned[:3],
        "context_used": "semantic_rag",
        "agent_engine": agent_engine,
    }
