"use client";
import { useEffect, useState } from "react";
import { processGmail, getAllApprovals, decideApproval, legacyApprovals, processLegacy } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export default function AutomationPage() {
  const [gmailResult,  setGmailResult]  = useState<any | null>(null);
  const [processing,   setProcessing]   = useState(false);
  const [webhookLog,   setWebhookLog]   = useState<string[]>([]);
  const [approvals,    setApprovals]    = useState<any[]>([]);
  const [legacy,       setLegacy]       = useState<any[]>([]);
  const [loadingAp,    setLoadingAp]    = useState(true);
  const [deciding,     setDeciding]     = useState<string | null>(null);
  const [status,       setStatus]       = useState<any | null>(null);
  const [loadingStatus,setLoadingStatus]= useState(true);

  async function loadStatus() {
    setLoadingStatus(true);
    try {
      const r = await fetch(`${API}/api/powerplex/status`);
      setStatus(await r.json());
    } catch {}
    setLoadingStatus(false);
  }

  async function loadApprovals() {
    setLoadingAp(true);
    try {
      const [ap, lg] = await Promise.all([getAllApprovals("pending"), legacyApprovals()]);
      setApprovals(ap);
      setLegacy(lg);
    } catch {}
    setLoadingAp(false);
  }

  useEffect(() => {
    loadStatus();
    loadApprovals();
  }, []);

  async function handleProcessGmail() {
    setProcessing(true);
    setGmailResult(null);
    try {
      const res = await processGmail();
      setGmailResult(res);
      addLog(`Gmail processed: ${res.processed ?? 0} emails, ${res.tickets_created ?? 0} tickets`);
      loadApprovals();
    } catch (e: any) {
      setGmailResult({ error: String(e) });
      addLog(`Gmail processing failed: ${e}`);
    }
    setProcessing(false);
  }

  function addLog(msg: string) {
    const ts = new Date().toLocaleTimeString();
    setWebhookLog(prev => [`[${ts}] ${msg}`, ...prev].slice(0, 50));
  }

  async function triggerWebhook(type: "n8n" | "make") {
    const endpoint = type === "n8n" ? "/api/webhook/n8n" : "/api/webhook/make";
    addLog(`Triggering ${type.toUpperCase()} webhook...`);
    try {
      const r = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ test: true, source: "powerplex-ui", timestamp: new Date().toISOString() }),
      });
      const data = await r.json();
      addLog(`${type.toUpperCase()} response: ${JSON.stringify(data).slice(0, 120)}`);
    } catch (e) {
      addLog(`${type.toUpperCase()} error: ${e}`);
    }
  }

  async function decide(id: string, decision: "approved" | "rejected", isLegacy = false) {
    setDeciding(id);
    try {
      if (isLegacy) await processLegacy(id, decision);
      else          await decideApproval(id, decision);
      addLog(`Approval ${id}: ${decision}`);
      loadApprovals();
    } catch(e) { addLog(`Approval error: ${e}`); }
    setDeciding(null);
  }

  const allPending = [
    ...approvals.map(a => ({ ...a, _src: "pp" })),
    ...legacy
      .filter(l => !approvals.find(a => a.approval_id === l.approval_id))
      .map(l => ({ ...l, _src: "legacy" })),
  ].filter(a => a.status === "pending");

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Automation Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Gmail inbox processing · webhook automation · approval queue
        </p>
      </div>

      {/* System Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {loadingStatus ? (
          Array(4).fill(0).map((_, i) => (
            <div key={i} className="bg-white border border-gray-100 rounded-xl p-4 animate-pulse h-20" />
          ))
        ) : status ? (
          <>
            <StatusCard label="Groq LLM" ok={status.groq_connected} />
            <StatusCard label="AutoGen" ok={status.autogen_available} />
            <StatusCard label="CrewAI" ok={status.crewai_available} />
            <StatusCard label="MCTS" ok={status.mcts_enabled} />
          </>
        ) : (
          <div className="col-span-4 text-sm text-gray-400">Could not load system status.</div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Gmail Processing */}
        <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="font-semibold text-gray-800">Gmail Inbox Processing</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Reads emails · classifies · creates tickets · queues confirmations
              </p>
            </div>
            <button
              onClick={handleProcessGmail}
              disabled={processing}
              className="px-4 py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-medium hover:bg-[#5a3fd6] disabled:opacity-50 flex items-center gap-2">
              {processing && (
                <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />
              )}
              {processing ? "Processing..." : "Process Inbox"}
            </button>
          </div>

          {gmailResult && (
            <div className={`rounded-lg p-3 text-sm ${gmailResult.error ? "bg-red-50 border border-red-100 text-red-700" : "bg-green-50 border border-green-100 text-green-700"}`}>
              {gmailResult.error ? (
                <p>Error: {gmailResult.error}</p>
              ) : (
                <div className="space-y-1">
                  <p>Emails processed: <strong>{gmailResult.processed ?? 0}</strong></p>
                  <p>Tickets created: <strong>{gmailResult.tickets_created ?? 0}</strong></p>
                  {gmailResult.tickets?.map((t: any, i: number) => (
                    <div key={i} className="text-xs bg-white/60 rounded p-2 mt-1">
                      <span className="font-mono">{t.ticket_id}</span>
                      {" — "}{t.issue_description?.slice(0, 80)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Known demo emails */}
          <div className="mt-4">
            <p className="text-xs font-semibold text-gray-500 mb-2">Configured customer emails</p>
            {[
              { email: "arunchabra03@gmail.com", id: "CUST_DEMO1" },
              { email: "niveditakothuri9@gmail.com", id: "CUST_DEMO2" },
              { email: "knivedita132@gmail.com", id: "CUST_DEMO3" },
            ].map(e => (
              <div key={e.email} className="flex items-center justify-between py-1 text-xs text-gray-600">
                <span>{e.email}</span>
                <span className="font-mono text-indigo-500">{e.id}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Webhook Triggers */}
        <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
          <h2 className="font-semibold text-gray-800 mb-4">Webhook Automation</h2>
          <div className="flex gap-3 mb-4">
            <button
              onClick={() => triggerWebhook("n8n")}
              className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 font-medium">
              Trigger n8n
            </button>
            <button
              onClick={() => triggerWebhook("make")}
              className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm text-gray-700 hover:bg-gray-50 font-medium">
              Trigger Make.com
            </button>
          </div>

          {/* Webhook log */}
          <div className="bg-gray-900 rounded-lg p-3 font-mono text-xs text-green-400 h-48 overflow-y-auto space-y-1">
            {webhookLog.length === 0 ? (
              <span className="text-gray-500">Trigger a webhook to see logs...</span>
            ) : (
              webhookLog.map((line, i) => <div key={i}>{line}</div>)
            )}
          </div>

          <div className="mt-3 text-xs text-gray-400 space-y-1">
            <p>POST /api/webhook/n8n — inbound n8n payloads</p>
            <p>POST /api/webhook/make — inbound Make.com payloads</p>
            <p>POST /api/webhook/ticket-created — ticket lifecycle events</p>
          </div>
        </div>
      </div>

      {/* Approval Queue */}
      <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="font-semibold text-gray-800">Approval Queue</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              All AI-generated emails and actions require admin approval before execution
            </p>
          </div>
          <span className="text-xs px-2 py-1 bg-amber-100 text-amber-700 font-medium rounded-full">
            {allPending.length} pending
          </span>
        </div>

        {loadingAp ? (
          <div className="flex items-center justify-center h-24">
            <div className="animate-spin w-6 h-6 border-2 border-[#6C4FF8] border-t-transparent rounded-full" />
          </div>
        ) : allPending.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">No pending approvals</div>
        ) : (
          <div className="space-y-2">
            {allPending.slice(0, 10).map(item => (
              <div key={item.approval_id}
                className="flex items-center justify-between p-3 border border-gray-100 rounded-lg hover:bg-gray-50">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs font-mono text-gray-400">{item.approval_id?.slice(0, 16)}...</span>
                    <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">
                      {item.action_type?.replace(/_/g, " ")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700 truncate">
                    {item.subject ?? item.description ?? "Action pending approval"}
                  </p>
                </div>
                <div className="flex gap-2 ml-4 shrink-0">
                  <button
                    onClick={() => decide(item.approval_id, "approved", item._src === "legacy")}
                    disabled={deciding === item.approval_id}
                    className="px-3 py-1 bg-green-600 text-white text-xs rounded-lg hover:bg-green-700 disabled:opacity-50">
                    Approve
                  </button>
                  <button
                    onClick={() => decide(item.approval_id, "rejected", item._src === "legacy")}
                    disabled={deciding === item.approval_id}
                    className="px-3 py-1 bg-red-500 text-white text-xs rounded-lg hover:bg-red-600 disabled:opacity-50">
                    Reject
                  </button>
                </div>
              </div>
            ))}
            {allPending.length > 10 && (
              <a href="/approvals" className="block text-center text-sm text-[#6C4FF8] hover:underline pt-2">
                View all {allPending.length} pending approvals
              </a>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusCard({ label, ok }: { label: string; ok?: boolean }) {
  return (
    <div className={`bg-white border rounded-xl p-4 shadow-sm ${ok ? "border-green-100" : "border-gray-100"}`}>
      <div className="flex items-center gap-2">
        <span className={`w-2.5 h-2.5 rounded-full ${ok ? "bg-green-500" : "bg-gray-300"}`} />
        <span className="text-sm font-medium text-gray-700">{label}</span>
      </div>
      <p className={`text-xs mt-1 ${ok ? "text-green-600" : "text-gray-400"}`}>
        {ok ? "Connected" : "Not configured"}
      </p>
    </div>
  );
}
