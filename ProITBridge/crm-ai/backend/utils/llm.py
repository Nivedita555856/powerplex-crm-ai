"""
llm.py - Groq LLM wrapper with MCP context injection.
Reads API key fresh every call. Has a 20s timeout on all requests.
"""
import os
import httpx
from dotenv import load_dotenv
from backend.mcp.context_manager import get_context_as_messages, save_turn

load_dotenv(override=True)

_client = None
_client_key = None


def _get_client():
    global _client, _client_key
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key:
        print("[LLM] GROQ_API_KEY is not set.")
        return None
    if _client is None or key != _client_key:
        try:
            from groq import Groq
            _client = Groq(api_key=key, http_client=httpx.Client(timeout=20.0))
            _client_key = key
            print(f"[LLM] Groq client initialised (key ...{key[-6:]})")
        except Exception as e:
            print(f"[LLM] Groq init failed: {e}")
            _client = None
            _client_key = None
    return _client


def _get_model():
    return os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")


def _get_temperature():
    try:
        return float(os.getenv("LLM_TEMPERATURE", "0.3"))
    except ValueError:
        return 0.3


def call_llm(system_prompt: str, user_prompt: str, session_id: str = "",
             max_tokens: int = 400) -> str:
    global _client, _client_key
    client = _get_client()

    messages = []
    if session_id:
        history = get_context_as_messages(session_id)
        messages = [m for m in history[-8:] if m["role"] in ("user", "assistant")]

    messages_to_send = (
        [{"role": "system", "content": system_prompt}]
        + messages
        + [{"role": "user", "content": user_prompt}]
    )

    if client is None:
        return _fallback_response(user_prompt)

    try:
        resp = client.chat.completions.create(
            model=_get_model(),
            messages=messages_to_send,
            max_tokens=max_tokens,
            temperature=_get_temperature(),
            timeout=20.0,
        )
        response = resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM] Call failed: {e}")
        _client = None
        _client_key = None
        response = f"LLM error: {e}"

    if session_id:
        save_turn(session_id, "user", user_prompt[:500])
        save_turn(session_id, "assistant", response[:500])

    return response


def _fallback_response(query: str) -> str:
    q = query.lower()
    try:
        from backend.data_loader import get_appliances, get_open_tickets, get_customers

        if "warranty" in q:
            return "[Groq not connected] Select a customer and use the Warranty tab."

        if "recommend" in q or "suggest" in q or "product" in q:
            appliances = get_appliances()
            lines = ["Available appliances:\n"]
            for a in appliances:
                lines.append(f"  {a['brand']} {a['model']} ({a['category']}) - Rs.{int(a['price']):,}")
            lines.append("\nSet GROQ_API_KEY in .env for AI recommendations.")
            return "\n".join(lines)

        if "ticket" in q or "issue" in q or "open" in q:
            open_t = get_open_tickets()
            if not open_t:
                return "No open tickets at this time."
            lines = [f"Open tickets ({len(open_t)}):\n"]
            for t in open_t[:6]:
                lines.append(f"  [{t['priority'].upper()}] {t['ticket_id']}: {t['issue'][:50]}")
            return "\n".join(lines)

        if "repair" in q or "service" in q or "book" in q:
            msg = "To book a service visit:\n"
            msg += "1. Select the customer from the sidebar\n"
            msg += "2. Go to the Tickets tab\n"
            msg += "3. Click '+ Create Ticket' and describe the issue\n\n"
            msg += "A technician will be assigned based on location and specialization."
            return msg

        if "refund" in q:
            msg = "Refund eligibility:\n"
            msg += "  - Product must be within warranty period\n"
            msg += "  - Issue must be a manufacturing defect\n"
            msg += "  - Refunds above Rs.10,000 require manager approval\n\n"
            msg += "Please raise a ticket and our team will evaluate."
            return msg

        customers = get_customers()
        open_t = get_open_tickets()
        return (
            "[Data-only mode - Groq not connected]\n\n"
            f"System: {len(customers)} customers | {len(open_t)} open tickets\n\n"
            "Check that GROQ_API_KEY is set in .env, then restart the server."
        )
    except Exception:
        return "Please select a customer and try again."
