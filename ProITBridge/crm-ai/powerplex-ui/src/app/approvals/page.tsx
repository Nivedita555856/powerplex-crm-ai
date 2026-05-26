"use client";
import { useEffect, useState } from "react";
import { getAllApprovals, decideApproval, legacyApprovals, processLegacy } from "@/lib/api";

const TYPE_COLOUR: Record<string,string> = {
  email_ticket_confirmation:   "bg-blue-100 text-blue-700",
  email_technician_assignment: "bg-purple-100 text-purple-700",
  email_warranty_decision:     "bg-amber-100 text-amber-700",
  email_repair_completion:     "bg-green-100 text-green-700",
  email_escalation:            "bg-red-100 text-red-700",
  email_apology:               "bg-pink-100 text-pink-700",
  technician_assignment:       "bg-indigo-100 text-indigo-700",
  refund_approval:             "bg-orange-100 text-orange-700",
};

export default function ApprovalsPage() {
  const [items, setItems]     = useState<any[]>([]);
  const [legacy, setLegacy]   = useState<any[]>([]);
  const [preview, setPreview] = useState<any|null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab]         = useState<"pending"|"all">("pending");

  async function load() {
    setLoading(true);
    try {
      const [pp, lg] = await Promise.all([getAllApprovals(tab==="pending"?"pending":undefined), legacyApprovals()]);
      setItems(pp);
      setLegacy(lg);
    } catch {}
    setLoading(false);
  }

  useEffect(() => { load(); }, [tab]);

  async function decide(id: string, decision: "approved"|"rejected", legacy=false) {
    try {
      if (legacy) await processLegacy(id, decision);
      else        await decideApproval(id, decision);
      load();
      if (preview?.approval_id === id) setPreview(null);
    } catch(e) { alert("Error: " + e); }
  }

  const allItems = [...items, ...legacy.filter(l => !items.find(i => i.approval_id === l.approval_id))];
  const pending  = allItems.filter(i => i.status === "pending");

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-[#1E1B4B]">Approval Center</h1>
          <p className="text-sm text-[#9CA3AF]">Every email and assignment requires your approval before execution</p>
        </div>
        <div className="flex gap-2">
          {pending.length > 0 && <span className="bg-red-500 text-white text-xs font-bold px-3 py-1 rounded-full animate-pulse">{pending.length} pending</span>}
          <button onClick={load} className="px-4 py-2 bg-[#6C4FF8] text-white rounded-lg text-sm font-semibold hover:bg-[#4E38C2]">Refresh</button>
        </div>
      </div>

      <div className="flex gap-2 mb-4">
        {(["pending","all"] as const).map(t => (
          <button key={t} onClick={()=>setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all capitalize
              ${tab===t ? "bg-[#6C4FF8] text-white" : "bg-white text-[#4B5563] border border-[#DDD6FE] hover:border-[#6C4FF8]"}`}>{t}</button>
        ))}
      </div>

      {/* RULE banner */}
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 mb-5 flex gap-2 items-start">
        <span className="text-amber-500 font-bold text-lg">!</span>
        <div>
          <p className="text-xs font-bold text-amber-700">Approval Rule Active</p>
          <p className="text-xs text-amber-600">No email is sent and no technician is assigned without your explicit approval. All AI-generated outputs are held here first.</p>
        </div>
      </div>

      {loading ? <p className="text-sm text-[#9CA3AF]">Loading...</p> : (
        <div className="grid grid-cols-1 gap-3">
          {allItems.length === 0 && <div className="bg-white rounded-xl p-8 text-center text-[#9CA3AF] text-sm border border-[#E5E7EB]">No approval items</div>}
          {allItems.map(item => (
            <div key={item.approval_id}
              className={`bg-white rounded-xl border p-4 shadow-sm cursor-pointer hover:border-[#6C4FF8] transition-all
                ${item.status==="pending" ? "border-amber-200" : item.status==="approved" ? "border-green-200" : "border-red-200"}`}
              onClick={() => setPreview(item)}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${TYPE_COLOUR[item.item_type] || "bg-gray-100 text-gray-600"}`}>
                      {item.description || item.item_type}
                    </span>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold
                      ${item.status==="pending" ? "bg-amber-100 text-amber-700" : item.status==="approved" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
                      {item.status}
                    </span>
                  </div>
                  <p className="text-sm font-medium text-[#1E1B4B]">{item.subject || item.description || item.item_type}</p>
                  {item.to_email && <p className="text-xs text-[#9CA3AF] mt-0.5">To: {item.to_email}</p>}
                  {item.ticket_id && <p className="text-xs text-[#9CA3AF]">Ticket: {item.ticket_id}</p>}
                  {item.amount > 0 && <p className="text-xs text-[#9CA3AF]">Amount: Rs.{item.amount.toLocaleString()}</p>}
                </div>
                {item.status === "pending" && (
                  <div className="flex gap-2" onClick={e => e.stopPropagation()}>
                    <button onClick={() => decide(item.approval_id, "approved", !!item.item_type?.startsWith && !item.body)}
                      className="px-3 py-1.5 bg-green-100 text-green-700 border border-green-300 rounded-lg text-xs font-bold hover:bg-green-200">Approve</button>
                    <button onClick={() => decide(item.approval_id, "rejected", !!item.item_type?.startsWith && !item.body)}
                      className="px-3 py-1.5 bg-red-100 text-red-700 border border-red-300 rounded-lg text-xs font-bold hover:bg-red-200">Reject</button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Email preview modal */}
      {preview && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setPreview(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
            <div className="flex justify-between items-start mb-4">
              <div>
                <h2 className="font-bold text-[#1E1B4B] text-lg">{preview.subject || "Action Review"}</h2>
                {preview.to_email && <p className="text-sm text-[#9CA3AF]">To: {preview.to_email}</p>}
              </div>
              <button onClick={() => setPreview(null)} className="text-[#9CA3AF] hover:text-[#1E1B4B] text-xl font-bold">x</button>
            </div>
            {preview.body && (
              <div className="bg-[#F5F3FF] rounded-xl p-4 text-sm whitespace-pre-wrap text-[#1E1B4B] mb-4 leading-relaxed">{preview.body}</div>
            )}
            {preview.reasoning && (
              <div className="bg-amber-50 rounded-xl p-3 text-xs text-amber-700 mb-4 whitespace-pre-wrap">{preview.reasoning}</div>
            )}
            {preview.status === "pending" && (
              <div className="flex gap-3">
                <button onClick={() => decide(preview.approval_id, "approved")} className="flex-1 py-2.5 bg-green-600 text-white rounded-xl font-bold hover:bg-green-700">Approve & Queue Send</button>
                <button onClick={() => decide(preview.approval_id, "rejected")} className="flex-1 py-2.5 bg-red-100 text-red-700 rounded-xl font-bold hover:bg-red-200">Reject</button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
