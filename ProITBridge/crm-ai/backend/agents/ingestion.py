"""
ingestion.py — Ingestion Agent.
Pulls raw data, chunks it, embeds it, and stores in Zilliz + Supabase.
Can be triggered via API or run as a scheduled cron job on Render.
"""
from backend.utils.chunker import chunk_documents
from backend.utils.embeddings import embed_batch
from backend.db import pinecone_client, supabase_client
from datetime import datetime
from typing import List, Dict, Optional
import json


def ingest_documents(documents: List[Dict]) -> Dict:
    """
    Main ingestion pipeline.
    documents: list of { text, source_type, account_id, deal_id, rep_id, doc_date }
    Returns: { inserted, skipped, errors }
    """
    if not documents:
        return {"inserted": 0, "skipped": 0, "errors": []}

    errors = []
    total_inserted = 0

    try:
        # Step 1: Chunk all documents
        chunks = chunk_documents(documents)
        if not chunks:
            return {"inserted": 0, "skipped": len(documents), "errors": []}

        # Step 2: Batch embed all chunks
        texts = [c["text"] for c in chunks]
        embeddings = embed_batch(texts)

        # Step 3: Attach embeddings to chunks
        for chunk, emb in zip(chunks, embeddings):
            chunk["embedding"] = emb

        # Step 4: Insert into Zilliz Cloud
        inserted = pinecone_client.insert_chunks(chunks)
        total_inserted += inserted

        # Step 5: Log ingestion
        source_label = documents[0].get("source_type", "unknown") if documents else "unknown"
        supabase_client.log_ingestion(source=source_label, count=inserted, status="success")

        print(f"[Ingestion] Inserted {inserted} chunks from {len(documents)} documents.")

    except Exception as e:
        errors.append(str(e))
        print(f"[Ingestion] Error: {e}")

    return {
        "inserted": total_inserted,
        "skipped": len(documents) - total_inserted,
        "errors": errors
    }


def ingest_text(
    text: str,
    source_type: str,
    account_id: str = "",
    deal_id: str = "",
    rep_id: str = "",
    doc_date: Optional[str] = None
) -> Dict:
    """Convenience wrapper to ingest a single piece of text."""
    doc = {
        "text": text,
        "source_type": source_type,
        "account_id": account_id,
        "deal_id": deal_id,
        "rep_id": rep_id,
        "doc_date": doc_date or datetime.utcnow().date().isoformat()
    }
    return ingest_documents([doc])


# ── Sample data seeder ────────────────────────────────────────────────────────
def seed_sample_data() -> Dict:
    """
    Seeds demo CRM data into Supabase for first-run experience.
    Creates sample leads, deals, and activities.
    """
    from backend.db.supabase_client import upsert_lead, upsert_deal, insert_activity
    import uuid

    leads = [
        {"id": "lead-001", "name": "Sarah Johnson", "company": "TechCorp Inc", "email": "sarah@techcorp.com", "phone": "+1-555-0101", "title": "VP Engineering"},
        {"id": "lead-002", "name": "Michael Chen", "company": "DataFlow Systems", "email": "m.chen@dataflow.io", "phone": "+1-555-0102", "title": "CTO"},
        {"id": "lead-003", "name": "Priya Patel", "company": "CloudBase Ltd", "email": "priya@cloudbase.io", "phone": "+1-555-0103", "title": "Head of IT"},
        {"id": "lead-004", "name": "James Wilson", "company": "FinanceHub", "email": "jwilson@financehub.com", "phone": "+1-555-0104", "title": "CFO"},
        {"id": "lead-005", "name": "Emma Davis", "company": "RetailX", "email": "emma.davis@retailx.com", "phone": "+1-555-0105", "title": "Director of Ops"},
    ]

    deals = [
        {"id": "deal-001", "lead_id": "lead-001", "title": "TechCorp Enterprise Plan", "stage": "Proposal Sent", "value": 48000, "probability": 65, "expected_close_date": "2026-06-15", "last_contact_date": "2026-05-10", "rep_id": "rep-001", "notes": "Sent proposal on May 10. Awaiting feedback from Sarah."},
        {"id": "deal-002", "lead_id": "lead-002", "title": "DataFlow Analytics Suite", "stage": "Negotiation", "value": 92000, "probability": 80, "expected_close_date": "2026-05-30", "last_contact_date": "2026-05-18", "rep_id": "rep-001", "notes": "Michael requested discount. In final negotiation."},
        {"id": "deal-003", "lead_id": "lead-003", "title": "CloudBase Security Package", "stage": "Qualified", "value": 35000, "probability": 45, "expected_close_date": "2026-07-01", "last_contact_date": "2026-04-28", "rep_id": "rep-001", "notes": "Initial call done. Need follow-up on pricing."},
        {"id": "deal-004", "lead_id": "lead-004", "title": "FinanceHub Integration", "stage": "Discovery", "value": 67000, "probability": 30, "expected_close_date": "2026-08-01", "last_contact_date": "2026-05-15", "rep_id": "rep-001", "notes": "Discovery call scheduled for next week."},
        {"id": "deal-005", "lead_id": "lead-005", "title": "RetailX CRM Expansion", "stage": "Closed Won", "value": 23000, "probability": 100, "expected_close_date": "2026-05-01", "last_contact_date": "2026-05-01", "rep_id": "rep-001", "notes": "Deal closed! Onboarding in progress."},
    ]

    activities = [
        {"deal_id": "deal-001", "type": "email", "summary": "Sent enterprise pricing proposal to Sarah Johnson", "rep_id": "rep-001"},
        {"deal_id": "deal-002", "type": "call", "summary": "45-min call with Michael Chen — discussed discount options and timeline", "rep_id": "rep-001"},
        {"deal_id": "deal-003", "type": "email", "summary": "Initial outreach email sent to Priya Patel at CloudBase", "rep_id": "rep-001"},
        {"deal_id": "deal-002", "type": "meeting", "summary": "Demo meeting — showed analytics dashboard to DataFlow team", "rep_id": "rep-001"},
        {"deal_id": "deal-004", "type": "call", "summary": "Discovery call with James Wilson — identified 3 key pain points", "rep_id": "rep-001"},
    ]

    for lead in leads:
        try:
            upsert_lead(lead)
        except Exception as e:
            print(f"[Seed] Lead error: {e}")

    for deal in deals:
        try:
            upsert_deal(deal)
        except Exception as e:
            print(f"[Seed] Deal error: {e}")

    for activity in activities:
        try:
            insert_activity(activity)
        except Exception as e:
            print(f"[Seed] Activity error: {e}")

    # Also ingest sample texts into Zilliz
    sample_docs = [
        {"text": "Sarah from TechCorp requested a 10% discount on the enterprise plan. She mentioned budget constraints but confirmed the deal is moving forward.", "source_type": "email", "account_id": "lead-001", "deal_id": "deal-001", "rep_id": "rep-001", "doc_date": "2026-05-10"},
        {"text": "Michael Chen call transcript: discussed SLA requirements, wants 99.9% uptime guarantee. Very interested in the analytics module. Budget approved at $90k.", "source_type": "transcript", "account_id": "lead-002", "deal_id": "deal-002", "rep_id": "rep-001", "doc_date": "2026-05-18"},
        {"text": "Priya Patel initial call notes: CloudBase is migrating to cloud. Looking for security + compliance package. 3-month evaluation timeline.", "source_type": "document", "account_id": "lead-003", "deal_id": "deal-003", "rep_id": "rep-001", "doc_date": "2026-04-28"},
    ]

    ingest_documents(sample_docs)

    return {"leads": len(leads), "deals": len(deals), "activities": len(activities)}
