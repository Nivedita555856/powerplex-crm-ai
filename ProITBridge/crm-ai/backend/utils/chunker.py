"""
chunker.py — Pure Python text splitter. Zero external dependencies.
"""
from typing import List, Dict

CHUNK_SIZE    = 400
CHUNK_OVERLAP = 60

def chunk_text(text: str, metadata: Dict = None) -> List[Dict]:
    """Split text into overlapping chunks with metadata."""
    metadata = metadata or {}
    if not text or not text.strip():
        return []
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        window = words[i: i + CHUNK_SIZE]
        chunk_text_str = " ".join(window)
        if chunk_text_str.strip():
            chunks.append({"text": chunk_text_str, **metadata})
        if i + CHUNK_SIZE >= len(words):
            break
        i += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks

def chunk_documents(docs: List[Dict]) -> List[Dict]:
    """Chunk a list of documents. Each doc must have 'content' key."""
    all_chunks = []
    for doc in docs:
        content = doc.get("content") or doc.get("text") or ""
        meta    = {k: v for k, v in doc.items() if k not in ("content", "text")}
        all_chunks.extend(chunk_text(content, meta))
    return all_chunks
