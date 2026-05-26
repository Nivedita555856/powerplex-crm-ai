/* PowerPlex CRM — app.js */
// Auto-detect API base:
//   • On Render (backend serves frontend):   API = ""  → relative URLs
//   • On Vercel (static frontend + proxy):   API = ""  → vercel.json rewrites /api/* to Render
//   • Override via <meta name="api-base" content="https://..."> in index.html
const _metaBase = document.querySelector('meta[name="api-base"]');
const API = _metaBase ? _metaBase.getAttribute("content").replace(/\/$/, "") : "";
let allCustomers = [], allTickets = [], allTechnicians = [], allWarranties = [];
let currentCustomerId = null, sessionId = "session_" + Date.now();
let currentGlobalView = "chat", stageFilter = "", pendingModalItem = null;

const STAGES      = ["OPEN","UNDER_REVIEW","TECHNICIAN_PENDING","ASSIGNED","IN_PROGRESS","RESOLVED","CLOSED"];
const STAGE_SHORT = {"OPEN":"OP","UNDER_REVIEW":"UR","TECHNICIAN_PENDING":"TP","ASSIGNED":"AS","IN_PROGRESS":"IP","RESOLVED":"RS","CLOSED":"CL"};
const PRI_SHORT   = {"critical":"CR","high":"HI","medium":"ME","low":"LO"};
const PRIORITY_ORDER = {"critical":0,"high":1,"medium":2,"low":3};

// ── INIT ──────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  checkHealth();
  loadCustomers();
  loadStats();
  loadPendingBadge();
  setInterval(loadPendingBadge, 30000);
});

async function api(path, opts = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const r = await fetch(API + path, {
      headers: {"Content-Type": "application/json"},
      signal: controller.signal,
      ...opts
    });
    clearTimeout(timer);
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  } catch(e) {
    clearTimeout(timer);
    if (e.name === "AbortError") throw new Error("Request timed out — server took too long to respond.");
    throw e;
  }
}

// ── HEALTH ────────────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const d = await api("/api/health");
    const ok = d.status === "ok" || d.groq_connected;
    document.getElementById("statusDot").className  = "status-dot " + (ok ? "ok" : "err");
    document.getElementById("statusText").textContent = ok ? "Connected" : "AI Unavailable";
  } catch {
    document.getElementById("statusDot").className  = "status-dot err";
    document.getElementById("statusText").textContent = "Offline";
  }
}

function refreshAll() {
  checkHealth(); loadCustomers(); loadStats(); loadPendingBadge();
  if (currentGlobalView === "tickets")     loadAllTickets();
  if (currentGlobalView === "automation")  loadAutomation();
  if (currentGlobalView === "technicians") loadTechnicians();
}

// ── GLOBAL NAVIGATION ─────────────────────────────────────────────────────────
function switchGlobal(view) {
  currentGlobalView = view;
  document.querySelectorAll(".gtab").forEach(b => b.classList.remove("active"));
  document.getElementById("gtab-" + view)?.classList.add("active");
  document.querySelectorAll(".global-view").forEach(v => v.classList.remove("active"));
  document.getElementById("gview-" + view)?.classList.add("active");
  if (view === "tickets")     loadAllTickets();
  if (view === "automation")  loadAutomation();
  if (view === "technicians") loadTechnicians();
}

// ── CUSTOMERS ─────────────────────────────────────────────────────────────────
async function loadCustomers() {
  try {
    allCustomers = await api("/api/customers");
    renderCustomers(allCustomers);
    document.getElementById("custCount").textContent = allCustomers.length;
  } catch(e) { console.error(e); }
}

function renderCustomers(list) {
  const el = document.getElementById("customerList");
  if (!list.length) { el.innerHTML = '<div class="empty-state">No customers found</div>'; return; }
  el.innerHTML = list.map(c => {
    const seg = (c.segment || "Basic")[0]; // P / S / B
    return `<div class="customer-card ${c.customer_id===currentCustomerId?'active':''}"
         onclick="selectCustomer('${c.customer_id}')" aria-label="${c.name}">
      <div class="cc-name">${c.name}</div>
      <div class="cc-meta">
        <span class="cc-seg seg-${c.segment||'Basic'}" title="${c.segment||'Basic'}">${seg}</span>
        <span>${c.city||''}</span>
      </div>
    </div>`;
  }).join("");
}

function filterCustomers() {
  const q   = document.getElementById("customerSearch").value.toLowerCase();
  const seg = document.querySelector(".filter-btn.active")?.getAttribute("data-seg") || "all";
  let list  = allCustomers;
  if (seg && seg !== "all") list = list.filter(c => c.segment === seg);
  if (q) list = list.filter(c =>
    c.name?.toLowerCase().includes(q) || c.city?.toLowerCase().includes(q) || c.email?.toLowerCase().includes(q));
  renderCustomers(list);
}

function filterBySegment(seg, btn) {
  document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  btn.setAttribute("data-seg", seg);
  filterCustomers();
}

async function selectCustomer(id) {
  currentCustomerId = id;
  sessionId = "session_" + Date.now();
  renderCustomers(allCustomers);
  const c = allCustomers.find(x => x.customer_id === id);
  if (!c) return;

  const seg = c.segment || "Standard";
  const segColors = {
    Premium:  "background:var(--primary-light);color:var(--primary)",
    Standard: "background:var(--blue-bg);color:var(--blue)",
    Basic:    "background:#f3f4f6;color:#6b7280"
  };
  document.getElementById("customerHeader").innerHTML = `
    <div class="ch-loaded">
      <span class="ch-name">${c.name}</span>
      <span class="ch-id">${c.customer_id}</span>
      <span class="ch-tag" style="${segColors[seg]||''}">${seg[0]}</span>
      ${c.city ? `<span style="font-size:12px;color:var(--text-sub)">${c.city}</span>` : ""}
    </div>`;

  document.querySelectorAll(".cust-tab").forEach(b => b.setAttribute("data-unlocked","1"));
  if (currentGlobalView !== "chat") switchGlobal("chat");
  switchTab("chat", document.querySelector(".tab-btn.active") || document.querySelector(".tab-btn"));
  renderCustomerDetails(c);
  renderWarranty(id);
  showToast(`${c.name} loaded`);
}

// ── TABS ──────────────────────────────────────────────────────────────────────
function switchTab(tab, btn) {
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  const el = document.getElementById("tab-" + tab);
  if (el) el.classList.add("active");
  if (btn) btn.classList.add("active");
  else document.querySelectorAll(".tab-btn").forEach(b => {
    if (b.getAttribute("onclick")?.includes(`'${tab}'`)) b.classList.add("active");
  });
}

// ── CUSTOMER DETAILS ──────────────────────────────────────────────────────────
function renderCustomerDetails(c) {
  document.getElementById("customerDetails").innerHTML = `
    <div class="profile-card">
      <h4>Profile</h4>
      ${row("ID", c.customer_id)} ${row("Name", c.name)} ${row("Segment", c.segment||"-")}
      ${row("City", c.city||"-")} ${row("Email", c.email||"-")} ${row("Phone", c.phone||"-")}
      ${row("Since", c.created_at ? new Date(c.created_at).toLocaleDateString() : "-")}
    </div>`;
}

// ── WARRANTY ──────────────────────────────────────────────────────────────────
async function renderWarranty(custId) {
  const el = document.getElementById("warrantyPanel");
  try {
    const ws = await api(`/api/warranties?customer_id=${custId}`);
    if (!ws.length) { el.innerHTML = '<div class="empty-state">No warranty records</div>'; return; }
    el.innerHTML = ws.map(w => {
      const days = w.end_date ? Math.round((new Date(w.end_date)-Date.now())/86400000) : null;
      const sc   = w.status==="Active" ? "w-active" : w.status==="Expired" ? "w-expired" : "w-pending";
      return `<div class="profile-card">
        <h4>${w.warranty_id}</h4>
        ${row("Appliance", w.appliance_id||"-")}
        ${row("Status", `<span class="warranty-badge ${sc}">${w.status}</span>`)}
        ${row("Start", w.start_date||"-")} ${row("Expires", w.end_date||"-")}
        ${days!==null ? row("Days left", days>0 ? `<strong style="color:${days<30?'var(--red)':'var(--green)'}">${days}</strong>` : '<span style="color:var(--red)">Expired</span>') : ""}
      </div>`;
    }).join("");
  } catch { el.innerHTML = '<div class="empty-state">Could not load warranty data</div>'; }
}

function row(k, v) {
  return `<div class="profile-row"><span class="profile-key">${k}</span><span class="profile-val">${v}</span></div>`;
}

// ── RECOMMENDATIONS ───────────────────────────────────────────────────────────
async function getRecommendations() {
  if (!currentCustomerId) { showToast("Select a customer first"); return; }
  const q = document.getElementById("recQuery").value;
  const resultEl = document.getElementById("recommendResult");
  document.getElementById("recEngineNote").textContent = "";
  resultEl.innerHTML = '<div style="color:var(--text-muted);font-size:13px">Generating...</div>';
  try {
    const d = await api("/api/chat", {method:"POST", body: JSON.stringify({
      query: q || `Recommend the best appliance for ${allCustomers.find(c=>c.customer_id===currentCustomerId)?.name}`,
      customer_id: currentCustomerId, session_id: sessionId
    })});
    document.getElementById("recEngineNote").textContent = d.agent_engine ? `Engine: ${d.agent_engine}` : "";
    resultEl.innerHTML = `<div class="rec-answer">${d.answer}</div>`;
  } catch(e) {
    resultEl.innerHTML = `<div class="rec-answer" style="color:var(--red)">Error: ${e.message}</div>`;
  }
}

// ── CREATE TICKET ─────────────────────────────────────────────────────────────
async function createTicket() {
  const issue = document.getElementById("newTicketIssue").value.trim();
  const pri   = document.getElementById("ticketPriority").value;
  if (!issue) { showToast("Describe the issue first"); return; }
  const resultEl = document.getElementById("ticketCreateResult");
  try {
    const body = { issue_description: issue, priority: pri };
    if (currentCustomerId) body.customer_id = currentCustomerId;
    const d = await api("/api/tickets", {method:"POST", body: JSON.stringify(body)});
    resultEl.innerHTML = `<div style="color:var(--green);font-size:13px">Created: ${d.ticket_id||"OK"}</div>`;
    document.getElementById("newTicketIssue").value = "";
    loadAllTickets(); loadStats();
    showToast("Ticket created");
  } catch(e) {
    resultEl.innerHTML = `<div style="color:var(--red);font-size:13px">Error: ${e.message}</div>`;
  }
}

// ── ALL TICKETS ───────────────────────────────────────────────────────────────
async function loadAllTickets() {
  try {
    allTickets = await api("/api/tickets");
    buildStageStrip();
    renderTickets();
  } catch { document.getElementById("ticketsFeed").innerHTML = '<div class="empty-state">Could not load tickets</div>'; }
}

function buildStageStrip() {
  const counts = {};
  STAGES.forEach(s => counts[s] = allTickets.filter(t => t.status === s).length);
  document.getElementById("stageStrip").innerHTML = STAGES.map(s => `
    <div class="stage-pill ${stageFilter===s?'active':''}" onclick="toggleStageFilter('${s}')" aria-label="${s}">
      <div class="sp-count">${counts[s]}</div>
      <div class="sp-label">${STAGE_SHORT[s]||s}</div>
    </div>`).join("");
}

function toggleStageFilter(s) {
  stageFilter = stageFilter === s ? "" : s;
  document.getElementById("ticketStageFilter").value = stageFilter;
  buildStageStrip(); renderTickets();
}

function filterTickets() {
  stageFilter = document.getElementById("ticketStageFilter").value;
  buildStageStrip(); renderTickets();
}

// Priority customers always float to top
const PRIORITY_CUSTOMERS = ["CUST001","CUST002"];
const PRI_SCORE = {critical:4, high:3, medium:2, low:1};

function renderTickets() {
  const search = document.getElementById("ticketSearch")?.value.toLowerCase() || "";
  const priF   = document.getElementById("ticketPriFilter")?.value.toLowerCase() || "";
  let list = allTickets;
  if (stageFilter) list = list.filter(t => t.status === stageFilter);
  if (priF)        list = list.filter(t => (t.priority||"").toLowerCase() === priF);
  if (search) list = list.filter(t =>
    t.ticket_id?.toLowerCase().includes(search) ||
    t.issue_description?.toLowerCase().includes(search) ||
    (allCustomers.find(c=>c.customer_id===t.customer_id)?.name||"").toLowerCase().includes(search));

  // Sort: priority customers first → OPEN/routable → priority score → ticket id
  const ROUTE_STATUS = ["OPEN","UNDER_REVIEW","TECHNICIAN_PENDING"];
  list = [...list].sort((a, b) => {
    const aPri  = PRIORITY_CUSTOMERS.includes(a.customer_id) ? 1 : 0;
    const bPri  = PRIORITY_CUSTOMERS.includes(b.customer_id) ? 1 : 0;
    if (bPri !== aPri) return bPri - aPri;
    const aRoute = ROUTE_STATUS.includes(a.status) ? 1 : 0;
    const bRoute = ROUTE_STATUS.includes(b.status) ? 1 : 0;
    if (bRoute !== aRoute) return bRoute - aRoute;
    const aScore = PRI_SCORE[(a.priority||"").toLowerCase()] || 0;
    const bScore = PRI_SCORE[(b.priority||"").toLowerCase()] || 0;
    if (bScore !== aScore) return bScore - aScore;
    return a.ticket_id < b.ticket_id ? -1 : 1;
  });

  const el = document.getElementById("ticketsFeed");
  if (!list.length) { el.innerHTML = '<div class="empty-state">No tickets match filters</div>'; return; }
  el.innerHTML = list.map(t => buildTicketCard(t)).join("");
}

function buildTicketCard(t) {
  const cust = allCustomers.find(c => c.customer_id === t.customer_id);
  const tech = allTechnicians.find(x => x.technician_id === (t.assigned_technician || t.technician_id));
  const pri  = (t.priority || "medium").toLowerCase();
  const showRoute = ["OPEN","UNDER_REVIEW","TECHNICIAN_PENDING"].includes(t.status);
  const priShort  = PRI_SHORT[pri] || pri.slice(0,2).toUpperCase();
  const stgDot    = `<span class="status-dot-sm sd-${t.status||'OPEN'}" title="${t.status||'OPEN'}"></span>`;
  const desc = t.issue_description || t.issue || "";
  const isPriCust = PRIORITY_CUSTOMERS.includes(t.customer_id);
  const priCustBadge = "";
  return `
    <div class="ticket-card ${isPriCust ? 'ticket-card-priority' : ''}" id="tc-${t.ticket_id}">
      <div class="tc-top">
        <div class="tc-left">
          <div class="tc-badges">
            <span class="tc-id">${t.ticket_id}</span>
            ${stgDot}
            <span class="pri-short pri-${pri}" title="${t.priority}">${priShort}</span>
          </div>
          ${desc ? `<div class="tc-desc">${desc}</div>` : ""}
          <div class="tc-meta">
            ${cust ? `<span>${cust.name}</span>` : ""}
            ${t.appliance_id ? `<span>· ${t.appliance_id}</span>` : ""}
            ${t.created_at  ? `<span>· ${new Date(t.created_at).toLocaleDateString()}</span>` : ""}
            ${tech ? `<span class="tc-tech">· ${tech.name}</span>` : ""}
          </div>
        </div>
        <div class="tc-actions">
          <select class="form-select sm" onchange="updateStatus('${t.ticket_id}', this.value)" aria-label="Status">
            ${STAGES.map(s => `<option ${s===t.status?'selected':''} value="${s}">${STAGE_SHORT[s]||s}</option>`).join("")}
          </select>
          ${showRoute ? `<button class="btn-primary btn-sm btn-route" onclick="routeTicket('${t.ticket_id}')">&#8594; Route</button>` : `<span class="tc-tech-badge">${tech ? tech.name.split(" ")[0] : ""}</span>`}
        </div>
      </div>
      <div id="tc-msg-${t.ticket_id}"></div>
      <div id="tc-route-${t.ticket_id}"></div>
    </div>`;
}

async function updateStatus(ticketId, status) {
  try {
    await api(`/api/tickets/${ticketId}/status`, {method:"PATCH", body: JSON.stringify({status})});
    const el = document.getElementById(`tc-msg-${ticketId}`);
    if (el) { el.innerHTML = `<div class="tc-status-msg">${STAGE_SHORT[status]||status}</div>`; }
    setTimeout(() => { const e = document.getElementById(`tc-msg-${ticketId}`); if(e) e.innerHTML=""; }, 2000);
    loadStats();
  } catch(e) { showToast("Error: " + e.message); }
}

async function routeTicket(ticketId) {
  const btn = document.querySelector(`#tc-${ticketId} .btn-route`);
  if (btn) { btn.disabled = true; btn.textContent = "Routing..."; }
  const el = document.getElementById(`tc-route-${ticketId}`);
  el.innerHTML = `<div class="tc-route-loading">Finding best technician match...</div>`;
  try {
    const r   = await api(`/api/tickets/${ticketId}/route-technician`, {method:"POST", body:"{}"}, 45000);
    const rec       = r.recommendation?.recommended_technician || r.recommended_technician;
    const matchPct  = r.match_pct  || (r.score ? Math.round(r.score * 100) : null);
    const matchLabel= r.match_label || "";
    const draft     = r.email_draft;

    if (rec) {
      const draftHtml = draft ? `
        <div class="email-draft-box" id="draft-${ticketId}">
          <div class="draft-header">
            <span class="draft-label">RAG Email Draft</span>
            <span class="draft-to">To: ${draft.to}</span>
          </div>
          <div class="draft-subject"><strong>Subject:</strong> ${draft.subject}</div>
          <div class="draft-body">${draft.body.replace(/\n/g,'<br>')}</div>
          <div class="draft-actions">
            <button class="btn-send-email" onclick="sendEmailNow('${ticketId}','${draft.to}',this)">
              Send Email to Customer
            </button>
            <span class="draft-note">Admin gets a BCC copy</span>
          </div>
          ${draft.docs_used && draft.docs_used.length ? `
          <div class="draft-sources">
            <span class="draft-sources-label">Sources used</span>
            ${draft.docs_used.map(d => `<span class="draft-source-tag">${d.replace(/_/g,' ').replace('.txt','')}</span>`).join("")}
            ${draft.ai_enhanced ? '<span class="draft-ai-tag">AI-generated</span>' : '<span class="draft-ai-tag draft-ai-template">Template</span>'}
          </div>` : ''}
        </div>` : "";

      el.innerHTML = `
        <div class="tc-route-result">
          <div class="tc-route-header"><span class="tc-route-icon">&#10003;</span> Best match found</div>
          <div class="tc-route-tech">
            <strong>${rec.name}</strong>
            <span class="tc-route-spec">${rec.specialization || ""}</span>
            <span class="tc-route-id">ID: ${rec.technician_id || ""}</span>
            ${matchPct ? `<span class="tc-route-score">${matchPct}% match</span>${matchLabel ? ` <span class="tc-route-match-label">${matchLabel}</span>` : ""}` : ""}
          </div>
          <div class="tc-route-meta">
            ${rec.city ? `<span>${rec.city}</span>` : ""}
            ${rec.rating ? `<span>Rating: ${rec.rating}</span>` : ""}
            ${rec.active_tickets != null ? `<span>${rec.active_tickets} active tickets</span>` : ""}
          </div>
          <div class="tc-route-actions">
            <button class="btn-primary btn-sm" onclick="confirmAssign('${ticketId}','${rec.technician_id}','${rec.name}',this)">
              Confirm Assignment
            </button>
          </div>
          ${draftHtml}
        </div>`;
    } else {
      el.innerHTML = `<div class="tc-route-result tc-route-warn">No technician available at this time.</div>`;
    }
    loadStats();
  } catch(e) {
    el.innerHTML = `<div class="tc-route-result tc-route-err">Error: ${e.message}</div>`;
  }
  if (btn) { btn.disabled = false; btn.textContent = "Route"; }
}

async function confirmAssign(ticketId, techId, techName, btn) {
  btn.disabled = true; btn.textContent = "Assigning...";
  try {
    await api(`/api/tickets/${ticketId}/status`, {method:"PATCH", body: JSON.stringify({status:"ASSIGNED"})});
    btn.textContent = "Assigned";
    btn.style.background = "var(--green)";
    showToast(`${ticketId} assigned to ${techName}`);
    loadStats();
  } catch(e) {
    btn.disabled = false; btn.textContent = "Confirm Assignment";
    showToast("Assignment failed: " + e.message);
  }
}

async function sendEmailNow(ticketId, toEmail, btn) {
  const draftBox = document.getElementById(`draft-${ticketId}`);
  const subject  = draftBox.querySelector(".draft-subject").textContent.replace("Subject: ","").trim();
  const body     = draftBox.querySelector(".draft-body").innerText;
  btn.disabled = true; btn.textContent = "Sending...";
  try {
    const r = await api("/api/send-email", {
      method:"POST",
      body: JSON.stringify({to: toEmail, subject, body})
    }, 30000);
    if (r.skipped) {
      btn.textContent = "Display-only customer";
      btn.style.background = "#6b7280";
    } else {
      btn.textContent = "Sent!";
      btn.style.background = "var(--green)";
      showToast("Email sent to " + toEmail);
    }
  } catch(e) {
    btn.disabled = false; btn.textContent = "Retry Send";
    showToast("Send failed: " + e.message);
  }
}

// ── AUTOMATION ────────────────────────────────────────────────────────────────
async function loadAutomation() { loadApprovalQueue(); }

async function processGmail() {
  const btn = document.getElementById("gmailBtn");
  btn.disabled = true; btn.textContent = "...";
  const result = document.getElementById("gmailResult");
  result.style.display = "none";
  try {
    const d = await api("/api/gmail/process", {method:"POST"});
    result.className = "auto-result ok";
    result.innerHTML = `${d.processed||0} emails &nbsp; ${d.tickets_created||0} tickets`;
    result.style.display = "block";
    loadPendingBadge(); loadApprovalQueue(); loadStats();
    showToast("Processed");
  } catch(e) {
    result.className = "auto-result err";
    result.innerHTML = e.message;
    result.style.display = "block";
  }
  btn.disabled = false; btn.textContent = "Inbox";
}

async function triggerWebhook(type) {
  const log = document.getElementById("webhookLog");
  const ts  = new Date().toLocaleTimeString();
  const ep  = type === "n8n" ? "/api/webhook/n8n" : "/api/webhook/make";
  log.querySelector(".log-empty")?.remove();
  const line = document.createElement("div");
  line.className = "log-line";
  line.textContent = `${ts} ${type.toUpperCase()} ...`;
  log.prepend(line);
  // keep only 5 log lines
  Array.from(log.querySelectorAll(".log-line")).slice(5).forEach(l => l.remove());
  try {
    const d = await api(ep, {method:"POST", body: JSON.stringify({
      query: "webhook test ping from PowerPlex UI",
      source: "powerplex-ui",
      customer_id: currentCustomerId || null,
    })});
    line.textContent = `${ts} ${type.toUpperCase()} OK`;
    line.style.color = "#4ade80";
  } catch(e) {
    line.textContent = `${ts} ${type.toUpperCase()} ERR`;
    line.style.color = "#f87171";
  }
}

async function loadApprovalQueue() {
  const el      = document.getElementById("approvalQueue");
  const countEl = document.getElementById("approvalCount");
  try {
    const [newItems, legacyItems] = await Promise.all([
      api("/api/approvals/all?status=pending"),
      api("/api/approvals").catch(() => [])
    ]);
    const seen = new Set(newItems.map(i => i.approval_id));
    const all  = [...newItems, ...legacyItems.filter(l => !seen.has(l.approval_id) && l.status==="pending")];
    countEl.textContent = `${all.length} pending`;
    document.getElementById("statPending").textContent = all.length;
    if (!all.length) { el.innerHTML = '<div class="empty-state-sm">No pending approvals</div>'; return; }
    const isLegacyFn = item => !seen.has(item.approval_id);
    el.innerHTML = all.map(item => `
      <div class="approval-item">
        <div class="ai-left">
          <div class="ai-type">${(item.action_type||"action").replace(/_/g," ")}</div>
          <div class="ai-subject">${item.subject||item.description||"Pending"}</div>
          <div class="ai-meta">${item.to_email?"To: "+item.to_email:""} ${item.created_at?"· "+new Date(item.created_at).toLocaleTimeString():""}</div>
        </div>
        <div class="ai-actions">
          ${item.body||item.email_body ? `<button class="btn-preview" onclick='previewApproval(${JSON.stringify(item).replace(/'/g,"&#39;")}, ${isLegacyFn(item)})'>View</button>` : ""}
          <button class="btn-approve" onclick="decideApproval('${item.approval_id}','approved',${isLegacyFn(item)})">OK</button>
          <button class="btn-reject"  onclick="decideApproval('${item.approval_id}','rejected',${isLegacyFn(item)})">No</button>
        </div>
      </div>`).join("");
  } catch { el.innerHTML = '<div class="empty-state-sm">Error loading approvals</div>'; }
}

function previewApproval(item, isLegacy) {
  pendingModalItem = {item, isLegacy};
  document.getElementById("modalTitle").textContent = item.subject || "Email Preview";
  document.getElementById("modalBody").textContent  = item.body || item.email_body || JSON.stringify(item, null, 2);
  document.getElementById("modalApprove").onclick = () => decideApproval(item.approval_id, "approved", isLegacy, true);
  document.getElementById("modalReject").onclick  = () => decideApproval(item.approval_id, "rejected", isLegacy, true);
  document.getElementById("emailModal").classList.add("open");
}

function closeModal(e) {
  if (e.target.id === "emailModal") document.getElementById("emailModal").classList.remove("open");
}

async function decideApproval(id, decision, isLegacy, fromModal=false) {
  try {
    if (isLegacy) {
      await api("/api/approvals/process", {method:"POST", body: JSON.stringify({approval_id:id, decision})});
    } else {
      await api(`/api/approvals/${id}/decide`, {method:"POST", body: JSON.stringify({decision, decided_by:"admin"})});
    }
    if (fromModal) document.getElementById("emailModal").classList.remove("open");
    showToast(decision === "approved" ? "Approved" : "Rejected");
    loadApprovalQueue(); loadPendingBadge();
  } catch(e) { showToast("Error: " + e.message); }
}

async function loadPendingBadge() {
  try {
    const items = await api("/api/approvals/all?status=pending");
    const n = items.length;
    const badge = document.getElementById("pendingBadge");
    if (badge) { badge.textContent = n; badge.style.display = n>0 ? "inline-block" : "none"; }
    const stat = document.getElementById("statPending");
    if (stat) stat.textContent = n;
  } catch {}
}

// ── TECHNICIANS ───────────────────────────────────────────────────────────────
async function loadTechnicians() {
  const el = document.getElementById("techCards");
  try {
    allTechnicians = await api("/api/technicians");
    if (!allTickets.length) allTickets = await api("/api/tickets");
    if (!allTechnicians.length) { el.innerHTML = '<div class="empty-state">No technicians found</div>'; return; }
    el.innerHTML = allTechnicians.map(t => {
      // Normalise specialization: may be pipe-separated string or array
      const specRaw = t.specializations || t.specialization || "";
      const specs   = typeof specRaw === "string" ? specRaw.split("|").filter(Boolean) : specRaw;
      // Normalise technician_id field for ticket matching
      const tid = t.technician_id;
      const active = allTickets.filter(tk =>
        (tk.assigned_technician || tk.technician_id) === tid &&
        !["RESOLVED","CLOSED"].includes(tk.status)).length;
      const done = allTickets.filter(tk =>
        (tk.assigned_technician || tk.technician_id) === tid &&
        ["RESOLVED","CLOSED"].includes(tk.status)).length;
      const rating = parseFloat(t.rating) || 0;
      const rCls   = rating >= 4.5 ? "rating-good" : rating >= 3.5 ? "rating-mid" : "rating-low";
      const av     = t.availability_status || "Available";
      return `<div class="tech-card">
        <div class="tech-card-top">
          <div>
            <div class="tech-name">${t.name}</div>
            <div class="tech-id">${t.technician_id}</div>
          </div>
          <div class="tech-rating ${rCls}">${rating.toFixed(1)}</div>
        </div>
        <div style="margin-bottom:8px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
          <span class="avail-badge avail-${av}">${av}</span>
          ${t.city ? `<span style="font-size:11px;color:var(--text-muted)">${t.city}</span>` : ""}
        </div>
        <div class="tech-specs">${specs.map(s=>`<span class="spec-tag">${s}</span>`).join("")}</div>
        <div class="tech-stats">
          <div class="ts-item"><div class="ts-val">${active}</div><div class="ts-label">active</div></div>
          <div class="ts-item"><div class="ts-val" style="color:var(--green)">${done}</div><div class="ts-label">done</div></div>
          ${t.experience_years ? `<div class="ts-item"><div class="ts-val" style="color:var(--text-sub)">${t.experience_years}</div><div class="ts-label">yrs</div></div>` : ""}
        </div>
      </div>`;
    }).join("");
  } catch(e) { el.innerHTML = `<div class="empty-state">Could not load technicians: ${e.message}</div>`; }
}

async function routeTicketFromPanel() {
  const ticketId = document.getElementById("routeTicketId").value.trim();
  if (!ticketId) { showToast("Enter a ticket ID"); return; }
  const resultEl = document.getElementById("routeResult");
  resultEl.innerHTML = '<div style="color:var(--text-muted);font-size:13px">Routing...</div>';
  try {
    const r     = await api(`/api/tickets/${ticketId}/route-technician`, {method:"POST", body:"{}"});
    const rec   = r.recommendation?.recommended_technician;
    const score = r.recommendation?.score;
    const pct   = score ? Math.round(score * 100) + "%" : "-";
    resultEl.innerHTML = `<div class="route-result-box">
      <strong>${rec?.name||"-"}</strong> — ${pct}<br/>
      <a href="#" onclick="switchGlobal('automation')">Review</a>
    </div>`;
    loadPendingBadge();
  } catch(e) {
    resultEl.innerHTML = `<div class="route-result-box err">Error: ${e.message}</div>`;
  }
}

// ── STATS ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const d = await api("/api/stats");
    document.getElementById("statCustomers").textContent = d.total_customers || "-";
    document.getElementById("statLeads").textContent     = d.total_leads     || "-";
    document.getElementById("statTickets").textContent   = d.open_tickets    || "-";
  } catch {}
}

// ── CHAT ──────────────────────────────────────────────────────────────────────
function autoResize(ta) {
  ta.style.height = "auto";
  ta.style.height = Math.min(ta.scrollHeight, 140) + "px";
}

function handleChatKey(e) {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}


function appendTyping() {
  const el  = document.getElementById("chatMessages");
  const div = document.createElement("div");
  const id  = "typing_" + Date.now();
  div.id = id;
  div.className = "msg bot";
  div.innerHTML = '<div class="msg-bubble typing-bubble"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>';
  el.appendChild(div);
  el.scrollTop = el.scrollHeight;
  return id;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

async function sendMessage() {
  const ta    = document.getElementById("chatInput");
  const query = ta.value.trim();
  if (!query) return;
  ta.value = ""; autoResize(ta);
  appendMsg("user", query);
  const typingId = appendTyping();
  document.getElementById("sendBtn").disabled = true;
  try {
    const d = await api("/api/chat", {method:"POST", body: JSON.stringify({
      query, customer_id: currentCustomerId || null, session_id: sessionId
    })}, 45000);
    removeTyping(typingId);
    appendMsg("bot", d.answer, d.intent, d.agent_used);
  } catch(e) {
    removeTyping(typingId);
    appendMsg("bot", "Error: " + e.message);
  }
  document.getElementById("sendBtn").disabled = false;
}

function appendMsg(role, text, intent, agent) {
  const el  = document.getElementById("chatMessages");
  const div = document.createElement("div");
  div.className = `msg ${role}`;

  // Global analysis table card
  if (role === "bot" && text?.includes("GLOBAL_TABLE_START")) {
    div.innerHTML = renderGlobalTable(text);
    el.appendChild(div); el.scrollTop = el.scrollHeight; return div;
  }

  // Delay analysis card
  if (role === "bot" && text?.includes("DELAY_ANALYSIS_START")) {
    div.innerHTML = renderDelayCard(text);
    el.appendChild(div); el.scrollTop = el.scrollHeight; return div;
  }

  // Email draft card
  if (role === "bot" && text?.includes("EMAIL_DRAFT_START")) {
    const inner   = text.match(/EMAIL_DRAFT_START\n([\s\S]*?)EMAIL_DRAFT_END/);
    const payload = inner ? inner[1] : text;
    const lines   = payload.split("\n");
    const meta    = {}; let bodyLines = [], sep = 0;
    for (const ln of lines) {
      if (ln.startsWith("label:"))    { meta.label    = ln.slice(6); continue; }
      if (ln.startsWith("to:"))       { meta.to       = ln.slice(3); continue; }
      if (ln.startsWith("subject:"))  { meta.subject  = ln.slice(8); continue; }
      if (ln.startsWith("approval:")) { meta.approval = ln.slice(9).trim(); continue; }
      if (ln.startsWith("─")) { sep++; if (sep > 1) break; continue; }
      if (sep === 1) bodyLines.push(ln);
    }
    const body = bodyLines.join("\n");
    div.innerHTML = `<div class="email-card">
      <div class="email-card-head">
        <span class="email-card-label">${meta.label||"Email Draft"}</span>
        ${meta.approval ? `<span class="email-badge">Queued</span>` : ""}
      </div>
      <div class="email-card-row"><span class="ek">To</span><span class="ev">${meta.to||"-"}</span></div>
      <div class="email-card-row"><span class="ek">Subject</span><span class="ev"><strong>${meta.subject||"-"}</strong></span></div>
      <div class="email-body-preview">${body.replace(/\n/g,"<br>")}</div>
      ${meta.approval ? `<div class="email-card-actions">
        <button class="btn-approve-sm" onclick="quickApprove('${meta.approval}')">Approve</button>
        <button class="btn-reject-sm"  onclick="quickReject('${meta.approval}')">Reject</button>
        <button class="btn-view-sm"    onclick="switchGlobal('automation')">View</button>
      </div>` : ""}
    </div>`;
    el.appendChild(div); el.scrollTop = el.scrollHeight; return div;
  }

  // Normal message
  const formatted = role === "bot" ? formatBotText(text) : escapeHtml(text);
  const metaRow   = role === "bot" && (intent || agent) ?
    `<div class="msg-meta">${intent?`<span class="meta-agent">${intent}</span>`:""}${agent?`<span class="meta-agent">${agent}</span>`:""}</div>` : "";
  div.innerHTML = `<div class="msg-bubble">${formatted}</div>${metaRow}`;
  el.appendChild(div); el.scrollTop = el.scrollHeight; return div;
}

async function quickApprove(id) {
  try { await api(`/api/approvals/${id}/decide`, {method:"POST", body: JSON.stringify({decision:"approved", decided_by:"admin"})}); showToast("Approved"); loadPendingBadge(); } catch(e) { showToast("Error: "+e.message); }
}
async function quickReject(id) {
  try { await api(`/api/approvals/${id}/decide`, {method:"POST", body: JSON.stringify({decision:"rejected", decided_by:"admin"})}); showToast("Rejected"); loadPendingBadge(); } catch(e) { showToast("Error: "+e.message); }
}

function escapeHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function formatBotText(text) {
  return escapeHtml(text).replace(/\n/g,"<br>")
    .replace(/(TKT[\w-]+)/g,'<span class="mono-tag">$1</span>')
    .replace(/(CUST\d{3})/g,'<span class="mono-tag">$1</span>')
    .replace(/(APR-[\w]+)/g, '<span class="mono-tag">$1</span>');
}

// ── GLOBAL TABLE CARD ─────────────────────────────────────────────────────────
function renderGlobalTable(text) {
  const inner = text.match(/GLOBAL_TABLE_START\n([\s\S]*?)GLOBAL_TABLE_END/);
  if (!inner) return `<div class="msg-bubble">${formatBotText(text)}</div>`;
  const payload = inner[1];
  let title = "Issues", count = "";
  const rows = [];
  for (const line of payload.split("\n")) {
    if (line.startsWith("title:")) { title = line.slice(6); continue; }
    if (line.startsWith("count:")) { count = line.slice(6); continue; }
    if (line.trim()) rows.push(line);
  }
  const afterEnd = text.split("GLOBAL_TABLE_END\n")[1] || "";

  const rowsHtml = rows.map(r => {
    const parts  = r.replace(/^([\u{1F534}\u{1F7E0}\u{1F7E1}\u{1F7E2}⚪])\s*/u, "").split(" | ");
    const custId = parts[0]?.trim() || "";
    const name   = parts[1]?.trim() || "";
    const issue  = parts[2]?.trim() || "";
    const priRaw = (parts[3]?.trim() || "").toLowerCase().replace(/\s+.*$/,"");
    const days   = parts[4]?.trim() || "";
    const priShort = PRI_SHORT[priRaw] || priRaw.slice(0,2).toUpperCase();
    return `<tr class="gt-row" onclick="filterChatByCustomer('${custId}')">
      <td class="gt-id"><span class="mono-tag">${custId}</span></td>
      <td class="gt-name">${name}</td>
      <td class="gt-issue">${issue}</td>
      <td><span class="pri-short pri-${priRaw}">${priShort}</span></td>
      <td class="gt-days">${days}</td>
    </tr>`;
  }).join("");

  const patternMatch = afterEnd.match(/Pattern summary[\s\S]*?(?=\n\n|$)/);
  const groqMatch    = afterEnd.match(/AI insight:\s*([\s\S]+?)(?=\n\n|$)/);

  return `<div class="global-table-card">
    <div class="gtc-head">
      <span class="gtc-title">${title}</span>
      ${count ? `<span class="gtc-count">${count}</span>` : ""}
    </div>
    <div class="gtc-body">
      <table class="global-table">
        <thead><tr><th>ID</th><th>Name</th><th>Issue</th><th>Pri</th><th>Open</th></tr></thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
    ${patternMatch ? `<div class="pattern-box">${escapeHtml(patternMatch[0]).replace(/\n/g,"<br>")}</div>` : ""}
    ${groqMatch    ? `<div class="ai-insight">${escapeHtml(groqMatch[1])}</div>` : ""}
  </div>`;
}

function filterChatByCustomer(custId) {
  if (custId) selectCustomer(custId);
}

// ── DELAY CARD ────────────────────────────────────────────────────────────────
f