/* Explicit-request-only AI explanations. Merely attaching a control does no I/O. */
(function () {
  'use strict';
  let context = () => ({});
  let active = null;
  let serial = 0;
  const failedHovers = new Set();
  const terminal = new Set(['ready', 'failed', 'unavailable', 'cancelled']);
  const node = (tag, text, cls) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  };
  const button = (text, action) => {
    const el = node('button', text, 'btn btn-secondary btn-xs');
    el.type = 'button'; el.addEventListener('click', action); return el;
  };
  async function api(path, data) {
    const response = await fetch(path, {method: data ? 'POST' : 'GET',
      signal: AbortSignal.timeout(15000),
      headers: {'Content-Type': 'application/json', 'X-COC-Token': window.COC_API_TOKEN || ''},
      ...(data ? {body: JSON.stringify(data)} : {})});
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Explanation request failed.');
    return body;
  }
  function detach(job) {
    if (job?.job_id && job?.viewer) api(`/api/ai-explanations/${job.job_id}/cancel`, {viewer: job.viewer}).catch(() => {});
  }
  function close() {
    if (!active) return;
    const old = active; active = null; serial++;
    clearTimeout(old.timer); clearTimeout(old.leaveTimer);
    old.panel.remove(); detach(old.job);
    if (old.pinned && old.anchor?.isConnected) old.anchor.focus();
  }
  function panel(anchor, pinned) {
    const el = node('section', undefined, 'ai-explainer-panel');
    el.setAttribute('role', 'dialog'); el.setAttribute('aria-label', 'AI stat explanation');
    const heading = node('div', undefined, 'ai-explainer-heading');
    heading.append(node('strong', 'AI historian / adviser'), button('Close / Cancel', close));
    const body = node('div'); body.setAttribute('aria-live', 'polite');
    el.append(heading, body); document.body.appendChild(el);
    el.addEventListener('pointerenter', () => { if (active) clearTimeout(active.leaveTimer); });
    el.addEventListener('pointerleave', scheduleHoverClose);
    el.addEventListener('click', () => { if (active) active.pinned = true; });
    el.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
    return {panel: el, body, anchor, pinned, world: context().world_id, token: ++serial};
  }
  function scheduleHoverClose() {
    if (active && !active.pinned) {
      clearTimeout(active.leaveTimer);
      active.leaveTimer = setTimeout(() => { if (active && !active.pinned) close(); }, 450);
    }
  }
  function section(body, title, text) {
    body.append(node('h4', title)); if (text) body.append(node('p', text));
  }
  function render(current, job) {
    current.job = job;
    const body = current.body; body.replaceChildren();
    const selection = current.selection;
    body.append(node('p', `${selection.entity} · ${selection.metric_id} · Turn ${selection.turn}`));
    if (!terminal.has(job.state)) {
      const loading = node('div', undefined, 'ai-loading'); loading.setAttribute('role', 'status');
      const spinner = node('span', '', 'ai-spinner'); spinner.setAttribute('aria-hidden', 'true');
      loading.append(spinner, node('span', job.message)); body.append(loading);
      body.append(node('p', 'You can keep playing. This explanation stays at the selected turn.'));
      return;
    }
    if (job.state !== 'ready') {
      failedHovers.add(current.key);
      body.append(node('p', job.message));
      body.append(button('Retry explanation', () => start(current.selection, current.anchor, true, true)));
      return;
    }
    const {packet, narrative, proposal_logs: logs = [], warnings = []} = job.result;
    const v = packet.values;
    section(body, 'What changed', `${v.before ?? 'Unknown'} → ${v.after ?? 'Unknown'} ${v.unit || ''}; delta ${v.delta ?? 'unavailable'}`);
    if (selection.display) body.append(node('p', `Chart context: ${selection.display}. Values above describe raw recorded turn boundaries.`));
    section(body, 'Why it changed');
    for (const claim of narrative.claims) {
      body.append(node('p', claim.text)); body.append(node('small', `Evidence: ${claim.level.replaceAll('_', ' ')}`));
    }
    section(body, 'A historical parallel');
    const parallel = narrative.historical_parallel;
    const history = parallel && packet.historical_candidates.find(h => h.id === parallel.entry_id);
    if (history) {
      body.append(node('strong', `${history.title} (${history.start_year}–${history.end_year})`));
      if (history.later_than_scenario) body.append(node('p', 'This comparison occurs after the scenario date.'));
      for (const text of [history.cause, history.response, history.outcome, parallel.comparison, parallel.difference, history.difference]) body.append(node('p', text));
      for (const source of history.sources) {
        const link = node('a', source.title); link.href = source.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; body.append(link);
      }
    } else body.append(node('p', 'No suitable reviewed historical parallel was selected.'));
    section(body, 'Options in this game');
    for (const advice of narrative.suggested_actions) {
      const action = packet.actions.find(a => a.id === advice.action_id);
      body.append(node('strong', action.label), node('p', advice.rationale),
        node('p', `${action.available ? 'Available at request time' : 'Blocked at request time'}: ${action.prerequisites}`),
        node('p', action.tradeoffs), node('p', `Find control: ${action.navigation}`));
      body.append(button('Review ' + action.label, async () => {
        try {
          const availability = await api(`/api/ai-explanations/${job.job_id}/availability?viewer=${encodeURIComponent(job.viewer)}`);
          if (active !== current) return;
          const fresh = availability.actions.find(a => a.id === action.id);
          const review = node('details'); review.open = true; review.append(node('summary', 'Current action review'));
          if (!fresh) review.append(node('p', 'The world or target changed. Reopen the appropriate policy control.'));
          else {
            review.append(node('p', `Turn ${availability.turn}: ${fresh.available ? 'Available' : 'Blocked'}. ${fresh.prerequisites}`), node('p', fresh.effect));
            if (fresh.command && fresh.available) review.append(button('Apply ' + fresh.label, async event => {
              if (active !== current || current.world !== context().world_id) return;
              event.currentTarget.disabled = true;
              try { const outcome = await api('/api/command', fresh.command); review.append(node('p', outcome.message || outcome.error || 'Action resolved.')); }
              catch (error) { review.append(node('p', error.message)); }
            }));
          }
          body.append(review);
          review.scrollIntoView({block: 'nearest'});
        } catch (error) { if (active === current) body.append(node('p', error.message)); }
      }));
    }
    if (!narrative.suggested_actions.length) body.append(node('p', 'No supported playable response was selected from the known catalog.'));
    body.append(node('small', 'Availability describes the captured state. Check the current control before acting.'));
    for (const [i, proposal] of narrative.future_mechanics.entries()) {
      section(body, 'Possible future mechanic — not implemented', proposal.title);
      for (const text of [proposal.unmet_need, proposal.gap_reason, proposal.proposal, proposal.tradeoffs]) body.append(node('p', text));
      const list = node('ul'); for (const criterion of proposal.acceptance_criteria) list.append(node('li', criterion)); body.append(list);
      body.append(node('p', 'Provisional design; current catalog coverage is incomplete. Requires code/design review.'));
      const log = logs[i]; body.append(node('p', log?.status === 'logged' ? `Logged for review: ${log.path}` : 'Not logged: planning folder could not be written.'));
      if (log?.status !== 'logged') body.append(button('Retry planning log', async () => {
        try { const updated = await api(`/api/ai-explanations/${job.job_id}/log`, {viewer: job.viewer}); if (active === current) render(current, updated); }
        catch (error) { if (active === current) body.append(node('p', error.message)); }
      }));
    }
    const details = node('details'); details.append(node('summary', 'Evidence and limitations'));
    for (const gap of packet.limitations) details.append(node('p', gap));
    details.append(node('p', packet.catalog_coverage));
    for (const evidence of packet.evidence) {
      const link = node('a', `${evidence.kind} · T${evidence.turn} · ${evidence.status}`);
      link.href = `/api/trace?${new URLSearchParams({event_id: evidence.event_id, boundary: packet.selection.boundary, explain: '1'})}`;
      link.target = '_blank'; link.rel = 'noopener'; details.append(link, node('br'));
    }
    body.append(details); for (const warning of warnings) body.append(node('p', warning));
  }
  async function poll(current) {
    if (active !== current) return;
    if (current.world !== context().world_id) { close(); return; }
    try {
      const job = await api(`/api/ai-explanations/${current.job.job_id}?viewer=${encodeURIComponent(current.job.viewer)}`);
      if (active !== current) return;
      render(current, job);
      if (!terminal.has(job.state)) current.timer = setTimeout(() => poll(current), 700);
    } catch (error) {
      if (active === current) render(current, {...current.job, state: 'failed', message: error.message});
    }
  }
  async function start(selection, anchor, pinned, retry = false) {
    const key = JSON.stringify(selection);
    if (!pinned && failedHovers.has(key)) return;
    if (active?.key === key && !retry) { active.pinned ||= pinned; clearTimeout(active.leaveTimer); return; }
    close(); const current = panel(anchor, pinned); current.key = key; current.selection = {...selection}; active = current;
    render(current, {state: 'collecting_evidence', message: 'Reading recorded causes…'});
    try {
      const job = await api('/api/ai-explanations', selection);
      if (active !== current || current.world !== context().world_id) { detach(job); if (active === current) close(); return; }
      render(current, job); if (!terminal.has(job.state)) current.timer = setTimeout(() => poll(current), 350);
    } catch (error) {
      if (active === current) render(current, {state: 'failed', message: error.message});
    }
  }
  function attach(container, getSelection) {
    const control = button('Explain with AI', () => start(getSelection(), control, true));
    control.classList.add('ai-explain-control'); control.title = 'Explain this stat and turn. Deliberate hover also requests an explanation.';
    let timer;
    control.addEventListener('pointerenter', event => {
      if (event.pointerType !== 'mouse' || localStorage.getItem('coc-ai-hover') === 'off') return;
      clearTimeout(timer); timer = setTimeout(() => { if (control.isConnected) start(getSelection(), control, false); }, 700);
      if (active?.anchor === control) clearTimeout(active.leaveTimer);
    });
    control.addEventListener('pointerleave', () => { clearTimeout(timer); if (active?.anchor === control) scheduleHoverClose(); });
    control.addEventListener('keydown', () => clearTimeout(timer));
    container.append(control); return control;
  }
  async function chooser(anchor) {
    close(); const current = panel(anchor, true); active = current;
    current.body.append(node('p', 'Choose a stat and completed turn. No generation occurs until you request it.'));
    try {
      const data = await api('/api/ai-metrics'); if (active !== current) return;
      const form = node('form'); const ctx = context();
      function input(label, value, list) {
        const wrap = node('label', label); const field = node('input'); field.value = value || '';
        if (list) { const choices = node('datalist'); choices.id = 'ai-choices-' + label.replaceAll(' ', '-');
          for (const option of list) { const opt = node('option'); opt.value = option; choices.append(opt); }
          field.setAttribute('list', choices.id); wrap.append(choices); }
        wrap.append(field); form.append(wrap); return field;
      }
      const entity = input('Entity', ctx.entity, ctx.entities);
      const metric = input('Metric', 'finance.treasury', data.metrics.map(m => m.id));
      const turn = input('Turn', ctx.turn); turn.type = 'number'; turn.min = 0; turn.max = ctx.turn;
      const good = input('Good (if applicable)', '');
      const disease = input('Disease (if applicable)', '');
      const group = input('Class group (if applicable)', '');
      const submit = node('button', 'Generate explanation', 'btn'); submit.type = 'submit'; form.append(submit);
      form.addEventListener('submit', event => { event.preventDefault(); const selection = {entity: entity.value, metric_id: metric.value, turn: Number(turn.value)};
        if (good.value) selection.good = good.value; if (disease.value) selection.disease = disease.value; if (group.value) selection.class_group = group.value;
        start(selection, anchor, true); });
      const setting = node('label', 'Enable deliberate hover on AI controls '); const check = node('input'); check.type = 'checkbox';
      check.checked = localStorage.getItem('coc-ai-hover') !== 'off'; check.addEventListener('change', () => localStorage.setItem('coc-ai-hover', check.checked ? 'on' : 'off')); setting.append(check);
      current.body.append(form, setting);
    } catch (error) { if (active === current) current.body.append(node('p', error.message)); }
  }
  function setContext(getContext) {
    context = getContext;
    const launcher = button('AI: explain a stat', () => chooser(launcher)); launcher.classList.add('ai-explainer-launcher'); document.body.append(launcher);
    // Local lifecycle monitoring only: no generation, polling or network on turns.
    setInterval(() => { if (active && active.world !== context().world_id) close(); }, 500);
  }
  window.CoCAIExplainer = {attach, setContext, close};
}());
