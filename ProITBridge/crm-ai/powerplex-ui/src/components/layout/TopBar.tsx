"use client";
import { useEffect, useState } from "react";
import { getStatus } from "@/lib/api";

const PILLS = [
  { label: "5x RAG",   cls: "bg-green-900/30 text-green-300  border-green-700/50" },
  { label: "AutoGen",  cls: "bg-amber-900/30 text-amber-300  border-amber-700/50" },
  { label: "CrewAI",   cls: "bg-red-900/30   text-red-300    border-red-700/50"   },
  { label: "MCTS",     cls: "bg-indigo-900/30 text-indigo-300 border-indigo-700/50"},
  { label: "MCP",      cls: "bg-white/10      text-white/80   border-white/30"    },
];

export function TopBar() {
  const [pending, setPending] = useState<number>(0);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    getStatus().then((s) => { setPending(s.pending_approvals || 0); setConnected(true); }).catch(() => {});
    const t = setInterval(() => {
      getStatus().then((s) => setPending(s.pending_approvals || 0)).catch(() => {});
    }, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <nav className="h-14 bg-gradient-to-r from-[#6C4FF8] to-[#4E38C2] flex items-center justify-between px-5 sticky top-0 z-50 shadow-lg">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 bg-white/20 border border-white/30 rounded-lg flex items-center justify-center font-black text-white text-base">P</div>
        <div>
          <div className="font-bold text-white text-sm leading-tight">PowerPlex</div>
          <div className="text-[10px] text-white/65">Enterprise Agentic CRM</div>
        </div>
      </div>

      <div className="flex gap-1.5">
        {PILLS.map((p) => (
          <span key={p.label} className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${p.cls}`}>{p.label}</span>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <span className="flex items-center gap-1.5 text-xs text-white/80">
          <span className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-amber-400 animate-pulse"}`}/>
          {connected ? "Connected" : "Connecting..."}
        </span>
        {pending > 0 && (
          <a href="/approvals" className="bg-red-500 text-white text-xs font-bold px-2.5 py-1 rounded-full animate-pulse">
            {pending} pending
          </a>
        )}
        <div className="bg-white/20 border border-white/30 px-3 py-1 rounded-full text-xs font-semibold text-white">Nivedita</div>
      </div>
    </nav>
  );
}
