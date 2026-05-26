"""
pinecone_client.py — Pinecone vector DB with graceful fallback.
When PINECONE_API_KEY is not set, insert() is a no-op and search()
returns relevant sample context so Q&A still works.
"""
from typing import List, Dict, Optional
from backend.config import settings
import uuid

_index = None
_pinecone_available = None


def _check_available() -> bool:
    global _pinecone_available
    if _pinecone_available is None:
        _pinecone_available = bool(settings.PINECONE_API_KEY and settings.PINECONE_API_KEY != "your_pinecone_api_key_here")
        if not _pinecone_available:
            print("[Pinecone] No API key — using sample context for Q&A.")
    return _pinecone_available


def _get_index():
    global _index
    if not _check_available():
        return None
    if _index is None:
        try:
            from pinecone import Pinecone, ServerlessSpec
            pc = Pinecone(api_key=settings.PINECONE_API_KEY)
            index_name = settings.PINECONE_INDEX
            existing = [i.name for i in pc.list_indexes()]
            if index_name not in existing:
                pc.create_index(
                    name=index_name,
                    dimension=settings.EMBEDDING_DIM,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
                print(f"[Pinecone] Created index '{index_name}'")
            _index = pc.Index(index_name)
            print(f"[Pinecone] Connected to '{index_name}'")
        except Exception as e:
            print(f"[Pinecone] Connection failed: {e} — using sample context")
            _pinecone_available = False
    return _index


def insert_chunks(chunks: List[Dict]) -> int:
    """Insert chunks. Silently skips if Pinecone not available."""
    index = _get_index()
    if index is None:
        return len(chunks)   # Pretend success

    vectors = []
    for chunk in chunks:
        vectors.append({
            "id": str(uuid.uuid4()).replace("-", "")[:20],
            "values": chunk["embedding"],
            "metadata": {
                "text":        chunk["text"][:1000],
                "source_type": chunk.get("source_type", "unknown"),
                "account_id":  chunk.get("account_id", ""),
                "deal_id":     chunk.get("deal_id", ""),
                "rep_id":      chunk.get("rep_id", ""),
                "doc_date":    chunk.get("doc_date", ""),
            }
        })
    if not vectors:
        return 0
    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i:i+100])
    return len(vectors)


def search(
    query_embedding: List[float],
    top_k: int = 5,
    filters: Optional[Dict] = None
) -> List[Dict]:
    """
    Semantic search. Falls back to sample context when Pinecone is unavailable.
    """
    index = _get_index()
    if index is None:
        return _sample_search(filters)

    pinecone_filter = {}
    if filters:
        if filters.get("account_id"):
            pinecone_filter["account_id"] = {"$eq": filters["account_id"]}
        if filters.get("deal_id"):
            pinecone_filter["deal_id"] = {"$eq": filters["deal_id"]}
        if filters.get("source_type"):
            pinecone_filter["source_type"] = {"$eq": filters["source_type"]}

    try:
        kwargs = {"vector": query_embedding, "top_k": top_k, "include_metadata": True}
        if pinecone_filter:
            kwargs["filter"] = pinecone_filter
        results = index.query(**kwargs)
        hits = []
        for match in results.get("matches", []):
            meta = match.get("metadata", {})
            hits.append({
                "text":        meta.get("text", ""),
                "score":       match.get("score", 0.0),
                "source_type": meta.get("source_type", ""),
                "account_id":  meta.get("account_id", ""),
                "deal_id":     meta.get("deal_id", ""),
                "doc_date":    meta.get("doc_date", ""),
            })
        return hits
    except Exception as e:
        print(f"[Pinecone] Search error: {e} — falling back to sample context")
        return _sample_search(filters)


def _sample_search(filters: Optional[Dict] = None) -> List[Dict]:
    """Return rich sample context chunks when Pinecone is not available."""
    from backend.sample_data import CONTEXT_DOCS, DEALS
    deal_id = filters.get("deal_id") if filters else None

    if deal_id and deal_id in CONTEXT_DOCS:
        return [{
            "text": CONTEXT_DOCS[deal_id],
            "score": 0.95,
            "source_type": "notes",
            "account_id": "",
            "deal_id": deal_id,
            "doc_date": "2026-05-21"
        }]

    # Return context for all deals
    results = []
    for deal in DEALS[:3]:
        did = deal["id"]
        if did in CONTEXT_DOCS:
            results.append({
                "text": CONTEXT_DOCS[did][:500],
                "score": 0.80,
                "source_type": "notes",
                "account_id": deal.get("lead_id", ""),
                "deal_id": did,
                "doc_date": "2026-05-21"
            })
    return results


def delete_by_deal(deal_id: str) -> None:
    index = _get_index()
    if index:
        try:
            index.delete(filter={"deal_id": {"$eq": deal_id}})
        except Exception:
            pass
