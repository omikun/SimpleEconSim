const assert = require('node:assert/strict');
require('./web_client/ui_utils.js');
require('./web_client/state_sync.js');
require('./web_client/hex_geometry.js');
require('./web_client/chart_renderer.js');
require('./web_client/help_content.js');

assert.ok(globalThis.CoCUIUtils);
const { escapeHtml, safeClassToken, safeCssColor } = globalThis.CoCUIUtils;

assert.equal(escapeHtml(`<img src=x onerror='alert(1)'>&`), '&lt;img src=x onerror=&#39;alert(1)&#39;&gt;&amp;');
assert.equal(escapeHtml(null), '');
assert.equal(safeClassToken('state-active_2'), 'state-active_2');
assert.equal(safeClassToken('badge-unrest riot'), 'badge-unrest riot');
assert.equal(safeClassToken('bad token!', 'fallback'), 'fallback');
assert.equal(safeCssColor('#A1b2C3'), '#A1b2C3');
assert.equal(safeCssColor('red; background:url(javascript:alert(1))'), '#38bdf8');

assert.ok(globalThis.CoCHexGeometry);
const geometry = globalThis.CoCHexGeometry;
for (const cell of [{ q: 0, r: 0 }, { q: 3, r: -2 }, { q: -4, r: 5 }]) {
  const point = geometry.axialToPixel(cell.q, cell.r, 50);
  assert.deepEqual(geometry.pixelToAxial(point.x, point.y, 50), cell);
}
assert.deepEqual(geometry.pixelToAxial(0, 0, 50), { q: 0, r: 0 });

const chartCalls = [];
const chartContext = new Proxy({}, {
  get(_target, key) {
    if (key === 'scale') return (...args) => chartCalls.push(['scale', ...args]);
    if (key === 'clearRect' || key === 'moveTo' || key === 'lineTo' || key === 'fillText' || key === 'arc') {
      return (...args) => chartCalls.push([key, ...args]);
    }
    return () => chartCalls.push([key]);
  },
  set(_target, key, value) { chartCalls.push(['set', key, value]); return true; }
});
const chartCanvas = { clientWidth: 300, clientHeight: 160, getContext: () => chartContext };
assert.ok(globalThis.CoCCharts);
const chartLegend = globalThis.CoCCharts.drawHistoricalChart(chartCanvas, [10, 20, 15], 'gdp', 2);
assert.equal(chartCanvas.width, 600);
assert.equal(chartCanvas.height, 320);
assert.match(chartLegend, /GDP: Historical Trend/);
assert.ok(chartCalls.some(call => call[0] === 'arc'));
assert.equal(globalThis.CoCCharts.getChartCatalog().economic[0].id, 'gdp');
assert.equal(globalThis.CoCCharts.getChartCatalog().economic[0].name, 'Nominal GDP');
for (const [chartId, metricId] of Object.entries({
  gdp: 'economy.gdp_nominal', treasury: 'finance.treasury',
  food_price: 'goods.national_food_price', pop: 'people.population',
  unrest: 'politics.protest_energy', production: 'goods.production',
  inventories: 'goods.producer_inventory', soil: 'ecology.soil_fertility',
  nutrition: 'ecology.nutrition_density', smog: 'ecology.pollution_air',
  effluent: 'ecology.pollution_water', illness_deaths: 'health.fatalities',
  malnutrition_cases: 'health.disease_cases', waterborne_cases: 'health.disease_cases',
  respiratory_cases: 'health.disease_cases', chemical_cases: 'health.disease_cases',
  health_outlays: 'health.medical_spending'
})) {
  assert.equal(globalThis.CoCCharts.getTraceBinding(chartId).metricId, metricId);
}
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('gdp').tilePath, ['economic', 'gdp']);
assert.equal(globalThis.CoCCharts.getTraceBinding('production').good, 'food');
assert.equal(globalThis.CoCCharts.getTraceBinding('inventories').good, 'food');
assert.equal(globalThis.CoCCharts.getTraceBinding('soil').chartScale, 100);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('nutrition').tilePath,
  ['ecological', 'soil_nutrition', 'nutrition']);
assert.equal(globalThis.CoCCharts.getTraceBinding('waterborne_cases').disease, 'waterborne');
assert.deepEqual(globalThis.CoCCharts.getTileSeries({ ecological: { healthcare_outlay: {
  private: [2, 3, 4], public: [5, 7, 11]
} } }, globalThis.CoCCharts.getTraceBinding('health_outlays')), [7, 10, 15]);
assert.equal(globalThis.CoCCharts.getTraceBinding('strikes'), null);

const listeners = {};
const selectedPoints = [];
const interactiveCanvas = {
  clientWidth: 300,
  clientHeight: 160,
  style: {},
  getContext: () => chartContext,
  getBoundingClientRect: () => ({ left: 0, top: 0 }),
  addEventListener: (name, callback) => { listeners[name] = callback; },
  removeEventListener: name => { delete listeners[name]; }
};
globalThis.CoCCharts.drawHistoricalChart(
  interactiveCanvas, [10, 20, 15], 'food_price', 1,
  { turns: [3, 4, 5], onPointSelect: point => selectedPoints.push(point) });
assert.equal(interactiveCanvas.style.cursor, 'crosshair');
listeners.click({ clientX: 165, clientY: 18 });
assert.deepEqual(selectedPoints, [{ index: 1, value: 20, turn: 4, metric: 'food_price' }]);
listeners.click({ clientX: 150, clientY: 80 });
assert.equal(selectedPoints.length, 1);

assert.ok(globalThis.CoCHelpContent);
const helpHtml = globalThis.CoCHelpContent.renderHelpPage('3', {
  seed: 17,
  nations: [{
    name: '<img src=x onerror=alert(1)>',
    regime_type: 'Kingdom <script>',
    flag_color: 'red; background:url(javascript:alert(1))',
    tiles_count: 4,
    gdp: 1000,
    credit_rating: 'A&'
  }]
});
assert.match(helpHtml, /&lt;img src=x onerror=alert\(1\)&gt;/);
assert.doesNotMatch(helpHtml, /<img src=x/);
assert.match(helpHtml, /color:#38bdf8/);

const calls = [];
let commandResult;
let networkError;
assert.ok(globalThis.CoCStateSync);
const sync = globalThis.CoCStateSync.createStateSync({
  fetchImpl: async (...args) => {
    calls.push(args);
    return { json: async () => ({ success: true }) };
  },
  getToken: () => 'local-token',
  onCommandResult: result => { commandResult = result; },
  onNetworkError: error => { networkError = error; }
});

(async () => {
  await sync.fetchState('instance:1&other=value');
  assert.equal(calls[0][0], '/api/state?compact=1&since=instance%3A1%26other%3Dvalue');
  await sync.fetchTile('A/B');
  assert.equal(calls[1][0], '/api/tile?name=A%2FB');
  await sync.sendCommand('STEP', { count: 1 });
  assert.equal(calls[2][0], '/api/command');
  assert.equal(calls[2][1].headers['X-COC-Token'], 'local-token');
  assert.deepEqual(commandResult, { success: true });
  assert.equal(networkError, undefined);
  console.log('UI utility, geometry, and API transport checks passed');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
