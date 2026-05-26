"use client";
import { useEffect, useState } from "react";
import { getCustomers, getWarranties, getTickets, chat } from "@/lib/api";

const SEGMENT_COLOR: Record<string, string> = {
  Premium:  "bg-purple-100 text-purple-700 border border-purple-200",
  Standard: "bg-blue-100 text-blue-700 border border-blue-200",
  Basic:    "bg-gray-100 text-gray-600 border border-gray-200",
};

export default function CustomersPage() {
  const [customers,   setCustomers]  = useState<any[]>([]);
  const [warranties,  setWarranties] = useState<any[]>([]);
  const [tickets,     setTickets]    = useState<any[]>([]);
  const [loading,     setLoading]    = useState(true);
  const [search,      setSearch]     = useState("");
  const [segFilter,   setSegFilter]  = useState("ALL");
  const [selected,    setSelected]   = useState<any | null>(null);
  const [recQuery,    setRecQuery]   = useState("");
  const [recResult,   setRecResult]  = useState<string | null>(null);
  const [recLoading,  setRecLoading] = useState(false);
  const [sessionId]                  = useState(() => `cust-${Date.now()}`);

  async function load() {
    setLoading(true);
    try {
      const [cu, wa, ti] = await Promise.all([getCustomers(), getWarranties(), getTickets()]);
      setCustomers(cu);
      setWarranties(wa);
      setTickets(ti);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  function warrantyFor(custId: string) {
    return warranties.filter(w => w.customer_id === custId);
  }

  function ticketsFor(custId: string) {
    return tickets.filter(t => t.customer_id === custId);
  }

  function activeWarranty(custId: string) {
    return warrantyFor(custId).find(w => w.status === "Active");
  }

  async function getRecommendation(custId: string) {
    setRecLoading(true);
    setRecResult(null);
    try {
      const q = recQuery
        ? recQuery
        : `Recommend the best appliance for ${selected?.name ?? "this customer"}`;
      const res = await chat(q, custId, sessionId);
      setRecResult(res.answer);
    } catch(e) {
      setRecResult("Error fetching recommendation: " + e);
    }
    setRecLoading(false);
  }

  const filtered = customers
    .filter(c => segFilter === "ALL" || c.segment === segFilter)
    .filter(c => {
      if (!search) return true;
      const s = search.toLowerCase();
      return (
        c.name?.toLowerCase().includes(s) ||
        c.customer_id?.toLowerCase().includes(s) ||
        c.city?.toLowerCase().includes(s) ||
        c.email?.toLowerCase().includes(s)
      );
    });

  const segments = ["ALL", ...Array.from(new Set(customers.map(c => c.segment).filter(Boolean)))];

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Customer Intelligence</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Purchase history · warranty analytics · AI recommendations
          </p>
        </div>
        <button onClick={load}
          className="px-4 py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-medium hover:bg-[#5a3fd6]">
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <SummaryCard label="Total Customers" value={customers.length} color="purple" />
        <SummaryCard label="Active Warranties" value={warranties.filter(w => w.status === "Active").length} color="green" />
        <SummaryCard label="Premium Segment" value={customers.filter(c => c.segment === "Premium").length} color="amber" />
        <SummaryCard label="Expiring Soon" value={warranties.filter(w => {
          if (!w.end_date) return false;
          const days = (new Date(w.end_date).getTime() - Date.now()) / 86400000;
          return days > 0 && days <= 30;
        }).length} color="red" />
      </div>

      <div className="flex gap-6">
        {/* Customer List */}
        <div className="flex-1 min-w-0">
          {/* Filters */}
          <div className="flex gap-3 mb-4 flex-wrap">
            <input
              className="border border-gray-200 rounded-lg px-3 py-2 text-sm w-56 focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30"
              placeholder="Search name, city, email..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
            <div className="flex gap-2">
              {segments.map(seg => (
                <button key={seg}
                  onClick={() => setSegFilter(seg)}
                  className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                    segFilter === seg
                      ? "bg-[#6C4FF8] text-white border-[#6C4FF8]"
                      : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}>
                  {seg}
                </button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="animate-spin w-8 h-8 border-2 border-[#6C4FF8] border-t-transparent rounded-full" />
            </div>
          ) : (
            <div className="space-y-2">
              {filtered.map(customer => {
                const cw = warrantyFor(customer.customer_id);
                const ct = ticketsFor(customer.customer_id);
                const aw = activeWarranty(customer.customer_id);
                const isSelected = selected?.customer_id === customer.customer_id;

                return (
                  <div key={customer.customer_id}
                    onClick={() => { setSelected(isSelected ? null : customer); setRecResult(null); }}
                    className={`bg-white border rounded-xl p-4 cursor-pointer transition-all shadow-sm hover:shadow-md ${
                      isSelected ? "border-[#6C4FF8] ring-2 ring-[#6C4FF8]/20" : "border-gray-100"
                    }`}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <span className="text-xs font-mono text-gray-400">{customer.customer_id}</span>
                          {customer.segment && (
                            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SEGMENT_COLOR[customer.segment] ?? "bg-gray-100 text-gray-600"}`}>
                              {customer.segment}
                            </span>
                          )}
                          {aw && (
                            <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full border border-green-200 font-medium">
                              Active warranty
                            </span>
                          )}
                        </div>
                        <p className="font-semibold text-gray-900">{customer.name}</p>
                        <div className="flex gap-3 mt-1 text-xs text-gray-400 flex-wrap">
                          {customer.city && <span>{customer.city}</span>}
                          {customer.email && <span>{customer.email}</span>}
                          {customer.phone && <span>{customer.phone}</span>}
                        </div>
                      </div>
                      <div className="flex gap-3 text-center ml-4 shrink-0">
                        <div>
                          <div className="text-lg font-bold text-[#6C4FF8]">{cw.length}</div>
                          <div className="text-xs text-gray-400">warranties</div>
                        </div>
                        <div>
                          <div className="text-lg font-bold text-gray-700">{ct.length}</div>
                          <div className="text-xs text-gray-400">tickets</div>
                        </div>
                      </div>
                    </div>

                    {/* Expanded: warranties + tickets */}
                    {isSelected && (
                      <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
                        {cw.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold text-gray-500 mb-2">Warranties</p>
                            <div className="space-y-1">
                              {cw.map((w: any) => (
                                <div key={w.warranty_id} className="flex items-center justify-between text-xs bg-gray-50 rounded-lg px-3 py-2">
                                  <span className="font-mono text-gray-500">{w.warranty_id}</span>
                                  <span className="text-gray-600">{w.appliance_id}</span>
                                  <span className={`px-2 py-0.5 rounded-full font-medium ${w.status === "Active" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                                    {w.status}
                                  </span>
                                  <span className="text-gray-400">
                                    {w.end_date ? `Exp: ${new Date(w.end_date).toLocaleDateString()}` : "—"}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {ct.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold text-gray-500 mb-2">Recent Tickets</p>
                            <div className="space-y-1">
                              {ct.slice(0, 3).map((t: any) => (
                                <div key={t.ticket_id} className="flex items-center gap-3 text-xs bg-gray-50 rounded-lg px-3 py-2">
                                  <span className="font-mono text-gray-500">{t.ticket_id}</span>
                                  <span className="flex-1 text-gray-600 truncate">{t.issue_description?.slice(0, 60)}</span>
                                  <span className={`px-2 py-0.5 rounded-full font-medium shrink-0 ${
                                    t.status === "RESOLVED" || t.status === "CLOSED"
                                      ? "bg-green-100 text-green-700"
                                      : "bg-yellow-100 text-yellow-700"
                                  }`}>{t.status}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Recommendation Panel */}
        {selected && (
          <div className="w-80 shrink-0">
            <div className="bg-white border border-gray-100 rounded-xl p-5 shadow-sm sticky top-6">
              <h3 className="font-semibold text-gray-800 mb-1">AI Recommendations</h3>
              <p className="text-xs text-gray-400 mb-4">for {selected.name}</p>

              <textarea
                className="w-full border border-gray-200 rounded-lg p-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-[#6C4FF8]/30 mb-3"
                rows={2}
                placeholder="e.g. best washing machine for a family of 4..."
                value={recQuery}
                onChange={e => setRecQuery(e.target.value)}
              />
              <button
                onClick={() => getRecommendation(selected.customer_id)}
                disabled={recLoading}
                className="w-full py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-medium hover:bg-[#5a3fd6] disabled:opacity-50 flex items-center justify-center gap-2">
                {recLoading && <span className="animate-spin w-3 h-3 border border-white border-t-transparent rounded-full" />}
                {recLoading ? "Generating..." : "Get AI Recommendation"}
              </button>

              {recResult && (
                <div className="mt-4 p-3 bg-purple-50 border border-purple-100 rounded-lg text-sm text-gray-700 whitespace-pre-line leading-relaxed">
                  {recResult}
                </div>
              )}

              {/* Warranty expiry notice */}
              {warrantyFor(selected.customer_id).map(w => {
                if (!w.end_date) return null;
                const days = Math.round((new Date(w.end_date).getTime() - Date.now()) / 86400000);
                if (days > 60 || days < 0) return null;
                return (
                  <div key={w.warranty_id} className="mt-3 p-3 bg-amber-50 border border-amber-100 rounded-lg text-xs text-amber-700">
                    Warranty <span className="font-mono">{w.warranty_id}</span> expires in{" "}
                    <strong>{days} days</strong> ({w.end_date})
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color: string }) {
  const colors: Record<string, string> = {
    purple: "border-purple-100 bg-purple-50 text-purple-700",
    green:  "border-green-100 bg-green-50 text-green-700",
    amber:  "border-amber-100 bg-amber-50 text-amber-700",
    red:    "border-red-100 bg-red-50 text-red-700",
  };
  return (
    <div className={`border rounded-xl p-4 shadow-sm ${colors[color]}`}>
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-xs font-medium mt-0.5 opacity-80">{label}</div>
    </div>
  );
}
