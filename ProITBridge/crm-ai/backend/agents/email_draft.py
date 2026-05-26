"""
email_draft.py — Email Draft Agent.
Retrieves full conversation history and generates personalized follow-up emails.
Human-in-the-loop: drafts are saved to Supabase pending rep approval.
"""
from backend.rag.retriever import naive_retrieve, format_context
from backend.db import supabase_client
from backend.config import settings
from groq import Groq
from typing import Dict, Optional

_groq = Groq(api_key=settings.GROQ_API_KEY)


def draft_email(
    deal_id: str,
    rep_name: str = "Your Rep",
    context_hint: str = "",
    tone: str = "professional"
) -> Dict:
    """
    Draft a personalized follow-up email for a deal.
    Returns draft saved to Supabase — requires rep approval before sending.
    """

    # Get deal info
    deal = supabase_client.get_deal_by_id(deal_id)
    if not deal:
        return {"error": f"Deal {deal_id} not found"}

    lead = deal.get("leads") or {}
    lead_name = lead.get("name", "there")
    lead_company = lead.get("company", "your company")
    deal_title = deal.get("title", "our proposal")
    deal_stage = deal.get("stage", "")

    # Retrieve recent conversation context from Zilliz
    recent_chunks = naive_retrieve(
        query=f"latest communication with {lead_name} about {deal_title}",
        filters={"deal_id": deal_id},
        top_k=5
    )
    context_text = "\n".join([c["text"] for c in recent_chunks]) if recent_chunks else "No prior communication found."

    # Recent activities
    activities = supabase_client.get_activities(deal_id=deal_id, limit=5)
    activity_text = "\n".join([
        f"- {a.get('type', 'activity')}: {a.get('summary', '')}"
        for a in activities
    ]) if activities else "No recent activities."

    prompt = f"""You are a sales rep named {rep_name}. Write a personalized follow-up email to {lead_name} at {lead_company}.

DEAL: {deal_title}
STAGE: {deal_stage}
TONE: {tone}
CONTEXT HINT: {context_hint or "General follow-up"}

PRIOR COMMUNICATION:
{context_text}

RECENT ACTIVITIES:
{activity_text}

Write a concise, personalized email (150-200 words). Include:
- A warm, specific opening referencing something from prior communication
- A clear purpose / next step
- A soft call to action (schedule a call, respond with questions, etc.)
- Professional closing

Return ONLY the email text (subject line first, then body). No preamble."""

    resp = _groq.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.6
    )

    email_text = resp.choices[0].message.content.strip()

    # Parse subject line (first line) from body
    lines = email_text.split("\n", 1)
    subject = lines[0].replace("Subject:", "").strip() if lines else "Follow-up"
    body = lines[1].strip() if len(lines) > 1 else email_text

    # Save draft to Supabase (pending approval)
    draft = supabase_client.save_email_draft({
        "deal_id": deal_id,
        "to_email": lead.get("email", ""),
        "to_name": lead_name,
        "subject": subject,
        "body": body,
        "rep_name": rep_name,
        "tone": tone,
    })

    return {
        "draft_id": draft.get("id"),
        "to": lead.get("email", ""),
        "to_name": lead_name,
        "subject": subject,
        "body": body,
        "deal_id": deal_id,
        "status": "pending_approval",
        "message": "Draft saved. Review and approve to send."
    }


def send_approved_email(draft_id: str) -> Dict:
    """
    Mark an email draft as approved and log the send activity.
    (Actual SMTP sending can be wired via SendGrid/Resend free tier.)
    """
    draft = supabase_client.approve_email_draft(draft_id)

    # Log activity
    if draft:
        supabase_client.insert_activity({
            "deal_id": draft.get("deal_id"),
            "type": "email",
            "summary": f"Email sent: {draft.get('subject')}",
            "rep_id": draft.get("rep_name", "rep")
        })

    return {"status": "sent", "draft_id": draft_id}
