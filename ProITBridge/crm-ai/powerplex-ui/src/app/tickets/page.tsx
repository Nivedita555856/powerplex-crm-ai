"use client";
import { useEffect, useState } from "react";
import {
  getTickets, getCustomers, getTechnicians,
  routeTechnician, updateTicketStatus, getAllApprovals
} from "@/lib/api";

const STAGES = [
  "OPEN", "UNDER_REVIEW", "TECHNICIAN_PENDING",
  "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"
];

const STAGE_COLOR: Record<string, string> = {
  OPEN:                "bg-gray-100 text-gray-700",
  UNDER_REVIEW:        "bg-yellow-100 text-yellow-700",
  TECHNICIAN_PENDING:  "bg-orange-100 text-orange-700",
  ASSIGNED:            "bg-blue-100 text-blue-700",
  IN_PROGRESS:         "bg-indigo-100 text-indigo-700",
  RESOLVED:            "bg-green-100 text-green-700",
  CLOSED:              "bg-slate-100 text-slate-600",
};

const PRIORITY_COLOR: Record<string, string> = {
  critical: "bg-red-100 text-red-700 border border-red-200",
  high:     "bg-orange-100 text-orange-700 border border-orange-200",
  medium:   "bg-yellow-100 text-yellow-700 border border-yellow-200",
  low:      "bg-green-100 text-green-700 border border-green-200",
};

export default function TicketsPage() {
  const [tickets,    setTickets]    = useState<any[]>([]);
  const [customers,  setCustomers]  = useState<any[]>([]);
  const [technicians,setTechnicians]= useState<any[]>([]);
  const [pending,    setPending]    = useState(0);
  const [loading,    setLoading]    = useState(true);
  const [filter,     setFilter]     = useState<string>("ALL");
  const [priFilter,  setPriFilter]  = useState<string>("ALL");
  const [search,     setSearch]     = useState("");
  const [routing,    setRouting]    = useState<string | null>(null);
  const [routeResult,setRouteResult]= useState<Record<string, any>>({});
  const [statusMsg,  setStatusMsg]  = useState<Record<string, string>>({});

  async function load() {
    setLoading(true);
    try {
      const [tk, cu, te, ap] = await Promise.all([
        getTickets(), getCustomers(), getTechnicians(), getAllApprovals("pending")
      ]);
      setTickets(tk);
      setCustomers(cu);
      setTechnicians(te);
      setPending(ap.length);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function customerName(id: string) {
    return customers.find(c => c.customer_id === id)?.name ?? id;
  }

  async function handleRoute(ticketId: string) {
    setRouting(ticketId);
    try {
      const res = await routeTechnician(ticketId);
      setRouteResult(prev => ({ ...prev, [ticketId]: res }));
    } catch(e) { alert("Error routing: " + e); }
    setRouting(null);
  }

  async function handleStatus(ticketId: string, status: string) {
    try {
      await updateTicketStatus(ticketId, status);
      setStatusMsg(prev => ({ ...prev, [ticketId]: `Updated to ${status}` }));
      setTimeout(() => setStatusMsg(prev => { const n={...prev}; delete n[ticketId]; return n; }), 2000);
      load();
    } catch(e) { alert("Error: " + e); }
  }

  const filtered = tickets
    .filter(t => filter === "ALL" || t.status === filter)
    .filter(t => priFilter === "ALL" || (t.priority ?? "").toLowerCase() === priFilter)
    .filter(t => {
      if (!search) return true;
      const s = search.toLowerCase();
      return (
        t.ticket_id?.toLowerCase().includes(s) ||
        t.issue_description?.toLowerCase().includes(s) ||
        customerName(t.customer_id)?.toLowerCase().includes(s)
      );
    });

  const stageCount = STAGES.reduce((acc, s) => {
    acc[s] = tickets.filter(t => t.status === s).length;
    return acc;
  }, {} as Record<string, number>);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Ticket Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            7-stage lifecycle · technician routing · {tickets.length} total tickets
          </p>
        </div>
        <div className="flex gap-2">
          {pending > 0 && (
            <a href="/approvals"
              className="flex items-center gap-2 px-4 py-2 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-100">
              <span className="w-5 h-5 bg-amber-500 text-white rounded-full flex items-center justify-center text-xs font-bold">{pending}</span>
              Pending Approvals
            </a>
          )}
          <button onClick={load}
            className="px-4 py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-medium hover:bg-[#5a3fd6]">
            Refresh
          </button>
        </div>
      </div>

      {/* Pipeline Kanban Strip */}
      <div className="grid grid-cols-7 gap-2 mb-6">
        {STAGES.map(stage => (
          <button key={stage}
            onClick={() => setFilter(filter === stage ? "ALL" : stage)}
            className={`rounded-xl p-3 text-center transition-all border ${
              filter === stage
                ? "border-[#6C4FF8] bg-[#6C4FF8] text-white shadow-md"
                : "border-gray-200 bg-white hover:border-[#6C4FF8] hover:bg-purple-50"
            }`}>
            <div className="text-xl font-bold">{stageCount[stage] ?? 0}</div>
            <div className={`text-[10px] font-semibold mt-0.5 leading-tight ${filter === stage ? "text-white/90" : "text-gray-500"}`}>
              {stage.replace("_", " ")}
            </div>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <input
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30"
          placeholder="Search tickets, customers..."
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30"
          value={priFilter}
          onChange={e => setPriFilter(e.target.value)}>
          <option value="ALL">All Priorities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        {(filter !== "ALL" || priFilter !== "ALL" || search) && (
          <button onClick={() => { setFilter("ALL"); setPriFilter("ALL"); setSearch(""); }}
            className="px-3 py-2 text-sm text-gray-500 border border-gray-200 rounded-lg hover:bg-gray-50">
            Clear filters
          </button>
        )}
        <span className="ml-auto text-sm text-gray-500 self-center">{filtered.length} tickets shown</span>
      </div>

      {/* Tickets Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin w-8 h-8 border-2 border-[#6C4FF8] border-t-transparent rounded-full" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 text-gray-400">No tickets match your filters.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map(ticket => (
            <div key={ticket.ticket_id}
              className="bg-white border border-gray-100 rounded-xl p-4 shadow-sm hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between gap-4">
                {/* Left: ticket info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1 flex-wrap">
                    <span className="text-xs font-mono text-gray-400">{ticket.ticket_id}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${STAGE_COLOR[ticket.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {ticket.status?.replace(/_/g, " ")}
                    </span>
                    {ticket.priority && (
                      <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${PRIORITY_COLOR[ticket.priority?.toLowerCase()] ?? ""}`}>
                        {ticket.priority}
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-800 font-medium truncate">
                    {ticket.issue_description ?? "No description"}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-gray-400 flex-wrap">
                    <span>{customerName(ticket.customer_id)}</span>
                    {ticket.appliance_id && <span>· {ticket.appliance_id}</span>}
                    {ticket.created_at && (
                      <span>· {new Date(ticket.created_at).toLocaleDateString()}</span>
                    )}
                    {ticket.assigned_technician && (
                      <span className="text-indigo-500 font-medium">
                        · Tech: {technicians.find(t => t.technician_id === ticket.assigned_technician)?.name ?? ticket.assigned_technician}
                      </span>
                    )}
                  </div>
                  {statusMsg[ticket.ticket_id] && (
                    <p className="text-xs text-green-600 mt-1">{statusMsg[ticket.ticket_id]}</p>
                  )}
                  {/* Route result */}
                  {routeResult[ticket.ticket_id] && (
                    <div className="mt-2 p-2 bg-indigo-50 border border-indigo-100 rounded-lg text-xs">
                      <span className="font-semibold text-indigo-700">Routing suggestion queued for approval.</span>
                      {" "}Recommended:{" "}
                      <span className="text-indigo-600">
                        {routeResult[ticket.ticket_id]?.recommendation?.recommended_technician?.name ?? "—"}
                      </span>
                      {" · "}Score: {routeResult[ticket.ticket_id]?.recommendation?.score?.toFixed(2) ?? "—"}
                    </div>
                  )}
                </div>

                {/* Right: actions */}
                <div className="flex flex-col gap-2 items-end shrink-0">
                  <select
                    className="text-xs border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-1 focus:ring-[#6C4FF8]/40"
                    value={ticket.status}
                    onChange={e => handleStatus(ticket.ticket_id, e.target.value)}>
                    {STAGES.map(s => (
                      <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                    ))}
                  </select>
                  {(ticket.status === "OPEN" || ticket.status === "UNDER_REVIEW" || ticket.status === "TECHNICIAN_PENDING") && (
                    <button
                      onClick={() => handleRoute(ticket.ticket_id)}
                      disabled={routing === ticket.ticket_id}
                      className="text-xs px-3 py-1 bg-[#6C4FF8] text-white rounded-lg hover:bg-[#5a3fd6] disabled:opacity-50">
                      {routing === ticket.ticket_id ? "Routing..." : "Route Technician"}
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
