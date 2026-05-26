"""
qa_agent.py — Contextual Q&A Agent.
Handles natural language questions from reps using Agentic + Corrective RAG.
Maintains conversation context via MCP.
"""
from backend.rag.retriever import agentic_retrieve, format_context
from backend.rag.corrective import corrective_retrieve
from backend.mcp.context_manager import get_context
from backend.config import settings
from groq import Groq
from typing import Dict, Optional

_groq = Groq(api_key=settings.GROQ_API_KEY)

SYSTEM_PROMPT = """You are an AI Sales Copilot. You help sales reps make better decisions by analyzing their CRM data, emails, call transcripts, and deal history.

Your job:
- Answer questions about specific deals and prospects
- Suggest concrete next steps with reasoning
- Highlight risks and opportunities
- Be direct, specific, and actionable

Always ground your answers in the provided context. If the context doesn't have enough information, say so clearly."""


def answer_query(
    query: str,
    session_id: str,
    deal_id: Optional[str] = None
) -> Dict:
    """
    Main Q&A pipeline:
    1. Load MCP context
    2. Run Agentic RAG retrieval
    3. Apply Corrective RAG check
    4. Generate LLM answer with full context
    5. Save turn to MCP

    Returns: { answer, confidence, sources, suggested_actions }
    """

    # Step 1: Load session context
    mcp = get_context(session_id)
    mcp.add_turn("user", query, agent="rep")

    # Step 2: Agentic RAG — multi-step retrieval
    retrieved = agentic_retrieve(query=query, deal_id=deal_id)
    context_str = format_context(retrieved)

    # Step 3: Corrective RAG check on vector chunks
    all_chunks = retrieved.get("all_chunks", [])
    confidence = "high"
    if all_chunks:
        from backend.rag.corrective import score_relevance
        score = score_relevance(query, all_chunks)
        if score < settings.RELEVANCE_THRESHOLD:
            confidence = "low"
            # Re-retrieve with corrective logic
            corrected_chunks, is_confident, score = corrective_retrieve(
                query=query,
                filters={"deal_id": deal_id} if deal_id else {},
            )
            if corrected_chunks:
                retrieved["all_chunks"] = corrected_chunks
                context_str = format_context(retrieved)
            confidence = "high" if is_confident else "low"

    # Step 4: Build messages for LLM
    prior_messages = mcp.get_messages_for_llm()[:-1]  # Exclude current query (already added)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if prior_messages:
        messages.extend(prior_messages[-6:])  # Last 3 exchanges

    messages.append({
        "role": "user",
        "content": f"""CONTEXT FROM CRM:
{context_str}

QUESTION: {query}

Provide a direct answer and then suggest 1-2 specific next actions."""
    })

    # Step 5: LLM call
    resp = _groq.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        max_tokens=500,
        temperature=0.4
    )

    answer = resp.choices[0].message.content.strip()

    # Step 6: Save assistant turn to MCP
    mcp.add_turn("assistant", answer, agent="qa_agent")

    # Build sources list
    sources = [
        {
            "type": c.get("source_type", "unknown"),
            "date": c.get("doc_date", ""),
            "preview": c["text"][:80] + "..."
        }
        for c in (retrieved.get("all_chunks", []))[:3]
    ]

    return {
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "deal_id": deal_id,
        "session_id": session_id
    }
