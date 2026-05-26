"""
prestart.py — Run once before uvicorn starts on Render.
Downloads the sentence-transformers model so the first request isn't slow.
"""
import os, sys

MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
CACHE = os.path.join(os.path.dirname(__file__), "..", ".model_cache")

print(f"[prestart] Downloading embedding model '{MODEL}' → {CACHE}")
try:
    from sentence_transformers import SentenceTransformer
    SentenceTransformer(MODEL, cache_folder=CACHE)
    print("[prestart] Model ready ✓")
except Exception as e:
    print(f"[prestart] Warning: could not pre-download model: {e}")
    sys.exit(0)   # non-fatal — app will try again at first request
