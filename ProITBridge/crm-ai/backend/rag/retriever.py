"""
retriever.py — Unified RAG retriever combining Zilliz (semantic) + Supabase (structured).
Supports: Naive RAG, Agentic RAG (multi-step), Hybrid retrieval.
"""
from backend.db import pinecone_client, supabase_client
from backend.utils.embeddings import embed_text
from backend.config import settings
from typing import List, Dict, Optional
import json


# ── Naive RAG ─────────────────────────────────────────────────────────────────
def naive_retrieve(query: str, filters: Optional[Dict] = None, top_k: int = None) -> List[Dict]:
    """
    Simple single-step semantic search.
    Best for: factual lookups, quick Q&A.
    """
    top_k = top_k or settings.TOP_K_RESULTS
    query_embedding = embed_text(query)
    return pinecone_client.search(query_embedding, top_k=top_k, filters=filters)


# ── Hybrid Retrieval ──────────────────────────────────────────────────────────
def hybrid_retrieve(query: str, deal_id: Optional[str] = None) -> Dict:
    """
    Combines Zilliz semantic search + Supabase structured query.
    Returns { vector_results, structured_data }
    """
    # Vector search
    filters = {"deal_id": deal_id} if deal_id else {}
    vector_results = naive_retrieve(query, filters=filters)

    # Structured data from Supabase
    structured_data = {}
    if deal_id:
        deal = supabase_client.get_deal_by_id(deal_id)
        activities = supabase_client.get_activities(deal_id=deal_id, limit=5)
        structured_data = {
            "deal": deal,
            "recent_activities": activities
        }

    return {
        "vector_results": vector_results,
        "structured_data": structured_data
    }


# ── Agentic RAG ───────────────────────────────────────────────────────────────
def agentic_retrieve(query: str, deal_id: Optional[str] = None) -> Dict:
    """
    Multi-step retrieval — fetches different data sources in sequence
    and combines them for richer context.
    Steps: emails → transcripts → deal structure → activities
    """
    base_filters = {"deal_id": deal_id} if deal_id else {}

    # Step 1: Retrieve emails
    email_results = naive_retrieve(
        query,
        filters={**base_filters, "source_type": "email"},
        top_k=3
    )

    # Step 2: Retrieve call transcripts
    transcript_results = naive_retrieve(
        query,
        filters={**base_filters, "source_type": "transcript"},
        top_k=2
    )

    # Step 3: Retrieve documents (proposals, notes)
    doc_results = naive_retrieve(
        query,
        filters={**base_filters, "source_type": "document"},
        top_k=2
    )

    # Step 4: Structured deal + activity data
    structured = {}
    if deal_id:
        deal = supabase_client.get_deal_by_id(deal_id)
        activities = supabase_client.get_activities(deal_id=deal_id, limit=10)
        follow_ups = supabase_client.get_follow_ups()
        structured = {
            "deal": deal,
            "activities": activities,
            "pending_follow_ups": [
                f for f in follow_ups if f.get("deal_id") == deal_id
            ]
        }

    return {
        "emails":      email_results,
        "transcripts": transcript_results,
        "documents":   doc_results,
        "structured":  structured,
        "all_chunks":  email_results + transcript_results + doc_results
    }


# ── Context formatter ─────────────────────────────────────────────────────────
def format_context(retrieved: Dict) -> str:
    """
    Formats retrieved data into a clean prompt context string for the LLM.
    """
    parts = []

    # Vector chunks
    chunks = retrieved.get("all_chunks") or retrieved.get("vector_results", [])
    if chunks:
        parts.append("=== RETRIEVED KNOWLEDGE ===")
        for i, chunk in enumerate(chunks, 1):
            src = chunk.get("source_type", "unknown")
            date = chunk.get("doc_date", "")
            parts.append(f"[{i}] ({src} {date})\n{chunk['text']}")

    # Structured deal data
    structured = retrieved.get("structured_data") or retrieved.get("structured", {})
    if structured.get("deal"):
        deal = structured["deal"]
        parts.append("\n=== DEAL DETAILS ===")
        parts.append(
            f"Title: {deal.get('title')}\n"
            f"Stage: {deal.get('stage')}\n"
            f"Value: ${deal.get('value', 0):,.0f}\n"
            f"Close Date: {deal.get('expected_close_date')}\n"
            f"Last Contact: {deal.get('last_contact_date')}"
        )

    if structured.get("activities"):
        parts.append("\n=== RECENT ACTIVITIES ===")
        for act in structured["activities"][:5]:
            parts.append(f"- [{act.get('type')}] {act.get('summary')} ({act.get('created_at', '')[:10]})")

    return "\n".join(parts)
