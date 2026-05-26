"""
corrective_rag.py — Corrective RAG: self-check relevance, re-query if needed.
Step 1: Retrieve candidates
Step 2: Check relevance scores — filter below threshold
Step 3: If insufficient results, reformulate query and retry once
"""
from typing import List, Dict, Optional
from backend.config import settings
from backend.rag.semantic_rag import retrieve as semantic_retrieve

def _relevance_filter(chunks: List[Dict], threshold: float) -> List[Dict]:
    return [c for c in chunks if c.get("score", 0) >= threshold]

def _reformulate(query: str) -> str:
    """Simple query expansion for re-retrieval."""
    expansions = {
        "warranty": "warranty policy coverage terms conditions",
        "refund":   "refund return policy amount eligibility",
        "repair":   "repair service technician visit fix",
        "not working": "troubleshooting error issue fault",
        "install":  "installation guide setup steps",
    }
    q_lower = query.lower()
    for key, expansion in expansions.items():
        if key in q_lower:
            return f"{query} {expansion}"
    return query + " appliance service support"

def retrieve(query: str, top_k: int = 4, filters: Optional[Dict] = None) -> List[Dict]:
    """Retrieve with quality check and one automatic re-query if needed."""
    threshold = settings.RELEVANCE_THRESHOLD
    results = semantic_retrieve(query, top_k=top_k, filters=filters)
    good = _relevance_filter(results, threshold)

    if len(good) < 2:
        # Re-query with expanded/reformulated query
        new_query = _reformulate(query)
        results2  = semantic_retrieve(new_query, top_k=top_k, filters=filters)
        # Merge, preferring higher-scored results
        seen = {r["text"][:80] for r in good}
        for r in results2:
            if r["text"][:80] not in seen:
                good.append(r)
                seen.add(r["text"][:80])

    return sorted(good, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

def format_context(chunks: List[Dict]) -> str:
    if not chunks:
        return "No relevant documents found."
    return "\n\n".join(f"[{i+1}] (relevance={round(c.get('score',0),2)}): {c['text'][:400]}"
                        for i, c in enumerate(chunks))
