"""
lead_priority.py — Lead Priority Scoring Agent.
Scores all active deals by urgency and close probability.
Uses Supabase (structured) + Zilliz (recent context) + Groq (LLM reasoning).
"""
from backend.db import supabase_client
from backend.rag.retriever import naive_retrieve
from backend.utils.embeddings import embed_text
from backend.config import settings
from groq import Groq
from datetime import datetime, date
from typing import List, Dict
import json

_groq = Groq(api_key=settings.GROQ_API_KEY)


def score_deals() -> List[Dict]:
    """
    Score and rank all active deals.
    Returns sorted list of deals with AI priority scores and reasoning.
    """
    deals = supabase_client.get_all_deals()
    if not deals:
        return []

    # Filter active deals only
    active_deals = [d for d in deals if d.get("stage") not in ("Closed Won", "Closed Lost")]

    scored = []
    for deal in active_deals:
        try:
            score_data = _score_single_deal(deal)
            scored.append({**deal, **score_data})
        except Exception as e:
            print(f"[LeadPriority] Error scoring deal {deal.get('id')}: {e}")
            scored.append({**deal, "priority_score": 50, "priority_reason": "Score unavailable", "urgency": "medium"})

    # Sort by priority score descending
    scored.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    return scored


def _score_single_deal(deal: Dict) -> Dict:
    """Score a single deal using LLM reasoning over deal data + recent context."""

    # Get recent context from Zilliz
    recent_chunks = naive_retrieve(
        query=f"latest updates for {deal.get('title', '')}",
        filters={"deal_id": deal.get("id", "")},
        top_k=3
    )
    context_text = "\n".join([c["text"] for c in recent_chunks]) if recent_chunks else "No recent context available."

    # Calculate days since last contact
    last_contact = deal.get("last_contact_date", "")
    days_since = _days_since(last_contact)

    # Calculate days until close
    close_date = deal.get("expected_close_date", "")
    days_to_close = _days_until(close_date)

    prompt = f"""You are a sales intelligence AI. Score this deal's priority from 0-100 and explain why.

DEAL INFO:
- Title: {deal.get('title')}
- Stage: {deal.get('stage')}
- Value: ${deal.get('value', 0):,.0f}
- Probability: {deal.get('probability', 0)}%
- Days since last contact: {days_since}
- Days until expected close: {days_to_close}
- Notes: {deal.get('notes', 'None')}

RECENT CONTEXT:
{context_text}

Respond in JSON only:
{{
  "priority_score": <0-100 integer>,
  "urgency": "<low|medium|high|critical>",
  "priority_reason": "<1-2 sentences explaining the score>",
  "recommended_action": "<specific next action the rep should take>"
}}"""

    resp = _groq.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0.3,
        response_format={"type": "json_object"}
    )

    result = json.loads(resp.choices[0].message.content)
    return result


def _days_since(date_str: str) -> int:
    """Days since a given date string."""
    try:
        dt = datetime.fromisoformat(date_str[:10]).date()
        return (date.today() - dt).days
    except Exception:
        return 999


def _days_until(date_str: str) -> int:
    """Days until a given date string."""
    try:
        dt = datetime.fromisoformat(date_str[:10]).date()
        return (dt - date.today()).days
    except Exception:
        return 999
