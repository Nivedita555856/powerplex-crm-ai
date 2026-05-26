"""
hybrid_rag.py — Hybrid RAG: combines keyword (BM25-style) + semantic scores.
Falls back gracefully to semantic-only when docs are not indexed.
"""
import re
from typing import List, Dict, Optional
from backend.rag.semantic_rag import retrieve as semantic_retrieve
from backend.data_loader import get_docs

def _keyword_score(text: str, query: str) -> float:
    """Simple keyword overlap score (no external library)."""
    query_terms = set(re.findall(r"\w+", query.lower()))
    doc_terms   = set(re.findall(r"\w+", text.lower()))
    if not query_terms:
        return 0.0
    overlap = len(query_terms & doc_terms)
    return overlap / len(query_terms)

def retrieve(query: str, top_k: int = 4, filters: Optional[Dict] = None) -> List[Dict]:
    """Retrieve using semantic + keyword re-ranking."""
    # Get semantic candidates (2x top_k for re-ranking pool)
    candidates = semantic_retrieve(query, top_k=top_k * 2, filters=filters)

    # Re-rank with combined score
    for c in candidates:
        sem_score = c.get("score", 0.5)
        kw_score  = _keyword_score(c.get("text", ""), query)
        c["hybrid_score"] = 0.65 * sem_score + 0.35 * kw_score

    candidates.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return candidates[:top_k]

def format_context(chunks: List[Dict]) -> str:
    if not chunks:
        return "No relevant documents found."
    parts = []
    for i, c in enumerate(chunks, 1):
        score = round(c.get("hybrid_score", c.get("score", 0)), 2)
        parts.append(f"[{i}] (score={score}): {c['text'][:400]}")
    return "\n\n".join(parts)
