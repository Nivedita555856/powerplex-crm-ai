"""
zilliz_client.py — Zilliz Cloud (Milvus-compatible) vector DB operations.
Collection: crm_embeddings
Fields: id, embedding (384-dim), text, source_type, account_id, deal_id, rep_id, doc_date
"""
from pymilvus import MilvusClient, DataType, CollectionSchema, FieldSchema
from backend.config import settings
from typing import List, Dict, Any, Optional
import json
import uuid

# ── Singleton client ──────────────────────────────────────────────────────────
_client: Optional[MilvusClient] = None

def get_client() -> MilvusClient:
    global _client
    if _client is None:
        _client = MilvusClient(
            uri=settings.ZILLIZ_CLOUD_URI,
            token=settings.ZILLIZ_CLOUD_TOKEN
        )
    return _client


# ── Collection setup ──────────────────────────────────────────────────────────
def ensure_collection() -> None:
    """Create the collection if it doesn't exist yet."""
    client = get_client()
    name = settings.ZILLIZ_COLLECTION

    if client.has_collection(name):
        return

    schema = MilvusClient.create_schema(auto_id=False, enable_dynamic_field=True)
    schema.add_field("id",          DataType.VARCHAR,      max_length=64,  is_primary=True)
    schema.add_field("embedding",   DataType.FLOAT_VECTOR, dim=settings.EMBEDDING_DIM)
    schema.add_field("text",        DataType.VARCHAR,      max_length=4096)
    schema.add_field("source_type", DataType.VARCHAR,      max_length=64)   # email|transcript|doc|note
    schema.add_field("account_id",  DataType.VARCHAR,      max_length=64)
    schema.add_field("deal_id",     DataType.VARCHAR,      max_length=64)
    schema.add_field("rep_id",      DataType.VARCHAR,      max_length=64)
    schema.add_field("doc_date",    DataType.VARCHAR,      max_length=32)

    index_params = client.prepare_index_params()
    index_params.add_index(
        field_name="embedding",
        index_type="AUTOINDEX",
        metric_type="COSINE"
    )

    client.create_collection(
        collection_name=name,
        schema=schema,
        index_params=index_params
    )
    print(f"[Zilliz] Collection '{name}' created.")


# ── Insert ────────────────────────────────────────────────────────────────────
def insert_chunks(chunks: List[Dict]) -> int:
    """
    Insert embedding chunks into Zilliz.
    Each chunk: { text, embedding, source_type, account_id, deal_id, rep_id, doc_date }
    Returns count of inserted records.
    """
    ensure_collection()
    client = get_client()

    data = []
    for chunk in chunks:
        data.append({
            "id":          str(uuid.uuid4()).replace("-", "")[:20],
            "embedding":   chunk["embedding"],
            "text":        chunk["text"][:4000],
            "source_type": chunk.get("source_type", "unknown"),
            "account_id":  chunk.get("account_id", ""),
            "deal_id":     chunk.get("deal_id", ""),
            "rep_id":      chunk.get("rep_id", ""),
            "doc_date":    chunk.get("doc_date", ""),
        })

    if data:
        client.insert(collection_name=settings.ZILLIZ_COLLECTION, data=data)

    return len(data)


# ── Search ────────────────────────────────────────────────────────────────────
def search(
    query_embedding: List[float],
    top_k: int = 5,
    filters: Optional[Dict] = None
) -> List[Dict]:
    """
    Semantic search in Zilliz.
    filters: { account_id, deal_id, source_type } — all optional
    Returns list of { text, score, source_type, account_id, deal_id }
    """
    ensure_collection()
    client = get_client()

    # Build filter expression
    expr_parts = []
    if filters:
        if filters.get("account_id"):
            expr_parts.append(f'account_id == "{filters["account_id"]}"')
        if filters.get("deal_id"):
            expr_parts.append(f'deal_id == "{filters["deal_id"]}"')
        if filters.get("source_type"):
            expr_parts.append(f'source_type == "{filters["source_type"]}"')

    filter_expr = " && ".join(expr_parts) if expr_parts else ""

    results = client.search(
        collection_name=settings.ZILLIZ_COLLECTION,
        data=[query_embedding],
        limit=top_k,
        filter=filter_expr if filter_expr else None,
        output_fields=["text", "source_type", "account_id", "deal_id", "doc_date"]
    )

    hits = []
    if results and results[0]:
        for hit in results[0]:
            hits.append({
                "text":        hit["entity"].get("text", ""),
                "score":       hit["distance"],
                "source_type": hit["entity"].get("source_type", ""),
                "account_id":  hit["entity"].get("account_id", ""),
                "deal_id":     hit["entity"].get("deal_id", ""),
                "doc_date":    hit["entity"].get("doc_date", ""),
            })

    return hits


# ── Delete ────────────────────────────────────────────────────────────────────
def delete_by_deal(deal_id: str) -> None:
    """Remove all vectors for a specific deal."""
    ensure_collection()
    client = get_client()
    client.delete(
        collection_name=settings.ZILLIZ_COLLECTION,
        filter=f'deal_id == "{deal_id}"'
    )
