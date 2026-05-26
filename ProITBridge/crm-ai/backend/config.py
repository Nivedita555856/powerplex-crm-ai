"""config.py — Central settings for Appliance CRM."""
import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    # LLM
    GROQ_API_KEY: str      = os.getenv("GROQ_API_KEY", "")
    LLM_MODEL: str         = os.getenv("LLM_MODEL", "llama3-70b-8192")
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # Embeddings
    EMBEDDING_MODEL: str   = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    EMBEDDING_DIM: int     = int(os.getenv("EMBEDDING_DIM", "384"))

    # Pinecone
    PINECONE_API_KEY: str  = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX: str    = os.getenv("PINECONE_INDEX", "appliance-crm")

    # Supabase
    SUPABASE_URL: str              = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    # RAG
    RELEVANCE_THRESHOLD: float = float(os.getenv("RELEVANCE_THRESHOLD", "0.60"))
    TOP_K: int                 = int(os.getenv("TOP_K", "4"))

    # n8n / Webhooks
    N8N_WEBHOOK_URL: str       = os.getenv("N8N_WEBHOOK_URL", "")
    N8N_QUERY_WEBHOOK_URL: str = os.getenv("N8N_QUERY_WEBHOOK_URL", "")
    BACKEND_PUBLIC_URL: str    = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")

    # Approval thresholds
    REFUND_APPROVAL_THRESHOLD: int   = int(os.getenv("REFUND_APPROVAL_THRESHOLD", "10000"))
    ESCALATION_AUTO_THRESHOLD: int   = int(os.getenv("ESCALATION_AUTO_THRESHOLD", "5000"))

    # Data paths
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "data")
    DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "docs")

settings = Settings()
