"""
context_manager.py — MCP (Model Context Protocol) session manager.
Stores per-session conversation history and entity context.
"""
from typing import List, Dict, Optional
from datetime import datetime
from backend.sample_data import CONTEXT_STORE

MAX_CONTEXT_TURNS = 10   # keep last N turns to avoid token bloat


def save_turn(session_id: str, role: str, content: str, metadata: Dict = None):
    """Append a single turn to session context."""
    if session_id not in CONTEXT_STORE:
        CONTEXT_STORE[session_id] = []
    CONTEXT_STORE[session_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": metadata or {},
    })
    # Trim to last N turns
    if len(CONTEXT_STORE[session_id]) > MAX_CONTEXT_TURNS * 2:
        CONTEXT_STORE[session_id] = CONTEXT_STORE[session_id][-MAX_CONTEXT_TURNS * 2:]


def get_context(session_id: str) -> List[Dict]:
    """Return conversation history for a session."""
    return CONTEXT_STORE.get(session_id, [])


def get_context_as_messages(session_id: str) -> List[Dict]:
    """Return context formatted as LLM messages (role/content pairs only)."""
    return [
        {"role": t["role"], "content": t["content"]}
        for t in CONTEXT_STORE.get(session_id, [])
    ]


def set_entity(session_id: str, key: str, value):
    """Store a named entity in context (e.g., current customer_id)."""
    if session_id not in CONTEXT_STORE:
        CONTEXT_STORE[session_id] = []
    # Store as a special system entry
    for t in CONTEXT_STORE[session_id]:
        if t.get("role") == "_entity" and t.get("metadata", {}).get("key") == key:
            t["content"] = str(value)
            t["timestamp"] = datetime.utcnow().isoformat()
            return
    CONTEXT_STORE[session_id].insert(0, {
        "role": "_entity",
        "content": str(value),
        "timestamp": datetime.utcnow().isoformat(),
        "metadata": {"key": key},
    })


def get_entity(session_id: str, key: str) -> Optional[str]:
    """Retrieve a named entity from context."""
    for t in CONTEXT_STORE.get(session_id, []):
        if t.get("role") == "_entity" and t.get("metadata", {}).get("key") == key:
            return t["content"]
    return None


def clear_session(session_id: str):
    if session_id in CONTEXT_STORE:
        del CONTEXT_STORE[session_id]
