"""
agentic_rag.py — Agentic RAG: multi-step retrieval with query decomposition.
Step 1: Decompose complex query into sub-queries via LLM
Step 2: Retrieve for each sub-query
Step 3: Merge and deduplicate results
"""
import re
from typing import List, Dict, Optional
from backend.rag.semantic_rag import retrieve as semantic_retrieve
from backend.utils.embeddings import embed_text

def _decompose_query(query: str) -> List[str]:
    """
    Simple rule-based query decomposition.
    For complex queries, breaks into sub-questions.
    """
    sub_queries = [query]
    # If query contains multiple concepts, split on conjunctions
    if " and " in query.lower():
        parts = re.split(r"\s+and\s+", query, flags=re.IGNORECASE)
        sub_queries = [p.strip() for p in parts if p.strip()]
    elif "?" in query and len(query) > 80:
        # Break long queries at '?' boundaries
        parts = [p.strip() for p in query.split("?") if p.strip()]
        sub_queries = [p + "?" for p in parts]
    return sub_queries[:3]  # Max 3 sub-queries

def retrieve(query: str, top_k: int = 4, filters: Optional[Dict] = None) -> List[Dict]:
    """Multi-step agentic retrieval."""
    sub_queries = _decompose_query(query)
    all_results: Dict[str, Dict] = {}

    for sq in sub_queries:
        results = semantic_retrieve(sq, top_k=top_k, filters=filters)
        for r in results:
            key = r["text"][:100]  # dedup key
            if key not in all_results or r.get("score", 0) > all_results[key].get("score", 0):
                all_results[key] = r

    merged = sorted(all_results.values(), key=lambda x: x.get("score", 0), reverse=True)
    return merged[:top_k]

def format_context(chunks: List[Dict]) -> str:
    if not chunks:
        return "No relevant documents found."
    return "\n\n".join(f"[{i+1}]: {c['text'][:400]}" for i, c in enumerate(chunks))
