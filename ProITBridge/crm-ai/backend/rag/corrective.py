"""
corrective.py — Corrective RAG logic.
After initial retrieval, scores chunk relevance against the query.
If score < threshold → rewrites query → re-retrieves → flags low confidence.
"""
from backend.rag.retriever import naive_retrieve, format_context
from backend.utils.embeddings import embed_text, cosine_similarity
from backend.config import settings
from groq import Groq
from typing import List, Dict, Tuple
import json

_groq = Groq(api_key=settings.GROQ_API_KEY)


def score_relevance(query: str, chunks: List[Dict]) -> float:
    """
    Average cosine similarity between query embedding and chunk embeddings.
    Used to determine if retrieved context is actually relevant.
    """
    if not chunks:
        return 0.0

    query_vec = embed_text(query)
    scores = []
    for chunk in chunks:
        if chunk.get("embedding"):
            scores.append(cosine_similarity(query_vec, chunk["embedding"]))
        else:
            # Re-embed the chunk text for scoring
            chunk_vec = embed_text(chunk["text"])
            scores.append(cosine_similarity(query_vec, chunk_vec))

    return sum(scores) / len(scores) if scores else 0.0


def rewrite_query(original_query: str) -> str:
    """
    Use LLM to rewrite a poorly-performing search query.
    Makes it more specific and retrieval-friendly.
    """
    prompt = f"""You are a search query optimizer for a CRM system.
The following query returned poor results. Rewrite it to be more specific and retrieval-friendly.
Keep it concise (under 20 words). Return ONLY the rewritten query, nothing else.

Original query: {original_query}
Rewritten query:"""

    resp = _groq.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50,
        temperature=0.3
    )
    return resp.choices[0].message.content.strip()


def corrective_retrieve(
    query: str,
    filters: Dict = None,
    top_k: int = None
) -> Tuple[List[Dict], bool, float]:
    """
    Corrective RAG pipeline:
    1. Retrieve chunks
    2. Score relevance
    3. If score < threshold → rewrite query → re-retrieve
    4. Return (chunks, is_high_confidence, final_score)
    """
    top_k = top_k or settings.TOP_K_RESULTS
    threshold = settings.RELEVANCE_THRESHOLD

    # First attempt
    chunks = naive_retrieve(query, filters=filters, top_k=top_k)
    score = score_relevance(query, chunks)

    if score >= threshold:
        return chunks, True, score

    # Score too low — rewrite and retry
    rewritten = rewrite_query(query)
    print(f"[Corrective RAG] Low score ({score:.2f}). Rewritten query: '{rewritten}'")

    chunks = naive_retrieve(rewritten, filters=filters, top_k=top_k)
    score = score_relevance(rewritten, chunks)

    is_confident = score >= threshold
    return chunks, is_confident, score
