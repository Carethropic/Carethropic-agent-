const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" });
const label = (s) => String(s || "").replace(/_/g, " ");

let state = { result: null, tab: "overview", file: null, authorities: {} };

async function init() {
  const st = await fetch("/api/status").then((r) => r.json());
  const chip = $("#modeChip");
  chip.textContent = st.live ? `Live · ${st.model}` : "Replay mode · add API key for live";
  chip.className = "chip " + (st.live ? "chip-live" : "chip-warn");
  await loadQueue();
  $("#tabs").addEventListener("click", (e) => { if (e.target.dataset.tab) { state.tab = e.target.dataset.tab; renderTabs(); } });
  const drop = $("#drop"), fi = $("#fileInput");
  drop.addEventListener("click", () => fi.click());
  fi.addEventListener("change", () => setFile(fi.files[0]));
  drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("has"); });
  drop.addEventListener("drop", (e) => { e.preventDefault(); setFile(e.dataTransfer.files[0]); });
  $("#analyzeNew").addEventListener("click", runNew);
}

function setFile(f) {
  if (!f) return;
  state.file = f;
  $("#drop").classList.add("has");
  $("#dropText").textContent = f.name;
}

async function loadQueue() {
  const items = await fetch("/api/samples").then((r) => r.json());
  $("#queue").innerHTML = items.map((s) => {
    const d = s.next_deadline;
    const sev = d ? (d.severity === "critical" ? "chip-red" : d.severity === "high" ? "chip-warn" : "") : "";
    const when = d ? (d.days_left <= 0 ? "Act today" : `${d.days_left} days`) : "No deadline";
    return `<button class="qcard" data-id="${s.id}">
      <div class="qrow"><span class="qname">${esc(s.client.display_name)}</span><span class="chip ${sev} count">${when}</span></div>
      <div class="qtitle">${esc(s.title)}</div>
      <div class="qrow"><span class="chip">${esc(s.client.preferred_language)}</span>
      ${s.review_status === "needs_human_expert" ? '<span class="chip chip-red">Escalate</span>' : '<span class="chip chip-live">Navigator ready</span>'}
      ${s.simulated ? '<span class="chip">2027 rule</span>' : ""}</div>
    </button>`;
  }).join("");
  document.querySelectorAll(".qcard").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".qcard").forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    const s = items.find((i) => i.id === b.dataset.id);
    startCase({ sampleId: s.id, image: s.image, name: s.client.display_name, title: s.title, simulated: s.simulated, asOf: s.as_of });
  }));
}

function runNew() {
  const kids = $("#cKids").value.split(",").map((x) => parseInt(x.trim(), 10)).filter((x) => !isNaN(x));
  const client = {
    display_name: $("#cName").value || "New client",
    preferred_language: $("#cLang").value,
    pregnant: $("#cPreg").checked,
    pregnancy_end_date: $("#cBirth").value || null,
    children_ages: kids,
    disability_or_medically_frail: $("#cFrail").checked,
    meets_calfresh_or_calworks_work_rules: $("#cSnap").checked,
  };
  if (!state.file && !$("#pasteText").value.trim()) { alert("Add a notice photo, PDF, or text first."); return; }
  startCase({ client, file: state.file, text: $("#pasteText").value, name: client.display_name, title: "Uploaded notice",
    image: state.file && state.file.type.startsWith("image/") ? URL.createObjectURL(state.file) : null });
}

async function startCase(opts) {
  $("#empty").hidden = true;
  $("#workspace").hidden = false;
  $("#caseEyebrow").textContent = opts.name;
  $("#caseTitle").textContent = opts.title;
  const sim = $("#simBanner");
  sim.hidden = !opts.simulated;
  if (opts.simulated) sim.textContent = `Simulated date ${fmtDate(opts.asOf)} · work rules start Jan 1, 2027`;
  const img = $("#noticeImg");
  img.parentElement.hidden = !opts.image;
  if (opts.image) img.src = opts.image;
  $("#trace").innerHTML = "";
  $("#gate").hidden = true;
  $("#panel").innerHTML = '<p class="muted">Decoding…</p>';
  state.result = null;

  const fd = new FormData();
  if (opts.sampleId) fd.append("sample_id", opts.sampleId);
  if (opts.client) fd.append("client_json", JSON.stringify(opts.client));
  if (opts.text) fd.append("text", opts.text);
  if (opts.file) fd.append("file", opts.file);

  const resp = await fetch("/api/analyze", { method: "POST", body: fd });
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const line = buf.slice(0, i).replace(/^data: /, "");
      buf = buf.slice(i + 2);
      if (line.trim()) handle(JSON.parse(line));
    }
  }
}

function handle(ev) {
  if (ev.type === "step") {
    const id = "step-" + ev.agent.replace(/\W/g, "");
    let li = document.getElementById(id);
    if (!li) { li = document.createElement("li"); li.id = id; $("#trace").appendChild(li); }
    li.innerHTML = `<span class="dot ${ev.status}"></span><div><div class="agent">${esc(ev.agent)}</div><div class="detail">${esc(ev.detail)}</div></div>`;
  } else if (ev.type === "result") {
    state.result = ev.data;
    state.authorities = Object.fromEntries(ev.data.authorities.map((a) => [a.id, a]));
    state.tab = "overview";
    renderGate();
    renderTabs();
  } else if (ev.type === "error") {
    $("#panel").innerHTML = `<div class="flag escalate"><span class="lvl">Error</span><span>${esc(ev.message)}</span></div>`;
  }
}

function renderGate() {
  const r = state.result.rules;
  const g = $("#gate");
  g.hidden = false;
  if (r.review_status === "needs_human_expert") {
    g.className = "gate esc";
    g.innerHTML = `<div><strong>Escalate to a benefits attorney or senior navigator</strong>
      <ul>${r.review_reasons.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
  } else {
    g.className = "gate ok";
    g.innerHTML = `<div><strong>Ready for navigator review</strong>No escalation triggers. Review the drafts, edit as needed, and approve to release.</div>`;
  }
}

function renderTabs() {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("active", b.dataset.tab === state.tab));
  if (!state.result) return;
  const R = state.result, p = $("#panel");
  const views = { overview, plan, checklist, client, letter, sources, audit };
  p.innerHTML = views[state.tab](R);
  wire(p);
}

const cites = (ids) => ids.map((i) => `<button class="cite" data-auth="${esc(i)}">${esc(state.authorities[i]?.citation || i)}</button>`).join("");

function overview(R) {
  const r = R.rules, f = R.facts;
  const dl = r.deadlines.slice().sort((a, b) => a.days_left - b.days_left).map((d) => `
    <div class="card deadline ${d.severity}">
      <h4>${esc(d.label)}</h4>
      <div class="big">${fmtDate(d.act_by)}</div>
      <div class="${d.days_left <= 3 ? "chip chip-red" : "chip"}" style="margin:6px 0">${d.days_left <= 0 ? "Act today" : d.days_left + " days left"}</div>
      <div class="small muted">${esc(d.basis)}</div>
      <div style="margin-top:8px">${cites([d.authority_id])}</div>
    </div>`).join("");
  const flags = r.flags.map((x) => `<div class="flag ${x.level}"><span class="lvl">${esc(x.level)}</span><span>${esc(x.message)} ${x.authority_id ? cites([x.authority_id]) : ""}</span></div>`).join("");
  const ex = r.exemptions.length ? `<h3 class="section-h">Exemptions that appear to apply</h3><div class="exempt">${r.exemptions.map((e) => `<div><strong>${esc(e.label)}</strong><div class="small">Proof: ${esc(e.proof)}</div></div>`).join("<hr style='border:0;border-top:1px solid var(--line)'>")}</div>` : "";
  return `
    <div class="summary">${esc(f.plain_summary)}</div>
    <div class="small muted" style="margin-top:8px">${esc(f.program)} · ${esc(label(f.notice_type))} · notice dated ${f.notice_date ? fmtDate(f.notice_date) : "unknown"} · case ${esc(f.case_number || "not shown")} · triage ${r.triage_score}/100</div>
    <h3 class="section-h">Deadlines</h3>
    <div class="cards">${dl || '<p class="muted">No deadlines computed.</p>'}</div>
    <div class="btn-row"><button class="btn" id="icsBtn">Add deadlines to calendar (.ics)</button></div>
    ${ex}
    <h3 class="section-h">Flags</h3>${flags || '<p class="muted">No flags.</p>'}`;
}

function claimList(cs) {
  return cs.map((c) => `<div class="claim"><div class="claim-top"><span class="pri ${c.priority}">${esc(c.priority)}</span>
    <span class="verified" title="${esc(c.verdict_reason)}">✓ ${esc(label(c.verdict))} · code checks passed</span></div>
    <div>${esc(c.text)}</div><div style="margin-top:8px">${cites(c.authority_ids)}</div></div>`).join("");
}

function plan(R) {
  const rights = R.claims.filter((c) => c.agent === "rights"), health = R.claims.filter((c) => c.agent === "health");
  const dropped = R.dropped_claims.length ? `<h3 class="section-h">Removed by the verifier</h3>${R.dropped_claims.map((c) => `<div class="flag warn"><span class="lvl">Removed</span><span>${esc(c.text)}<br><span class="small muted">${esc([...(c.hard_problems || []), c.verdict_reason].filter(Boolean).join("; "))}</span></span></div>`).join("")}` :
    `<p class="small muted" style="margin-top:14px">The verifier checked ${R.claims.length} claims against their citations and the computed deadlines. None were removed.</p>`;
  return `<div class="two-col"><div><h3 class="section-h" style="margin-top:0">Rights Agent</h3>${claimList(rights)}</div>
    <div><h3 class="section-h" style="margin-top:0">Health Navigator</h3>${claimList(health)}
    <h3 class="section-h">Support lines</h3>${R.resources.map((x) => `<div class="src"><strong>${esc(x.name)}</strong><div>${esc(x.contact)}</div><div class="small muted">${esc(x.when)}</div></div>`).join("")}</div></div>${dropped}`;
}

function checklist(R) {
  return R.drafts.document_checklist.map((c, i) => `<label class="check-item"><input type="checkbox" /><div><strong>${esc(c.item)}</strong><div class="small muted">${esc(c.why)}</div></div></label>`).join("") +
    `<h3 class="section-h">Navigator notes</h3><div class="summary">${esc(R.drafts.navigator_notes)}</div>`;
}

function client(R) {
  return `<div class="claim-top"><span class="chip chip-live">${esc(R.client.preferred_language || "English")}</span><span class="small muted">Plain language for the client. Review before sharing.</span></div>
    <div class="prose">${esc(R.drafts.client_explanation)}</div>
    <div class="btn-row"><button class="btn" data-copy="client">Copy</button><button class="btn" onclick="window.print()">Print</button></div>`;
}

function letter(R) {
  return `<p class="small muted">Edit freely. Nothing is released until a navigator approves it, and the approval is hashed into the audit trail.</p>
    <textarea id="letterEdit">${esc(R.drafts.response_letter)}</textarea>
    <div class="grid2" style="max-width:420px;margin-top:10px"><label>Approving navigator<input id="navName" placeholder="Your name" /></label></div>
    <div class="btn-row"><button class="btn btn-primary" id="approveBtn">Approve and release</button><button class="btn" data-copy="letter">Copy</button><button class="btn" id="dlLetter">Download .txt</button></div>
    <div id="approvedBox"></div>`;
}

function sources(R) {
  return `<p class="small muted">${esc(R.disclaimer)}</p>` + R.authorities.map((a) => `<div class="src"><strong>${esc(a.title)}</strong> <span class="mono">${esc(a.citation)}</span>
    <div style="margin:6px 0">${esc(a.summary)}</div><div class="small"><strong>How to use it.</strong> ${esc(a.how_to_use)}</div>
    <a href="${esc(a.url)}" target="_blank" rel="noopener">Official source</a></div>`).join("");
}

function audit() {
  setTimeout(async () => {
    const d = await fetch(`/api/audit/${state.result.case_id}`).then((r) => r.json());
    $("#auditBody").innerHTML = `<p><span class="chip ${d.chain.ok ? "chip-live" : "chip-red"}">${d.chain.ok ? "✓ Hash chain intact" : "Chain broken"} · ${d.chain.entries} entries</span>
      <span class="small muted">Only hashes are stored. No client data is kept in the log.</span></p>
      <table><tr><th>Time</th><th>Step</th><th>Actor</th><th>Output hash</th><th>Entry hash</th></tr>
      ${d.trail.map((e) => `<tr><td class="mono">${esc(e.ts.slice(11, 19))}</td><td>${esc(label(e.step))}</td><td>${esc(e.actor)}</td><td class="mono">${esc((e.output_sha256 || "").slice(0, 12))}</td><td class="mono">${esc(e.entry_hash.slice(0, 12))}</td></tr>`).join("")}</table>`;
  }, 0);
  return `<div id="auditBody"><p class="muted">Loading audit trail…</p></div>`;
}

function wire(p) {
  p.querySelectorAll(".cite").forEach((b) => {
    b.addEventListener("mouseenter", (e) => {
      const a = state.authorities[b.dataset.auth]; if (!a) return;
      const t = $("#tooltip"); t.hidden = false; t.innerHTML = `<strong>${esc(a.title)}</strong><br>${esc(a.summary)}`;
      const r = b.getBoundingClientRect(); t.style.left = Math.min(r.left, innerWidth - 380) + "px"; t.style.top = r.bottom + 8 + "px";
    });
    b.addEventListener("mouseleave", () => ($("#tooltip").hidden = true));
    b.addEventListener("click", () => { state.tab = "sources"; renderTabs(); });
  });
  p.querySelectorAll("[data-copy]").forEach((b) => b.addEventListener("click", () => {
    const txt = b.dataset.copy === "client" ? state.result.drafts.client_explanation : $("#letterEdit").value;
    navigator.clipboard.writeText(txt); b.textContent = "Copied";
  }));
  const ics = $("#icsBtn"); if (ics) ics.addEventListener("click", downloadIcs);
  const dl = $("#dlLetter"); if (dl) dl.addEventListener("click", () => download("response_letter.txt", $("#letterEdit").value, "text/plain"));
  const ap = $("#approveBtn"); if (ap) ap.addEventListener("click", approve);
}

async function approve() {
  const nav = $("#navName").value.trim();
  if (!nav) { $("#navName").focus(); return; }
  const letterTxt = $("#letterEdit").value;
  const res = await fetch("/api/approve", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: state.result.case_id, navigator: nav, letter: letterTxt, edits_made: letterTxt !== state.result.drafts.response_letter }) }).then((r) => r.json());
  $("#approvedBox").innerHTML = `<div class="approved">✓ Approved by ${esc(nav)}. Recorded in the audit trail as <span class="mono">${esc(res.entry_hash.slice(0, 16))}</span>.</div>`;
  $("#approveBtn").disabled = true;
}

function download(name, content, type) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([content], { type }));
  a.download = name; a.click();
}

function downloadIcs() {
  const R = state.result, who = R.client.display_name || "Client";
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
  const ev = R.rules.deadlines.map((d, i) => {
    const day = d.act_by.replace(/-/g, "");
    return ["BEGIN:VEVENT", `UID:${R.case_id}-${i}@kalinga`, `DTSTAMP:${stamp}`, `DTSTART;VALUE=DATE:${day}`,
      `SUMMARY:${who}: ${d.label}`, `DESCRIPTION:${d.basis} (${state.authorities[d.authority_id]?.citation || ""})`,
      "BEGIN:VALARM", "TRIGGER:-P2D", "ACTION:DISPLAY", `DESCRIPTION:${d.label}`, "END:VALARM", "END:VEVENT"].join("\r\n");
  });
  download("kalinga_deadlines.ics", ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Kalinga//EN", ...ev, "END:VCALENDAR"].join("\r\n"), "text/calendar");
}

init();
