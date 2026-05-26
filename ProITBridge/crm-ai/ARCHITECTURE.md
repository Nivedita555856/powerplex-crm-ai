# AppliServe AI CRM — Architecture Guide

## Stack Mapping

| Architecture Layer | Your Stack | Hosted On |
|---|---|---|
| Frontend | HTML / CSS / JS (static) | Render (same service) or Vercel |
| Orchestrator | FastAPI + Pure Python Orchestrator | Render Web Service |
| Structured Data | Supabase PostgreSQL | Supabase Cloud (free tier) |
| Vector / RAG | Pinecone Serverless (5 RAG types) | Pinecone free tier |
| AI Reasoning | Groq — llama3-70b-8192 | Groq Cloud (free tier) |
| Multi-Agent | AutoGen (support) + CrewAI (recommendations) | Same Render service |
| MCTS | Pure Python (80 simulations) | Same Render service |
| MCP Context | In-memory session store (context_manager.py) | Same Render service |
| Automation | n8n self-hosted OR Make.com webhooks | n8n Cloud / Make.com free |

---

## Flow Diagram

```
[ Browser — HTML/CSS/JS ]
         |
    HTTP POST /api/chat
         |
         v
[ FastAPI on Render ]
         |
    orchestrator.run()
         |
    ┌────┴─────────────────────────────────────────────────────────┐
    │  Intent Classification (regex rules)                         │
    │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
    │  │data_query│ │warranty  │ │recommend │ │support/general │  │
    │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬────────┘  │
    │       │             │             │               │            │
    │  CSV data      Graph RAG    Semantic RAG    Corrective RAG    │
    │  (no LLM)    + Groq LLM    + CrewAI crew   + Graph RAG       │
    │                             (if available)  + AutoGen        │
    │                                             + MCTS decision  │
    └──────────────────────────────────────────────────────────────┘
         |
    MCP context saved (session store)
         |
    Guardrails check
         |
    Return JSON → Frontend
         |
    [Ticket created?] → POST /api/webhook/ticket-created
                              |
                         n8n / Make.com
                              |
                    ┌─────────┴──────────┐
                    v                    v
               Slack alert        Gmail draft
```

---

## 5 RAG Types — When Each Fires

| RAG Type | Intent | What it does |
|---|---|---|
| **Semantic** | `recommendation` | Embed query → Pinecone cosine search |
| **Hybrid** | `validation` | Keyword overlap + semantic re-ranking |
| **Agentic** | `general` (unknown) | Decomposes query → multi-step retrieval |
| **Corrective** | `support` | Retrieves, scores relevance, re-queries if < 0.6 |
| **Graph** | `warranty`, `support` | NetworkX relationship traversal |

---

## Setting Up Supabase

1. Go to [supabase.com](https://supabase.com) → New Project
2. Open **SQL Editor** → paste `supabase_schema.sql` → Run
3. Go to **Settings → API** → copy:
   - `Project URL` → `SUPABASE_URL` in `.env`
   - `service_role` secret → `SUPABASE_SERVICE_ROLE_KEY` in `.env`
4. To load your CSV data into Supabase, run:
   ```bash
   python scripts/load_supabase.py
   ```

---

## Setting Up n8n Automation

### Option A — n8n Cloud (free, recommended)
1. Sign up at [n8n.io](https://n8n.io) → create a workflow
2. Add **Webhook** trigger node → copy the webhook URL
3. Paste it into `.env`: `N8N_WEBHOOK_URL=https://your-n8n-url/webhook/abc123`
4. Restart the FastAPI server

### Option B — Self-hosted n8n (Docker)
```bash
docker run -it --rm --name n8n -p 5678:5678 n8nio/n8n
```

### Workflow 1 — New Ticket Alert to Slack
```
[Webhook: POST /api/webhook/ticket-created]
    → [n8n receives ticket JSON]
    → [IF priority == critical]
    → [Slack: post to #support-alerts channel]
    → [Send email to assigned technician]
```

### Workflow 2 — Customer Query via n8n
```
[n8n Schedule or Gmail trigger]
    → [HTTP Request: POST https://<render-url>/api/webhook/n8n]
      Body: { "query": "...", "customer_id": "CUST001" }
    → [Receive AI answer]
    → [Gmail: create draft reply]
```

### Testing webhooks locally
```bash
# Start server
uvicorn backend.main:app --reload

# Test n8n inbound
curl -X POST http://localhost:8000/api/webhook/n8n \
  -H "Content-Type: application/json" \
  -d '{"query": "What problem is Divya Joshi having?", "customer_id": "CUST005"}'

# Test ticket webhook
curl -X POST http://localhost:8000/api/webhook/ticket-created \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "CUST001", "issue": "AC not cooling", "priority": "critical", "source": "n8n"}'
```

---

## Neo4j Knowledge Graph (Upgrade Path)

Right now the project uses **NetworkX** for Graph RAG (runs locally, no API needed).
When you're ready to upgrade to Neo4j Aura free tier:

### Step 1 — Create Neo4j Aura instance
1. Go to [console.neo4j.io](https://console.neo4j.io) → New Instance → Free tier
2. Download the `.txt` credentials file → copy `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`
3. Add to `.env`:
   ```
   NEO4J_URI=neo4j+s://xxxxxxxx.databases.neo4j.io
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your-password
   ```

### Step 2 — Install driver
```bash
pip install neo4j==5.20.0
```

### Step 3 — Replace graph_rag.py

Swap `backend/rag/graph_rag.py` with this Neo4j version:

```python
from neo4j import GraphDatabase
from backend.config import settings

_driver = None

def _get_driver():
    global _driver
    if _driver is None and settings.NEO4J_URI:
        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USERNAME, settings.NEO4J_PASSWORD)
        )
    return _driver

def build_graph():
    """Load customers, appliances, warranties into Neo4j."""
    from backend.data_loader import get_customers, get_appliances, get_warranty_data
    driver = _get_driver()
    if not driver:
        return
    with driver.session() as s:
        for c in get_customers():
            s.run("MERGE (c:Customer {id:$id, name:$name, city:$city})",
                  id=c["customer_id"], name=c["name"], city=c["city"])
        for a in get_appliances():
            s.run("MERGE (a:Appliance {id:$id, brand:$brand, model:$model})",
                  id=a["appliance_id"], brand=a["brand"], model=a["model"])
        for w in get_warranty_data():
            s.run("""
                MATCH (c:Customer {id:$cid}), (a:Appliance {id:$aid})
                MERGE (c)-[:OWNS {warranty_id:$wid, status:$st, expiry:$exp}]->(a)
            """, cid=w["customer_id"], aid=w["appliance_id"],
                 wid=w["warranty_id"], st=w["status"], exp=w["expiry_date"])

def retrieve_by_customer(customer_id: str):
    """Get all appliances and relationships for a customer."""
    driver = _get_driver()
    if not driver:
        return []  # Falls back to NetworkX
    with driver.session() as s:
        result = s.run("""
            MATCH (c:Customer {id:$cid})-[r:OWNS]->(a:Appliance)
            RETURN a.brand + ' ' + a.model AS name,
                   r.status AS warranty_status,
                   r.expiry AS expiry
        """, cid=customer_id)
        return [{"text": f"{row['name']} — warranty {row['warranty_status']} till {row['expiry']}"}
                for row in result]
```

### Step 4 — Add to config.py
```python
NEO4J_URI:      str = os.getenv("NEO4J_URI", "")
NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
```

---

## MCP (Model Context Protocol) Connection

The project uses a custom MCP context manager (`backend/mcp/context_manager.py`) that:
- Stores the last 10 turns per session in memory
- Resolves entity context (customer_id persists across turns)
- Enables follow-up queries ("give me the count" after "list appliances")

To connect this to the **Anthropic MCP standard** (for use with Claude Desktop or MCP clients):
1. Expose a `/mcp` SSE endpoint in main.py (future upgrade)
2. Or use the existing session context via `/api/chat` with consistent `session_id`

The frontend already generates and sends a `session_id` per customer, so every follow-up 
query within that session maintains full context.

---

## Environment Variables (.env)

```bash
# LLM
GROQ_API_KEY=gsk_...

# Vector DB
PINECONE_API_KEY=pcsk_...
PINECONE_INDEX=appliance-crm

# Database
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# Automation
N8N_WEBHOOK_URL=https://your-n8n-url/webhook/...

# Knowledge Graph (optional upgrade)
NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Settings
LLM_MODEL=llama3-70b-8192
LLM_TEMPERATURE=0.3
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIM=384
RELEVANCE_THRESHOLD=0.60
TOP_K=4
REFUND_APPROVAL_THRESHOLD=10000
```
