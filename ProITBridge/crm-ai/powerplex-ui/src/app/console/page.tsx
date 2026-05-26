"use client";
import { useState, useRef, useEffect } from "react";
import { sendChat, getCustomers, getStatus } from "@/lib/api";

const SUGGESTIONS = [
  "What problem is Divya Joshi having?",
  "Show open tickets sorted by priority",
  "How many customers bought AC?",
  "Check warranty status for Priya Sharma",
  "Recommend a product for premium customer",
  "How many technicians do we have?",
];

type Msg = { role: "user"|"assistant"; text: string; meta?: any };

export default function ConsolePage() {
  const [msgs, setMsgs]       = useState<Msg[]>([]);
  const [input, setInput]     = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus]   = useState<any>({});
  const [sessionId]           = useState("pp-" + Math.random().toString(36).slice(2,10));
  const bottomRef             = useRef<HTMLDivElement>(null);

  useEffect(() => { getStatus().then(setStatus).catch(() => {}); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  async function send(q?: string) {
    const query = q || input.trim();
    if (!query || loading) return;
    setInput("");
    setMsgs(m => [...m, { role: "user", text: query }]);
    setLoading(true);
    try {
      const d = await sendChat(query, sessionId);
      setMsgs(m => [...m, { role: "assistant", text: d.answer || "No response.", meta: d }]);
      if (d.mcts_decision) setStatus((s:any) => ({...s, last_mcts: d.mcts_decision, last_agent: d.agent_used}));
    } catch { setMsgs(m => [...m, { role: "assistant", text: "Server error. Please try again." }]); }
    setLoading(false);
  }

  return (
    <div className="flex h-full">
      {/* Chat area */}
      <div className="flex-1 flex flex-col">
        <div className="px-6 py-4 border-b border-[#DDD6FE] bg-white">
          <h1 className="font-bold text-[#1E1B4B] text-lg">AI Support Console</h1>
          <p className="text-xs text-[#9CA3AF]">5-RAG pipeline · AutoGen · CrewAI · MCTS · MCP context</p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {msgs.length === 0 && (
            <div className="text-center py-16">
              <div className="inline-block bg-[#EDE9FE] text-[#6C4FF8] text-xs font-bold px-4 py-1.5 rounded-full mb-4 uppercase tracking-widest">PowerPlex AI Engine</div>
              <h2 className="text-xl font-bold text-[#1E1B4B] mb-2">Ask anything — no customer selection needed</h2>
              <p className="text-sm text-[#9CA3AF] mb-6">Powered by Groq · Pinecone RAG · Neo4j Graph · MCTS decisions</p>
              <div className="flex flex-wrap gap-2 justify-center max-w-xl mx-auto">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => send(s)}
                    className="px-3 py-1.5 bg-white border border-[#DDD6FE] rounded-full text-xs text-[#4B5563] hover:border-[#6C4FF8] hover:text-[#6C4FF8] transition-all">{s}</button>
                ))}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[75%] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap leading-relaxed
                ${m.role === "user" ? "bg-[#6C4FF8] text-white rounded-br-sm" : "bg-white border border-[#E5E7EB] text-[#1E1B4B] rounded-bl-sm shadow-sm"}`}>
                {m.text}
                {m.meta && (
                  <div className="flex gap-1.5 flex-wrap mt-2">
                    {m.meta.intent     && <span className="text-[10px] bg-[#EDE9FE] text-[#6C4FF8] px-2 py-0.5 rounded-full font-medium">intent: {m.meta.intent}</span>}
                    {m.meta.mcts_decision && <span className="text-[10px] bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">mcts: {m.meta.mcts_decision}</span>}
                    {m.meta.agent_used && <span className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full font-medium">agent: {m.meta.agent_used}</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-[#E5E7EB] rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1">{[0,1,2].map(i=><span key={i} className="w-1.5 h-1.5 bg-[#9CA3AF] rounded-full animate-bounce" style={{animationDelay:`${i*0.15}s`}}/>)}</div>
              </div>
            </div>
          )}
          <div ref={bottomRef}/>
        </div>

        <div className="p-4 border-t border-[#DDD6FE] bg-white">
          <div className="flex gap-3">
            <input value={input} onChange={e=>setInput(e.target.value)}
              onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send();}}}
              placeholder="Ask about customers, tickets, warranties, recommendations..."
              className="flex-1 px-4 py-2.5 bg-[#F5F3FF] border border-[#DDD6FE] rounded-xl text-sm outline-none focus:border-[#6C4FF8] text-[#1E1B4B]"/>
            <button onClick={()=>send()} disabled={loading||!input.trim()}
              className="px-5 py-2.5 bg-[#6C4FF8] text-white rounded-xl text-sm font-semibold disabled:opacity-50 hover:bg-[#4E38C2] transition-all">Send</button>
          </div>
          <p className="text-[11px] text-[#9CA3AF] mt-2">Try: "What problem is Divya Joshi having?" · "Status of CUST003" · "How many open tickets?"</p>
        </div>
      </div>

      {/* AI Engine panel */}
      <div className="w-56 border-l border-[#DDD6FE] bg-white p-4 flex flex-col gap-4 overflow-y-auto">
        <div>
          <p className="text-[10px] font-bold text-[#6C4FF8] uppercase tracking-widest mb-2">AI Engine</p>
          <div className="space-y-1.5">
            {["Semantic","Hybrid","Agentic","Corrective","Graph"].map(r=>(
              <div key={r} className="flex justify-between items-center text-xs">
                <span className="text-[#4B5563]">{r} RAG</span>
                <span className="w-2 h-2 rounded-full bg-green-500"/>
              </div>
            ))}
          </div>
        </div>
        <div className="border-t border-[#EDE9FE] pt-3">
          <p className="text-[10px] font-bold text-[#9CA3AF] uppercase tracking-widest mb-2">Frameworks</p>
          {[
            {k:"AutoGen",  v: status.autogen  ? "Active" : "Not installed"},
            {k:"CrewAI",   v: status.crewai   ? "Active" : "Not installed"},
            {k:"MCTS",     v: "80 simulations"},
            {k:"MCP",      v: "Session active"},
            {k:"Groq LLM", v: status.groq     ? "Connected" : "Offline"},
          ].map(({k,v})=>(
            <div key={k} className="flex justify-between items-center text-xs mb-1.5">
              <span className="text-[#4B5563]">{k}</span>
              <span className={`text-[10px] font-semibold ${v.includes("Active")||v.includes("Connect")||v.includes("simul") ? "text-green-600":"text-[#9CA3AF]"}`}>{v}</span>
            </div>
          ))}
          {status.last_mcts && (
            <div className="mt-2 bg-amber-50 rounded-lg p-2">
              <p className="text-[9px] text-amber-600 font-bold uppercase">Last MCTS</p>
              <p className="text-xs text-amber-700 font-semibold">{status.last_mcts}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
