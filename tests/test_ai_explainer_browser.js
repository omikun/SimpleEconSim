/* Run from the repository root with NODE_PATH pointing at the bundled Playwright. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

async function setup(page) {
  page.setDefaultTimeout(7000);
  await page.route('http://fixture.local/**', route => route.fulfill({contentType: 'text/html', body: '<meta name="viewport" content="width=device-width,initial-scale=1"><main id="target" style="padding:20px"></main>'}));
  await page.goto('http://fixture.local/');
  await page.addStyleTag({path: path.join(root, 'web_client/style.css')});
  await page.evaluate(() => {
    window.ctx = {world_id: 'world-a', turn: 3, entity: 'tile:Delta', entities: ['tile:Delta', 'nation:Egypt']};
    window.calls = 0; window.generations = 0; window.cancelled = 0; window.executions = 0; window.release = false; window.jobs = {}; window.cache = {};
    window.COC_API_TOKEN = 'fixture-token';
    const result = {
      packet: {selection: {boundary: 100}, values: {before: 20, after: 30, delta: 10, unit: 'C'},
        historical_candidates: [{id: 'history', title: 'Reviewed historical episode', start_year: 1848, end_year: 1848,
          cause: 'Recorded historical context.', response: 'A documented response.', outcome: 'A limited documented outcome.',
          difference: 'Historical institutions differ.', sources: [{title: 'Primary source', url: 'https://www.legislation.gov.uk/'}]}],
        actions: [{id: 'relief', label: 'Existing relief', available: false, prerequisites: 'Requires reserves.', tradeoffs: 'Uses stored food.', navigation: 'Policies → Relief'}],
        evidence: [{kind: 'calculation', turn: 3, status: 'verified_formula', event_id: 'run:1'}],
        limitations: ['Upstream coverage is incomplete.'], catalog_coverage: 'Known catalog is incomplete.'},
      narrative: {claims: [{text: 'Recorded output explains part of the change.', level: 'verified_formula'}],
        historical_parallel: {entry_id: 'history', comparison: 'The mechanism has a useful parallel.', difference: 'The institutions differ.'},
        suggested_actions: [{action_id: 'relief', rationale: 'Immediate relief can address hunger if funded.'}],
        future_mechanics: [{title: 'Water-source protection', unmet_need: 'Prevent exposure.', gap_reason: 'Care does not prevent exposure.',
          proposal: 'Add a maintained protection project.', tradeoffs: 'Construction and upkeep consume resources.', acceptance_criteria: ['Record the exposure effect.']}]},
      proposal_logs: [{status: 'not_logged'}], warnings: []};
    window.fetch = async (url, options = {}) => {
      assertToken(options.headers);
      function assertToken(headers) { if (headers['X-COC-Token'] !== 'fixture-token') throw new Error('Missing authentication'); }
      if (url === '/api/ai-metrics') return {ok: true, json: async () => ({metrics: [{id: 'economy.gdp_nominal'}]})};
      if (url.includes('/availability?')) return {ok: true, json: async () => ({state: 'current', turn: 3,
        actions: [{...result.packet.actions[0], available: true, effect: 'Feeds selected hungry households.',
          command: {cmd: 'SET_POLICY', payload: {key: 'granary_relief', val: true}}}]})};
      if (url === '/api/command') { window.executions++; return {ok: true, json: async () => ({success: true, message: 'Action resolved.'})}; }
      if (url.endsWith('/cancel')) { window.cancelled++; return {ok: true, json: async () => ({state: 'cancelled'})}; }
      if (url.endsWith('/log')) {
        result.proposal_logs = [{status: 'logged', path: 'planning/potential_future_mechanisms/fixture.json'}];
        const job = Object.values(window.jobs).at(-1);
        return {ok: true, json: async () => ({...job, state: 'ready', result})};
      }
      if (url === '/api/ai-explanations') {
        window.calls++; const selection = JSON.parse(options.body); const key = JSON.stringify(selection);
        if (!window.cache[key]) { window.generations++; window.cache[key] = true; }
        const id = 'job-' + window.calls; const job = {job_id: id, viewer: 'viewer-' + id, state: window.release ? 'ready' : 'generating',
          message: 'Writing the explanation…', result: window.release ? result : null}; window.jobs[id] = job;
        if (window.delaySubmit) await new Promise(resolve => { window.resolveSubmit = resolve; });
        return {ok: true, json: async () => job};
      }
      const id = url.split('/').at(-1).split('?')[0];
      return {ok: true, json: async () => ({...window.jobs[id], state: window.release ? 'ready' : 'generating',
        message: 'Writing the explanation…', result: window.release ? result : null})};
    };
  });
  await page.addScriptTag({path: path.join(root, 'web_client/ai_explainer.js')});
  await page.evaluate(() => {
    CoCAIExplainer.setContext(() => ctx);
    CoCAIExplainer.attach(document.querySelector('#target'), () => ({entity: 'tile:Delta', metric_id: 'economy.gdp_nominal', turn: 3}));
  });
}

(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  try {
    const page = await browser.newPage({viewport: {width: 1100, height: 900}}); await setup(page);
    await page.waitForTimeout(800); assert.equal(await page.evaluate(() => calls), 0);
    const control = page.getByRole('button', {name: 'Explain with AI', exact: true});
    await control.focus(); await page.waitForTimeout(750); assert.equal(await page.evaluate(() => calls), 0);
    await control.hover(); await page.waitForTimeout(180); await page.mouse.move(900, 30); await page.waitForTimeout(650);
    assert.equal(await page.evaluate(() => calls), 0);
    await control.hover(); await page.waitForTimeout(800);
    await page.getByRole('status').waitFor(); assert.equal(await page.evaluate(() => calls), 1);
    await control.click(); assert.equal(await page.evaluate(() => calls), 1); // pin, don't duplicate
    await page.screenshot({path: path.join(root, 'tmp/ai-explainer-loading.png')});
    await page.evaluate(() => { release = true; });
    await page.getByRole('heading', {name: 'What changed', exact: true}).waitFor();
    await page.getByRole('heading', {name: 'Possible future mechanic — not implemented', exact: true}).waitFor();
    assert.equal(await page.getByRole('button', {name: /Water-source protection/}).count(), 0);
    await page.getByRole('button', {name: 'Retry planning log', exact: true}).click();
    await page.getByText('Logged for review: planning/potential_future_mechanisms/fixture.json', {exact: true}).waitFor();
    assert.equal(await page.evaluate(() => generations), 1);
    await page.screenshot({path: path.join(root, 'tmp/ai-explainer-result.png')});
    await page.getByRole('button', {name: 'Review Existing relief', exact: true}).click();
    await page.getByRole('button', {name: 'Apply Existing relief', exact: true}).waitFor();
    assert.equal(await page.evaluate(() => executions), 0);
    await page.getByRole('button', {name: 'Apply Existing relief', exact: true}).click();
    await page.getByText('Action resolved.', {exact: true}).waitFor();
    assert.equal(await page.evaluate(() => executions), 1); assert.equal(await page.evaluate(() => generations), 1);
    await page.getByRole('button', {name: 'Close / Cancel', exact: true}).click();
    await control.click(); await page.getByRole('heading', {name: 'What changed', exact: true}).waitFor();
    assert.equal(await page.evaluate(() => generations), 1);
    await page.getByRole('button', {name: 'Close / Cancel', exact: true}).click();
    await page.evaluate(() => { release = false; delaySubmit = true; });
    await control.click(); await page.getByRole('status').waitFor();
    await page.evaluate(() => { ctx.world_id = 'world-b'; });
    await page.waitForTimeout(600); assert.equal(await page.getByRole('dialog').count(), 0);
    await page.evaluate(() => { resolveSubmit(); }); await page.waitForTimeout(150);
    assert.ok(await page.evaluate(() => cancelled >= 3));
    const before = await page.evaluate(() => generations);
    await page.getByRole('button', {name: 'AI: explain a stat', exact: true}).click();
    await page.getByLabel('Metric', {exact: true}).waitFor(); assert.equal(await page.evaluate(() => generations), before);
    await page.getByRole('button', {name: 'Close / Cancel', exact: true}).click();
    await page.close();
    const mobile = await browser.newPage({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true});
    await setup(mobile); await mobile.getByRole('button', {name: 'Explain with AI', exact: true}).tap();
    await mobile.getByRole('status').waitFor(); assert.equal(await mobile.evaluate(() => calls), 1);
    await mobile.evaluate(() => { release = true; });
    await mobile.getByRole('heading', {name: 'What changed', exact: true}).waitFor();
    const box = await mobile.getByRole('dialog').boundingBox(); assert.ok(box.x >= 0 && box.width <= 390);
    await mobile.screenshot({path: path.join(root, 'tmp/ai-explainer-mobile.png')});
    console.log('PASS: dormant UI, focus/short hover, deliberate hover, click dedup, loading, cache, proposal log retry, explicit action review/apply, stale-world cancellation, chooser, and touch layout.');
  } finally { await browser.close(); }
})().catch(error => {console.error(error); process.exitCode = 1;});
