// PowerPlex API Client
const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

// ── Health & Status ──────────────────────────────────────────────────────────
export const getHealth    = () => req<any>("/api/health");
export const getStatus    = () => req<any>("/api/powerplex/status");

// ── Chat ─────────────────────────────────────────────────────────────────────
export const sendChat = (query: string, sessionId: string, customerId?: string) =>
  req<any>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ query, session_id: sessionId, customer_id: customerId }),
  });

// ── Customers ────────────────────────────────────────────────────────────────
export const getCustomers    = ()  => req<any[]>("/api/customers");
export const getCustomer     = (id: string) => req<any>(`/api/customers/${id}`);
export const getAppliances   = ()  => req<any[]>("/api/appliances");
export const getWarranties   = ()  => req<any[]>("/api/warranties");

// ── Tickets ──────────────────────────────────────────────────────────────────
export const getTickets          = (status?: string) =>
  req<any[]>(`/api/tickets${status ? `?status=${status}` : ""}`);
export const createTicket        = (data: any) =>
  req<any>("/api/tickets", { method: "POST", body: JSON.stringify(data) });
export const classifyText        = (text: string) =>
  req<any>("/api/tickets/classify", { method: "POST", body: JSON.stringify({ text }) });
export const routeTechnician     = (ticketId: string, data?: any) =>
  req<any>(`/api/tickets/${ticketId}/route-technician`, { method: "POST", body: JSON.stringify(data ?? {}) });
export const updateTicketStatus  = (ticketId: string, status: string) =>
  req<any>(`/api/tickets/${ticketId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });

// ── Approvals ────────────────────────────────────────────────────────────────
export const getAllApprovals  = (status?: string) =>
  req<any[]>(`/api/approvals/all${status ? `?status=${status}` : ""}`);
export const getApproval      = (id: string)  => req<any>(`/api/approvals/${id}`);
export const decideApproval   = (id: string, decision: "approved" | "rejected") =>
  req<any>(`/api/approvals/${id}/decide`, { method: "POST", body: JSON.stringify({ decision, decided_by: "admin" }) });
export const legacyApprovals  = () => req<any[]>("/api/approvals");
export const processLegacy    = (id: string, decision: string) =>
  req<any>("/api/approvals/process", { method: "POST", body: JSON.stringify({ approval_id: id, decision }) });

// ── Email Drafts ─────────────────────────────────────────────────────────────
export const generateDraft   = (data: any) =>
  req<any>("/api/emails/draft", { method: "POST", body: JSON.stringify(data) });
export const readyToSend     = () => req<any[]>("/api/approvals/ready-to-send");

// ── Gmail ────────────────────────────────────────────────────────────────────
export const previewGmail    = () => req<any>("/api/gmail/preview");
export const processGmail    = () => req<any>("/api/gmail/process", { method: "POST" });

// ── Recommendations ──────────────────────────────────────────────────────────
export const getRecommendations = (customerId: string, query?: string) =>
  req<any>(`/api/recommendations/${customerId}${query ? `?query=${encodeURIComponent(query)}` : ""}`);

// ── Stats ────────────────────────────────────────────────────────────────────
export const getStats        = () => req<any>("/api/stats");
export const getTechnicians  = () => req<any[]>("/api/technicians");

// ── Convenience aliases ───────────────────────────────────────────────────────
export const chat = (query: string, customerId: string | null, sessionId: string) =>
  sendChat(query, sessionId, customerId ?? undefined);
