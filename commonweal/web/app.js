'use strict';
const GRID_W = 20, GRID_H = 12;
const LEFT = [
  ['gdp', 'Measured output (GDP) per person', '#e3b341', 2],
  ['output', 'Real food output per person', '#c9a24a', 2],
  ['capital', 'Capital stock (machinery)', '#b8860b', 0],
  ['wealth_gini', 'Wealth concentration (Gini)', '#d08a3c', 2],
];
const RIGHT = [
  ['med_health', 'Median health', '#6fbf73', 2],
  ['free_hours', 'Free hours per day', '#5fb3a1', 1],
  ['lifespan', 'Mean age at death (80-season window)', '#8cc56e', 0],
  ['ties', 'Social ties per adult', '#6aa9d8', 1],
  ['culture', 'Living culture (shared practices)', '#b48ad8', 2],
  ['commons', 'Commons (forest, pasture, fish)', '#7fae5a', 2],
  ['wellbeing', 'Wellbeing', '#e08f9f', 2],
  ['landless', 'Share with no land', '#d9604c', 2],
];
const CLASS_COLOR = { employer:'#e3b341', owner:'#c9a24a', smallholder:'#8cc56e', wage:'#6aa9d8', landless:'#d9604c' };
let state = null, playing = false, timer = null, selected = null;

const $ = (id) => document.getElementById(id);
const api = (path, body) => fetch(path, body === undefined ? {} : { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) }).then(r => r.json());

function yearly(v) { // average each year (4 seasons) for smooth charts
  const out = [];
  for (let i = 0; i < v.length; i += 4) { const s = v.slice(i, i + 4); out.push(s.reduce((a, b) => a + b, 0) / s.length); }
  return out;
}

function buildCharts(el, defs) {
  el.innerHTML = '';
  defs.forEach(([key, name]) => {
    const d = document.createElement('div'); d.className = 'chart'; d.id = 'c-' + key;
    d.innerHTML = '<div class="row"><span class="name"></span><span class="val"></span></div><canvas></canvas>';
    d.querySelector('.name').textContent = name;
    el.appendChild(d);
  });
}

function drawChart(key, color, dec, goodUp) {
  const box = $('c-' + key); if (!box) return;
  const v = yearly(state.series[key] || []);
  const cv = box.querySelector('canvas');
  const w = cv.clientWidth * devicePixelRatio, h = cv.clientHeight * devicePixelRatio;
  cv.width = w; cv.height = h;
  const g = cv.getContext('2d');
  if (v.length < 2) return;
  const lo = Math.min(...v, 0), hi = Math.max(...v) * 1.08 || 1;
  g.strokeStyle = color; g.lineWidth = 2 * devicePixelRatio; g.beginPath();
  v.forEach((y, i) => { const px = i / (v.length - 1) * (w - 4) + 2, py = h - 3 - (y - lo) / (hi - lo || 1) * (h - 8); i ? g.lineTo(px, py) : g.moveTo(px, py); });
  g.stroke();
  const first = v[0], last = v[v.length - 1];
  const pct = first ? (last / first - 1) * 100 : 0;
  const cls = Math.abs(pct) < 1 ? '' : (pct > 0) === goodUp ? 'up' : 'down';
  box.querySelector('.val').innerHTML = last.toFixed(dec) + ' <span class="' + cls + '">' + (pct >= 0 ? '+' : '') + pct.toFixed(0) + '%</span>';
}

function hash(id, n) { let x = id * 2654435761 % 4294967296; return ((x >>> (n * 5)) & 255) / 255; }

function colorHealth(h) { const r = Math.round(217 - 110 * h), g = Math.round(96 + 95 * h); return `rgb(${r},${g},90)`; }

function drawMap() {
  const cv = $('map'), g = cv.getContext('2d'), cw = cv.width / GRID_W, ch = cv.height / GRID_H;
  g.clearRect(0, 0, cv.width, cv.height);
  const commons = (state.series.commons || [1]).slice(-1)[0];
  g.fillStyle = `rgba(80,140,70,${0.08 + 0.2 * commons})`; g.fillRect(0, 0, cv.width, cv.height);
  g.strokeStyle = 'rgba(255,255,255,0.04)';
  for (let x = 0; x <= GRID_W; x++) { g.beginPath(); g.moveTo(x * cw, 0); g.lineTo(x * cw, cv.height); g.stroke(); }
  for (let y = 0; y <= GRID_H; y++) { g.beginPath(); g.moveTo(0, y * ch); g.lineTo(cv.width, y * ch); g.stroke(); }
  state.people.forEach(([id, x, y, health, wb, area, cash, cls, adult]) => {
    const px = (x + 0.15 + 0.7 * hash(id, 1)) * cw, py = (y + 0.15 + 0.7 * hash(id, 2)) * ch;
    const r = adult ? 5 + Math.min(area, 4) * 1.2 : 2.5;
    g.beginPath(); g.arc(px, py, r, 0, 6.283);
    g.fillStyle = colorHealth(health); g.fill();
    if (adult) { g.lineWidth = id === selected ? 3 : 2; g.strokeStyle = id === selected ? '#fff' : CLASS_COLOR[cls]; g.stroke(); }
  });
}

function render() {
  if (!state) return;
  const years = state.year;
  $('clock').textContent = `Year ${years}, ${state.season} · pop ${state.people.length} · harvest ×${state.weather} · money ${state.money}`;
  LEFT.forEach(([k, , c, d]) => drawChart(k, c, d, true));
  RIGHT.forEach(([k, , c, d]) => drawChart(k, c, d, k !== 'landless'));
  drawMap();
  $('chronicle').innerHTML = '';
  state.chronicle.slice().reverse().forEach(([t, txt]) => {
    const d = document.createElement('div'); const b = document.createElement('b');
    b.textContent = 'Yr ' + Math.floor(t / 4) + ' '; d.appendChild(b); d.appendChild(document.createTextNode(txt)); $('chronicle').appendChild(d);
  });
  if (selected) loadPerson(selected);
}

async function loadPerson(id) {
  const p = await api('/api/person?id=' + id);
  const el = $('person'); el.innerHTML = '';
  if (p.error) { el.textContent = p.error; return; }
  const h = p.hours, tot = 16;
  const seg = (k, c) => `<i style="width:${h[k] / tot * 100}%;background:${c}" title="${k} ${h[k]}h"></i>`;
  const add = (html) => { const d = document.createElement('div'); d.innerHTML = html; el.appendChild(d); };
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;' }[c]));
  add(`<h3>${esc(p.name)} <span class="muted">${p.alive ? '' : '(dead) '}age ${p.age} · ${p.class}</span></h3>`);
  add(`<table class="kv"><tr><td>health / wellbeing</td><td>${p.health} / ${p.wellbeing}</td></tr>
    <tr><td>land (area) · dependents</td><td>${p.area} · ${p.dependents}</td></tr>
    <tr><td>cash · debt</td><td>${p.cash} · ${p.debt}</td></tr>
    <tr><td>ties (strength)</td><td>${p.ties} (${p.tie_strength})</td></tr>
    <tr><td>grudges inherited / held</td><td>${p.grudges}</td></tr></table>`);
  add(`<h4>A day (16 waking hours)</h4><div class="bar">${seg('land','#8cc56e')}${seg('wage','#e3b341')}${seg('forage','#7fae5a')}${seg('care','#6aa9d8')}${seg('community','#b48ad8')}${seg('leisure','#555')}</div>
    <div class="muted" style="font-size:11px">land ${h.land} · wage ${h.wage} · forage ${h.forage} · care ${h.care} · community ${h.community} · rest ${h.leisure}</div>`);
  add('<h4>Practices known</h4>' + Object.entries(p.know).map(([k, v]) => `<div class="muted" style="font-size:11px">${k.replace('_', ' ')} <span style="display:inline-block;width:${v * 100}px;height:6px;background:#b48ad8"></span> ${v}</div>`).join(''));
  const tr = p.trail;
  const inc = Object.entries(tr.income_by).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${v}</td></tr>`).join('') || '<tr><td class="muted">none</td><td></td></tr>';
  add(`<h4>Money trail — where cash came from</h4><table class="kv">${inc}</table>
    <div class="muted" style="font-size:11px">biggest sources: ${tr.top_sources.map(([n, v]) => esc(n) + ' ' + v).join(', ') || '—'}</div>`);
  if (tr.employees_now || tr.hired_person_days) add(`<div class="muted" style="font-size:12px;margin-top:6px">Bought ${tr.hired_person_days} person-days of labour (${tr.employees_now} workers now, ${tr.employer_hours || '—'}h day, their mean health ${tr.employees_mean_health ?? '—'}).</div>`);
  add('<h4>Life events</h4><ul>' + p.events.slice().reverse().map(([t, x]) => `<li><b>Yr ${Math.floor(t / 4)}</b> ${esc(x)}</li>`).join('') + '</ul>');
}

function applyState(s) { state = s; render(); syncDials(); }

function syncDials() {
  const d = state.dials;
  $('d-alien').checked = d.land_alienable;
  $('d-hours').value = d.hours_cap; $('v-hours').textContent = d.hours_cap;
  $('d-levy').value = Math.round(d.relief_levy * 100); $('v-levy').textContent = Math.round(d.relief_levy * 100);
  $('d-usury').value = Math.round(d.usury_cap * 100); $('v-usury').textContent = Math.round(d.usury_cap * 100);
}

async function step(n) { applyState(await api('/api/step', { n })); }

function setPlaying(on) {
  playing = on; $('play').textContent = on ? '⏸ Pause' : '▶ Play';
  clearInterval(timer);
  if (on) timer = setInterval(() => { if (!busy) { busy = true; step(+$('speed').value).finally(() => busy = false); } }, 250);
}
let busy = false;

function bind() {
  buildCharts($('left-charts'), LEFT); buildCharts($('right-charts'), RIGHT);
  $('legend').innerHTML = Object.entries(CLASS_COLOR).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join('') + '<span>fill: red = ill, green = healthy · size = land held</span>';
  $('play').onclick = () => setPlaying(!playing);
  document.querySelectorAll('[data-step]').forEach((b) => b.onclick = () => step(+b.dataset.step));
  $('reset').onclick = async () => { selected = null; $('person').innerHTML = '<p class="muted">Click a dot on the map.</p>'; applyState(await api('/api/reset', { seed: +$('seed').value, preset: $('preset').value })); };
  $('map').onclick = (e) => {
    const cv = $('map'), r = cv.getBoundingClientRect(), sx = cv.width / r.width;
    const mx = (e.clientX - r.left) * sx, my = (e.clientY - r.top) * sx, cw = cv.width / GRID_W, ch = cv.height / GRID_H;
    let best = null, bd = 400;
    state.people.forEach(([id, x, y]) => { const px = (x + 0.15 + 0.7 * hash(id, 1)) * cw, py = (y + 0.15 + 0.7 * hash(id, 2)) * ch; const d = (px - mx) ** 2 + (py - my) ** 2; if (d < bd) { bd = d; best = id; } });
    if (best) { selected = best; render(); }
  };
  const push = () => api('/api/dials', { land_alienable: $('d-alien').checked, hours_cap: +$('d-hours').value, relief_levy: +$('d-levy').value / 100, usury_cap: +$('d-usury').value / 100 }).then(applyState);
  ['d-alien', 'd-hours', 'd-levy', 'd-usury'].forEach((id) => $(id).onchange = push);
  window.onresize = render;
}

(async () => {
  bind();
  const s = await api('/api/state');
  const sel = $('preset');
  Object.entries(s.presets).forEach(([k, d]) => { const o = document.createElement('option'); o.value = k; o.textContent = d; sel.appendChild(o); });
  applyState(s);
})();
