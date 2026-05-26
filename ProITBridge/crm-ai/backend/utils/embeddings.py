"""
embeddings.py — HuggingFace sentence-transformers embeddings (free, no API cost).
Falls back to TF-IDF style random-stable vectors when model unavailable.
"""
from typing import List
import hashlib, struct
from backend.config import settings

_model = None

def _get_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer(settings.EMBEDDING_MODEL)
            print(f"[Embeddings] Loaded model: {settings.EMBEDDING_MODEL}")
        except Exception as e:
            print(f"[Embeddings] Model load failed: {e} — using hash fallback")
            _model = "fallback"
    return _model

def _hash_embed(text: str, dim: int = 384) -> List[float]:
    """Stable hash-based pseudo-embedding for fallback (no model needed)."""
    vec = []
    for i in range(dim):
        seed = hashlib.md5(f"{text[:200]}:{i}".encode()).digest()
        val = struct.unpack("f", seed[:4])[0]
        vec.append(max(-1.0, min(1.0, val)))
    norm = sum(x*x for x in vec) ** 0.5 or 1.0
    return [x / norm for x in vec]

def embed_text(text: str) -> List[float]:
    model = _get_model()
    if model == "fallback":
        return _hash_embed(text, settings.EMBEDDING_DIM)
    try:
        vec = model.encode(text, normalize_embeddings=True).tolist()
        return vec
    except Exception:
        return _hash_embed(text, settings.EMBEDDING_DIM)

def embed_batch(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    if model == "fallback":
        return [_hash_embed(t, settings.EMBEDDING_DIM) for t in texts]
    try:
        vecs = model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [v.tolist() for v in vecs]
    except Exception:
        return [_hash_embed(t, settings.EMBEDDING_DIM) for t in texts]
