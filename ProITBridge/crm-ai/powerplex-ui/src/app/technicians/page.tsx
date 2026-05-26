"use client";
import { useEffect, useState } from "react";
import { getTechnicians, getTickets, routeTechnician } from "@/lib/api";

const RATING_COLOR = (r: number) =>
  r >= 4.5 ? "text-green-600" : r >= 3.5 ? "text-amber-500" : "text-red-500";

const STATUS_COLOR: Record<string, string> = {
  Available:  "bg-green-100 text-green-700 border-green-200",
  Busy:       "bg-orange-100 text-orange-700 border-orange-200",
  Offline:    "bg-gray-100 text-gray-500 border-gray-200",
};

export default function TechniciansPage() {
  const [technicians, setTechnicians] = useState<any[]>([]);
  const [tickets,     setTickets]     = useState<any[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [search,      setSearch]      = useState("");
  const [specFilter,  setSpecFilter]  = useState("ALL");
  const [selected,    setSelected]    = useState<any | null>(null);
  const [routing,     setRouting]     = useState<string | null>(null);
  const [routeResult, setRouteResult] = useState<any | null>(null);
  const [routeTicket, setRouteTicket] = useState("");

  async function load() {
    setLoading(true);
    try {
      const [te, ti] = await Promise.all([getTechnicians(), getTickets()]);
      setTechnicians(te);
      setTickets(ti);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function assignedTickets(techId: string) {
    return tickets.filter(t =>
      t.assigned_technician === techId && !["RESOLVED", "CLOSED"].includes(t.status)
    );
  }

  function completedTickets(techId: string) {
    return tickets.filter(t =>
      t.assigned_technician === techId && ["RESOLVED", "CLOSED"].includes(t.status)
    );
  }

  async function handleRoute() {
    if (!routeTicket.trim()) return;
    setRouting(routeTicket);
    setRouteResult(null);
    try {
      const res = await routeTechnician(routeTicket.trim());
      setRouteResult(res);
    } catch(e) {
      setRouteResult({ error: String(e) });
    }
    setRouting(null);
  }

  const specs = Array.from(new Set(
    technicians.flatMap(t => (t.specializations ?? t.specialization ?? []))
  )).sort();

  const filtered = technicians
    .filter(t => specFilter === "ALL" || (t.specializations ?? t.specialization ?? []).includes(specFilter))
    .filter(t => {
      if (!search) return true;
      const s = search.toLowerCase();
      return (
        t.name?.toLowerCase().includes(s) ||
        t.technician_id?.toLowerCase().includes(s) ||
        t.city?.toLowerCase().includes(s)
      );
    });

  // Workload summary
  const workloadData = technicians.map(t => ({
    ...t,
    active: assignedTickets(t.technician_id).length,
    done:   completedTickets(t.technician_id).length,
  })).sort((a, b) => b.active - a.active);

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Technician Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Workload analytics · specialization routing · ticket assignments
          </p>
        </div>
        <button onClick={load}
          className="px-4 py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-medium hover:bg-[#5a3fd6]">
          Refresh
        </button>
      </div>

      {/* Workload Bar Chart */}
      <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm mb-6">
        <h2 className="font-semibold text-gray-700 mb-4 text-sm">Active Workload Distribution</h2>
        <div className="space-y-2">
          {workloadData.map(t => {
            const maxActive = Math.max(...workloadData.map(x => x.active), 1);
            const pct = Math.round((t.active / maxActive) * 100);
            return (
              <div key={t.technician_id} className="flex items-center gap-3">
                <span className="text-xs text-gray-600 w-28 truncate font-medium">{t.name}</span>
                <div className="flex-1 bg-gray-100 rounded-full h-4 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#6C4FF8] to-[#9d87fa] rounded-full transition-all"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="text-xs text-gray-500 w-16 text-right">
                  {t.active} active · {t.done} done
                </span>
              </div>
            );
          })}
        </div>
      </div>

      <div className="flex gap-6">
        {/* Technician List */}
        <div className="flex-1 min-w-0">
          {/* Filters */}
          <div className="flex gap-3 mb-4 flex-wrap">
            <input
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-48 focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30"
              placeholder="Search..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            <select
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30"
              value={specFilter}
              onChange={e => setSpecFilter(e.target.value)}>
              <option value="ALL">All Specializations</option>
              {specs.map(s => <option key={String(s)} value={String(s)}>{String(s)}</option>)}
            </select>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin w-8 h-8 border-2 border-[#6C4FF8] border-t-transparent rounded-full" />
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filtered.map(tech => {
                const active    = assignedTickets(tech.technician_id);
                const completed = completedTickets(tech.technician_id);
                const specs_    = tech.specializations ?? tech.specialization ?? [];
                const isSelected= selected?.technician_id === tech.technician_id;

                return (
                  <div key={tech.technician_id}
                    onClick={() => setSelected(isSelected ? null : tech)}
                    className={`bg-white border rounded-xl p-4 cursor-pointer transition-all shadow-sm hover:shadow-md ${
                      isSelected ? "border-[#6C4FF8] ring-2 ring-[#6C4FF8]/20" : "border-gray-100"
                    }`}>
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-xs font-mono text-gray-400">{tech.technician_id}</span>
                          {tech.availability_status && (
                            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_COLOR[tech.availability_status] ?? "bg-gray-100 text-gray-500"}`}>
                              {tech.availability_status}
                            </span>
                          )}
                        </div>
                        <p className="font-semibold text-gray-900">{tech.name}</p>
                        {tech.city && <p className="text-xs text-gray-400 mt-0.5">{tech.city}</p>}
                      </div>
                      {tech.rating && (
                        <div className="text-right">
                          <span className={`text-lg font-bold ${RATING_COLOR(Number(tech.rating))}`}>
                            {Number(tech.rating).toFixed(1)}
                          </span>
                          <p className="text-xs text-gray-400">rating</p>
                        </div>
                      )}
                    </div>

                    {/* Specializations */}
                    {specs_.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-3">
                        {specs_.map((s: string) => (
                          <span key={s} className="text-xs bg-indigo-50 text-indigo-600 border border-indigo-100 px-2 py-0.5 rounded-full">
                            {s}
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Stats */}
                    <div className="flex gap-4 text-center">
                      <div>
                        <span className="text-lg font-bold text-[#6C4FF8]">{active.length}</span>
                        <p className="text-xs text-gray-400">active</p>
                      </div>
                      <div>
                        <span className="text-lg font-bold text-green-600">{completed.length}</span>
                        <p className="text-xs text-gray-400">resolved</p>
                      </div>
                      {tech.experience_years && (
                        <div>
                          <span className="text-lg font-bold text-gray-700">{tech.experience_years}</span>
                          <p className="text-xs text-gray-400">yrs exp</p>
                        </div>
                      )}
                    </div>

                    {/* Expanded: active tickets */}
                    {isSelected && active.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <p className="text-xs font-semibold text-gray-500 mb-2">Active Tickets</p>
                        <div className="space-y-1">
                          {active.map((t: any) => (
                            <div key={t.ticket_id} className="flex items-center gap-2 text-xs bg-gray-50 rounded-lg px-3 py-2">
                              <span className="font-mono text-gray-500">{t.ticket_id}</span>
                              <span className="flex-1 text-gray-600 truncate">{t.issue_description?.slice(0, 50)}</span>
                              <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full shrink-0">
                                {t.status?.replace(/_/g, " ")}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Route Technician Panel */}
        <div className="w-72 shrink-0">
          <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm sticky top-6 space-y-4">
            <div>
              <h3 className="font-semibold text-gray-800">Route a Ticket</h3>
              <p className="text-xs text-gray-400 mt-0.5">
                AI scores technicians by specialization (60%) + rating (40%)
              </p>
            </div>

            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Ticket ID</label>
              <input
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30"
                placeholder="e.g. TKT001"
                value={routeTicket}
                onChange={e => setRouteTicket(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleRoute()}
              />
            </div>

            <button
              onClick={handleRoute}
              disabled={!!routing || !routeTicket.trim()}
              className="w-full py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-medium hover:bg-[#5a3fd6] disabled:opacity-50 flex items-center justify-center gap-2">
              {routing && <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />}
              {routing ? "Routing..." : "Route with AI"}
            </button>

            {routeResult && (
              <div className={`rounded-lg p-3 text-sm ${routeResult.error ? "bg-red-50 border border-red-100 text-red-700" : "bg-purple-50 border border-purple-100"}`}>
                {routeResult.error ? (
                  <p>{routeResult.error}</p>
                ) : (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 bg-amber-400 rounded-full" />
                      <span className="text-xs font-semibold text-amber-700">Queued for approval</span>
                    </div>
                    {routeResult.recommendation?.recommended_technician && (
                      <>
                        <p className="text-xs text-gray-700">
                          <strong>Recommended:</strong>{" "}
                          {routeResult.recommendation.recommended_technician.name}
                        </p>
                        <p className="text-xs text-gray-600">
                          Score: {routeResult.recommendation.score?.toFixed(3)}
                        </p>
                        <p className="text-xs text-gray-600 leading-relaxed">
                          {routeResult.recommendation.reasoning?.slice(0, 120)}...
                        </p>
                      </>
                    )}
                    <a href="/approvals" className="block text-xs text-[#6C4FF8] hover:underline mt-1">
                      Review in Approvals
                    </a>
                  </div>
                )}
              </div>
            )}

            {/* Scoring explanation */}
            <div className="border-t border-gray-100 pt-3 space-y-2">
              <p className="text-xs font-semibold text-gray-500">Routing Algorithm</p>
              <div className="space-y-1 text-xs text-gray-500">
                <div className="flex justify-between">
                  <span>Specialization match</span>
                  <span className="font-medium text-[#6C4FF8]">60%</span>
                </div>
                <div className="flex justify-between">
                  <span>Technician rating</span>
                  <span className="font-medium text-[#6C4FF8]">40%</span>
                </div>
                <div className="flex justify-between">
                  <span>Requires approval</span>
                  <span className="font-medium text-amber-600">Always</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
