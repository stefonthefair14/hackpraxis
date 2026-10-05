/* HackPraxis client. Vanilla JS, no build step, no external calls. */
'use strict';

const S = {
  meta: null,
  tools: {},
  modules: [],
  projects: [],
  active: null,          // active project slug
  activeProject: null,   // full object
  view: 'home',          // 'home' | module id
  tab: 'workspace',      // 'workspace' | 'learn'
  engine: {},            // module id -> engine id
  lastResults: null,
  findingsCache: { discovered: [], forbidden: [], reachable: [] },
  formCache: {},         // module id -> {field: value}  (survives tab switches)
  resultsCache: {},      // module id -> last run data
  _modId: null,          // module currently being rendered (for fieldWidget)
};

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = j.detail || msg; } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}
function jpost(path, body) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
}

function toast(msg, kind = '') {
  const t = $('#toast');
  t.textContent = msg; t.className = 'toast ' + kind; t.hidden = false;
  clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, 3200);
}

/* ---------------- boot ---------------- */
async function boot() {
  try {
    const [meta, tools, mods, projects] = await Promise.all([
      api('/api/meta'), api('/api/tools'), api('/api/modules'), api('/api/projects'),
    ]);
    S.meta = meta; S.tools = tools; S.modules = mods; S.projects = projects;
    $('#brand-ver').textContent = 'v' + meta.version;
    mods.forEach(m => { S.engine[m.id] = m.engines[0].id; });
    if (projects.length) setActive(projects[0].slug, false);
  } catch (e) {
    toast('Failed to load: ' + e.message, 'err');
  }
  render();
  wireChrome();
}

function setActive(slug, rerender = true) {
  S.active = slug;
  S.activeProject = S.projects.find(p => p.slug === slug) || null;
  if (rerender) render();
}

/* ---------------- top banner ---------------- */
function renderTopbar() {
  if (S.meta) $('#brand-ver').textContent = 'v' + S.meta.version;
  const order = ['ffuf', 'curl'];
  $('#tools-list').innerHTML = order.map(t => `
    <span class="tool-chip" title="${S.tools[t] ? 'found on PATH' : 'not installed'}">
      <span class="dot ${S.tools[t] ? 'on' : 'off'}"></span>${t}</span>`).join('');
  const dd = $('#project-dd');
  const opts = S.projects.map(p =>
    `<option value="${esc(p.slug)}" ${p.slug === S.active ? 'selected' : ''}>${esc(p.name)}</option>`).join('');
  dd.innerHTML = (S.projects.length ? opts : '<option value="" disabled selected>No project</option>')
    + '<option value="__new">+ New project…</option>';
  dd.onchange = () => {
    if (dd.value === '__new') { dd.value = S.active || ''; openModal(); return; }
    if (dd.value) setActive(dd.value);
  };
}

/* ---------- workflow steps (top stepper) ---------- */
const STEPS = [
  { n: 1, label: 'Enumeration', sub: 'Map the target', module: 'enumeration' },
  { n: 2, label: 'Bypassing', sub: 'Reach the forbidden', module: 'bypass_401_403' },
  { n: 3, label: 'Injection', sub: 'Exploit a parameter', module: 'path_traversal',
    types: [
      { id: 'path_traversal', label: 'Path Traversal' },
      { id: 'sqli', label: 'SQL Injection' },
      { id: 'xss', label: 'XSS' },
    ] },
];

function stepForModule(id) {
  return STEPS.find(s => s.module === id || (s.types || []).some(t => t.id === id));
}

const CHECK_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';

function stepperHTML(activeModuleId) {
  const active = stepForModule(activeModuleId);
  const enumDone = (S.findingsCache.discovered || []).length > 0;
  return `<nav class="stepper" aria-label="Workflow">${STEPS.map((s, i) => {
    const isActive = active && active.n === s.n;
    const done = s.module === 'enumeration' && enumDone && !isActive;
    return `${i ? '<span class="step-conn"></span>' : ''}
      <button class="step ${isActive ? 'active' : ''} ${done ? 'done' : ''}" data-module="${s.module}">
        <span class="step-dot">${done ? CHECK_SVG : s.n}</span>
        <span class="step-text"><span class="step-label">Step ${s.n}: ${esc(s.label)}</span>
          <span class="step-sub">${esc(s.sub)}</span></span>
      </button>`;
  }).join('')}</nav>`;
}

function wireStepper(root) {
  $$('.step', root).forEach(el => el.onclick = () => {
    S.view = el.dataset.module; S.tab = 'workspace'; S.lastResults = null; render();
  });
}

/* ---------------- main render ---------------- */
function render() {
  renderTopbar();
  if (S.view === 'home') return renderHome();
  return renderModule(S.modules.find(m => m.id === S.view));
}

/* ---------- home / project & scope ---------- */
async function renderHome() {
  await loadFindings();
  const main = $('#main');
  main.innerHTML = `
    ${stepperHTML(null)}
    <div class="page-head">
      <h1>Project &amp; scope</h1>
      <p>Define where you're authorized to test, then work the steps above. Nothing runs against a host outside the active project's scope.</p>
    </div>
    <div class="home-row">
      <div class="block" id="home-project"></div>
      <div class="block">
        <p class="block-label">Scope check</p>
        <div class="scope-check">
          <input type="text" id="sc-input" placeholder="https://host.example.com/path">
          <button class="btn" id="sc-btn">Check</button>
        </div>
        <div class="scope-result" id="sc-result"></div>
      </div>
    </div>`;
  wireStepper(main);
  renderHomeProject();
  $('#sc-btn').onclick = runScopeCheck;
  $('#sc-input').addEventListener('keydown', e => { if (e.key === 'Enter') runScopeCheck(); });
}

function renderHomeProject() {
  const el = $('#home-project');
  if (!el) return;
  if (!S.activeProject) {
    el.innerHTML = `<p class="block-label">Active project</p>
      <div class="empty-note">No project yet. Scope is required before any run.<br><br>
      <button class="btn btn-primary" id="hp-new">Create a project</button></div>`;
    $('#hp-new').onclick = openModal;
    return;
  }
  const p = S.activeProject;
  const row = (cls, tag, vals) => `<div class="row"><span class="tag ${cls}">${tag}</span>
    <span class="vals">${vals.length ? vals.map(h => `<span class="pill ${cls}">${esc(h)}</span>`).join('') : '<span class="pill empty">none</span>'}</span></div>`;
  el.innerHTML = `<p class="block-label">Active project</p>
    <div class="proj-active"><span class="pname">${esc(p.name)}</span>
      <button class="link-btn" id="hp-edit">Edit / switch</button></div>
    <div class="proj-scopes">
      ${row('in', 'in', p.in_scope || [])}
      ${row('out', 'out', p.out_of_scope || [])}
    </div>`;
  $('#hp-edit').onclick = openModal;
}

async function runScopeCheck() {
  const target = $('#sc-input').value.trim();
  const out = $('#sc-result');
  if (!S.active) { out.innerHTML = `<div class="banner warn">Select a project first.</div>`; return; }
  if (!target) return;
  try {
    const r = await jpost('/api/scope/check', { project_slug: S.active, target });
    out.innerHTML = `<div class="banner ${r.allowed ? 'ok' : 'danger'}">${r.allowed ? 'In scope' : 'Rejected'}: ${esc(r.reason)}</div>`;
  } catch (e) { out.innerHTML = `<div class="banner danger">${esc(e.message)}</div>`; }
}

/* ---------- module view ---------- */
function renderModule(mod) {
  if (!mod) { S.view = 'home'; return renderHome(); }
  const main = $('#main');
  const step = stepForModule(mod.id);
  const typeRow = (step && step.types && step.types.length > 1) ? `
    <div class="itype-row">
      <span class="itype-label">Type</span>
      ${step.types.map(t => `<button class="itype ${t.id === mod.id ? 'active' : ''} ${t.soon ? 'soon' : ''}"
        ${t.soon ? 'disabled' : `data-module="${t.id}"`}>${esc(t.label)}${t.soon ? '<span class="soon-tag">soon</span>' : ''}</button>`).join('')}
    </div>` : '';
  main.innerHTML = `
    ${stepperHTML(mod.id)}
    <div class="page-head">
      <h1>${step ? `Step ${step.n}: ` : ''}${esc(mod.title)}</h1>
      <p>${esc(mod.blurb)}</p>
    </div>
    ${typeRow}
    <div class="section-tabs">
      <div class="section-tab ${S.tab === 'workspace' ? 'active' : ''}" data-tab="workspace">Workspace</div>
      <div class="section-tab ${S.tab === 'learn' ? 'active' : ''}" data-tab="learn">Learn</div>
    </div>
    <div id="mod-body"></div>`;
  wireStepper(main);
  $$('.itype[data-module]', main).forEach(b => b.onclick = () => {
    S.view = b.dataset.module; S.tab = 'workspace'; S.lastResults = null; render();
  });
  $$('.section-tab').forEach(t => t.onclick = () => { S.tab = t.dataset.tab; renderModule(mod); });
  if (S.tab === 'learn') return renderLearn(mod);
  renderWorkspace(mod);
}

async function renderLearn(mod) {
  const body = $('#mod-body');
  body.innerHTML = `<div class="learn" id="learn-content"><p>Loading…</p></div>`;
  try { $('#learn-content').innerHTML = (await api('/api/content/' + mod.id)).html; }
  catch { $('#learn-content').innerHTML = '<p>No learning content found.</p>'; }
}

async function renderWorkspace(mod) {
  const body = $('#mod-body');
  S._modId = mod.id;
  await loadFindings();   // so url_combo datalists have the reachable pool
  const engine = S.engine[mod.id];
  const multiEngine = mod.engines.length > 1;
  const engineBlock = multiEngine ? `
    <div class="field-label" style="margin-bottom:8px">Engine</div>
    <div class="engine-row">${mod.engines.map(e => `
      <div class="engine-opt ${e.id === engine ? 'active' : ''}" data-engine="${e.id}">
        ${esc(e.label)}<span class="eh">${esc(e.hint)}</span></div>`).join('')}</div>` : '';

  const fields = mod.fields.filter(f => !f.engines || f.engines.includes(engine));
  const fieldHtml = fields.map(f => fieldWidget(f)).join('');

  const framePanel = mod.has_iframe ? `
    <div class="panel" style="margin-bottom:18px">
      <div class="panel-head"><h3>Live page</h3>
        <span class="ph-note"><a id="frame-open" href="#" target="_blank" rel="noopener">open in new tab &#8599;</a></span></div>
      <div class="panel-body">
        <div class="frame-note">Try it yourself in the real page. Some sites block being framed (X-Frame-Options) - use "open in new tab" if it stays blank.</div>
        <iframe id="hp-frame" class="hp-frame" referrerpolicy="no-referrer"
          sandbox="allow-scripts allow-forms allow-popups allow-modals allow-same-origin"></iframe>
      </div>
    </div>` : '';

  body.innerHTML = `
    <div class="workspace">
      <div>
        <div class="panel">
          <div class="panel-head"><h3>Configure</h3></div>
          <div class="panel-body">
            ${engineBlock}
            ${fieldHtml}
            <div class="btn-row">
              <button class="btn" id="btn-preview">Preview command</button>
              <button class="btn btn-primary" id="btn-run">Run</button>
            </div>
          </div>
        </div>
      </div>
      <div>
        <div id="run-guard"></div>
        <div id="aux-top"></div>
        ${framePanel}
        <div class="panel term">
          <div class="panel-head term-head"><span class="term-dots"><i></i><i></i><i></i></span>
            <h3>Command preview</h3>
            <span class="ph-note">the exact CLI HackPraxis will run</span></div>
          <div class="panel-body" id="preview-area">
            <div class="empty-note">Fill in the fields and hit <b>Preview command</b> to see the exact command and what every flag means.</div>
          </div>
        </div>
        <div class="results" id="results-area"></div>
        <div id="aux-bottom"></div>
      </div>
    </div>`;

  $$('.engine-opt', body).forEach(el => el.onclick = () => {
    S.engine[mod.id] = el.dataset.engine; renderModule(mod);
  });
  $('#btn-preview').onclick = () => doPreview(mod);
  $('#btn-run').onclick = () => doRun(mod);
  wireScopeSelects(body);

  // remember field values across tab switches; refresh the iframe on target change
  const saveForm = () => { S.formCache[mod.id] = collectParams(mod); };
  body.addEventListener('input', e => { if (e.target.dataset && e.target.dataset.field) saveForm(); });
  body.addEventListener('change', e => {
    saveForm();
    if (mod.has_iframe && e.target.dataset && e.target.dataset.field === 'target') updateFrame();
  });
  if (mod.has_iframe) updateFrame();

  renderRunGuard();
  // restore the last results for this module so switching tabs doesn't lose them
  if (S.resultsCache[mod.id]) $('#results-area').innerHTML = renderResults(S.resultsCache[mod.id]);
  if (mod.produces_findings) renderEnumFindings();
  if (mod.id === 'bypass_401_403') renderForbiddenPicker();
}

function iframeSrc(t) {
  if (!t) return '';
  let u = t.replace(/FUZZ/g, '').replace(/[?&]$/, '');
  if (u && u.indexOf('://') === -1) u = 'https://' + u;
  return u;
}
function updateFrame() {
  const fr = $('#hp-frame'); if (!fr) return;
  const inp = $('[data-field="target"]');
  const src = iframeSrc(inp ? inp.value.trim() : '');
  const open = $('#frame-open');
  if (src) { if (fr.src !== src) fr.src = src; if (open) open.href = src; }
  else { fr.removeAttribute('src'); if (open) open.href = '#'; }
}

/* ---------- findings (discovered + forbidden + reachable pool) ---------- */
async function loadFindings() {
  const empty = { discovered: [], forbidden: [], reachable: [] };
  if (!S.active) { S.findingsCache = empty; return S.findingsCache; }
  try { S.findingsCache = await api('/api/projects/' + S.active + '/findings'); }
  catch { S.findingsCache = empty; }
  return S.findingsCache;
}

function feLink(url) {
  return `<a href="${esc(url)}" target="_blank" rel="noopener" class="fe-link">${esc(url)}</a>`;
}
function groupByStatus(list, key) {
  const g = {};
  list.forEach(d => { const s = key(d); (g[s] = g[s] || []).push(d); });
  return g;
}

function discoveredPanel(list) {
  if (!list || !list.length) {
    return `<div class="panel" style="margin-top:22px"><div class="panel-head"><h3>Discovered endpoints</h3></div>
      <div class="panel-body"><div class="empty-note">No endpoints saved yet. Run a scan to populate this list and the project's <code>discovered.txt</code>.</div></div></div>`;
  }
  const forb = list.filter(d => d.status === 401 || d.status === 403).length;
  const g = groupByStatus(list, d => d.status);
  const statuses = Object.keys(g).map(Number).sort((a, b) => a - b);
  const acc = statuses.map(st => {
    const rows = g[st].map(d => `<div class="fe-row">${feLink(d.url)}${d.length ? `<span class="fe-size">${d.length} b</span>` : ''}</div>`).join('');
    const open = (st === 401 || st === 403) ? 'open' : '';
    return `<details class="acc" ${open}><summary>
        <span class="status-badge ${statusClass(st)}">${st}</span>
        <span class="acc-count">${g[st].length} endpoint${g[st].length > 1 ? 's' : ''}</span></summary>
      <div class="acc-body">${rows}</div></details>`;
  }).join('');
  return `<div class="panel" style="margin-top:22px">
    <div class="panel-head"><h3>Discovered endpoints</h3>
      <span class="ph-note">${list.length} saved${forb ? ` · ${forb} forbidden → Bypass` : ''}</span></div>
    <div class="panel-body">${acc}
      <p style="color:var(--faint);font-size:12px;margin-top:12px">Grouped by status. Saved to <code>discovered.txt</code> in this project's folder.</p>
    </div></div>`;
}

async function renderEnumFindings() {
  const el = $('#aux-bottom'); if (!el) return;
  el.innerHTML = discoveredPanel((await loadFindings()).discovered);
}

async function renderForbiddenPicker() {
  const el = $('#aux-top'); if (!el) return;
  const f = await loadFindings();
  const n = (f.forbidden || []).length;
  if (!n) {
    el.innerHTML = `<div class="banner info">No 401/403 endpoints yet. Run <b>Step 1: Enumeration</b>; forbidden endpoints are tested here automatically.</div>`;
    return;
  }
  const items = f.forbidden.map(d => `<div class="fe-row">
    <span class="status-badge ${statusClass(d.status)}">${d.status}</span>${feLink(d.url)}</div>`).join('');
  el.innerHTML = `<div class="banner info">Will test all <b>${n}</b> forbidden endpoint${n > 1 ? 's' : ''} from enumeration. Hit <b>Run</b> to see which bypasses work.</div>
    <details class="acc" style="margin-bottom:18px"><summary><span class="acc-count">Show the ${n} endpoint${n > 1 ? 's' : ''} to be tested</span></summary>
      <div class="acc-body">${items}</div></details>`;
}

function scopeHosts() {
  const raw = (S.activeProject && S.activeProject.in_scope) || [];
  const seen = new Set(); const out = [];
  raw.forEach(h => { let x = (h || '').trim(); if (x.startsWith('*.')) x = x.slice(2);
    if (x && !seen.has(x)) { seen.add(x); out.push(x); } });
  return out;
}
function reachableUrls() {
  return (S.findingsCache && S.findingsCache.reachable) || [];
}
// cached form value for the module currently being rendered
function fcGet(name, def) {
  const fc = S.formCache[S._modId] || {};
  return (name in fc) ? fc[name] : def;
}

function fieldWidget(f) {
  const hint = f.hint ? ` <span class="hint">${esc(f.hint)}</span>` : '';
  const labelSpan = `<span class="field-label">${esc(f.label)}${f.required ? ' <span class="hint">required</span>' : ''}${hint}</span>`;
  if (f.type === 'checkbox') {
    const on = fcGet(f.name, !!f.default);
    return `<label class="checkbox"><input type="checkbox" data-field="${f.name}" ${on ? 'checked' : ''}>
      <span>${esc(f.label)}</span></label>`;
  }
  if (f.type === 'scope_select') {
    const hosts = scopeHosts();
    const opts = hosts.map(h => `<option value="${esc(h)}">${esc(h)}</option>`).join('')
      + '<option value="__custom">Custom URL…</option>';
    return `<label class="field">${labelSpan}
      <select class="scopesel-dd" data-scopesel="${f.name}">${opts}</select>
      <input type="text" class="scopesel-custom" data-field="${f.name}" placeholder="${esc(f.placeholder || 'https://…')}" ${hosts.length ? 'hidden' : ''}>
    </label>`;
  }
  if (f.type === 'url_combo') {
    const urls = reachableUrls();
    const listId = 'ul-' + f.name;
    const opts = urls.map(u => `<option value="${esc(u.url)}">${esc(u.label || '')}</option>`).join('');
    const val = fcGet(f.name, '');
    return `<label class="field">${labelSpan}
      <input type="text" class="url-combo" data-field="${f.name}" list="${listId}" autocomplete="off"
        placeholder="${esc(f.placeholder || 'https://…')}" value="${esc(val)}">
      <datalist id="${listId}">${opts}</datalist></label>`;
  }
  const type = f.type === 'number' ? 'number' : 'text';
  const val = fcGet(f.name, f.default != null ? f.default : '');
  return `<label class="field">${labelSpan}
    <input type="${type}" data-field="${f.name}" placeholder="${esc(f.placeholder || '')}" value="${esc(val)}">
  </label>`;
}

function wireScopeSelects(root) {
  $$('[data-scopesel]', root).forEach(sel => {
    const input = $(`input[data-field="${sel.dataset.scopesel}"]`, root);
    const sync = () => {
      if (sel.value === '__custom') { input.hidden = false; input.value = ''; input.focus(); }
      else { input.hidden = true; input.value = sel.value; }
    };
    sel.onchange = sync;
    const cached = (S.formCache[S._modId] || {})[sel.dataset.scopesel];
    if (cached) {
      const opt = [...sel.options].find(o => o.value === cached);
      if (opt) { sel.value = cached; input.hidden = true; input.value = cached; }
      else { sel.value = '__custom'; input.hidden = false; input.value = cached; }
    } else if (sel.value && sel.value !== '__custom') {
      input.hidden = true; input.value = sel.value;
    } else { input.hidden = false; }
  });
}

function renderRunGuard() {
  const g = $('#run-guard'); if (!g) return;
  if (!S.active) {
    g.innerHTML = `<div class="banner danger">No active project. HackPraxis needs a project scope before it can run anything.
      <button class="link-btn" id="guard-new" style="margin-left:6px">Create one</button></div>`;
    $('#guard-new').onclick = openModal;
    $('#btn-run').disabled = true;
  } else {
    g.innerHTML = `<div class="banner info">Scope: <b>${esc(S.activeProject.name)}</b>. Runs are limited to its in-scope hosts.</div>`;
    $('#btn-run').disabled = false;
  }
}

function collectParams(mod) {
  const body = $('#mod-body');
  const params = {};
  $$('[data-field]', body).forEach(el => {
    if (el.type === 'checkbox') params[el.dataset.field] = el.checked;
    else if (el.value !== '') params[el.dataset.field] = el.value;
  });
  return params;
}

async function doPreview(mod) {
  const area = $('#preview-area');
  area.innerHTML = '<div class="empty-note"><span class="spinner"></span> building…</div>';
  try {
    const plan = await jpost('/api/plan', {
      module: mod.id, engine: S.engine[mod.id], params: collectParams(mod), project_slug: S.active,
    });
    area.innerHTML = renderPlan(plan);
  } catch (e) { area.innerHTML = `<div class="banner danger">${esc(e.message)}</div>`; }
}

function renderPlan(plan) {
  if (!plan.steps.length) return `<div class="banner warn">${esc(plan.summary)}</div>`;
  let html = '';
  if (plan.missing_tools.length) {
    html += `<div class="banner warn">Missing tool(s): <b>${plan.missing_tools.map(esc).join(', ')}</b>. Install them (see README); steps needing them will be skipped.</div>`;
  }
  html += `<div class="banner info">${esc(plan.summary)}</div>`;
  const show = plan.steps.slice(0, 8);
  show.forEach(s => {
    html += `<div class="cmd-block">
      <div class="cmd-label">${esc(s.label)}</div>
      <div class="cmd-line"><span class="prompt">$</span><span>${esc(s.display)}</span></div>
      <div class="explain">${s.explain.map(x => `
        <div class="explain-row"><code>${esc(x.token)}</code><span class="mean">${esc(x.meaning)}</span></div>`).join('')}</div>
    </div>`;
  });
  if (plan.steps.length > show.length) {
    html += `<div class="cmd-label">+ ${plan.steps.length - show.length} more request(s) of the same shape…</div>`;
  }
  return html;
}

async function doRun(mod) {
  if (!S.active) { toast('Select a project first.', 'err'); return; }
  const btn = $('#btn-run'); const results = $('#results-area');
  btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Running…';
  results.innerHTML = `<div class="panel"><div class="panel-body"><div class="empty-note"><span class="spinner"></span> executing. Large matrices can take a few seconds…</div></div></div>`;
  try {
    const data = await jpost('/api/run', {
      module: mod.id, engine: S.engine[mod.id], params: collectParams(mod), project_slug: S.active,
    });
    S.lastResults = data;
    S.resultsCache[mod.id] = data;   // survive tab switches
    results.innerHTML = renderResults(data);
    if (data.findings) {
      const el = $('#aux-bottom');
      if (el) el.innerHTML = discoveredPanel(data.findings.discovered);
      if (data.new_this_scan != null) {
        toast(`Scan parsed: ${data.new_this_scan} endpoint(s). ${data.findings.forbidden.length} are 401/403.`, 'ok');
      }
    }
  } catch (e) {
    results.innerHTML = `<div class="banner danger">${esc(e.message)}</div>`;
  } finally {
    btn.disabled = false; btn.textContent = 'Run';
  }
}

function statusClass(code) {
  if (!code) return 'sx';
  return 's' + String(code)[0];
}

function renderDetectResults(data) {
  const res = data.results || [];
  const sm = data.summary || {};
  const kind = (res.find(r => r.meta && r.meta.detect) || {}).meta.detect; // 'reflect' | 'sql-error'
  const hitWord = kind === 'reflect' ? 'reflected unescaped' : 'DB error';
  const scored = res.map(r => {
    const d = r.detect_result || {};
    return { r, status: d.status, hit: !!d.hit };
  });
  const hits = scored.filter(s => s.hit);

  const row = (s) => {
    const r = s.r;
    const link = (r.meta && r.meta.link) || '';
    const pl = esc((r.meta && r.meta.payload) || r.label || '');
    if (r.blocked) return `<div class="br-row"><span class="status-badge sx">blocked</span><span class="br-tech">${esc(r.reason || '')}</span></div>`;
    if (r.missing_tool) return `<div class="br-row"><span class="status-badge sx">no ${esc(r.missing_tool)}</span></div>`;
    const sc = s.status ? `<span class="status-badge ${statusClass(s.status)}">${s.status}</span>` : '<span class="status-badge sx">-</span>';
    return `<div class="br-row ${s.hit ? 'hit' : ''}">${sc}${feLink(link)}<span class="br-tech">${pl}</span></div>`;
  };

  let html = `<div class="panel"><div class="panel-head"><h3>${kind === 'reflect' ? 'XSS reflection' : 'SQLi'} results</h3>
      <span class="ph-note">${sm.ran ?? res.length} sent · ${hits.length} ${hitWord}</span></div><div class="panel-body">`;
  html += hits.length
    ? `<div class="banner ok">${hits.length} ${hitWord} hit(s). Open each link in the iframe or a new tab to confirm it really fires.</div>`
    : `<div class="banner info">No ${hitWord} detected automatically. Try payloads by hand in the iframe - reflection isn't always this obvious.</div>`;
  if (hits.length) {
    html += `<div class="br-worked"><div class="br-worked-h">${kind === 'reflect' ? 'Reflected unescaped' : 'Database errors'} (${hits.length})</div>${hits.map(row).join('')}</div>`;
  }
  const rest = scored.filter(s => !s.hit);
  const by = {}; const ord = [];
  rest.forEach(s => { const k = s.status || 0; if (!by[k]) { by[k] = []; ord.push(k); } by[k].push(s); });
  ord.sort((a, b) => a - b).forEach(k => {
    html += `<details class="acc"><summary><span class="status-badge ${statusClass(k)}">${k || '-'}</span><span class="acc-count">${by[k].length}</span></summary><div class="acc-body">${by[k].map(row).join('')}</div></details>`;
  });
  html += `</div></div>`;
  return html;
}

function renderBypassResults(data) {
  const res = data.results || [];
  const sm = data.summary || {};
  const order = []; const groups = {};
  res.forEach(r => {
    const ep = (r.meta && r.meta.endpoint) || '(unknown)';
    if (!groups[ep]) { groups[ep] = []; order.push(ep); }
    groups[ep].push(r);
  });

  let totalWorked = 0;
  const rowHtml = (s) => {
    const r = s.r, m = s.m;
    const link = (r.meta && r.meta.link) || (r.meta && r.meta.endpoint) || '';
    const tech = esc((r.meta && r.meta.technique) || r.label || '');
    if (r.blocked) return `<div class="br-row"><span class="status-badge sx">blocked</span><span class="br-tech">${esc(r.reason || '')}</span></div>`;
    if (r.missing_tool) return `<div class="br-row"><span class="status-badge sx">no curl</span><span class="br-tech">${tech}</span></div>`;
    if (!m) return `<div class="br-row"><span class="status-badge sx">-</span><span class="br-tech">${tech}</span></div>`;
    return `<div class="br-row ${s.ok ? 'hit' : ''}">
      <span class="status-badge ${statusClass(m.status)}">${m.status}</span>
      ${feLink(link)}<span class="br-tech">${tech}</span><span class="br-size">${m.size} b</span></div>`;
  };

  const blocks = order.map(ep => {
    const rows = groups[ep];
    const base = rows.find(r => r.meta && /^baseline/.test(r.meta.technique || ''));
    const baseStatus = base && base.metrics ? base.metrics.status : null;
    const baseSize = base && base.metrics ? base.metrics.size : null;
    const scored = rows.filter(r => r !== base).map(r => {
      const m = r.metrics;
      const ok = !!(m && baseStatus != null && (m.status !== baseStatus || Math.abs((m.size || 0) - (baseSize || 0)) > 25));
      return { r, m, ok };
    });
    const worked = scored.filter(s => s.ok && s.m && s.m.status < 400);
    totalWorked += worked.length;

    let inner = '';
    if (worked.length) {
      inner += `<div class="br-worked"><div class="br-worked-h">Bypasses that worked (${worked.length})</div>${worked.map(rowHtml).join('')}</div>`;
    }
    const rest = scored.filter(s => !(s.ok && s.m && s.m.status < 400));
    const byStatus = {}; const ord = [];
    rest.forEach(s => { const k = s.m ? s.m.status : 0; if (!byStatus[k]) { byStatus[k] = []; ord.push(k); } byStatus[k].push(s); });
    ord.sort((a, b) => a - b).forEach(k => {
      inner += `<details class="acc"><summary><span class="status-badge ${statusClass(k)}">${k || '-'}</span><span class="acc-count">${byStatus[k].length}</span></summary><div class="acc-body">${byStatus[k].map(rowHtml).join('')}</div></details>`;
    });

    const badge = baseStatus != null ? `<span class="status-badge ${statusClass(baseStatus)}">${baseStatus}</span>` : '';
    return `<details class="acc ep-acc" ${worked.length ? 'open' : ''}><summary>
        <span class="ep-sum">${badge}<span class="ep-url">${esc(ep)}</span></span>
        <span class="acc-count">${worked.length ? `<b class="ep-hit">${worked.length} worked</b>` : 'no change'}</span></summary>
      <div class="acc-body">${inner || '<div class="empty-note">No probes ran.</div>'}</div></details>`;
  }).join('');

  let html = `<div class="panel"><div class="panel-head"><h3>Bypass results</h3>
      <span class="ph-note">${order.length} endpoint(s) · ${sm.ran ?? res.length} requests${sm.blocked ? ` · ${sm.blocked} blocked` : ''}</span></div>
    <div class="panel-body">`;
  html += totalWorked
    ? `<div class="banner ok">${totalWorked} promising bypass(es) across ${order.length} endpoint(s). Open an endpoint for the link and the exact trick, then verify by visiting it.</div>`
    : `<div class="banner info">No status changed from the baseline — often the control is solid. Every endpoint's probes are still listed below.</div>`;
  html += blocks + `</div></div>`;
  return html;
}

function renderResults(data) {
  if (data.note && (!data.results || !data.results.length)) {
    return `<div class="banner warn">${esc(data.note)}</div>`;
  }
  const res = data.results || [];
  // xss/sqli curl probes carry a detect flag -> hit-grouped view
  if (res.some(r => r.meta && r.meta.detect)) return renderDetectResults(data);
  // bypass-style results carry per-endpoint meta -> grouped view
  if (res.some(r => r.meta && r.meta.endpoint)) return renderBypassResults(data);
  const sm = data.summary || {};
  const hasMetrics = res.some(r => r.metrics);
  let html = `<div class="panel"><div class="panel-head"><h3>Results</h3>
      <span style="font-size:11px;color:var(--faint)">${esc((S.activeProject || {}).name || '')}</span></div><div class="panel-body">`;
  html += `<div class="result-summary">
      <span><b>${sm.total ?? res.length}</b> requests</span>
      <span><b>${sm.ran ?? 0}</b> ran</span>
      ${sm.blocked ? `<span style="color:var(--danger)"><b>${sm.blocked}</b> blocked by scope</span>` : ''}
    </div>`;

  if (hasMetrics) {
    const baseline = res.find(r => r.metrics);
    const baseStatus = baseline && baseline.metrics ? baseline.metrics.status : null;
    const baseSize = baseline && baseline.metrics ? baseline.metrics.size : null;
    html += `<div class="table-wrap"><table class="metrics"><thead><tr>
        <th>Technique</th><th>Status</th><th>Size</th><th>Time</th></tr></thead><tbody>`;
    res.forEach((r, i) => {
      if (r.blocked) {
        html += `<tr class="blocked"><td class="label">${esc(r.label)}</td><td colspan="3">blocked: ${esc(r.reason)}</td></tr>`;
        return;
      }
      if (r.missing_tool) {
        html += `<tr><td class="label">${esc(r.label)}</td><td colspan="3" class="sx">missing tool: ${esc(r.missing_tool)}</td></tr>`;
        return;
      }
      const m = r.metrics;
      if (!m) {
        html += `<tr><td class="label">${esc(r.label)}</td><td colspan="3" class="sx">${r.timed_out ? 'timed out' : 'no response'}</td></tr>`;
        return;
      }
      const diff = i > 0 && (m.status !== baseStatus || Math.abs((m.size || 0) - (baseSize || 0)) > 25);
      html += `<tr class="${diff ? 'diff' : ''}">
        <td class="label">${esc(r.label)}</td>
        <td><span class="status-badge ${statusClass(m.status)}">${m.status}</span></td>
        <td>${m.size}</td>
        <td>${m.time != null ? m.time.toFixed(2) + 's' : '-'}</td></tr>`;
    });
    html += `</tbody></table></div>
      <p style="color:var(--faint);font-size:12px;margin-top:10px">Highlighted rows differ from the baseline. Confirm any lead by re-running that exact command and reading the body.</p>`;
  } else {
    res.forEach(r => {
      html += `<div class="cmd-label">${esc(r.label)} &nbsp; <span style="color:var(--faint)">${esc(r.display)}</span></div>`;
      if (r.blocked) { html += `<div class="banner danger">Blocked by scope: ${esc(r.reason)}</div>`; return; }
      if (r.missing_tool) { html += `<div class="banner warn">Required tool not installed: <b>${esc(r.missing_tool)}</b></div>`; return; }
      const out = esc(r.stdout || '').trim();
      const err = esc(r.stderr || '').trim();
      html += `<div class="console">${out || '<span style="color:var(--faint)">(no stdout)</span>'}${err ? `\n<span class="err">${err}</span>` : ''}</div>`;
      html += `<div style="height:14px"></div>`;
    });
  }
  html += `</div></div>`;
  return html;
}

/* ---------------- chrome + modal wiring ---------------- */
function wireChrome() {
  $('#brand-home').onclick = () => { S.view = 'home'; S.tab = 'workspace'; render(); };
  $('#btn-project-scope').onclick = () => { S.view = 'home'; S.tab = 'workspace'; render(); };
  $('#project-modal-close').onclick = closeModal;
  $('#project-modal').addEventListener('click', e => { if (e.target.id === 'project-modal') closeModal(); });
  $('#pm-save').onclick = saveProject;
}
function openModal() {
  const p = S.activeProject;
  $('#project-modal-title').textContent = p ? 'Projects' : 'New project';
  $('#pm-name').value = p ? p.name : '';
  $('#pm-inscope').value = p ? (p.in_scope || []).join('\n') : '';
  $('#pm-outscope').value = p ? (p.out_of_scope || []).join('\n') : '';
  $('#pm-notes').value = '';
  renderExisting();
  $('#project-modal').hidden = false;
}
function closeModal() { $('#project-modal').hidden = true; }

function renderExisting() {
  const box = $('#existing-projects');
  if (!S.projects.length) { box.innerHTML = ''; return; }
  box.innerHTML = `<div class="field-label" style="margin-bottom:8px">Saved projects</div>` +
    S.projects.map(p => `
      <div class="ep-row">
        <div><div class="ep-name">${esc(p.name)}</div>
          <div class="ep-scope">${(p.in_scope || []).slice(0, 3).join(', ') || 'no scope'}</div></div>
        <div class="ep-actions">
          <button class="link-btn" data-load="${p.slug}">Use</button>
          <button class="link-btn danger" data-del="${p.slug}">Delete</button>
        </div>
      </div>`).join('');
  $$('[data-load]', box).forEach(b => b.onclick = () => { setActive(b.dataset.load); closeModal(); toast('Switched project', 'ok'); });
  $$('[data-del]', box).forEach(b => b.onclick = () => deleteProject(b.dataset.del));
}

async function saveProject() {
  const name = $('#pm-name').value.trim();
  if (!name) { toast('Project needs a name', 'err'); return; }
  const lines = v => v.split('\n').map(x => x.trim()).filter(Boolean);
  try {
    const saved = await jpost('/api/projects', {
      name,
      in_scope: lines($('#pm-inscope').value),
      out_of_scope: lines($('#pm-outscope').value),
      notes: $('#pm-notes').value,
    });
    S.projects = await api('/api/projects');
    setActive(saved.slug);
    closeModal();
    toast('Project saved', 'ok');
  } catch (e) { toast(e.message, 'err'); }
}

async function deleteProject(slug) {
  try {
    await api('/api/projects/' + slug, { method: 'DELETE' });
    S.projects = await api('/api/projects');
    if (S.active === slug) {
      if (S.projects.length) setActive(S.projects[0].slug, false);
      else { S.active = null; S.activeProject = null; }
    }
    renderExisting(); render();
    toast('Project deleted');
  } catch (e) { toast(e.message, 'err'); }
}

boot();
