/**
 * test_frontend.js — Automated Frontend Unit & Module Verification Tests
 * Uses Node.js native test runner (`node --test`). Zero npm dependencies required.
 */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const projectRoot = process.cwd();

// Helper to execute client scripts in a browser-like sandbox
function createBrowserSandbox() {
  const sandbox = {
    window: {},
    globalThis: {},
    document: {
      createElement(tag) {
        return {
          tagName: tag.toUpperCase(),
          className: '',
          style: {},
          dataset: {},
          attributes: {},
          children: [],
          eventListeners: {},
          setAttribute(k, v) { this.attributes[k] = String(v); },
          getAttribute(k) { return this.attributes[k]; },
          addEventListener(ev, fn) {
            this.eventListeners[ev] = this.eventListeners[ev] || [];
            this.eventListeners[ev].push(fn);
          },
          appendChild(child) {
            if (child && child.nodeType === 11) {
              while (child.children.length > 0) {
                this.children.push(child.children.shift());
              }
              return child;
            }
            this.children.push(child);
            return child;
          },
          removeChild(child) {
            const idx = this.children.indexOf(child);
            if (idx !== -1) this.children.splice(idx, 1);
            return child;
          },
          get firstChild() {
            return this.children[0] || null;
          }
        };
      },
      createTextNode(text) {
        return { nodeType: 3, textContent: String(text) };
      },
      createDocumentFragment() {
        return {
          nodeType: 11,
          children: [],
          appendChild(child) {
            this.children.push(child);
            return child;
          }
        };
      }
    },
    performance: { now: () => Date.now() },
    console,
    Math
  };
  sandbox.globalThis = sandbox;
  sandbox.window = sandbox;
  return vm.createContext(sandbox);
}

function loadScript(filePath, context) {
  const code = fs.readFileSync(path.join(projectRoot, filePath), 'utf8');
  vm.runInContext(code, context);
}

test('Hex Geometry Module (hex_geometry.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/hex_geometry.js', ctx);
  const geo = ctx.window.CoCHexGeometry;

  assert.ok(geo, 'CoCHexGeometry must be exported');
  assert.equal(typeof geo.axialToPixel, 'function');
  assert.equal(typeof geo.pixelToAxial, 'function');

  // Test origin (0, 0)
  const p0 = geo.axialToPixel(0, 0, 50);
  assert.equal(p0.x, 0);
  assert.equal(p0.y, 0);

  // Test roundtrip: pixelToAxial(axialToPixel(q, r)) === (q, r)
  for (let q = -3; q <= 3; q++) {
    for (let r = -3; r <= 3; r++) {
      const p = geo.axialToPixel(q, r, 50);
      const a = geo.pixelToAxial(p.x, p.y, 50);
      assert.equal(a.q || 0, q || 0, `Roundtrip failed for q=${q}, r=${r}`);
      assert.equal(a.r || 0, r || 0, `Roundtrip failed for q=${q}, r=${r}`);
    }
  }
});

test('Safe DOM Builder Module (dom_builder.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/dom_builder.js', ctx);
  const dom = ctx.window.CoCDOM;

  assert.ok(dom, 'CoCDOM must be exported');

  // Test element creation with attributes & children
  let clicked = false;
  const btn = dom.el('button', {
    className: 'btn btn-primary',
    onClick: () => { clicked = true; }
  }, 'Click Me');

  assert.equal(btn.tagName, 'BUTTON');
  assert.equal(btn.className, 'btn btn-primary');
  assert.equal(btn.children.length, 1);
  assert.equal(btn.children[0].textContent, 'Click Me');

  // Trigger listener
  btn.eventListeners['click'][0]();
  assert.equal(clicked, true);

  // Test list rendering
  const listContainer = ctx.document.createElement('div');
  const items = ['Item A', 'Item B', 'Item C'];
  dom.renderList(listContainer, items, (item) => dom.el('span', {}, item));

  assert.equal(listContainer.children.length, 3);
  assert.equal(listContainer.children[0].children[0].textContent, 'Item A');
});

test('Reactive State Store Module (state_store.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/state_store.js', ctx);
  const store = ctx.window.CoCStateStore.createStore({
    initialCustomKey: 123
  });

  assert.ok(store, 'Store must be created');
  assert.equal(store.getState().initialCustomKey, 123);

  let tileEventData = null;
  store.on('tile_selected', (data) => {
    tileEventData = data;
  });

  store.dispatch('SELECT_TILE', 'Tile-Capital');
  assert.equal(store.getState().selectedTileName, 'Tile-Capital');
  assert.equal(tileEventData, 'Tile-Capital');

  // Drawer action
  store.dispatch('SET_ACTIVE_DRAWER', 'progress');
  assert.equal(store.getState().ui.activeDrawer, 'progress');

  // World update
  const fakeWorld = { version: '1:0', turn: 10, nations: [] };
  store.dispatch('SET_WORLD', fakeWorld);
  assert.equal(store.getState().world.turn, 10);
  assert.equal(store.getState().stateVersion, '1:0');
});

test('Overland Trade Animator Module (trade_animator.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/hex_geometry.js', ctx);
  loadScript('web_client/trade_animator.js', ctx);
  const animator = ctx.window.CoCTradeAnimator;

  assert.ok(animator, 'CoCTradeAnimator must be exported');
  assert.equal(typeof animator.drawTradeRoutes, 'function');
  assert.equal(typeof animator.drawTradeFlowParticles, 'function');
  assert.equal(typeof animator.createAnimationTicker, 'function');

  // Mock canvas context
  const mockCtx = {
    save() {},
    restore() {},
    beginPath() {},
    stroke() {},
    fill() {},
    arc() {},
    moveTo() {},
    lineTo() {},
    set strokeStyle(v) {},
    set fillStyle(v) {},
    set lineWidth(v) {}
  };

  const tileByName = new Map([
    ['A', { q: 0, r: 0 }],
    ['B', { q: 1, r: 0 }]
  ]);

  const tradeNetwork = {
    edges: [{ from: 'A', to: 'B' }],
    flows: [{ from: 'A', to: 'B', volume: 2.5, forward: true }]
  };

  // Ensure drawing does not throw
  assert.doesNotThrow(() => {
    animator.drawTradeRoutes(mockCtx, tradeNetwork, tileByName, 50, 1.0);
    animator.drawTradeFlowParticles(mockCtx, tradeNetwork, tileByName, 50, 1.0, 1000);
  });

  // Voronoi centroids and 3D custom projection function
  const voronoiTileMap = new Map([
    ['A', { centroid: [100, 100], elevation: 0.2 }],
    ['B', { centroid: [200, 300], elevation: 0.8 }]
  ]);
  assert.doesNotThrow(() => {
    animator.drawTradeRoutes(mockCtx, tradeNetwork, voronoiTileMap, 0, 1.0);
    animator.drawTradeFlowParticles(mockCtx, tradeNetwork, voronoiTileMap, 0, 1.0, 1000);
    // With 3D projectFn
    const projectFn = (tile) => ({ x: tile.centroid[0] * 1.5, y: tile.centroid[1] * 1.2, valid: true });
    animator.drawTradeRoutes(mockCtx, tradeNetwork, voronoiTileMap, 0, 1.0, projectFn);
    animator.drawTradeFlowParticles(mockCtx, tradeNetwork, voronoiTileMap, 0, 1.0, 1000, projectFn);
  });
});

test('Comparison Suite Visualizers (vis_pyramid.js, vis_radar_attractor.js, vis_circuits.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/vis_pyramid.js', ctx);
  loadScript('web_client/vis_radar_attractor.js', ctx);
  loadScript('web_client/vis_circuits.js', ctx);

  assert.ok(ctx.window.CoCVisPyramid, 'CoCVisPyramid must be defined');
  assert.ok(ctx.window.CoCVisRadarAttractor, 'CoCVisRadarAttractor must be defined');
  assert.ok(ctx.window.CoCVisCircuits, 'CoCVisCircuits must be defined');

  const mockCanvas = {
    getContext: () => ({
      save() {},
      restore() {},
      scale() {},
      clearRect() {},
      fillRect() {},
      strokeRect() {},
      beginPath() {},
      closePath() {},
      createLinearGradient: () => ({ addColorStop() {} }),
      fill() {},
      stroke() {},
      moveTo() {},
      lineTo() {},
      bezierCurveTo() {},
      arc() {},
      setLineDash() {},
      measureText: () => ({ width: 45 }),
      fillText() {},
      set fillStyle(v) {},
      set strokeStyle(v) {},
      set lineWidth(v) {},
      set font(v) {},
      set textAlign(v) {},
      set textBaseline(v) {}
    }),
    clientWidth: 400,
    clientHeight: 240,
    width: 0,
    height: 0
  };

  // Test all visualizer render routines
  assert.doesNotThrow(() => {
    ctx.window.CoCVisPyramid.drawWealthPyramid(mockCanvas, {});
    ctx.window.CoCVisPyramid.drawLorenzCurve(mockCanvas, { gini: 0.35 });
    ctx.window.CoCVisRadarAttractor.drawAlienationRadar(mockCanvas, { shiftHours: 12 });
    ctx.window.CoCVisRadarAttractor.drawRebellionAttractor(mockCanvas, { shiftHours: 12, consciousness: 0.5 });
    ctx.window.CoCVisCircuits.drawCircuitSankey(mockCanvas, { moneyCapital: 1000, productiveCapital: 800 });
    ctx.window.CoCVisCircuits.drawTRPFCurve(mockCanvas, { organicComp: 2.5, profitRate: 15.0 });
  });
});

test('UI Utils, Chart Renderer, Help Content, and State Sync Modules', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/ui_utils.js', ctx);
  loadScript('web_client/chart_renderer.js', ctx);
  loadScript('web_client/help_content.js', ctx);
  loadScript('web_client/state_sync.js', ctx);

  assert.ok(ctx.window.CoCUIUtils, 'CoCUIUtils must be defined');

  assert.ok(ctx.window.CoCCharts, 'CoCCharts must be defined');

  assert.ok(ctx.window.CoCHelpContent, 'CoCHelpContent must be defined');

  assert.ok(ctx.window.CoCStateSync, 'CoCStateSync must be defined');
});

test('every historical chart has a trace binding, including effective workday cap', () => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/chart_renderer.js', ctx);
  const charts = ctx.window.CoCCharts;
  for (const entries of Object.values(charts.getChartCatalog())) {
    for (const entry of entries) {
      assert.ok(charts.getTraceBinding(entry.id, 'food'),
        `missing trace binding for chart ${entry.id}`);
    }
  }
  for (const mode of ['labor', 'citizens']) {
    for (const entry of charts.getChartCatalog()[mode]) {
      assert.ok(charts.getTraceBinding(entry.id).historyKey,
        `missing Nation history key for ${entry.id}`);
    }
  }
  for (const id of ['trade', 'trade_exports', 'trade_imports']) {
    const binding = charts.getTraceBinding(id);
    assert.ok(binding.historyKey, `missing Nation trade history for ${id}`);
    assert.ok(binding.metricId.startsWith('trade.'));
  }

  const binding = charts.getTraceBinding('workday_cap');
  assert.equal(binding.metricId, 'labor.statutory_workday');
  assert.deepEqual(Array.from(binding.tilePath),
    ['labor', 'shifts_exploitation', 'caps']);
  assert.deepEqual(Array.from(charts.getTileSeries({
    labor: { shifts_exploitation: { caps: [16, 10] } }
  }, binding)), [16, 10]);

  const market = charts.getTraceBinding('market_price', 'wool');
  assert.equal(market.historyKey, 'market_price_wool');
  assert.equal(market.nationMetricId, 'goods.national_reference_price');
  for (const [chart, key, metric] of [
    ['market_production', 'market_production_wool', 'goods.production'],
    ['market_demand_ratio', 'market_demand_ratio_wool', 'goods.demand_ratio'],
    ['market_inventory', 'market_inventory_wool', 'goods.producer_inventory']
  ]) {
    const dynamic = charts.getTraceBinding(chart, 'wool');
    assert.equal(dynamic.historyKey, key);
    assert.equal(dynamic.nationMetricId, metric);
    assert.equal(dynamic.good, 'wool');
  }
});

test('historical chart leaves unavailable turns as gaps and keeps their turn indices', () => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/chart_renderer.js', ctx);
  const pathCalls = [];
  const listeners = {};
  const drawing = {
    save() {}, scale() {}, clearRect() {}, beginPath() {}, stroke() {}, fill() {},
    fillText() {}, arc() {}, restore() {},
    moveTo(x, y) { pathCalls.push(['moveTo', x, y]); },
    lineTo(x, y) { pathCalls.push(['lineTo', x, y]); }
  };
  const canvas = {
    clientWidth: 400, clientHeight: 230, style: {},
    getContext: () => drawing,
    getBoundingClientRect: () => ({ left: 0, top: 0 }),
    addEventListener(name, callback) { listeners[name] = callback; },
    removeEventListener(name) { delete listeners[name]; }
  };
  let selected = null;
  ctx.window.CoCCharts.drawHistoricalChart(
    canvas, [null, 1, 2, null, 4], 'market_price', 1,
    { turns: [0, 1, 2, 3, 4], onPointSelect: point => { selected = point; } });

  // Five grid lines plus the one valid data segment; the gap must not be joined.
  assert.equal(pathCalls.filter(([kind]) => kind === 'lineTo').length, 6);
  listeners.click({ clientX: 386, clientY: 18 });
  assert.equal(selected.index, 4);
  assert.equal(selected.turn, 4);
  assert.equal(selected.value, 4);
});

test('Voronoi Geometry Module (voronoi_geometry.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/voronoi_geometry.js', ctx);

  const vg = ctx.window.CoCVoronoiGeometry;
  assert.ok(vg, 'CoCVoronoiGeometry must be exported');

  // Test rectangle polygon [[0, 0], [100, 0], [100, 100], [0, 100]]
  const poly = [[0, 0], [100, 0], [100, 100], [0, 100]];

  // Point in polygon
  assert.equal(vg.pointInPolygon(50, 50, poly), true, 'Center must be inside');
  assert.equal(vg.pointInPolygon(150, 50, poly), false, 'Outside must be false');
  assert.equal(vg.pointInPolygon(-10, 50, poly), false, 'Outside negative must be false');

  // Bounding box
  const bbox = vg.polygonBBox(poly);
  assert.equal(bbox.minX, 0);
  assert.equal(bbox.minY, 0);
  assert.equal(bbox.maxX, 100);
  assert.equal(bbox.maxY, 100);

  // Centroid
  const [cx, cy] = vg.polygonCentroid(poly);
  assert.equal(Math.round(cx), 50);
  assert.equal(Math.round(cy), 50);

  // Canvas drawing
  let pathActions = [];
  const mockCtx = {
    beginPath: () => pathActions.push('beginPath'),
    moveTo: (x, y) => pathActions.push(`moveTo(${x},${y})`),
    lineTo: (x, y) => pathActions.push(`lineTo(${x},${y})`),
    closePath: () => pathActions.push('closePath'),
  };
  vg.drawPolygonPath(mockCtx, poly);
  assert.equal(pathActions[0], 'beginPath');
  assert.equal(pathActions[1], 'moveTo(0,0)');
  assert.equal(pathActions[pathActions.length - 1], 'closePath');
});

test('3D Perspective Projection Engine (projection_3d.js)', (t) => {
  const ctx = createBrowserSandbox();
  loadScript('web_client/projection_3d.js', ctx);

  const p3d = ctx.window.CoCProjection3D;
  assert.ok(p3d, 'CoCProjection3D must be exported');

  // Dynamic Civ-style Zoom interpolation
  const closeUp = p3d.computePitchYaw(2.5);
  assert.equal(Math.round(closeUp.pitch), 52, 'Close zoom must be 52° pitch');
  assert.equal(Math.round(closeUp.yaw), 9, 'Close zoom must be 9° yaw');

  const overview = p3d.computePitchYaw(0.8);
  assert.equal(Math.round(overview.pitch), 89, 'Overview zoom must be 89° pitch');
  assert.equal(Math.round(overview.yaw), 0, 'Overview zoom must be 0° yaw');

  // Camera MVP computation
  const cam = { pitch: 52.0, yaw: 9.0, zoom: 1.0, target_x: 512, target_y: 512 };
  const mvp = p3d.getCameraMVP(cam, 1024, 768);
  assert.equal(mvp.length, 16);

  // 3D Point projection
  const pt = p3d.projectPoint3D(mvp, 512, 512, 0, 1024, 768);
  assert.equal(pt.valid, true);
  // Center should project roughly near the center of the viewport
  assert.ok(pt.x > 300 && pt.x < 750, `Center X ${pt.x} within reasonable screen bounds`);
  assert.ok(pt.y > 200 && pt.y < 600, `Center Y ${pt.y} within reasonable screen bounds`);

  // 3D Polygon frustum clipping & projection
  const poly3D = [
    [400, 400, 10],
    [600, 400, 15],
    [600, 600, 20],
    [400, 600, 10]
  ];
  const projectedPoly = p3d.projectPolygon3D(mvp, poly3D, 1024, 768);
  assert.ok(projectedPoly.length >= 3, 'Projected polygon must have at least 3 vertices');

  // Ray unprojection
  const ray = p3d.screenToWorldRay(512, 384, mvp, 1024, 768);
  assert.ok(ray, 'Ray must be generated');
  assert.equal(ray.near.length, 3);
  assert.equal(ray.far.length, 3);
  assert.equal(ray.dir.length, 3);
});
