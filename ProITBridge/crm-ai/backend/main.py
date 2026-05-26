"""
main.py — FastAPI application for Appliance CRM AI.
Serves both API endpoints and static frontend.
"""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import os, uuid

app = FastAPI(title="Appliance CRM AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["GET","POST","PUT","DELETE","OPTIONS","PATCH"],
    allow_headers=["*"],
    allow_credentials=False,
    max_age=600,
)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

# ── Static files ──────────────────────────────────────────────────────────────
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def root():
    index = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Appliance CRM API running. Frontend not found."}

# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    # Check optional agent frameworks
    try:
        import autogen as _ag
        autogen_ok = True
    except ImportError:
        autogen_ok = False
    try:
        from crewai import Crew as _c
        crewai_ok = True
    except ImportError:
        crewai_ok = False

    from backend.utils.llm import _get_client
    groq_ok = _get_client() is not None

    return {
        "status": "ok",
        "service": "AppliServe AI CRM",
        "groq_connected":    groq_ok,
        "autogen_available": autogen_ok,
        "crewai_available":  crewai_ok,
        "rag_types":         ["semantic","hybrid","agentic","corrective","graph"],
        "mcts":              True,
        "mcp":               True,
    }

# ── Request models ─────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    customer_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

class ApprovalRequest(BaseModel):
    approval_id: str
    decision: str   # "approved" | "rejected"
    reason: Optional[str] = ""

class TicketRequest(BaseModel):
    customer_id: str
    issue: str
    priority: Optional[str] = "medium"
    warranty_id: Optional[str] = ""
    appliance_id: Optional[str] = ""

# ── Chat / Orchestrator ────────────────────────────────────────────────────────
@app.post("/api/chat")
def chat(req: ChatRequest):
    from backend.agents.orchestrator import run
    session_id = req.session_id or str(uuid.uuid4())
    try:
        result = run(
            query=req.query,
            session_id=session_id,
            customer_id=req.customer_id,
            extra=req.extra or {},
        )
        result["session_id"] = session_id
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Customers ──────────────────────────────────────────────────────────────────
@app.get("/api/customers")
def list_customers():
    from backend.data_loader import get_customers
    return get_customers()

@app.get("/api/customers/{customer_id}")
def get_customer(customer_id: str):
    from backend.agents.crm_agent import lookup_customer
    result = lookup_customer(customer_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# ── Tickets ────────────────────────────────────────────────────────────────────
def _normalize_ticket(t: dict) -> dict:
    STATUS_MAP = {
        "open":"OPEN","in progress":"IN_PROGRESS","in_progress":"IN_PROGRESS",
        "resolved":"RESOLVED","closed":"CLOSED","under review":"UNDER_REVIEW",
        "under_review":"UNDER_REVIEW","technician pending":"TECHNICIAN_PENDING",
        "technician_pending":"TECHNICIAN_PENDING","assigned":"ASSIGNED",
    }
    t = dict(t)
    t["status"] = STATUS_MAP.get(t.get("status","").lower(), t.get("status","OPEN").upper().replace(" ","_"))
    if "issue" in t and "issue_description" not in t:       t["issue_description"] = t["issue"]
    if "technician_id" in t and "assigned_technician" not in t: t["assigned_technician"] = t["technician_id"]
    if "created_date" in t and "created_at" not in t:       t["created_at"] = t["created_date"]
    return t

@app.get("/api/tickets")
def list_tickets(status: Optional[str] = None):
    from backend.data_loader import get_tickets
    from backend.sample_data import RUNTIME_TICKETS
    all_tickets = [_normalize_ticket(t) for t in get_tickets() + RUNTIME_TICKETS]
    if status:
        all_tickets = [t for t in all_tickets if t.get("status","").lower() == status.lower()]
    return all_tickets

@app.post("/api/tickets")
def create_ticket(req: TicketRequest):
    from backend.sample_data import add_ticket
    ticket = add_ticket(req.dict())
    return ticket

@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    from backend.data_loader import get_tickets
    from backend.sample_data import RUNTIME_TICKETS
    all_tickets = get_tickets() + RUNTIME_TICKETS
    t = next((t for t in all_tickets if t["ticket_id"] == ticket_id), None)
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return t

# ── Warranty ───────────────────────────────────────────────────────────────────
@app.get("/api/warranty/{customer_id}")
def check_warranty(customer_id: str, warranty_id: Optional[str] = None):
    from backend.agents.crm_agent import check_warranty as cw
    return cw(customer_id, warranty_id)

# ── Leads ──────────────────────────────────────────────────────────────────────
@app.get("/api/leads")
def list_leads():
    from backend.data_loader import get_sales_leads
    return get_sales_leads()

# ── Appliances ─────────────────────────────────────────────────────────────────
@app.get("/api/appliances")
def list_appliances():
    from backend.data_loader import get_appliances
    return get_appliances()

# ── Technicians ────────────────────────────────────────────────────────────────
@app.get("/api/technicians")
def list_technicians():
    from backend.data_loader import get_technicians
    return get_technicians()

# ── Warranties (all, or filter by customer_id) ────────────────────────────────
@app.get("/api/warranties")
def list_warranties(customer_id: Optional[str] = None):
    from backend.data_loader import get_warranty_data
    ws = get_warranty_data()
    if customer_id:
        ws = [w for w in ws if w.get("customer_id") == customer_id]
    return ws

# ── Recommendations ────────────────────────────────────────────────────────────
@app.get("/api/recommendations/{customer_id}")
def get_recommendations(customer_id: str, query: Optional[str] = ""):
    from backend.agents.recommendation_agent import recommend
    return recommend(customer_id, query, session_id=customer_id)

# ── Approvals ──────────────────────────────────────────────────────────────────
@app.get("/api/approvals")
def get_approvals():
    from backend.sample_data import get_pending_approvals
    return get_pending_approvals()

@app.post("/api/approvals/process")
def process_approval(req: ApprovalRequest):
    from backend.agents.human_approval_agent import process_approval as pa
    return pa(req.approval_id, req.decision, req.reason or "")

# ── Pipeline stats ─────────────────────────────────────────────────────────────
@app.get("/api/stats")
def pipeline_stats():
    from backend.agents.crm_agent import get_pipeline_stats
    return get_pipeline_stats()

# ── Ingest docs into Pinecone ──────────────────────────────────────────────────
@app.post("/api/ingest")
def ingest_docs():
    from backend.data_loader import get_docs
    from backend.utils.chunker import chunk_documents
    from backend.utils.embeddings import embed_batch
    from backend.db.pinecone_client import insert_chunks

    docs   = get_docs()
    chunks = chunk_documents(docs)
    texts  = [c["text"] for c in chunks]
    embeddings = embed_batch(texts)

    for i, c in enumerate(chunks):
        c["embedding"] = embeddings[i]
        c["source_type"] = c.get("source_type","doc")

    count = insert_chunks(chunks)
    return {"ingested": count, "chunks": len(chunks), "docs": len(docs)}

# ── Reviews ────────────────────────────────────────────────────────────────────
@app.get("/api/reviews")
def list_reviews():
    from backend.data_loader import get_reviews
    return get_reviews()

# ── n8n / Make.com Automation Webhooks ────────────────────────────────────────
class WebhookTicketPayload(BaseModel):
    ticket_id:   Optional[str] = None
    customer_id: str
    issue:       str
    priority:    Optional[str] = "medium"
    source:      Optional[str] = "n8n"   # "n8n" | "make" | "manual"

class WebhookChatPayload(BaseModel):
    query:       Optional[str] = "webhook test ping"   # default so test triggers work
    customer_id: Optional[str] = None
    session_id:  Optional[str] = None
    source:      Optional[str] = "n8n"

@app.post("/api/webhook/n8n")
async def n8n_webhook(payload: WebhookChatPayload):
    """
    Inbound webhook from n8n workflows.
    Use in n8n: HTTP Request node → POST https://<your-render-url>/api/webhook/n8n
    Body: { "query": "...", "customer_id": "CUST001", "session_id": "..." }
    """
    from backend.agents.orchestrator import run
    session_id = payload.session_id or f"n8n-{uuid.uuid4().hex[:8]}"
    result = run(
        query=payload.query,
        session_id=session_id,
        customer_id=payload.customer_id,
    )
    return {
        "source": "n8n",
        "session_id": session_id,
        "answer": result.get("answer", ""),
        "intent": result.get("intent", ""),
        "mcts_decision": result.get("mcts_decision", ""),
        "agent_used": result.get("agent_used", ""),
    }

@app.post("/api/webhook/ticket-created")
async def ticket_webhook(payload: WebhookTicketPayload):
    """
    Called automatically when a ticket is created.
    n8n listens here to trigger Slack/email notifications.
    Payload forwarded to n8n outbound webhook if N8N_WEBHOOK_URL is set.
    """
    import httpx
    from backend.sample_data import add_ticket
    ticket = add_ticket({
        "customer_id": payload.customer_id,
        "issue":       payload.issue,
        "priority":    payload.priority,
        "source":      payload.source,
    })
    # Fire outbound to n8n if configured
    n8n_url = settings.N8N_WEBHOOK_URL if hasattr(settings, "N8N_WEBHOOK_URL") else None
    forwarded = False
    if n8n_url:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(n8n_url, json=ticket)
            forwarded = True
        except Exception as e:
            print(f"[Webhook] n8n forward failed: {e}")

    return {"ticket": ticket, "forwarded_to_n8n": forwarded}

@app.post("/api/webhook/make")
async def make_webhook(payload: WebhookChatPayload):
    """
    Inbound webhook from Make.com (formerly Integromat).
    Identical contract to /api/webhook/n8n — use either.
    """
    payload.source = "make"
    return await n8n_webhook(payload)

@app.get("/api/n8n/config")
async def n8n_config():
    """Return the exact URLs and payload shapes to paste into n8n."""
    base = settings.BACKEND_PUBLIC_URL.rstrip("/")
    return {
        "status": "configured" if settings.N8N_WEBHOOK_URL else "pending",
        "n8n_webhook_url_set": bool(settings.N8N_WEBHOOK_URL),
        "endpoints": {
            "inbound_chat":    f"{base}/api/webhook/n8n",
            "inbound_ticket":  f"{base}/api/webhook/ticket-created",
            "inbound_make":    f"{base}/api/webhook/make",
        },
        "sample_payload": {
            "query": "What is the status of open tickets?",
            "customer_id": "CUST001",
            "session_id": "n8n-workflow-1",
            "source": "n8n"
        },
        "outbound_n8n_url": settings.N8N_WEBHOOK_URL or "(not set — add N8N_WEBHOOK_URL to .env)",
        "instructions": [
            "1. Run ngrok: ngrok http 8000",
            "2. Copy your ngrok URL into BACKEND_PUBLIC_URL in .env",
            "3. In n8n: Workflow > Webhook node > copy its URL into N8N_WEBHOOK_URL in .env",
            "4. Restart the server: uvicorn backend.main:app --reload",
        ]
    }

# ══════════════════════════════════════════════════════════════════════════════
# POWERPLEX ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── Email Processing ──────────────────────────────────────────────────────────
@app.post("/api/gmail/process")
async def process_gmail():
    """Read unread Gmail → classify → create tickets → queue confirmation emails."""
    from backend.automation.gmail_reader import process_emails_into_tickets
    results = process_emails_into_tickets()
    return {"processed": len(results), "results": results}

@app.get("/api/gmail/preview")
async def preview_gmail():
    """Preview unread support emails without creating tickets."""
    from backend.automation.gmail_reader import fetch_unread_support_emails, gmail_available
    emails = fetch_unread_support_emails()
    return {"gmail_connected": gmail_available(), "emails": emails}

# ── Ticket Classification ─────────────────────────────────────────────────────
@app.post("/api/tickets/classify")
async def classify_ticket_route(body: dict):
    """Classify a support text: severity, product type, urgency, warranty relevance."""
    from backend.agents.ticket_classifier import classify_ticket
    text = body.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    return classify_ticket(text)

# ── Technician Routing ────────────────────────────────────────────────────────
@app.post("/api/tickets/{ticket_id}/route-technician")
async def route_technician_for_ticket(ticket_id: str, body: dict = {}):
    """Route best technician + auto-generate RAG email draft for admin review."""
    from backend.agents.technician_router import route_technician
    from backend.data_loader import (get_tickets, get_customer_by_id,
                                     get_appliances, get_warranty_by_customer,
                                     get_technicians, get_tickets_by_customer)
    from backend.agents.communication_agent import generate_rag_email
    from backend.sample_data import RUNTIME_TICKETS

    # Find the ticket across all sources
    all_tickets = get_tickets() + RUNTIME_TICKETS
    ticket = next((t for t in all_tickets if t.get("ticket_id") == ticket_id), {})

    issue        = ticket.get("issue") or ticket.get("issue_description") or body.get("issue", "")
    product_type = ticket.get("product_type") or body.get("product_type")
    severity     = ticket.get("priority") or body.get("severity")
    customer_id  = ticket.get("customer_id") or body.get("customer_id", "")

    result = route_technician(issue or ticket_id, product_type, severity)

    # Auto-generate RAG email draft if we have customer + technician
    email_draft = None
    tech = result.get("recommended_technician") or {}
    if tech and customer_id:
        try:
            customer    = get_customer_by_id(customer_id)
            tickets_c   = get_tickets_by_customer(customer_id)
            appliances  = get_appliances()
            warranties  = get_warranty_by_customer(customer_id)
            technicians = get_technicians()
            if customer:
                # Try RAG email first
                try:
                    email_draft = generate_rag_email(
                        email_type  = "email_technician_assignment",
                        customer    = customer,
                        tickets     = tickets_c,
                        appliances  = appliances,
                        warranties  = warranties,
                        technicians = technicians,
                        query       = f"Technician {tech['name']} (ID: {tech.get('technician_id','')}) assigned to ticket {ticket_id}: {issue}",
                        session_id  = ticket_id,
                    )
                except Exception as llm_err:
                    print(f"[Route] LLM draft failed, using fallback: {llm_err}")
                    # Fallback draft without LLM
                    cname  = customer.get("name","Customer")
                    days   = 0
                    t_ref  = next((t for t in tickets_c if t.get("ticket_id")==ticket_id), tickets_c[0] if tickets_c else {})
                    email_draft = {
                        "subject": f"Technician Assigned — Ticket {ticket_id}",
                        "body": (
                            f"Dear {cname},\n\n"
                            f"We are pleased to inform you that a technician has been assigned to your service request.\n\n"
                            f"Ticket ID   : {ticket_id}\n"
                            f"Issue       : {issue or t_ref.get('issue','')}\n"
                            f"Technician  : {tech['name']} (ID: {tech.get('technician_id','')})\n"
                            f"Specialization: {tech.get('specialization','')}\n"
                            f"Contact     : {tech.get('phone','')}\n"
                            f"Expected visit within 24–48 hours.\n\n"
                            f"Warranty and service policies apply. Please keep your appliance accessible.\n\n"
                            f"Regards,\nPowerPlex Support Team"
                        ),
                    }

                result["email_draft"] = {
                    "to"      : customer.get("email", ""),
                    "subject" : email_draft.get("subject", ""),
                    "body"    : email_draft.get("body", ""),
                    "docs_used": email_draft.get("docs_used", []),
                    "ai_enhanced": email_draft.get("ai_enhanced", False),
                }
        except Exception as e:
            print(f"[Route] Email draft error: {e}")

    return result


@app.post("/api/send-email")
async def send_email_now(body: dict):
    """Send an email immediately via Gmail SMTP."""
    from backend.utils.email_sender import send_email
    to_email = body.get("to", "")
    subject  = body.get("subject", "PowerPlex Service Update")
    email_body = body.get("body", "")
    if not to_email or not email_body:
        raise HTTPException(status_code=400, detail="to and body are required")
    result = send_email(to_email, subject, email_body)
    if not result.get("success") and not result.get("skipped"):
        raise HTTPException(status_code=500, detail=result.get("error", "Send failed"))
    return result

# ── Email Draft Generation ────────────────────────────────────────────────────
class EmailDraftRequest(BaseModel):
    email_type:   str   # ticket_confirmation | technician_assignment | etc.
    customer_id:  str
    ticket_id:    Optional[str] = None
    technician_id: Optional[str] = None
    extra:        Optional[Dict[str, Any]] = {}

@app.post("/api/emails/draft")
async def generate_email_draft(req: EmailDraftRequest):
    """
    Generate an email draft and queue it for admin approval.
    NO email is sent — it goes to the approval queue first.
    """
    from backend.agents.communication_agent import (
        generate_ticket_confirmation, generate_technician_assignment,
        generate_escalation, generate_apology,
    )
    from backend.approval.approval_queue import queue_email_for_approval
    from backend.data_loader import get_customer_by_id, get_technicians

    customer = get_customer_by_id(req.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    ticket = {"ticket_id": req.ticket_id or "TKT-000", "issue": req.extra.get("issue", ""), "priority": req.extra.get("priority", "medium"), "product_type": req.extra.get("product_type", "Appliance")}

    if req.email_type == "ticket_confirmation":
        draft = generate_ticket_confirmation(customer, ticket)
    elif req.email_type == "technician_assignment":
        techs = get_technicians()
        tech  = next((t for t in techs if t["technician_id"] == req.technician_id), techs[0] if techs else {})
        draft = generate_technician_assignment(customer, ticket, tech)
    elif req.email_type == "escalation":
        draft = generate_escalation(customer, ticket, req.extra.get("reason", "complexity of the issue"))
    elif req.email_type == "apology":
        draft = generate_apology(customer, ticket, req.extra.get("delay_reason", "unexpected delay"))
    else:
        raise HTTPException(status_code=400, detail=f"Unknown email_type: {req.email_type}")

    approval = queue_email_for_approval(
        email_type  = f"email_{req.email_type}",
        to_email    = customer["email"],
        customer_id = req.customer_id,
        ticket_id   = req.ticket_id,
        draft       = draft,
    )
    return {"draft": draft, "approval": approval,
            "message": f"Email draft queued for approval. ID: {approval['approval_id']}"}

# ── PowerPlex Approval Center ─────────────────────────────────────────────────
@app.get("/api/approvals/all")
async def get_all_approvals_powerplex(status: Optional[str] = None):
    """Get all approval items (emails + actions). Filter by status: pending/approved/rejected."""
    from backend.approval.approval_queue import get_all_approvals, get_pending_approvals
    if status == "pending":
        return get_pending_approvals()
    return get_all_approvals()

@app.get("/api/approvals/{approval_id}")
async def get_approval(approval_id: str):
    from backend.approval.approval_queue import get_approval as ga
    item = ga(approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="Approval not found")
    return item

@app.post("/api/approvals/{approval_id}/decide")
async def decide_approval(approval_id: str, body: dict):
    from backend.agents.human_approval_agent import process_approval as pa
    decision = body.get("decision", "approved")
    reason   = body.get("reason", "")
    return pa(approval_id, decision, reason)

@app.get("/api/approvals/ready-to-send")
async def get_ready_to_send():
    from backend.approval.approval_queue import get_approved_emails
    return get_approved_emails()

TICKET_STAGES = ["OPEN","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED",
                 "IN_PROGRESS","RESOLVED","CLOSED"]

@app.patch("/api/tickets/{ticket_id}/status")
async def update_ticket_status(ticket_id: str, body: dict):
    new_status = body.get("status", "").upper().replace(" ", "_")
    if new_status not in TICKET_STAGES:
        raise HTTPException(status_code=400, detail=f"Valid stages: {TICKET_STAGES}")
    return {"ticket_id": ticket_id, "status": new_status, "updated": True}

@app.get("/api/framework-status")
def framework_status():
    results = {}
    for name, mod in [("autogen","autogen"),("crewai","crewai"),
                      ("mcts","backend.mcts.mcts_planner"),
                      ("pinecone","pinecone"),("networkx","networkx")]:
        try:
            __import__(mod)
            results[name] = "available"
        except ImportError:
            results[name] = "not installed"
    return results
