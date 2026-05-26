"""
semantic_rag.py — Semantic RAG: pure embedding-based retrieval from Pinecone/fallback.
"""
from typing import List, Dict, Optional
from backend.utils.embeddings import embed_text
from backend.db.pinecone_client import search as pinecone_search

def retrieve(query: str, top_k: int = 4, filters: Optional[Dict] = None) -> List[Dict]:
    """Embed query and retrieve top-k semantically similar chunks."""
    q_vec = embed_text(query)
    return pinecone_search(q_vec, top_k=top_k, filters=filters)

def format_context(chunks: List[Dict]) -> str:
    if not chunks:
        return "No relevant documents found."
    parts = []
    for i, c in enumerate(chunks, 1):
        src = c.get("source_type", "doc")
        parts.append(f"[{i}] ({src}): {c['text'][:400]}")
    return "\n\n".join(parts)
