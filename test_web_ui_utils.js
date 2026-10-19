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
  wood_price: 'goods.price', furniture_price: 'goods.price',
  unrest: 'politics.protest_energy', production: 'goods.production',
  wood_production: 'goods.production', furniture_production: 'goods.production',
  food_demand_ratio: 'goods.demand_ratio', wood_demand_ratio: 'goods.demand_ratio',
  furniture_demand_ratio: 'goods.demand_ratio',
  inventories: 'goods.producer_inventory', gini: 'economy.gini',
  wood_inventories: 'goods.producer_inventory',
  furniture_inventories: 'goods.producer_inventory',
  soil: 'ecology.soil_fertility',
  nutrition: 'ecology.nutrition_density', smog: 'ecology.pollution_air',
  effluent: 'ecology.pollution_water', soil_pollution: 'ecology.pollution_soil',
  bodily_wear: 'health.average_bodily_wear', illness_deaths: 'health.fatalities',
  malnutrition_cases: 'health.disease_cases', waterborne_cases: 'health.disease_cases',
  respiratory_cases: 'health.disease_cases', chemical_cases: 'health.disease_cases',
  health_outlays: 'health.medical_spending',
  gov_income: 'finance.government_income',
  trade: 'trade.net_value', trade_exports: 'trade.export_value',
  trade_imports: 'trade.import_value',
  shift_hours: 'labor.average_shift_hours',
  exploitation: 'labor.exploitation_rate',
  alienation: 'labor.average_alienation',
  consciousness: 'labor.average_class_consciousness',
  strikes: 'labor.strikers',
  workplace_accidents: 'labor.workplace_accidents',
  entertainment: 'society.entertainment_level',
  machinery_sabotaged: 'labor.machinery_sabotaged',
  broken_machinery: 'labor.broken_machinery',
  class_serf: 'society.class_population',
  class_tenant: 'society.class_population',
  class_worker: 'society.class_population',
  class_dispossessed: 'society.class_population',
  class_gentry: 'society.class_population',
  class_artisan: 'society.class_population',
  food_foraged: 'food.foraged', food_purchased: 'food.purchased',
  commons_access: 'land.commons_access', rent_collected: 'finance.rent_collected',
  rent_arrears: 'finance.rent_arrears'
})) {
  assert.equal(globalThis.CoCCharts.getTraceBinding(chartId).metricId, metricId);
}
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('gdp').tilePath, ['economic', 'gdp']);
assert.equal(globalThis.CoCCharts.getTraceBinding('production').good, 'food');
assert.equal(globalThis.CoCCharts.getTraceBinding('wood_price').good, 'wood');
assert.equal(globalThis.CoCCharts.getTraceBinding('furniture_price').priceChart, true);
assert.equal(globalThis.CoCCharts.getTraceBinding('wood_production').good, 'wood');
assert.equal(globalThis.CoCCharts.getTraceBinding('furniture_demand_ratio').good,
  'furniture');
const cottonPriceBinding = globalThis.CoCCharts.getTraceBinding('market_price', 'cotton');
assert.equal(cottonPriceBinding.good, 'cotton');
assert.equal(cottonPriceBinding.tileMetricId, 'goods.price');
assert.equal(cottonPriceBinding.priceChart, true);
assert.deepEqual(cottonPriceBinding.tilePath, ['economic', 'prices', 'cotton']);
assert.equal(cottonPriceBinding.label, 'cotton price');
assert.deepEqual(globalThis.CoCCharts.getTileSeries({ economic: { prices: {
  cotton: [2.2, 2.4]
} } }, cottonPriceBinding), [2.2, 2.4]);
assert.equal(globalThis.CoCCharts.getChartCatalog().market.length, 4);
assert.equal(globalThis.CoCCharts.getTraceBinding('inventories').good, 'food');
assert.equal(globalThis.CoCCharts.getTraceBinding('gini').good, 'food');
assert.equal(globalThis.CoCCharts.getTraceBinding('gini').chartScale, 100);
assert.equal(globalThis.CoCCharts.getTraceBinding('soil').chartScale, 100);
assert.equal(globalThis.CoCCharts.getTraceBinding('bodily_wear').chartScale, 100);
assert.equal(globalThis.CoCCharts.getChartCatalog().economic.length, 21);
assert.equal(globalThis.CoCCharts.getChartCatalog().labor.length, 9);
assert.equal(globalThis.CoCCharts.getTraceBinding('class_worker').classGroup, 'worker');
assert.equal(globalThis.CoCCharts.getTraceBinding('commons_access').chartScale, 100);
assert.equal(globalThis.CoCCharts.getChartCatalog().citizens.length, 11);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('soil_pollution').tilePath,
  ['ecological', 'pollution', 'soil']);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('nutrition').tilePath,
  ['ecological', 'soil_nutrition', 'nutrition']);
assert.equal(globalThis.CoCCharts.getTraceBinding('waterborne_cases').disease, 'waterborne');
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('shift_hours').tilePath,
  ['labor', 'shifts_exploitation', 'shifts']);
assert.equal(globalThis.CoCCharts.getTraceBinding('exploitation').chartScale, 100);
assert.equal(globalThis.CoCCharts.getTraceBinding('alienation').chartScale, 100);
assert.equal(globalThis.CoCCharts.getTraceBinding('consciousness').chartScale, 100);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('strikes').tilePath,
  ['labor', 'workplace_resistance', 'strikers']);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('workplace_accidents').tilePath,
  ['labor', 'workplace_conditions', 'accidents']);
assert.equal(globalThis.CoCCharts.getTraceBinding('entertainment').chartScale, 100);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('machinery_sabotaged').tilePath,
  ['labor', 'workplace_conditions', 'sabotage']);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('broken_machinery').tilePath,
  ['labor', 'workplace_conditions', 'broken']);
assert.deepEqual(globalThis.CoCCharts.getTraceBinding('trade').tilePath,
  ['economic', 'trade_flow', 'balance']);
assert.deepEqual(globalThis.CoCCharts.getTileSeries({ ecological: { healthcare_outlay: {
  private: [2, 3, 4], public: [5, 7, 11]
} } }, globalThis.CoCCharts.getTraceBinding('health_outlays')), [7, 10, 15]);
assert.deepEqual(globalThis.CoCCharts.getTileSeries({ economic: { gov_income: {
  tax: [2, 3], tariff: [5, 7], inheritance: [1, 4]
} } }, globalThis.CoCCharts.getTraceBinding('gov_income')), [8, 14]);

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
chartCalls.length = 0;
const emptyLegend = globalThis.CoCCharts.drawHistoricalChart(
  interactiveCanvas, [], 'trade', 1,
  { onPointSelect: point => selectedPoints.push(point) });
assert.match(emptyLegend, /No data series available/);
assert.equal(interactiveCanvas.style.cursor, '');
assert.equal(listeners.click, undefined);
assert.equal(chartCalls.some(call => call[0] === 'lineTo' || call[0] === 'arc'), false);
assert.ok(chartCalls.some(call => call[0] === 'fillText'
  && call[1] === 'No data series available'));

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
