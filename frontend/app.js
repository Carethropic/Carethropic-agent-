/* Carethropic — frontend. No build step. */
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const view = $('#view');
  const state = { meta: null, lang: {}, ui: {}, record: null, recordLang: null, lastAnswer: null, lastSearch: null };
  const LANG_FLAG = { en: 'EN', tl: 'TL', 'zh-Hant': '中', vi: 'VI', ko: '한', hi: 'हि', es: 'ES' };
  const SEGMENT = { elder: 'Elder, lives alone', women: 'Mother / caregiver' };

  // ---------- helpers ----------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  async function api(path, opts = {}) {
    const r = await fetch('/api' + path, { headers: { 'Content-Type': 'application/json' }, ...opts });
    if (!r.ok) { let m = r.statusText; try { m = (await r.json()).detail || m; } catch (e) { } throw new Error(m); }
    return r.json();
  }
  const post = (p, body) => api(p, { method: 'POST', body: JSON.stringify(body || {}) });
  function toast(msg, ms = 2600) { const t = $('#toast'); t.textContent = msg; t.classList.remove('hidden'); clearTimeout(t._t); t._t = setTimeout(() => t.classList.add('hidden'), ms); }
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  async function ui(lang) { if (!state.ui[lang]) state.ui[lang] = await api('/i18n/' + lang); return state.ui[lang]; }
  const langName = (l) => (state.meta?.languages?.[l]) || l;

  // ---------- shell ----------
  async function loadMeta() {
    state.meta = await api('/meta');
    const m = state.meta;
    $('#modepill').innerHTML = `<span class="pill ${m.mode === 'live' ? '' : 'gray'}">${m.mode === 'live' ? 'Claude live · ' + esc(m.model) : 'Replay mode (no API key)'}</span><span>${esc(m.organization.name)}</span>`;
  }
  function setNav(route) { document.querySelectorAll('#nav a').forEach((a) => a.classList.toggle('active', a.dataset.route === route)); }

  // ---------- console ----------
  async function renderConsole() {
    setNav('console');
    view.innerHTML = `<h1>Navigator console</h1><p class="sub">One caseload, two kinds of care: mothers on Medi-Cal and elders who live alone. Flags are computed in code, never by the model.</p><div class="card"><p class="muted">Loading…</p></div>`;
    const data = await api('/console');
    const rows = data.rows.map((r) => {
      const flags = r.flags.map((f) => `<span class="flag ${f.kind}">${esc(f.text)}</span>`).join('') || '<span class="muted small">No flags</span>';
      const cases = r.cases.map((c) => `<a href="#/case/${c.id}" class="small">${esc(c.headline)}${c.status ? ' · ' + (c.status === 'attorney' ? '<span class="pill gold">attorney</span>' : '<span class="pill">navigator</span>') : ''}</a>`).join('<br>');
      const next = r.next_event ? `<div class="small">${esc(r.next_event.date)} · ${esc(r.next_event.title)}</div>` : '<span class="muted small">—</span>';
      return `<tr class="clickable" onclick="location.hash='#/record/${r.id}'">
        <td><b>${esc(r.name)}</b><div class="small muted">${r.age} · ${esc(r.city)} · ${esc(langName(r.language))}</div></td>
        <td><span class="tag">${esc(SEGMENT[r.segment] || r.segment)}</span></td>
        <td><span class="statdot ${r.status}"></span>${r.lives_alone ? esc(r.status.replace(/_/g, ' ')) : '<span class="muted">n/a</span>'}</td>
        <td>${flags}</td><td>${next}</td><td onclick="event.stopPropagation()">${cases || '<span class="muted small">—</span>'}</td></tr>`;
    }).join('');
    view.innerHTML = `<h1>Navigator console</h1><p class="sub">${esc(state.meta.organization.name)} · today ${esc(data.today)} · one caseload, two kinds of care: mothers on Medi-Cal and elders who live alone.</p>
      <div class="card"><div class="row" style="justify-content:space-between;margin-bottom:10px"><div><span class="flag act_today">Act today</span><span class="flag attorney">Attorney review</span><span class="flag missed_checkin">Missed check-in</span><span class="flag upcoming">Upcoming</span></div>
      <div class="row"><button class="btn small" id="decodeBtn">Decode a new notice</button><button class="btn small" id="resetBtn">Reset demo</button></div></div>
      <table class="console"><thead><tr><th>Person</th><th>Track</th><th>Check-in</th><th>Flags</th><th>Next date</th><th>Notices</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="card" style="margin-top:16px"><h2>Decode a notice <span class="pill gray">Claude vision + rules engine</span></h2>
        <div class="grid two"><div><label class="small muted">Person</label><select id="dPerson">${data.rows.map((r) => `<option value="${r.id}">${esc(r.name)} (${esc(langName(r.language))})</option>`).join('')}</select>
          <label class="small muted" style="margin-top:8px;display:block">Paste notice text</label><textarea id="dText" placeholder="Paste the notice text here. SSNs, phones, and emails are scrubbed before anything reaches the model."></textarea></div>
          <div><label class="small muted">Or upload a photo of the notice</label><input type="file" id="dImage" accept="image/*"><p class="small muted">In replay mode (no API key), pasted text is parsed by patterns and the recorded cases run as replays. With a key, Claude reads the photo.</p><button class="btn primary" id="dRun">Decode</button></div></div></div>`;
    $('#resetBtn').onclick = async () => { await post('/reset'); toast('Demo reset'); renderConsole(); };
    $('#decodeBtn').onclick = () => $('#dText').focus();
    $('#dRun').onclick = async () => {
      const fd = new FormData(); fd.append('person_id', $('#dPerson').value); fd.append('text', $('#dText').value);
      const f = $('#dImage').files[0]; if (f) fd.append('image', f);
      $('#dRun').disabled = true;
      try { const r = await fetch('/api/decode', { method: 'POST', body: fd }); if (!r.ok) throw new Error((await r.json()).detail); const res = await r.json(); location.hash = '#/case/' + res.case_id; }
      catch (e) { toast('Could not decode: ' + e.message); } finally { $('#dRun').disabled = false; }
    };
  }

  // ---------- case / decoder ----------
  const STAGES = ['Extract', 'Rules engine', 'Rights Agent ∥ Health Navigator', 'Verifier', 'Drafts', 'Human gate'];
  async function renderCase(id) {
    setNav('console');
    view.innerHTML = `<h1>Notice decoder</h1><p class="sub">Case ${esc(id)}</p><div class="pipeline" id="pipe">${STAGES.map((s) => `<span class="stage">${s}</span>`).join('')}</div><div class="card"><p class="muted" id="pmsg">Running…</p></div>`;
    let res = (await api('/cases/' + id)).result;
    const pipe = [...document.querySelectorAll('#pipe .stage')];
    if (!res) {
      const run = post('/cases/' + id + '/run');
      for (let i = 0; i < pipe.length; i++) { pipe[i].classList.add('active'); await sleep(260); pipe[i].classList.remove('active'); pipe[i].classList.add('done'); }
      try { res = await run; } catch (e) { view.innerHTML = `<div class="card">Could not run case: ${esc(e.message)}</div>`; return; }
    } else pipe.forEach((p) => p.classList.add('done'));
    drawCase(res);
  }
  function drawCase(res) {
    const r = res.rules, g = res.gate, n = res.notice;
    const deadlines = r.deadlines.sort((a, b) => a.date.localeCompare(b.date)).map((d) => `<div class="deadline ${d.days_left <= 3 ? 'urgent' : ''}"><div><div><b>${esc(d.label)}</b></div><div class="small muted">${esc(d.action)} · <span class="cite" title="${esc(d.authority)}">${esc(d.authority)}</span>${d.rolled_back ? ' · rolled back to a business day' : ''}</div></div><div style="text-align:right"><div class="d">${esc(d.date)}</div><div class="small ${d.days_left <= 3 ? 'pill red' : 'muted'}">${d.days_left < 0 ? 'passed' : d.days_left === 0 ? 'Act today' : d.days_left + ' days'}</div></div></div>`).join('') || '<p class="muted">No deadlines computed.</p>';
    const findings = [...r.defects.map((f) => `<li><span class="pill red">Notice defect</span> ${esc(f.message)} <span class="cite">${esc(f.authority)}</span></li>`),
      ...r.exemptions.map((f) => `<li><span class="pill">Exemption</span> ${esc(f.message)} <span class="cite">${esc(f.authority)}</span></li>`),
      ...r.escalations.map((f) => `<li><span class="pill gold">Escalation</span> ${esc(f.message)}</li>`)].join('') || '<li class="muted">No defects or escalations.</li>';
    const claims = res.claims.map((c) => `<div class="claim"><div class="who">${esc(c.agent)} · ${esc(c.kind)}</div>${esc(c.text)}<div>${(c.citations || []).map((x) => `<a class="cite" href="${esc(x.url)}" target="_blank" rel="noopener" title="${esc(x.title)}: ${esc(x.summary)}">${esc(x.cite)}</a>`).join('')}</div></div>`).join('');
    const removed = res.removed_claims.map((c) => `<div class="claim removed"><div class="who">${esc(c.agent)} · removed by verifier</div>${esc(c.text)}<div class="small muted">${c.reasons.map(esc).join(' ')}</div></div>`).join('');
    const conf = Object.entries(n.confidence || {}).map(([k, v]) => `<span class="tag" style="${v < 0.7 ? 'background:#fde8e6;color:#b42318' : ''}">${esc(k)} ${(v * 100).toFixed(0)}%</span>`).join('');
    const extractMode = res.trace.find((t) => t.stage === 'extract')?.mode, agentMode = res.trace.find((t) => t.stage === 'agents')?.mode;
    view.innerHTML = `<div class="row" style="justify-content:space-between"><div><h1>${esc(res.person.name)} <span class="pill gray">${esc(langName(res.person.language))}</span> <span class="pill gray">${esc(SEGMENT[res.person.segment] || '')}</span></h1>
      <p class="sub">${esc(n.agency)} · case ${esc(n.case_number)} · ${esc(n.notice_type.replace(/_/g, ' '))} · extraction: ${esc(extractMode)} · agents: ${esc(agentMode)} · KB ${esc(res.kb_version)}</p></div>
      <div class="row"><a class="btn" href="#/record/${res.person.id}">Open her Carethropic record</a><a class="btn" href="#/console">Console</a></div></div>
      <div class="pipeline">${STAGES.map((s) => `<span class="stage done">${s}</span>`).join('')}</div>
      <div class="gate ${g.approved ? 'approved' : g.route}" id="gate"><div class="row" style="justify-content:space-between"><div><h2 style="margin:0">${g.approved ? 'Approved by navigator' : g.route === 'attorney' ? 'Routed to attorney review' : 'Ready for navigator review'} ${g.urgent ? '<span class="pill red">Act today</span>' : ''}</h2><div class="small">${g.reasons.map(esc).join(' · ') || 'Routine case.'}${g.approval_hash ? ` · approval hash <span class="mono">${g.approval_hash.slice(0, 16)}…</span>` : ''}</div></div>
        <div class="row"><input type="text" id="navName" placeholder="Navigator name" style="width:180px" value="A. Navigator"><button class="btn primary" id="approveBtn" ${g.approved ? 'disabled' : ''}>Approve letter</button><button class="btn ${res.saved_to_record ? '' : 'warm'}" id="saveBtn">${res.saved_to_record ? 'Saved to Carethropic record' : 'Save deadlines to Carethropic record'}</button></div></div></div>
      <div class="grid two" style="margin-top:16px">
        <div class="card"><h2>Deadlines <span class="pill gray">computed in code</span></h2>${deadlines}<h3 style="margin-top:14px">Findings</h3><ul class="list">${findings}</ul></div>
        <div class="card"><h2>What the notice says <span class="pill gray">extracted</span></h2><p>${esc(n.reason)}</p><div class="small"><b>Notice date</b> ${esc(n.notice_date)}${n.effective_date ? ` · <b>Effective</b> ${esc(n.effective_date)}` : ''}${n.stated_due_date ? ` · <b>Stated due</b> ${esc(n.stated_due_date)}` : ''}</div><div class="small"><b>Requested</b> ${(n.requested_documents || []).map(esc).join(', ') || '—'}</div><div style="margin-top:8px">${conf}</div>
          <h3 style="margin-top:14px">Plain-language explanation <span class="pill">${esc(langName(res.drafts.explanation.lang))}</span></h3><div class="explain">${esc(res.drafts.explanation.text)}</div>${res.drafts.explanation_en ? `<p class="small muted">English: ${esc(res.drafts.explanation_en)}</p>` : ''}</div>
        <div class="card"><h2>Verified claims <span class="pill">${res.claims.length} kept</span> ${res.removed_claims.length ? `<span class="pill red">${res.removed_claims.length} removed</span>` : ''}</h2>${claims}${removed}<p class="small muted">Agents may only cite authority IDs the rules engine selected. Dates are placeholders filled from computed deadlines.</p></div>
        <div class="card"><h2>Draft reply <span class="pill gray">needs approval</span></h2><pre class="letter" id="letter" contenteditable="true">${esc(res.drafts.letter)}</pre><h3>Document checklist</h3><ul class="list">${res.drafts.checklist.map((c) => `<li>☐ ${esc(c)}</li>`).join('')}</ul></div>
      </div>`;
    $('#approveBtn').onclick = async () => { try { const gate = await post(`/cases/${res.case_id}/approve`, { navigator: $('#navName').value || 'Navigator', letter: $('#letter').innerText }); res.gate = gate; toast('Approved and hashed into the audit chain'); drawCase(res); } catch (e) { toast(e.message); } };
    $('#saveBtn').onclick = async () => { try { const out = await post(`/cases/${res.case_id}/save`); res.saved_to_record = true; toast(`${out.saved.length} deadline(s) saved to her record`); drawCase(res); } catch (e) { toast(e.message); } };
  }

  // ---------- record (elder view) ----------
  async function renderRecord(pid, lang) {
    setNav('console');
    const p = await api('/people/' + pid);
    if (state.recordPid !== pid) state.recordLang = null;   // a new person starts in her own language
    state.record = p; state.recordPid = pid; state.recordLang = lang || state.recordLang || p.language;
    const L = state.recordLang; const T = await ui(L);
    const V = window.CarethropicVoice; const BCP = { tl: 'fil-PH', 'zh-Hant': 'zh-HK', vi: 'vi-VN', ko: 'ko-KR', hi: 'hi-IN', es: 'es-US', en: 'en-US' }[L] || 'en-US';
    const st = p.status; const todayStr = state.meta.today;
    const dueState = (m) => { const items = st.items.filter((i) => i.item_id === m.id); const taken = items.filter((i) => i.state === 'taken').length; const due = items.length; return { taken, due, missed: items.some((i) => i.state === 'missed'), late: items.some((i) => i.state === 'late') }; };
    const meds = p.medications.map((m) => { const d = dueState(m); return `<li class="med"><div><div class="name">${esc(m.name)} ${esc(m.dose)}</div><div class="meta">${esc(m.purpose)} · ${m.times.join(', ')} · ${esc(T.refill)} ${esc(m.refill_date)}</div></div>
      <div class="row"><span class="check">${d.taken ? '✅'.repeat(d.taken) : ''}${d.missed ? ' ⚠️' : ''}</span><button class="btn ${d.due > d.taken ? 'primary' : ''}" data-med="${m.id}">${esc(T.taken)}</button></div></li>`; }).join('') || `<li class="muted">—</li>`;
    const events = p.events.filter((e) => e.date >= todayStr).map((e) => `<li><div class="row" style="justify-content:space-between"><div><b>${esc(e.date)}${e.time ? ' · ' + esc(e.time) : ''}</b><div>${esc((e.title_local && e.title_local[L]) || e.title)}</div>${e.place ? `<div class="meta muted">${esc(e.place)}</div>` : ''}</div><span class="pill ${e.type === 'deadline' ? 'warm' : 'gray'}">${e.type === 'deadline' ? 'Medi-Cal' : 'visit'}</span></div></li>`).join('') || `<li class="muted">—</li>`;
    const cov = p.coverage.map((c) => `<li><b>${esc(c.program)}</b><div class="meta muted">${esc(c.plan)} · ID ${esc(c.member_id)} · ${esc(c.status)}</div></li>`).join('');
    const em = p.emergency;
    const statusText = T['status_' + st.level] || st.level;
    const langButtons = Object.entries(state.meta.languages).map(([k, v]) => `<button class="${k === L ? 'active' : ''}" data-lang="${k}">${esc(v)}</button>`).join('');
    view.innerHTML = `<div class="elder">
      <div class="row" style="justify-content:space-between;align-items:flex-start"><div><h1>${esc(p.display_name)}</h1><p class="sub">${esc(T.today)} ${esc(todayStr)} · <span class="statdot ${st.level}"></span>${esc(statusText)}</p></div>
        <div><div class="langbar">${langButtons}</div><div class="row noprint" style="margin-top:8px;justify-content:flex-end"><button class="btn voice ${V.enabled ? 'on' : ''}" id="voiceBtn" aria-pressed="${V.enabled}">${V.enabled ? '🔊 ' + esc(T.voice_on) : '🔇 ' + esc(T.voice_off)}</button><button class="btn" id="readBtn">▶ ${esc(T.read_today)}</button></div></div></div>
      <div id="briefing" class="briefing noprint" aria-live="polite"></div>
      <div class="grid two">
        <div class="card"><button class="btn big primary" id="okBtn">${esc(T.im_ok)}</button><p class="small muted noprint" style="margin:8px 0 0">${st.last_daily ? 'Last check-in ' + esc(st.last_daily) : 'No check-in yet'}. Missed check-ins show on the navigator console. No automatic calls or texts.</p></div>
        <div class="card"><h2>${esc(T.ask_title)} <span class="pill gray small">answers only from her record</span></h2><button class="btn big mic" id="micBtn" aria-label="${esc(T.ask_by_voice)}">🎤 ${esc(T.ask_by_voice)}</button><div class="row" style="margin-top:10px"><input type="text" id="askInput" placeholder="${esc(T.ask_placeholder)}"><button class="btn primary" id="askBtn">${esc(T.ask_button)}</button></div><div id="askOut" aria-live="polite"></div>
          <div class="row noprint" style="margin-top:8px"><button class="btn small" data-q="Did I take my blood pressure pill today?">Did I take my pill?</button><button class="btn small" data-q="When is my Medi-Cal deadline?">My Medi-Cal deadline?</button><button class="btn small" data-q="Should I take two pills since I forgot this morning?">Take two pills?</button><button class="btn small" data-q="Who is my emergency contact?">Emergency contact?</button></div></div>
        <div class="card"><h2>${esc(T.my_meds)}</h2><ul class="list">${meds}</ul></div>
        <div class="card"><h2>${esc(T.my_events)}</h2><ul class="list">${events}</ul></div>
        <div class="card"><h2>${esc(T.my_coverage)}</h2><ul class="list">${cov}</ul></div>
        <div class="card"><h2>${esc(T.emergency)}</h2><ul class="list"><li><b>${esc(T.contacts)}</b><div>${em.contacts.map((c) => `${esc(c.name)} · ${esc(c.phone)}`).join('<br>') || '—'}</div></li><li><b>${esc(T.allergies)}</b><div>${em.allergies.map(esc).join(', ') || '—'}</div></li><li><b>${esc(T.directive)}</b><div>${esc(em.advance_directive_location || '—')}</div></li></ul>
          <div class="row noprint" style="margin-top:10px"><label class="small"><input type="checkbox" id="consentBox" ${p.consent ? 'checked' : ''}> She agrees to share this on a wallet card</label><button class="btn" id="cardBtn">${esc(T.card_title)}</button></div><p class="small muted noprint">${p.consent ? `Consent recorded ${esc(p.consent.at)} by ${esc(p.consent.recorded_by)}, hashed into the audit chain.` : 'Card prints only after consent is recorded. No member IDs or addresses go on the card.'}</p><div id="cardOut"></div></div>
      </div></div>
      <div class="callbar elder"><a class="btn warm" href="tel:${esc(state.meta.organization.navigator_phone)}">📞 ${esc(T.call_navigator)} · ${esc(state.meta.organization.navigator_phone)}</a></div>`;
    document.querySelectorAll('.langbar button').forEach((b) => b.onclick = () => renderRecord(pid, b.dataset.lang));
    $('#okBtn').onclick = async () => { const r = await post(`/people/${pid}/checkin`, { type: 'daily', lang: L }); toast('✓'); state.pendingSpeech = r.spoken; renderRecord(pid); };
    document.querySelectorAll('[data-med]').forEach((b) => b.onclick = async () => { const r = await post(`/people/${pid}/checkin`, { type: 'med', item_id: b.dataset.med, lang: L }); toast('✓'); state.pendingSpeech = r.spoken; renderRecord(pid); });
    const briefing = async ({ aloud }) => {
      const b = await api(`/people/${pid}/briefing?lang=${encodeURIComponent(L)}`);
      $('#briefing').innerHTML = `<div class="card brief"><div class="text">${b.sentences.map(esc).join(' ')}</div><div class="small muted">Composed in code from her record · cited ${b.cited_record_ids.map(esc).join(', ') || 'nothing'}</div></div>`;
      if (aloud) V.speak(b.text, b.bcp47, { force: true });
      return b;
    };
    $('#voiceBtn').onclick = async () => {
      V.setEnabled(!V.enabled);
      const T2 = await ui(L); const vb = $('#voiceBtn'); vb.classList.toggle('on', V.enabled); vb.setAttribute('aria-pressed', V.enabled);
      vb.textContent = V.enabled ? '🔊 ' + T2.voice_on : '🔇 ' + T2.voice_off;
      if (V.enabled) { if (!V.canSpeak) toast('Read-aloud is not available in this browser'); await briefing({ aloud: true }); }
    };
    $('#readBtn').onclick = () => briefing({ aloud: true });
    if (state.pendingSpeech) { V.speak(state.pendingSpeech, BCP); state.pendingSpeech = null; }
    else if (V.enabled && state.briefedFor !== pid + L) { state.briefedFor = pid + L; briefing({ aloud: true }); }
    document.querySelectorAll('[data-q]').forEach((b) => b.onclick = () => { $('#askInput').value = b.dataset.q; ask(); });
    const ask = async () => {
      const q = $('#askInput').value.trim(); if (!q) return;
      $('#askOut').innerHTML = `<div class="answer muted">…</div>`;
      try {
        const a = await post(`/people/${pid}/ask`, { question: q, lang: L });
        const cites = a.cited.map((c) => `<span class="cite" title="${esc(c.id)}">${esc(c.label)}</span>`).join('');
        $('#askOut').innerHTML = `<div class="answer ${a.guard ? 'guard' : ''}">${esc(a.answer)}</div><div class="small muted" style="margin-top:6px">${a.guard ? 'Medical advice guard: Carethropic never advises on doses. ' : ''}Intent: ${esc(a.intent)} · ${a.mode === 'live' ? 'Claude phrased it' : 'template'} · cited ${cites || 'nothing'}${a.verifier.passed ? '' : ' · <b>verifier replaced the model answer</b>: ' + esc(a.verifier.notes.join(' '))}</div>`;
        V.speak(a.answer, BCP, { force: state.speakOnce }); state.speakOnce = false;
      } catch (e) { $('#askOut').innerHTML = `<div class="answer guard">${esc(e.message)}</div>`; }
    };
    $('#askBtn').onclick = ask; $('#askInput').onkeydown = (e) => { if (e.key === 'Enter') ask(); };
    $('#micBtn').onclick = () => {
      if (!V.canListen) { toast('Voice input is not available in this browser'); return; }
      const mb = $('#micBtn'); mb.classList.add('listening'); toast(T.listening, 6000);
      state.speakOnce = true;   // an answer to a spoken question is always spoken back, even with voice off
      V.listen(BCP, (text) => { mb.classList.remove('listening'); $('#askInput').value = text; ask(); },
               () => { mb.classList.remove('listening'); toast('Could not hear that'); });
    };
    $('#cardBtn').onclick = async () => {
      try {
        const granted = $('#consentBox').checked;
        if (granted !== !!p.consent) await post(`/people/${pid}/consent`, { granted, given_by: 'self', recorded_by: 'A. Navigator' });
        const c = await api(`/people/${pid}/emergency-card`);
        $('#cardOut').innerHTML = `<div class="qrcard" style="margin-top:12px">${c.qr_svg}<div class="lines">${c.lines.map(esc).join('<br>')}<div class="row noprint" style="margin-top:8px"><button class="btn small" onclick="window.print()">Print wallet card</button></div></div></div>`;
      } catch (e) { toast(e.message); if (!$('#consentBox').checked) renderRecord(pid); }
    };
  }

  // ---------- finder ----------
  async function renderFinder() {
    setNav('finder');
    const q = state.lastSearch?.query || '';
    view.innerHTML = `<h1>Nonprofit finder</h1><p class="sub">Claude for Nonprofits partners first, then Bay Area nonprofits serving Asian American women and elders. Curated, versioned directory; Claude only re-ranks and explains fit.</p>
      <div class="card"><div class="row"><input type="text" id="q" placeholder="Try: Claude Non-profit sponsors in san francisco" value="${esc(q)}"><button class="btn primary" id="go">Search</button></div>
      <div class="row noprint" style="margin-top:8px">${['Claude Non-profit sponsors in san francisco', 'Vietnamese senior services San Jose', 'Tagalog elder health East Bay', 'Korean seniors Oakland', 'Hindi speaking women support South Bay', 'Medicare counseling for Chinese elders SF'].map((s) => `<button class="btn small" data-s="${esc(s)}">${esc(s)}</button>`).join('')}</div></div><div id="results"></div>`;
    const run = async () => {
      const query = $('#q').value.trim(); if (!query) return;
      $('#results').innerHTML = `<div class="card" style="margin-top:16px"><p class="muted">Searching…</p></div>`;
      try { const r = await api('/nonprofits/search?q=' + encodeURIComponent(query)); state.lastSearch = r; drawResults(r); } catch (e) { $('#results').innerHTML = `<div class="card" style="margin-top:16px">${esc(e.message)}</div>`; }
    };
    $('#go').onclick = run; $('#q').onkeydown = (e) => { if (e.key === 'Enter') run(); };
    document.querySelectorAll('[data-s]').forEach((b) => b.onclick = () => { $('#q').value = b.dataset.s; run(); });
    if (state.lastSearch) drawResults(state.lastSearch);
  }
  function drawResults(r) {
    const p = r.parsed;
    const groups = r.groups.map((g) => `<div class="card" style="margin-top:16px"><h2>${esc(g.title)} <span class="pill gray">${g.results.length}</span></h2>${g.results.map((o) => `<div class="result"><div class="row" style="justify-content:space-between"><span class="name">${esc(o.name)}</span><span>${o.local ? '<span class="pill">local</span>' : ''}${o.roles.map((x) => `<span class="pill gold">${esc(x)}</span>`).join(' ')}</span></div>
      <div class="why">${esc(o.why)}</div>${o.fit ? `<div class="fit">${esc(o.fit)}</div>` : ''}<div class="links"><a href="${esc(o.website)}" target="_blank" rel="noopener">Website</a> · <a href="${esc(o.source_url)}" target="_blank" rel="noopener">Source</a>${o.hq_city ? ' · HQ ' + esc(o.hq_city) : ''}${o.languages.length ? ' · ' + o.languages.map(esc).join(', ') : ''}</div></div>`).join('') || '<p class="muted">No matches in this group.</p>'}</div>`).join('');
    $('#results').innerHTML = `<p class="parsed" style="margin-top:12px">Parsed in code: place <b>${esc(p.place.label || 'any')}</b> · Claude partner intent <b>${p.claude_intent ? 'yes' : 'no'}</b> · terms <b>${p.terms.map(esc).join(', ') || '—'}</b> · languages <b>${p.languages.map(esc).join(', ') || '—'}</b> · directory ${esc(r.directory_version)} · ${r.mode === 'live' ? 'Claude re-ranked' : 'code ranking'}${r.note ? ' · ' + esc(r.note) : ''}</p>${groups}`;
  }

  // ---------- why ----------
  async function renderWhy() {
    setNav('why');
    const d = await api('/insights');
    const head = d.headline.map((f) => `<div class="card"><div class="stat ${f.id.includes('women') ? 'warm' : ''}">${esc(f.stat)}</div><p>${esc(f.text)}</p><div class="src">${esc(f.source)} · <a href="${esc(f.url)}" target="_blank" rel="noopener">source</a></div></div>`).join('');
    const facts = d.facts.map((f) => `<div class="fact"><div class="n">${esc(f.stat)}</div><div>${esc(f.text)}<div class="src">${esc(f.source)} · <a href="${esc(f.url)}" target="_blank" rel="noopener">source</a></div></div></div>`).join('');
    const cols = ['Cantonese', 'Mandarin', 'Vietnamese', 'Tagalog', 'Korean', 'Hindi', 'Punjabi'];
    const table = `<table class="langs"><thead><tr><th>County</th>${cols.map((c) => `<th>${c}</th>`).join('')}</tr></thead><tbody>${d.county_language.rows.map((r) => `<tr><td>${esc(r.county)}</td>${cols.map((c) => `<td>${(r[c] || 0).toLocaleString()}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    view.innerHTML = `<h1>Why Carethropic</h1><p class="sub">${esc(d.framing)}</p><div class="grid two">${head}</div>
      <div class="grid two" style="margin-top:16px"><div class="card"><h2>What the research says</h2>${facts}</div>
      <div><div class="card"><h2>Medi-Cal members by primary language <span class="pill gray">Oct 2026</span></h2>${table}<p class="src" style="margin-top:8px">${esc(d.computed_note)}</p></div>
      <div class="card" style="margin-top:16px"><h2>Data gaps Carethropic works around</h2><ul class="list">${d.data_gaps.map((g) => `<li>${esc(g)}</li>`).join('')}</ul></div></div></div>`;
  }

  // ---------- audit ----------
  async function renderAudit() {
    setNav('audit');
    const a = await api('/audit');
    view.innerHTML = `<h1>Audit trail</h1><p class="sub">SHA-256 hash chain. Only hashes are stored, never client data. Chain valid: <b>${a.valid ? 'yes' : 'NO'}</b> · ${a.count} entries</p>
      <div class="card"><ul class="list audit">${a.entries.map((e) => `<li>#${e.i} ${esc(e.ts)} <b>${esc(e.kind)}</b> payload ${esc(e.payload_hash.slice(0, 16))}… hash ${esc(e.hash.slice(0, 16))}… prev ${esc(e.prev.slice(0, 8))}…</li>`).join('') || '<li class="muted">No entries yet.</li>'}</ul></div>`;
  }

  // ---------- router ----------
  async function route() {
    if (window.CarethropicVoice) window.CarethropicVoice.stop();
    const h = location.hash || '#/console';
    const [, name, arg] = h.match(/^#\/([a-z]+)\/?([^/]*)/) || [];
    try {
      if (!state.meta) await loadMeta();
      if (name === 'case') await renderCase(arg);
      else if (name === 'record') await renderRecord(arg);
      else if (name === 'finder') await renderFinder();
      else if (name === 'why') await renderWhy();
      else if (name === 'audit') await renderAudit();
      else await renderConsole();
    } catch (e) { view.innerHTML = `<div class="card">Something went wrong: ${esc(e.message)}</div>`; }
  }
  window.addEventListener('hashchange', route);
  route();
})();
