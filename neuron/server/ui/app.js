// NEURON phone interface. Talks only to the NEURON machine on the local network.
const $ = (s, el = document) => el.querySelector(s);
const view = $('#view');
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const LABEL = { draft: 'Draft', queued: 'Waiting to start', running: 'Working', done: 'Done and checked', answered: 'Answered, not checked', partial: 'Partly done', failed: 'Not done',
  waiting_approval: 'Needs your OK', waiting_input: 'Needs your reply', paused: 'Paused', waiting_network: 'Waiting for the internet' };
const STEP = { pending: '', in_progress: '·', done: '✓', partial: '~', failed: '!', skipped: '-', waiting_approval: '?', waiting_input: '?', waiting_network: '…' };
let timer = null;
let gen = 0;       // only the newest screen may draw: an older one that finishes loading later is dropped

async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { 'X-Neuron': '1', ...(opts.json ? { 'Content-Type': 'application/json' } : {}), ...(opts.headers || {}) },
    body: opts.json ? JSON.stringify(opts.json) : opts.body, credentials: 'same-origin' });
  if (r.status === 401) { location.hash = '#/pair'; throw new Error('not paired'); }
  const data = r.headers.get('Content-Type')?.includes('json') ? await r.json() : await r.text();
  if (!r.ok) throw new Error(data.error || 'request failed');
  return data;
}
function ago(t) { const s = Math.round(Date.now() / 1000 - t); return s < 60 ? 'just now' : s < 3600 ? `${Math.round(s / 60)} min ago` : s < 86400 ? `${Math.round(s / 3600)} h ago` : new Date(t * 1000).toLocaleDateString(); }

async function pill() {
  try { const s = await api('/api/status'); const p = $('#netpill');
    p.textContent = s.online ? 'Online' : 'Offline, working locally'; p.className = 'pill ' + (s.online ? 'on' : 'off'); } catch (e) { }
}

function pairView() {
  view.innerHTML = `<section class="card hero"><h1>Pair this phone</h1>
  <p class="lead">Type the 6-digit code shown on the NEURON computer. You only do this once.</p>
  <input id="code" inputmode="numeric" autocomplete="one-time-code" maxlength="6" class="code" aria-label="Pairing code" placeholder="000000">
  <div class="row"><button class="btn primary" id="pair">Pair this phone</button></div><div id="msg"></div>
  <p class="note">The code is printed when NEURON starts. Ask for a new one on that computer with: ~/.neuron/start.sh code</p></section>`;
  $('#pair').onclick = async () => {
    try { await api('/api/pair', { method: 'POST', json: { code: $('#code').value, name: navigator.userAgent.includes('Mobile') ? 'phone' : 'browser' } });
      location.hash = '#/'; } catch (e) { $('#msg').innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  };
}

async function homeView(g) {
  const files = [];
  view.innerHTML = `<section class="card hero"><h1>What should NEURON do?</h1>
  <p class="lead">Describe the goal in your own words. Attach data, documents or a whole project as a .zip.</p>
  <textarea id="goal" aria-label="Your goal" placeholder="For example: make an Excel summary of these sales by region"></textarea>
  <div class="files" id="files"></div>
  <div class="row"><label class="btn small" for="pick">Attach files</label><input id="pick" type="file" multiple hidden>
  <button class="btn primary" id="go">Start</button></div><div id="msg"></div></section>
  <h2>Recent work</h2><div class="list" id="jobs"><p class="note">Loading</p></div>`;
  $('#pick').onchange = (e) => { for (const f of e.target.files) files.push(f);
    $('#files').innerHTML = files.map(f => `<span class="chip">${esc(f.name)}</span>`).join(''); };
  $('#go').onclick = async () => {
    const goal = $('#goal').value.trim(); if (!goal) return;
    $('#go').disabled = true; $('#go').textContent = 'Sending';
    try { const { id } = await api('/api/jobs', { method: 'POST', json: { goal } });
      for (const f of files) await api(`/api/jobs/${id}/upload?name=${encodeURIComponent(f.name)}`, { method: 'POST', body: await f.arrayBuffer() });
      await api(`/api/jobs/${id}/start`, { method: 'POST' }); location.hash = `#/job/${id}`;
    } catch (e) { $('#msg').innerHTML = `<div class="err">${esc(e.message)}</div>`; $('#go').disabled = false; $('#go').textContent = 'Start'; }
  };
  const { jobs } = await api('/api/jobs');
  if (g !== gen) return;
  $('#jobs').innerHTML = jobs.length ? jobs.map(j => `<a class="item" href="#/job/${j.id}"><div><div class="t">${esc(j.title)}</div>
    <div class="s">${ago(j.created)}</div></div><span class="badge b-${j.status}">${LABEL[j.status] || j.status}</span></a>`).join('')
    : '<p class="note">Nothing yet. Your first job will appear here.</p>';
}

async function jobView(id, g) {
  let after = 0, feed = [];
  async function draw() {
    const j = await api(`/api/jobs/${id}`);
    const ev = (await api(`/api/jobs/${id}/events?after=${after}`)).events;
    if (g !== gen) return; if (ev.length) { after = ev[ev.length - 1].seq; feed = feed.concat(ev).slice(-60); }
    const live = ['queued', 'running'].includes(j.status);
    const outs = (j.outputs || []).filter(o => !o.path.startsWith('app/'));            // the whole app comes as app.zip
    const hasApp = (j.outputs || []).some(o => o.path === 'app/app.py');
    const earlier = (j.thread || []).filter(t => t.id !== j.id);
    view.innerHTML = `<p><a href="#/">Back</a></p>
      ${earlier.length ? `<section class="card thread"><h2>Earlier in this conversation</h2>${earlier.map(t => `<a class="said" href="#/job/${t.id}">
        <span>${esc(t.said).slice(0, 160)}</span><span class="badge b-${t.status}">${LABEL[t.status] || t.status}</span></a>`).join('')}</section>` : ''}
      <section class="card"><span class="badge b-${j.status}">${LABEL[j.status] || j.status}</span>
      <h1 style="margin-top:12px">${esc(j.title)}</h1>${(j.request || j.goal) !== j.title ? `<p class="lead">${esc(j.request || j.goal).slice(0, 600)}</p>` : ''}
      ${j.kind ? `<p class="note">Understood as: ${esc(j.kind.replace('_', ' '))}</p>` : ''}
      <div class="row">${live ? `<button class="btn danger small" id="stop">Stop</button>` : ''}
      ${['paused', 'failed', 'partial'].includes(j.status) ? `<button class="btn small" id="resume">Resume</button>` : ''}
      ${hasApp ? `<button class="btn primary small" id="preview">Open the app</button>` : ''}</div></section>
      ${j.owner_inputs?.length ? `<section class="card"><h2>Your replies</h2>${j.owner_inputs.map(t =>
        `<p>${esc(t.question)}<br><b>${esc(t.answer)}</b></p>`).join('')}</section>` : ''}
      ${j.input_request ? `<form class="card" id="input-form"><h2>One detail needed</h2>
        <label for="owner-input">${esc(j.input_request.question)}</label>
        <textarea id="owner-input" required maxlength="1200"></textarea>
        <button class="btn primary" type="submit">Reply and continue</button><div role="status" class="err" id="input-error"></div></form>` : ''}
      ${j.approvals.length ? `<section class="card"><h2>Needs your OK</h2>${j.approvals.map(a => `<p>${esc(a.question || a.action)} (step ${esc(a.task)})</p>
        <div class="row"><button class="btn primary small" data-ok="${esc(a.task)}|${esc(a.action)}">Approve</button>
        <button class="btn danger small" data-no="${esc(a.task)}|${esc(a.action)}">Reject</button></div>`).join('')}</section>` : ''}
      ${j.answer ? `<section class="card"><h2>Answer</h2><div class="answer">${esc(j.answer)}</div></section>` : ''}
      <section class="card"><h2>Steps</h2><div class="steps">${j.plan.map(t => `<div class="step"><span class="dot ${t.status}">${STEP[t.status] || ''}</span>
        <div><div class="t">${esc(t.title)}</div>${t.summary ? `<div class="s">${esc(t.summary)}</div>` : ''}
        <div class="m">${t.verification ? 'Checked by: ' + esc(t.verification) : ''}${t.made_by ? ' · made by: ' + esc(t.made_by) : ''}${t.tries > 1 ? ' · tries: ' + t.tries : ''}</div>
        ${t.last_failure && t.status !== 'done' && t.status !== 'partial' ? `<div class="s no">${esc(t.last_failure).slice(0, 300)}</div>` : ''}
        ${(t.gaps || []).map(g => `<div class="s no">Not done: ${esc(g)}</div>`).join('')}</div></div>`).join('') || '<p class="note">Planning</p>'}</div></section>
      ${outs.length ? `<section class="card out"><h2>Results</h2>${outs.map(o => `<a href="/api/jobs/${id}/file?path=${encodeURIComponent(o.path)}">
        <span>${esc(o.path)}</span><span class="note">${Math.max(1, Math.round(o.bytes / 1024))} KB</span></a>`).join('')}</section>` : ''}
      ${j.evidence.length ? `<section class="card"><h2>Evidence</h2>${j.evidence.slice(-4).map(e => `<h3>${esc(e.task)}: ${e.passed ? 'passed' : 'failed'}</h3>
        <p class="note">${esc(e.how)}</p><div class="checks">${e.checks.map(c => `<div class="ck"><b class="${c.pass ? 'ok' : 'no'}">${c.pass ? '✓' : '✗'}</b>
        <span>${esc(c.id.replace(/_/g, ' '))}${c.detail ? ': ' + esc(c.detail) : ''}</span></div>`).join('')}</div>`).join('')}</section>` : ''}
      ${!live && !['draft', 'waiting_input'].includes(j.status) ? `<section class="card"><h2>Ask for a change or a next step</h2>
        <textarea id="more" aria-label="Follow-up" placeholder="For example: add a column for VAT, or make it shorter"></textarea>
        <div class="row"><button class="btn primary" id="send">Send</button></div><div id="msg2"></div></section>` : ''}
      <section class="card"><h2>What NEURON is doing</h2><div class="feed">${feed.slice().reverse().map(e => `<div>${esc(e.text)}</div>`).join('') || '<p class="note">Nothing yet</p>'}</div></section>`;
    $('#input-form')?.addEventListener('submit', async event => {
      event.preventDefault();
      const answer = $('#owner-input').value.trim();
      const button = event.currentTarget.querySelector('button');
      if (!answer || button.disabled) return;
      button.disabled = true;
      try {
        await api(`/api/jobs/${id}/input`, { method: 'POST', json: { id: j.input_request.id, answer } });
        await draw();
      } catch (err) {
        if (g === gen && $('#input-error')) $('#input-error').textContent = err.message;
        button.disabled = false;
      }
    });
    $('#send')?.addEventListener('click', async () => { const text = $('#more').value.trim(); if (!text) return;
      $('#send').disabled = true;
      try { const r = await api(`/api/jobs/${id}/followup`, { method: 'POST', json: { text } }); location.hash = `#/job/${r.id}`; }
      catch (e) { $('#msg2').innerHTML = `<div class="err">${esc(e.message)}</div>`; $('#send').disabled = false; } });
    $('#stop')?.addEventListener('click', () => api(`/api/jobs/${id}/stop`, { method: 'POST' }).then(draw));
    $('#resume')?.addEventListener('click', () => api(`/api/jobs/${id}/start`, { method: 'POST' }).then(draw));
    $('#preview')?.addEventListener('click', async () => { const r = await api(`/api/jobs/${id}/preview`, { method: 'POST' });
      if (r.url) location.href = `${location.protocol}//${location.hostname}${r.url}`; });
    view.querySelectorAll('[data-ok],[data-no]').forEach(b => b.onclick = () => { const [task, action] = (b.dataset.ok || b.dataset.no).split('|');
      api(`/api/jobs/${id}/approve`, { method: 'POST', json: { task, action, approve: !!b.dataset.ok } }).then(draw); });
    clearTimeout(timer); if (live || j.status === 'waiting_approval') timer = setTimeout(() => g === gen && draw(), 2500);
  }
  await draw();
}

async function statusView(g) {
  const s = await api('/api/status');
  if (g !== gen) return;
  const m = s.memory || {};
  view.innerHTML = `<p><a href="#/">Back</a></p><section class="card"><h1>This NEURON</h1><div class="stats">
    <div class="stat"><b>${s.online ? 'Online' : 'Offline'}</b><span>Internet</span></div>
    <div class="stat"><b>${m.available_mb ? Math.round(m.available_mb / 1024 * 10) / 10 + ' GB' : '?'}</b><span>Memory free of ${m.total_mb ? Math.round(m.total_mb / 1024) + ' GB' : '?'}</span></div>
    <div class="stat"><b>${esc(s.loaded_model || 'none')}</b><span>Model in memory</span></div>
    <div class="stat"><b>${s.load?.load_1min ?? '?'}</b><span>CPU load (${s.load?.cpus || '?'} cores)</span></div></div>
    <h2 style="margin-top:18px">Model</h2><p class="note">${s.models?.problem ? esc(s.models.problem) : 'Memory tier ' + esc(s.models?.tier || '?') + ', model ' + esc(s.models?.builder || 'not chosen yet')}</p>
    <p class="note">Online boost: ${s.models?.online_boost?.on ? 'on, ' + esc(s.models.online_boost.provider) + ' for ' + esc((s.models.online_boost.roles || []).join(' and ')) + ' when the internet is up' : 'off (NEURON works fully on this computer)'}</p>
    <p class="note">Working on: ${esc(s.current_job || 'nothing')} · waiting: ${s.queue.length}</p></section>`;
}

async function route() {
  clearTimeout(timer);
  const g = ++gen;
  const h = location.hash || '#/';
  try {
    if (h === '#/pair') return pairView();
    const me = await api('/api/me'); if (g !== gen) return; if (!me.paired) { location.hash = '#/pair'; return; }
    pill();
    if (h.startsWith('#/job/')) return jobView(h.slice(6), g);
    if (h === '#/status') return statusView(g);
    return homeView(g);
  } catch (e) { if (e.message !== 'not paired' && g === gen) view.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}
window.addEventListener('hashchange', route);
route(); setInterval(pill, 30000);
