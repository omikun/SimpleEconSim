/**
 * REGNUM Web Client — Comprehensive Sovereign Macroeconomic Simulation Client
 * 100% Desktop Parity: 9 Thematic Layers, 6 Sovereign Suites, 20 Charts Engine,
 * Cadastre Plot Management, 6-Tab Comparison Suite, Fiscal Bailout Dialog,
 * 3-Page Paginated Encyclopedia, and Real-Time Authoritative WebSocket/REST Sync.
 */

(function () {
  'use strict';

  const SQRT3 = Math.sqrt(3.0);
  const DEFAULT_HEX_SIZE = 50.0;

  // Global World & Simulation State
  let worldState = null;
  let selectedTileName = null;
  let selectedTileDetail = null;
  let isPlaying = false;
  let pollTimer = null;
  let isRequestPending = false;

  // Active UI Navigation State
  let activeLeftDrawer = null;       // 'build' | 'gov' | 'diplomacy' | 'debt' | 'science' | 'military' | null
  let activeRightTab = 'overview';   // 'overview' | 'charts' | 'cadastre' | 'citizens' | 'policies' | 'workhouse' | 'news'
  let activeLayer = 'overview';      // 1..9 thematic layers
  let activeBuildCat = 'industry';   // 'industry' | 'ecology'
  let activeBuildTier = 'all';       // 'all' | 'tile' | 'province' | 'nation'
  let activeGovScope = 'tile';       // 'tile' | 'province' | 'nation' | 'frontier'
  let activeDebtScope = 'domestic';  // 'domestic' | 'foreign'
  let activeScienceEra = 1;          // 1 | 2 | 3 | 4
  let activeBondDuration = 20;       // 20 | 50 | 100
  let activeChartMode = 'economic';  // 'economic' | 'ecological' | 'labor'
  let activeChartMetric = 'gdp';
  let activeCompareTab = '1';        // '1'..'6'
  let activeCompareDrilldown = 'country'; // 'country' | 'province' | 'tile'
  let activeCitizenSub = 'class';    // 'class' | 'labor'
  let activeHelpPage = '1';          // '1'..'3'
  let activeDiploNation = null;
  let cadastreScrollOffset = 0;

  // Photorealistic Topographic Terrain State
  let useTerrainImage = true;
  let terrainImage = new Image();
  let terrainLoaded = false;
  let terrainLoading = false;
  let currentTerrainSeed = null;

  // Camera & Interaction State
  let camX = 0;
  let camY = 0;
  let camZoom = 1.0;
  let isInitialCentered = false;
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let camStartX = 0;
  let camStartY = 0;
  let touchStartTime = 0;
  let initialPinchDist = null;
  let initialPinchZoom = 1.0;

  // Pending Fiscal Transfer Data
  let pendingFiscalTransfer = null;

  // DOM Elements
  const canvas = document.getElementById('map-canvas');
  const ctx = canvas.getContext('2d');
  const turnDisplay = document.getElementById('turn-display');
  const btnPlay = document.getElementById('btn-play');
  const btnStep = document.getElementById('btn-step');
  const btnNew = document.getElementById('btn-new');
  const btnCompare = document.getElementById('btn-compare');
  const btnHelp = document.getElementById('btn-help');
  const btnQr = document.getElementById('btn-qr');
  const btnToggleTerrain = document.getElementById('btn-toggle-terrain');
  const btnTogglePipeline = document.getElementById('btn-toggle-pipeline');
  const btnTopDiplo = document.getElementById('btn-top-diplo');
  const btnTopMilitary = document.getElementById('btn-top-military');
  const statusDot = document.getElementById('status-dot');
  const selectNation = document.getElementById('select-nation');
  const activeFlagDot = document.getElementById('active-flag-dot');
  const quickPill = document.getElementById('quick-pill');
  const pillText = document.getElementById('pill-text');

  // Left Drawer Elements
  const leftDrawer = document.getElementById('left-drawer');
  const drawerTitle = document.getElementById('drawer-title');
  const btnCloseLeft = document.getElementById('btn-close-left');

  // Layer Selector Elements
  const btnLayerToggle = document.getElementById('btn-layer-toggle');
  const layerMenu = document.getElementById('layer-menu');
  const activeLayerDot = document.getElementById('active-layer-dot');
  const activeLayerName = document.getElementById('active-layer-name');

  // Right Panel Elements
  const rightPanel = document.getElementById('right-panel');
  const rightDrawerHandle = document.getElementById('right-drawer-handle');
  const drawerToggleBtn = document.getElementById('drawer-toggle-btn');
  const tileNameEl = document.getElementById('tile-name');
  const tileSubEl = document.getElementById('tile-sub');

  // Modals
  const compareModal = document.getElementById('compare-modal');
  const btnCloseCompare = document.getElementById('btn-close-compare');
  const compareBackdrop = document.getElementById('compare-backdrop');
  const helpModal = document.getElementById('help-modal');
  const btnCloseHelp = document.getElementById('btn-close-help');
  const helpBackdrop = document.getElementById('help-backdrop');
  const commandSuiteModal = document.getElementById('command-suite-modal');
  const btnCloseCommandSuite = document.getElementById('btn-close-command-suite');
  const commandSuiteBackdrop = document.getElementById('command-suite-backdrop');
  const fiscalTransferModal = document.getElementById('fiscal-transfer-modal');
  const btnCloseFiscalTransfer = document.getElementById('btn-close-fiscal-transfer');
  const fiscalTransferBackdrop = document.getElementById('fiscal-transfer-backdrop');
  const qrModal = document.getElementById('qr-modal');
  const btnCloseQr = document.getElementById('btn-close-qr');
  const qrBackdrop = document.getElementById('qr-backdrop');
  const qrUrlText = document.getElementById('qr-url-text');
  const btnCopyUrl = document.getElementById('btn-copy-url');

  // Toast Container
  const toastContainer = document.getElementById('toast-container');

  // ---------------- Hex Math & Geometry ----------------

  function getHexRadius() {
    return (worldState && typeof worldState.hex_size === 'number') ? worldState.hex_size : DEFAULT_HEX_SIZE;
  }

  function axialToPixel(q, r, size) {
    const x = size * (SQRT3 * q + (SQRT3 / 2.0) * r);
    const y = size * (1.5 * r);
    return { x, y };
  }

  function pixelToAxial(px, py, size) {
    const q = ((SQRT3 / 3.0) * px - (1.0 / 3.0) * py) / size;
    const r = ((2.0 / 3.0) * py) / size;
    return axialRound(q, r);
  }

  function axialRound(q, r) {
    let s = -q - r;
    let rq = Math.round(q);
    let rr = Math.round(r);
    let rs = Math.round(s);
    const dq = Math.abs(rq - q);
    const dr = Math.abs(rr - r);
    const ds = Math.abs(rs - s);
    if (dq > dr && dq > ds) rq = -rr - rs;
    else if (dr > ds) rr = -rq - rs;
    return { q: rq, r: rr };
  }

  function drawHexPolygon(ctx, cx, cy, radius) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 180.0) * (60 * i - 30);
      const x = cx + radius * Math.cos(angle);
      const y = cy + radius * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
  }

  // ---------------- Canvas Resizing & Camera ----------------

  function resizeCanvas() {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.clientWidth;
    const h = canvas.parentElement.clientHeight;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    renderMap();
  }

  function centerCameraOnWorld() {
    if (!worldState || !worldState.tiles || worldState.tiles.length === 0) return;
    const hexRadius = getHexRadius();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

    worldState.tiles.forEach(t => {
      const { x, y } = axialToPixel(t.q, t.r, hexRadius);
      minX = Math.min(minX, x - hexRadius);
      maxX = Math.max(maxX, x + hexRadius);
      minY = Math.min(minY, y - hexRadius);
      maxY = Math.max(maxY, y + hexRadius);
    });

    const w = canvas.parentElement.clientWidth;
    const h = canvas.parentElement.clientHeight;
    const worldW = maxX - minX;
    const worldH = maxY - minY;

    const pad = 60;
    const zX = (w - pad * 2) / Math.max(worldW, 100);
    const zY = (h - pad * 2) / Math.max(worldH, 100);
    camZoom = Math.min(Math.max(Math.min(zX, zY), 0.4), 2.2);

    camX = w / 2 - ((minX + maxX) / 2) * camZoom;
    camY = h / 2 - ((minY + maxY) / 2) * camZoom;
    isInitialCentered = true;
    renderMap();
  }

  // ---------------- Terrain Image Synchronizer ----------------

  function syncTerrainImage(seed) {
    if (!seed) return;
    if (currentTerrainSeed === seed && (terrainLoaded || terrainLoading)) return;
    currentTerrainSeed = seed;
    terrainLoading = true;
    terrainLoaded = false;

    terrainImage = new Image();
    terrainImage.crossOrigin = 'anonymous';
    terrainImage.onload = () => {
      terrainLoaded = true;
      terrainLoading = false;
      renderMap();
    };
    terrainImage.onerror = () => {
      terrainLoading = false;
      terrainLoaded = false;
      renderMap();
    };
    terrainImage.src = `/api/terrain.png?seed=${seed}&t=${Date.now()}`;
  }

  // ---------------- Map & Thematic Layers Renderer ----------------

  function renderMap() {
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.clientWidth;
    const h = canvas.parentElement.clientHeight;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Deep cosmic background
    ctx.fillStyle = '#0a0d14';
    ctx.fillRect(0, 0, w, h);

    ctx.save();
    ctx.translate(camX, camY);
    ctx.scale(camZoom, camZoom);

    // Photorealistic continuous terrain image layer
    if (useTerrainImage && terrainLoaded && terrainImage.width > 0 && worldState && worldState.terrain_bounds) {
      const b = worldState.terrain_bounds;
      const imgW = (typeof b.width === 'number' && b.width > 0) ? b.width : ((b.max_x || 0) - (b.min_x || 0));
      const imgH = (typeof b.height === 'number' && b.height > 0) ? b.height : ((b.max_y || 0) - (b.min_y || 0));
      if (imgW > 0 && imgH > 0) {
        ctx.drawImage(terrainImage, b.min_x, b.min_y, imgW, imgH);
      }
    }

    // Render hex tiles
    if (worldState && worldState.tiles) {
      const hexRadius = getHexRadius();

      worldState.tiles.forEach(tile => {
        const { x, y } = axialToPixel(tile.q, tile.r, hexRadius);
        const isSelected = (selectedTileName && tile.name === selectedTileName);

        // If not using terrain image or terrain not loaded, render procedural vector terrain
        if (!useTerrainImage || !terrainLoaded) {
          drawHexPolygon(ctx, x, y, hexRadius - 0.5);
          ctx.fillStyle = tile.color || '#1e293b';
          ctx.fill();
        }

        // Active Thematic Layer overlay
        renderThematicLayerOverlay(ctx, tile, x, y, hexRadius);

        // Hex territorial boundary border
        // 1. High contrast outer shadow stroke so grid lines are clearly visible on any terrain texture
        drawHexPolygon(ctx, x, y, hexRadius);
        ctx.strokeStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.lineWidth = (isSelected ? 5.5 : 3.2) / camZoom;
        ctx.stroke();

        // 2. Crisp bright foreground border with distinct nation colors
        drawHexPolygon(ctx, x, y, hexRadius);
        if (isSelected) {
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 3.6 / camZoom;
          ctx.stroke();
        } else if (tile.nation_color) {
          ctx.strokeStyle = tile.nation_color;
          ctx.lineWidth = 2.4 / camZoom;
          ctx.stroke();
        } else {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.65)';
          ctx.lineWidth = 1.8 / camZoom;
          ctx.stroke();
        }

        // Hex information badges & icons
        renderHexBadges(ctx, tile, x, y, hexRadius);
      });
    }

    ctx.restore();
    ctx.restore();
  }

  function renderThematicLayerOverlay(ctx, tile, cx, cy, size) {
    if (activeLayer === 'overview') return;

    ctx.save();
    drawHexPolygon(ctx, cx, cy, size - 1.0);

    if (activeLayer === 'physical') {
      const elev = tile.elevation_meters || 0;
      const norm = Math.min(Math.max(elev / 3000.0, 0), 1.0);
      ctx.fillStyle = `rgba(140, 225, 255, ${norm * 0.55})`;
      ctx.fill();
    } else if (activeLayer === 'population') {
      const pop = tile.population || 0;
      const norm = Math.min(pop / 150.0, 1.0);
      const unrest = Math.min((tile.protest_energy || 0) / 5.0, 1.0);
      ctx.fillStyle = `rgba(${Math.round(245 * unrest + 56 * (1 - unrest))}, ${Math.round(140 * (1 - unrest))}, 60, ${0.15 + norm * 0.55})`;
      ctx.fill();
    } else if (activeLayer === 'economy') {
      const gdp = tile.gdp || 0;
      const norm = Math.min(gdp / 1000.0, 1.0);
      ctx.fillStyle = `rgba(120, 225, 130, ${0.15 + norm * 0.55})`;
      ctx.fill();
    } else if (activeLayer === 'production') {
      const bCount = (tile.buildings && tile.buildings.length) || 0;
      const norm = Math.min(bCount / 5.0, 1.0);
      ctx.fillStyle = `rgba(245, 210, 90, ${0.15 + norm * 0.55})`;
      ctx.fill();
    } else if (activeLayer === 'military') {
      const g = tile.garrison || 0;
      const norm = Math.min(g / 50.0, 1.0);
      ctx.fillStyle = `rgba(235, 80, 80, ${0.15 + norm * 0.55})`;
      ctx.fill();
    } else if (activeLayer === 'enclosure') {
      const enc = (tile.tenure && tile.tenure.enclosed_fraction) || 0;
      ctx.fillStyle = `rgba(215, 175, 75, ${0.15 + enc * 0.6})`;
      ctx.fill();
    } else if (activeLayer === 'exploitation') {
      const s_v = (tile.tenure && tile.tenure.surplus_value_rate) || 0.5;
      const norm = Math.min(s_v / 2.0, 1.0);
      ctx.fillStyle = `rgba(235, 75, 75, ${0.2 + norm * 0.6})`;
      ctx.fill();
    } else if (activeLayer === 'externalities') {
      const smog = (tile.ecology && tile.ecology.pollution_air) || 0;
      const norm = Math.min(smog / 100.0, 1.0);
      ctx.fillStyle = `rgba(100, 215, 140, ${0.15 + (1 - norm) * 0.4})`;
      ctx.fill();
    }

    ctx.restore();
  }

  function renderHexBadges(ctx, tile, cx, cy, size) {
    if (camZoom < 0.6) return;

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // Settlement / City Name Label
    if (tile.is_settlement || tile.population > 0) {
      const fontSize = Math.max(10, Math.min(13, Math.round(11 / camZoom)));
      ctx.font = `bold ${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = '#ffffff';
      ctx.shadowColor = 'rgba(0, 0, 0, 0.85)';
      ctx.shadowBlur = 4;
      ctx.fillText(tile.display_name || tile.name, cx, cy - size * 0.25);
      ctx.shadowBlur = 0;
    }

    // Population & Protest Badges
    if (tile.population > 0 && camZoom >= 0.8) {
      const subFont = Math.max(9, Math.min(11, Math.round(10 / camZoom)));
      ctx.font = `${subFont}px -apple-system, sans-serif`;
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(`👥 ${tile.population}`, cx, cy + size * 0.15);

      if (tile.protest_energy > 0.5) {
        ctx.fillStyle = '#ef4444';
        ctx.fillText(`🔥 ${(tile.protest_energy).toFixed(1)}`, cx, cy + size * 0.45);
      }
    }

    ctx.restore();
  }

  // ---------------- Top Macroeconomic Bar Synchronizer ----------------

  // ---------------- Top Bar Macro Indicators & Tooltips System ----------------

  let activeTooltipStat = null;
  let isTooltipLocked = false;
  let tooltipHoverTimeout = null;

  function updateTopMacroBar() {
    if (!worldState) return;

    if (turnDisplay) turnDisplay.textContent = worldState.turn || 0;

    const macro = worldState.macro || {};
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    const trCash = Math.round(macro.treasury_cash || 0);
    const trFood = Math.round(macro.treasury_food !== undefined ? macro.treasury_food : (macro.granary_food || 0));
    const isrbYield = (macro.bond_yield !== undefined ? macro.bond_yield.toFixed(2) : '0.18') + '%';

    setVal('val-treasury', `$${trCash.toLocaleString()}`);
    setVal('val-food', trFood.toLocaleString());
    setVal('val-pop', (macro.population || 0).toLocaleString());
    setVal('val-gdp', `$${Math.round(macro.gdp || 0).toLocaleString()}`);
    setVal('val-gini', (macro.gini || 0).toFixed(2));
    setVal('val-trade', `$${Math.round(macro.trade_balance || 0).toLocaleString()}`);
    setVal('val-col', (macro.cost_of_living || 1.0).toFixed(2));
    setVal('val-isrb', `${macro.credit_rating || 'BBB'} ${isrbYield}`);

    const elUnrest = document.getElementById('val-unrest');
    if (elUnrest) {
      const stage = macro.unrest_stage || 'Calm';
      elUnrest.textContent = `${(macro.unrest_energy || 0).toFixed(1)} ${stage}`;
      elUnrest.className = `macro-val badge-unrest ${stage.toLowerCase()}`;
    }

    if (btnPlay) {
      isPlaying = Boolean(worldState.playing !== undefined ? worldState.playing : worldState.is_playing);
      btnPlay.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
      btnPlay.className = isPlaying ? 'btn btn-secondary' : 'btn btn-primary';
    }

    // Sovereign Nations Switcher Dropdown
    if (selectNation && worldState.nations) {
      if (selectNation.children.length <= 1 || selectNation.children[0].value === '') {
        selectNation.innerHTML = '';
        worldState.nations.forEach(nat => {
          const opt = document.createElement('option');
          opt.value = nat.name;
          opt.textContent = `${nat.name} (${nat.regime_type || 'Sovereign'})`;
          selectNation.appendChild(opt);
        });
      }
      selectNation.value = worldState.player_nation || '';

      const pNat = worldState.nations.find(n => n.name === worldState.player_nation);
      if (pNat && activeFlagDot) {
        activeFlagDot.style.background = pNat.flag_color || '#38bdf8';
      }
    }

    if (btnTogglePipeline) {
      btnTogglePipeline.querySelector('.btn-text').textContent = useTerrainImage ? 'Pipeline: Photoreal' : 'Pipeline: Flat';
    }

    // Live-update open tooltip popover if one is active
    if (activeTooltipStat) {
      const anchorEl = document.querySelector(`[data-stat="${activeTooltipStat}"]`);
      if (anchorEl) {
        renderMacroTooltip(activeTooltipStat, anchorEl);
      }
    }
  }

  function getMacroTooltipContent(statKey) {
    if (!worldState) return null;
    const macro = worldState.macro || {};
    const trFood = Math.round(macro.treasury_food !== undefined ? macro.treasury_food : (macro.granary_food || 0));
    const trCash = Math.round(macro.treasury_cash || 0);
    const trDelta = Math.round(macro.treasury_delta || 0);
    const cur = macro.currency || 'USD';

    switch (statKey) {
      case 'treasury': {
        const deltaHtml = trDelta >= 0
          ? `<span class="delta-pos">+${trDelta.toLocaleString()}</span>`
          : `<span class="delta-neg">${trDelta.toLocaleString()}</span>`;
        return {
          title: '💰 Sovereign Treasury Vault',
          badge: `${cur} $${trCash.toLocaleString()}`,
          badgeClass: 'text-gold',
          rows: [
            { label: 'Liquid Cash Vault', val: `$${trCash.toLocaleString()}`, valClass: 'text-gold' },
            { label: 'Turn Balance Delta', val: `${deltaHtml} / turn` },
            { label: 'Emergency Granary', val: `${trFood.toLocaleString()} food units`, valClass: 'text-green' },
            { label: 'Statutory Income Tax', val: `${((macro.tax_rate || 0.15) * 100).toFixed(1)}%` },
            { label: 'Customs Tariff Rate', val: `${((macro.tariff_rate || 0.10) * 100).toFixed(1)}%` },
            { label: 'Outstanding Public Debt', val: `$${Math.round(macro.public_debt || 0).toLocaleString()}`, valClass: macro.public_debt > 0 ? 'text-ruby' : 'text-green' },
            { label: 'Armed Forces Payroll', val: `${macro.garrison || 0} stationed troops` }
          ],
          footer: 'Adjust statutory taxes in Governance [G] or float public bonds in Debt [S].'
        };
      }

      case 'granary': {
        const foodPrice = Number(macro.cost_of_living || 1.0).toFixed(2);
        const secLevel = trFood > 50 ? 'Secure Surplus' : (trFood > 15 ? 'Marginal Buffer' : 'Critical Depletion');
        const secClass = trFood > 50 ? 'text-green' : (trFood > 15 ? 'text-gold' : 'text-ruby');
        const unrestVal = Number(macro.unrest_energy || 0);
        return {
          title: '🌾 Crown Granary & Food Security',
          badge: `${trFood.toLocaleString()} Units`,
          badgeClass: 'text-green',
          rows: [
            { label: 'Emergency Granary Reserve', val: `${trFood.toLocaleString()} units`, valClass: 'text-green' },
            { label: 'Market Staple Grain Price', val: `$${foodPrice} / unit`, valClass: 'text-gold' },
            { label: 'Food Security Status', val: secLevel, valClass: secClass },
            { label: 'Famine & Starvation Risk', val: unrestVal > 3 ? 'Elevated' : 'Low', valClass: unrestVal > 3 ? 'text-ruby' : 'text-green' },
            { label: 'Emergency Bread Relief', val: 'Directly quells popular discontent' }
          ],
          footer: 'Click Governance [G] -> Social Relief to disburse bread from the granary.'
        };
      }

      case 'pop': {
        const popVal = (macro.population || 0).toLocaleString();
        const pDelta = macro.population_delta || 0;
        const deltaHtml = pDelta >= 0
          ? `<span class="delta-pos">+${pDelta}</span>`
          : `<span class="delta-neg">${pDelta}</span>`;
        return {
          title: '👥 Demographics & Living Citizens',
          badge: `${popVal} Pops`,
          badgeClass: 'text-cyan',
          rows: [
            { label: 'Total Living Population', val: `${popVal} citizens` },
            { label: 'Turn Demographic Delta', val: `${deltaHtml} net / turn` },
            { label: 'Productive Settlement Tiles', val: `${macro.tiles_count || (worldState.tiles || []).length} regions` },
            { label: 'Standing Town Garrisons', val: `${macro.garrison || 0} soldiers` },
            { label: 'Field Military Formations', val: `${macro.standing_armies || 0} active regiments` },
            { label: 'Primary Class Hierarchy', val: 'Serfs, Tenants, Artisans, Gentry' }
          ],
          footer: 'Select any map hex to inspect individual citizen careers, wages, and needs.'
        };
      }

      case 'gdp': {
        const gdpVal = Math.round(macro.gdp || 0).toLocaleString();
        const gDelta = Math.round(macro.gdp_delta || 0);
        const deltaHtml = gDelta >= 0
          ? `<span class="delta-pos">+${gDelta.toLocaleString()}</span>`
          : `<span class="delta-neg">${gDelta.toLocaleString()}</span>`;
        const gdpPc = Number(macro.gdp_per_capita || 0).toFixed(1);
        return {
          title: '📈 Gross Domestic Product (GDP)',
          badge: `$${gdpVal}`,
          badgeClass: 'text-cyan',
          rows: [
            { label: 'Aggregate Real GDP Output', val: `$${gdpVal}`, valClass: 'text-cyan' },
            { label: 'Turn Economic Delta', val: `${deltaHtml} / turn` },
            { label: 'GDP per Capita', val: `$${gdpPc} / citizen`, valClass: 'text-gold' },
            { label: 'Territorial Market Centers', val: `${macro.tiles_count || 0} claimed biomes` },
            { label: 'Production Sectors', val: 'Agriculture, Lumber, Furniture, Mining' }
          ],
          footer: 'Commission new mills, mines, and artisan workshops via Build Menu [B].'
        };
      }

      case 'unrest': {
        const unrestVal = Number(macro.unrest_energy || 0).toFixed(2);
        const stage = macro.unrest_stage || 'Calm';
        const uDelta = Number(macro.unrest_delta || 0).toFixed(2);
        const deltaHtml = uDelta <= 0
          ? `<span class="delta-pos">${uDelta}</span>`
          : `<span class="delta-neg">+${uDelta}</span>`;
        return {
          title: '🔥 Civil Unrest & Popular Protest',
          badge: `Stage: ${stage}`,
          badgeClass: `badge-unrest ${stage.toLowerCase()}`,
          rows: [
            { label: 'National Protest Energy', val: `${unrestVal} / 10.00`, valClass: unrestVal > 3 ? 'text-ruby' : 'text-green' },
            { label: 'Turn Protest Delta', val: `${deltaHtml} / turn` },
            { label: 'Civil Threat Classification', val: stage, valClass: `badge-unrest ${stage.toLowerCase()}` },
            { label: 'Root Grievance Vectors', val: 'Overwork, Enclosure, Hunger, Taxes' },
            { label: 'Stationed Garrisons', val: `${macro.garrison || 0} soldiers active` },
            { label: 'Revolution Threshold', val: 'Riot (6.5) → Insurrection (8.0)' }
          ],
          footer: 'Press [C] for 6-cause breakdown or [G] to deploy garrisons & lower taxes.'
        };
      }

      case 'gini': {
        const giniVal = Number(macro.gini || 0).toFixed(2);
        const rating = macro.gini < 0.30 ? 'Equitable (<0.30)' : (macro.gini < 0.45 ? 'Moderate (0.30–0.45)' : 'High Disparity (>0.45)');
        const ratingClass = macro.gini < 0.30 ? 'text-green' : (macro.gini < 0.45 ? 'text-gold' : 'text-ruby');
        return {
          title: '⚖️ Wealth Disparity (Gini Index)',
          badge: `Gini: ${giniVal}`,
          badgeClass: ratingClass,
          rows: [
            { label: 'Gini Inequality Coefficient', val: giniVal, valClass: ratingClass },
            { label: 'Distribution Assessment', val: rating, valClass: ratingClass },
            { label: 'Accumulation Mechanism', val: 'Enclosed estates vs landless wage-labor' },
            { label: 'Social Friction Risk', val: macro.gini > 0.40 ? 'Severe class tension' : 'Stable social cohesion' },
            { label: 'Redistribution Tools', val: 'Revert customary commons, fair wages' }
          ],
          footer: 'View Cadastre tab in tile inspection to re-open common land for tenants.'
        };
      }

      case 'trade': {
        const tb = Math.round(macro.trade_balance || 0);
        const tbHtml = tb >= 0 ? `<span class="delta-pos">+$${tb.toLocaleString()}</span>` : `<span class="delta-neg">-$${Math.abs(tb).toLocaleString()}</span>`;
        const tDelta = Math.round(macro.trade_delta || 0);
        const tDeltaHtml = tDelta >= 0 ? `<span class="delta-pos">+$${tDelta.toLocaleString()}</span>` : `<span class="delta-neg">-$${Math.abs(tDelta).toLocaleString()}</span>`;
        return {
          title: '🚢 Foreign Trade & Customs Ledger',
          badge: tb >= 0 ? 'Trade Surplus' : 'Trade Deficit',
          badgeClass: tb >= 0 ? 'text-green' : 'text-ruby',
          rows: [
            { label: 'Net Commercial Balance', val: `${tbHtml}` },
            { label: 'Turn Balance Delta', val: `${tDeltaHtml} / turn` },
            { label: 'Total Foreign Exports', val: `$${Math.round(macro.exports || 0).toLocaleString()}`, valClass: 'text-cyan' },
            { label: 'Total Foreign Imports', val: `$${Math.round(macro.imports || 0).toLocaleString()}`, valClass: 'text-gold' },
            { label: 'Statutory Customs Tariff', val: `${((macro.tariff_rate || 0.10) * 100).toFixed(1)}% import duty` }
          ],
          footer: 'Dispatch envoys to sign bilateral trade pacts via Diplomacy [D].'
        };
      }

      case 'col': {
        const colVal = Number(macro.cost_of_living || 1.0).toFixed(2);
        return {
          title: '🧺 Cost of Living & Commodity Basket',
          badge: `CoL: ${colVal}`,
          badgeClass: 'text-gold',
          rows: [
            { label: 'Consumer Market Basket', val: `${colVal}x index` },
            { label: 'Normalized Food Price', val: `$${colVal} / bushel`, valClass: 'text-green' },
            { label: 'Purchasing Affordability', val: macro.cost_of_living <= 1.25 ? 'Stable / Accessible' : 'Price Pressures', valClass: macro.cost_of_living <= 1.25 ? 'text-green' : 'text-gold' },
            { label: 'Logistics Infrastructure', val: 'Transport costs inflate remote markets' },
            { label: 'Remediation Decrees', val: 'Pave regional highways & standardize routes' }
          ],
          footer: 'Issue provincial highway decrees in Governance [G] to lower freight costs.'
        };
      }

      case 'isrb': {
        const rating = macro.credit_rating || 'BBB';
        const yld = (macro.bond_yield !== undefined ? macro.bond_yield.toFixed(2) : '0.18') + '%';
        return {
          title: '🏛️ ISRB Sovereign Rating Desk',
          badge: `${rating} | ${yld}`,
          badgeClass: 'text-gold',
          rows: [
            { label: 'ISRB Sovereign Credit Grade', val: rating, valClass: 'text-gold' },
            { label: 'Benchmark 10Y Bond Yield', val: yld, valClass: 'text-cyan' },
            { label: 'Total Outstanding Debt', val: `$${Math.round(macro.public_debt || 0).toLocaleString()}`, valClass: macro.public_debt > 0 ? 'text-ruby' : 'text-green' },
            { label: 'International Market Access', val: ['AAA','AA','A'].includes(rating) ? 'Prime Tier (Low Cost)' : (['BBB','BB'].includes(rating) ? 'Investment Grade' : 'High Risk Speculative') },
            { label: 'Credit Rating Factors', val: 'Debt ratio, real GDP growth, unrest score' }
          ],
          footer: 'Press [S] to open Sovereign Debt suite, issue bonds, or lobby the ISRB.'
        };
      }

      case 'turn': {
        return {
          title: '⏱️ Simulation Engine & Chronicle',
          badge: `Turn ${worldState.turn || 0}`,
          badgeClass: 'text-cyan',
          rows: [
            { label: 'Current World Turn', val: `${worldState.turn || 0}` },
            { label: 'Simulation State', val: isPlaying ? 'Running (Auto-advancing)' : 'Paused', valClass: isPlaying ? 'text-green' : 'text-gold' },
            { label: 'Tick Speed', val: '1 turn every ~400ms' },
            { label: 'Hotkey Controls', val: 'Space = Play/Pause, Enter = +1 Step' }
          ],
          footer: 'Press Space to play or pause the sovereign historical simulation.'
        };
      }

      default:
        return null;
    }
  }

  function renderMacroTooltip(statKey, anchorEl) {
    const popover = document.getElementById('macro-tooltip-popover');
    if (!popover || !anchorEl) return;

    const data = getMacroTooltipContent(statKey);
    if (!data) return;

    popover.innerHTML = `
      <div class="popover-header">
        <div class="popover-title-row">
          <span>${data.title}</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="popover-badge ${data.badgeClass || ''}">${data.badge}</span>
          <button class="popover-close-btn" id="popover-close-btn" aria-label="Close tooltip">&times;</button>
        </div>
      </div>
      <div class="popover-body">
        ${data.rows.map(r => `
          <div class="popover-row">
            <span class="row-label">${r.label}</span>
            <span class="row-val ${r.valClass || ''}">${r.val}</span>
          </div>
        `).join('')}
      </div>
      <div class="popover-footer">
        ${data.footer}
      </div>
    `;

    popover.classList.remove('hidden');

    const closeBtn = popover.querySelector('#popover-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        hideMacroTooltip();
      });
    }

    // Positioning
    const rect = anchorEl.getBoundingClientRect();
    const popoverW = Math.min(330, window.innerWidth - 20);
    popover.style.width = `${popoverW}px`;

    let left = rect.left + rect.width / 2 - popoverW / 2;
    left = Math.max(10, Math.min(window.innerWidth - popoverW - 10, left));
    const top = rect.bottom + 6;

    popover.style.left = `${left}px`;
    popover.style.top = `${top}px`;

    // Arrow offset
    const arrowX = Math.max(16, Math.min(popoverW - 20, (rect.left + rect.width / 2) - left));
    popover.style.setProperty('--arrow-offset', `${arrowX}px`);
  }

  function showMacroTooltip(statKey, anchorEl, lock = false) {
    activeTooltipStat = statKey;
    if (lock) isTooltipLocked = true;

    document.querySelectorAll('.macro-stat, .turn-box').forEach(el => el.classList.remove('active'));
    anchorEl.classList.add('active');

    renderMacroTooltip(statKey, anchorEl);
  }

  function hideMacroTooltip() {
    activeTooltipStat = null;
    isTooltipLocked = false;
    const popover = document.getElementById('macro-tooltip-popover');
    if (popover) popover.classList.add('hidden');
    document.querySelectorAll('.macro-stat, .turn-box').forEach(el => el.classList.remove('active'));
  }

  function setupTopBarTooltips() {
    const statElements = document.querySelectorAll('.macro-stat, .turn-box');
    statElements.forEach(el => {
      const statKey = el.dataset.stat;
      if (!statKey) return;

      // Click to open & lock popover
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        if (activeTooltipStat === statKey && isTooltipLocked) {
          hideMacroTooltip();
        } else {
          showMacroTooltip(statKey, el, true);
        }
      });

      // Hover on desktop
      el.addEventListener('mouseenter', () => {
        if (!isTooltipLocked) {
          clearTimeout(tooltipHoverTimeout);
          tooltipHoverTimeout = setTimeout(() => {
            if (!isTooltipLocked) showMacroTooltip(statKey, el, false);
          }, 80);
        }
      });

      el.addEventListener('mouseleave', () => {
        clearTimeout(tooltipHoverTimeout);
        if (!isTooltipLocked) {
          hideMacroTooltip();
        }
      });
    });

    // Dismiss when clicking anywhere outside
    document.addEventListener('click', (e) => {
      const popover = document.getElementById('macro-tooltip-popover');
      if (popover && !popover.classList.contains('hidden')) {
        if (!popover.contains(e.target) && !e.target.closest('.macro-stat') && !e.target.closest('.turn-box')) {
          hideMacroTooltip();
        }
      }
    });

    // Dismiss on Escape
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && activeTooltipStat) {
        hideMacroTooltip();
      }
    });

    window.addEventListener('resize', () => {
      if (activeTooltipStat) {
        const anchorEl = document.querySelector(`[data-stat="${activeTooltipStat}"]`);
        if (anchorEl) renderMacroTooltip(activeTooltipStat, anchorEl);
      }
    });
  }

  // ---------------- Left Sovereign Suites Navigation & Drawers ----------------

  function setupLeftDrawer() {
    // Dock Tab Buttons
    document.querySelectorAll('.dock-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const suite = btn.dataset.drawer;
        if (activeLeftDrawer === suite) closeLeftDrawer();
        else openLeftDrawer(suite);
      });
    });

    // Drawer Top Suite Icon Switcher Buttons
    document.querySelectorAll('.suite-tab-icon-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        openLeftDrawer(btn.dataset.drawer);
      });
    });

    if (btnCloseLeft) {
      btnCloseLeft.addEventListener('click', closeLeftDrawer);
    }

    // Suite 1: Build Filters & Categories
    document.querySelectorAll('.cat-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeBuildCat = btn.dataset.cat;
        renderBuildRecipes();
      });
    });

    document.querySelectorAll('.tier-filter-chips .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.tier-filter-chips .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeBuildTier = chip.dataset.tier;
        renderBuildRecipes();
      });
    });

    // Suite 2: Governance Scopes & Decrees
    document.querySelectorAll('.scope-btn[data-gov-scope]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.scope-btn[data-gov-scope]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeGovScope = btn.dataset.govScope;

        ['tile', 'province', 'nation', 'frontier'].forEach(s => {
          const el = document.getElementById(`gov-scope-${s}`);
          if (el) el.classList.toggle('hidden', s !== activeGovScope);
        });
      });
    });

    // Gov Sliders & Buttons
    setupGovPolicyControls();

    // Suite 4: Debt Scopes
    document.querySelectorAll('.scope-btn[data-debt-scope]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.scope-btn[data-debt-scope]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeDebtScope = btn.dataset.debtScope;

        const elDom = document.getElementById('debt-scope-domestic');
        const elFor = document.getElementById('debt-scope-foreign');
        if (elDom) elDom.classList.toggle('hidden', activeDebtScope !== 'domestic');
        if (elFor) elFor.classList.toggle('hidden', activeDebtScope !== 'foreign');
      });
    });

    setupDebtControls();

    // Suite 5: Science Eras
    document.querySelectorAll('.era-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.era-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeScienceEra = parseInt(chip.dataset.era, 10);
        renderScienceTechs();
      });
    });

    // Suite 6: Military Recruits
    const btnRecruitGarrison = document.getElementById('btn-recruit-garrison');
    if (btnRecruitGarrison) {
      btnRecruitGarrison.addEventListener('click', () => {
        if (!selectedTileName) {
          showToast('Select a territory to station recruited garrison.', true);
          return;
        }
        sendCommand('RECRUIT_UNIT', { tile: selectedTileName, soldiers: 15 });
      });
    }

    const btnMobilizeExpedition = document.getElementById('btn-mobilize-expedition');
    if (btnMobilizeExpedition) {
      btnMobilizeExpedition.addEventListener('click', () => {
        sendCommand('RECRUIT_UNIT', { tile: selectedTileName || (worldState && worldState.tiles[0].name), soldiers: 50 });
      });
    }
  }

  function openLeftDrawer(suiteName) {
    hideMacroTooltip();
    activeLeftDrawer = suiteName;
    if (leftDrawer) leftDrawer.classList.remove('closed');

    document.querySelectorAll('.dock-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.drawer === suiteName);
    });
    document.querySelectorAll('.suite-tab-icon-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.drawer === suiteName);
    });

    document.querySelectorAll('.drawer-pane').forEach(pane => {
      pane.classList.remove('active');
    });

    const targetPane = document.getElementById(`pane-${suiteName}`);
    if (targetPane) targetPane.classList.add('active');

    const titles = {
      build: '🔨 Build & Infrastructure',
      gov: '🏛️ Governance & Decrees',
      diplomacy: '🤝 Diplomacy & Treaties',
      debt: '📜 Sovereign Debt & ISRB',
      science: '🔬 Science & Technology Tree',
      military: '⚔️ Military Operations'
    };
    if (drawerTitle) drawerTitle.textContent = titles[suiteName] || 'Sovereign Suite';

    updateLeftDrawerPanes();
  }

  function closeLeftDrawer() {
    activeLeftDrawer = null;
    if (leftDrawer) leftDrawer.classList.add('closed');
    document.querySelectorAll('.dock-tab-btn').forEach(btn => btn.classList.remove('active'));
  }

  function updateLeftDrawerPanes() {
    if (!activeLeftDrawer) return;

    if (activeLeftDrawer === 'build') {
      const lbl = document.getElementById('build-target-tile');
      if (lbl) lbl.textContent = `Selected Tile: ${selectedTileName || 'None'}`;
      renderBuildRecipes();
      renderActiveProjects();
    } else if (activeLeftDrawer === 'gov') {
      const fTarget = document.getElementById('frontier-target-tile');
      if (fTarget) fTarget.textContent = selectedTileName || 'None';
    } else if (activeLeftDrawer === 'diplomacy') {
      renderDiplomacyNations();
    } else if (activeLeftDrawer === 'debt') {
      renderSovereignDebt();
    } else if (activeLeftDrawer === 'science') {
      renderScienceTechs();
    } else if (activeLeftDrawer === 'military') {
      renderMilitarySuite();
    }
  }

  // ---------------- Governance Controls & Decrees ----------------

  function setupGovPolicyControls() {
    const sTax = document.getElementById('slider-income-tax');
    const lblTax = document.getElementById('lbl-income-tax');
    const sTariff = document.getElementById('slider-tariff-rate');
    const lblTariff = document.getElementById('lbl-tariff-rate');
    const sWorkday = document.getElementById('slider-gov-workday');
    const lblWorkday = document.getElementById('lbl-gov-workday');

    if (sTax) {
      sTax.addEventListener('input', () => {
        if (lblTax) lblTax.textContent = `${(parseFloat(sTax.value) * 100).toFixed(1)}%`;
      });
      sTax.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'tax_rate', val: parseFloat(sTax.value) });
      });
    }

    if (sTariff) {
      sTariff.addEventListener('input', () => {
        if (lblTariff) lblTariff.textContent = `${(parseFloat(sTariff.value) * 100).toFixed(1)}%`;
      });
      sTariff.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'tariff_rate', val: parseFloat(sTariff.value) });
      });
    }

    if (sWorkday) {
      sWorkday.addEventListener('input', () => {
        if (lblWorkday) lblWorkday.textContent = `${parseFloat(sWorkday.value).toFixed(1)}h`;
      });
      sWorkday.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'workday_hours', val: parseFloat(sWorkday.value) });
      });
    }

    // Quick +/- Tax Buttons
    const btnTaxMinus = document.getElementById('btn-tax-minus2');
    const btnTaxPlus = document.getElementById('btn-tax-plus2');
    if (btnTaxMinus && sTax) {
      btnTaxMinus.addEventListener('click', () => {
        sTax.value = Math.max(0, parseFloat(sTax.value) - 0.02);
        sTax.dispatchEvent(new Event('input'));
        sTax.dispatchEvent(new Event('change'));
      });
    }
    if (btnTaxPlus && sTax) {
      btnTaxPlus.addEventListener('click', () => {
        sTax.value = Math.min(0.50, parseFloat(sTax.value) + 0.02);
        sTax.dispatchEvent(new Event('input'));
        sTax.dispatchEvent(new Event('change'));
      });
    }

    // Workday Quick +/- Buttons
    const btnWorkdayMinus = document.getElementById('btn-workday-minus2');
    const btnWorkdayPlus = document.getElementById('btn-workday-plus2');
    if (btnWorkdayMinus && sWorkday) {
      btnWorkdayMinus.addEventListener('click', () => {
        sWorkday.value = Math.max(8, parseFloat(sWorkday.value) - 2.0);
        sWorkday.dispatchEvent(new Event('input'));
        sWorkday.dispatchEvent(new Event('change'));
      });
    }
    if (btnWorkdayPlus && sWorkday) {
      btnWorkdayPlus.addEventListener('click', () => {
        sWorkday.value = Math.min(16, parseFloat(sWorkday.value) + 2.0);
        sWorkday.dispatchEvent(new Event('input'));
        sWorkday.dispatchEvent(new Event('change'));
      });
    }

    // Tax & Tariff Presets
    document.querySelectorAll('.btn-tax-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        const val = parseFloat(btn.dataset.val);
        if (sTax) {
          sTax.value = val;
          sTax.dispatchEvent(new Event('input'));
          sTax.dispatchEvent(new Event('change'));
        }
      });
    });

    document.querySelectorAll('.btn-tariff-preset').forEach(btn => {
      btn.addEventListener('click', () => {
        const val = parseFloat(btn.dataset.val);
        if (sTariff) {
          sTariff.value = val;
          sTariff.dispatchEvent(new Event('input'));
          sTariff.dispatchEvent(new Event('change'));
        }
      });
    });

    // Checkbox Toggles
    const chkTenHour = document.getElementById('chk-ten-hour');
    if (chkTenHour) {
      chkTenHour.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'ten_hour_act', val: chkTenHour.checked });
      });
    }

    const chkSafety = document.getElementById('chk-factory-safety');
    if (chkSafety) {
      chkSafety.addEventListener('change', () => {
        sendCommand('SET_FACTORY_SAFETY', { enabled: chkSafety.checked });
      });
    }

    const chkTruck = document.getElementById('chk-truck-act');
    if (chkTruck) {
      chkTruck.addEventListener('change', () => {
        sendCommand('SET_TRUCK_ACT', { enabled: chkTruck.checked });
      });
    }

    const chkBorders = document.getElementById('chk-open-borders');
    if (chkBorders) {
      chkBorders.addEventListener('change', () => {
        sendCommand('SET_BORDER_POLICY', { open_borders: chkBorders.checked });
      });
    }

    // City Decrees
    const btnRelief = document.getElementById('btn-decree-granary');
    if (btnRelief) {
      btnRelief.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a territory first.', true); return; }
        sendCommand('EXECUTE_DECREE', { tile: selectedTileName, decree: 'food_relief' });
      });
    }

    const btnCurfew = document.getElementById('btn-decree-order');
    if (btnCurfew) {
      btnCurfew.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a territory first.', true); return; }
        sendCommand('EXECUTE_DECREE', { tile: selectedTileName, decree: 'police_curfew' });
      });
    }

    const btnPatrol = document.getElementById('btn-decree-patrol');
    if (btnPatrol) {
      btnPatrol.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a territory first.', true); return; }
        sendCommand('EXECUTE_DECREE', { tile: selectedTileName, decree: 'safety_patrol' });
      });
    }

    const btnFarmSub = document.getElementById('btn-decree-farming');
    if (btnFarmSub) {
      btnFarmSub.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a territory first.', true); return; }
        sendCommand('EXECUTE_DECREE', { tile: selectedTileName, decree: 'subsidize_farming' });
      });
    }

    const btnUbiTile = document.getElementById('btn-decree-ubi-tile');
    if (btnUbiTile) {
      btnUbiTile.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a territory first.', true); return; }
        sendCommand('EXECUTE_DECREE', { tile: selectedTileName, decree: 'ubi' });
      });
    }

    const btnEncloseTile = document.getElementById('btn-decree-enclose-tile');
    if (btnEncloseTile) {
      btnEncloseTile.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a territory first.', true); return; }
        sendCommand('ENCLOSE_PLOT', { tile: selectedTileName, plot_id: 'default' });
      });
    }

    // Provincial Decrees
    const provDecrees = [
      { id: 'btn-prov-highway', decree: 'pave_highway' },
      { id: 'btn-prov-health', decree: 'health_initiative' },
      { id: 'btn-prov-equalize', decree: 'provincial_equalization' },
      { id: 'btn-prov-routes', decree: 'standardize_routes' },
      { id: 'btn-prov-harmonize', decree: 'harmonize_taxes' },
      { id: 'btn-prov-soil', decree: 'soil_conservation' }
    ];
    provDecrees.forEach(({ id, decree }) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener('click', () => {
          const prov = (selectedTileDetail && selectedTileDetail.province) || 'Central Province';
          sendCommand('PROVINCE_DECREE', { province: prov, decree });
        });
      }
    });

    // Sovereign Decrees
    const btnSciencePrize = document.getElementById('btn-decree-science-prize');
    if (btnSciencePrize) {
      btnSciencePrize.addEventListener('click', () => {
        sendCommand('RESEARCH_TECH', { action: 'pledge_prize', tech_id: 'crop_rotation', amount: 300 });
      });
    }

    const btnMobilize = document.getElementById('btn-decree-mobilize');
    if (btnMobilize) {
      btnMobilize.addEventListener('click', () => {
        sendCommand('RECRUIT_UNIT', { tile: selectedTileName || (worldState && worldState.tiles[0].name), soldiers: 50 });
      });
    }

    const btnSovEqual = document.getElementById('btn-decree-sovereign-equalize');
    if (btnSovEqual) {
      btnSovEqual.addEventListener('click', () => {
        sendCommand('SOVEREIGN_EQUALIZATION', {});
      });
    }

    const btnUbiEmpire = document.getElementById('btn-decree-ubi-empire');
    if (btnUbiEmpire) {
      btnUbiEmpire.addEventListener('click', () => {
        sendCommand('EXECUTE_DECREE', { empire: true, decree: 'ubi' });
      });
    }

    // Frontier Actions
    const btnFrontierSponsor = document.getElementById('btn-frontier-sponsor');
    if (btnFrontierSponsor) {
      btnFrontierSponsor.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select a wilderness territory to settle.', true); return; }
        sendCommand('FRONTIER_EXPEDITION', { tile: selectedTileName, action: 'sponsor_settlers' });
      });
    }

    const btnFrontierAid = document.getElementById('btn-frontier-aid');
    if (btnFrontierAid) {
      btnFrontierAid.addEventListener('click', () => {
        if (!selectedTileName) { showToast('Select an outpost territory.', true); return; }
        sendCommand('FRONTIER_EXPEDITION', { tile: selectedTileName, action: 'pioneer_aid' });
      });
    }
  }

  // ---------------- Suite 1: Build & Infrastructure Engine ----------------

  function renderBuildRecipes() {
    const list = document.getElementById('build-recipes-list');
    if (!list || !worldState || !worldState.build_recipes) return;
    list.innerHTML = '';

    const all = worldState.build_recipes;
    const catList = all[activeBuildCat] || all.industry || [];

    const filtered = catList.filter(r => {
      if (activeBuildTier === 'all') return true;
      return (r.tier || 'tile') === activeBuildTier;
    });

    if (filtered.length === 0) {
      list.innerHTML = '<div class="empty-state">No blueprints available in this category.</div>';
      return;
    }

    filtered.forEach(recipe => {
      const card = document.createElement('div');
      card.className = 'item-card';

      card.innerHTML = `
        <div class="card-top">
          <span class="card-title">🏛️ ${recipe.name}</span>
          <span class="card-badge ${recipe.status || 'unlocked'}">${recipe.tier || 'Tier 1'}</span>
        </div>
        <div class="card-desc">${recipe.description || 'Public works infrastructure blueprint.'}</div>
        <div class="card-meta-row">
          <span>Cost: <strong class="text-gold">$${recipe.cost || 100}</strong></span>
          <span>Time: ${recipe.turns || 3} turns</span>
        </div>
        <button class="btn btn-primary btn-sm mt-2 btn-construct" data-recipe="${recipe.id || recipe.name}">
          🔨 Commission Project
        </button>
      `;

      card.querySelector('.btn-construct').addEventListener('click', () => {
        if (!selectedTileName) {
          showToast('Select a territory on the map first.', true);
          return;
        }

        // Check if shortfall bailout dialog should be triggered
        const tileCost = recipe.cost || 100;
        const onHand = (selectedTileDetail && selectedTileDetail.gov_cash) || 0;

        if (onHand < tileCost && onHand < 50) {
          openFiscalTransferDialog(selectedTileName, recipe.name, tileCost, onHand);
        } else {
          sendCommand('BUILD_PROJECT', { tile: selectedTileName, building: recipe.id || recipe.name });
        }
      });

      list.appendChild(card);
    });
  }

  function renderActiveProjects() {
    const sec = document.getElementById('active-projects-section');
    const list = document.getElementById('active-projects-list');
    if (!sec || !list) return;

    if (!selectedTileDetail || !selectedTileDetail.construction_projects || selectedTileDetail.construction_projects.length === 0) {
      sec.classList.add('hidden');
      return;
    }

    sec.classList.remove('hidden');
    list.innerHTML = '';

    selectedTileDetail.construction_projects.forEach(p => {
      const pct = Math.min(100, Math.round(((p.progress_turns || 1) / (p.total_turns || 3)) * 100));
      const card = document.createElement('div');
      card.className = 'item-card';
      card.innerHTML = `
        <div class="card-top">
          <span class="card-title">⏳ ${p.recipe_name || 'Construction'}</span>
          <span class="text-xs text-dim">${p.progress_turns || 1} / ${p.total_turns || 3} turns</span>
        </div>
        <div class="progress-gauge-container">
          <div class="progress-gauge-fill" style="width: ${pct}%"></div>
        </div>
      `;
      list.appendChild(card);
    });
  }

  // ---------------- Suite 3: Diplomacy & Treaties ----------------

  function renderDiplomacyNations() {
    const tabsBar = document.getElementById('diplo-nation-tabs');
    const activeCard = document.getElementById('diplomacy-active-nation-card');
    const list = document.getElementById('diplomacy-nations-list');
    if (!tabsBar || !worldState || !worldState.nations) return;

    const foreign = worldState.nations.filter(n => n.name !== worldState.player_nation);
    if (foreign.length === 0) {
      if (list) list.innerHTML = '<div class="empty-state">No foreign sovereign nations known.</div>';
      return;
    }

    if (!activeDiploNation || !foreign.find(n => n.name === activeDiploNation)) {
      activeDiploNation = foreign[0].name;
    }

    // Tabs
    tabsBar.innerHTML = '';
    foreign.forEach(n => {
      const btn = document.createElement('button');
      btn.className = `diplo-tab-btn ${n.name === activeDiploNation ? 'active' : ''}`;
      btn.textContent = `👑 ${n.name}`;
      btn.addEventListener('click', () => {
        activeDiploNation = n.name;
        renderDiplomacyNations();
      });
      tabsBar.appendChild(btn);
    });

    const activeNat = foreign.find(n => n.name === activeDiploNation);
    if (activeNat && activeCard) {
      activeCard.innerHTML = `
        <div class="gov-card">
          <div class="flex-between">
            <h4 class="card-title" style="color:${activeNat.flag_color || '#38bdf8'}">👑 ${activeNat.name}</h4>
            <span class="card-badge mastered">${activeNat.regime_type || 'Empire'}</span>
          </div>
          <div class="stat-row mt-2">
            <span>Bilateral Relations Score:</span>
            <strong class="text-gold">${activeNat.relations || 0} / 100</strong>
          </div>
          <div class="stat-row">
            <span>Diplomatic Standing:</span>
            <strong class="text-green">${activeNat.treaty_status || 'Peace'}</strong>
          </div>
          <div class="dual-btn-row mt-3">
            <button class="btn btn-secondary btn-sm btn-diplo-act" data-act="propose_trade">🤝 Propose Trade Pact</button>
            <button class="btn btn-secondary btn-sm btn-diplo-act" data-act="propose_nap">🛡️ Non-Aggression Pact</button>
          </div>
          <div class="dual-btn-row mt-2">
            <button class="btn btn-secondary btn-sm btn-diplo-act" data-act="defensive_alliance">⚔️ Defensive Alliance</button>
            <button class="btn btn-secondary btn-sm text-ruby btn-diplo-act" data-act="declare_war">🔥 Declare War</button>
          </div>
          <button class="btn btn-primary btn-block mt-3 btn-diplo-act" data-act="send_aid">
            🎁 Dispatch Foreign Aid Gift ($100 • +15 Relations)
          </button>
        </div>
      `;

      activeCard.querySelectorAll('.btn-diplo-act').forEach(b => {
        b.addEventListener('click', () => {
          sendCommand('DIPLOMATIC_ACTION', { target: activeNat.name, action: b.dataset.act });
        });
      });
    }
  }

  // ---------------- Suite 4: Sovereign Debt & ISRB ----------------

  function setupDebtControls() {
    document.querySelectorAll('#bond-duration-chips .chip').forEach(c => {
      c.addEventListener('click', () => {
        document.querySelectorAll('#bond-duration-chips .chip').forEach(ch => ch.classList.remove('active'));
        c.classList.add('active');
        activeBondDuration = parseInt(c.dataset.duration, 10);
      });
    });

    const b500 = document.getElementById('btn-issue-bond-500');
    if (b500) {
      b500.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'issue_bond', amount: 500, duration: activeBondDuration });
      });
    }

    const b1000 = document.getElementById('btn-issue-bond-1000');
    if (b1000) {
      b1000.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'issue_bond', amount: 1000, duration: activeBondDuration });
      });
    }

    const bLobby = document.getElementById('btn-lobby-isrb');
    if (bLobby) {
      bLobby.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'lobby_isrb' });
      });
    }

    const bAudit = document.getElementById('btn-audit-rival');
    if (bAudit) {
      bAudit.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'audit_rival' });
      });
    }

    const bSeat = document.getElementById('btn-acquire-seat');
    if (bSeat) {
      bSeat.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'buy_board_seat' });
      });
    }
  }

  function renderSovereignDebt() {
    if (!worldState || !worldState.sovereign_debt) return;
    const sd = worldState.sovereign_debt;

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    setTxt('debt-isrb-rating', sd.credit_rating || 'BBB');
    setTxt('debt-market-yield', `${(sd.benchmark_yield || 0.18).toFixed(2)}% / t`);
    setTxt('debt-total-amount', `$${Math.round(sd.outstanding_debt || 0).toLocaleString()}`);
    setTxt('debt-isrb-seat', sd.isrb_seat ? 'Permanent Member' : 'Observer');

    // Live Bond Offerings
    const oList = document.getElementById('active-offerings-list');
    if (oList) {
      oList.innerHTML = '';
      const offers = sd.live_offerings || [];
      if (offers.length === 0) {
        oList.innerHTML = '<div class="empty-state">No sovereign bond tranches currently issued.</div>';
      } else {
        offers.forEach(b => {
          const c = document.createElement('div');
          c.className = 'item-card';
          c.innerHTML = `
            <div class="card-top">
              <span class="card-title">📜 Tranche #${b.tranche_id || '1'}</span>
              <span class="text-gold">$${Math.round(b.principal).toLocaleString()}</span>
            </div>
            <div class="card-meta-row">
              <span>Coupon: ${(b.coupon_rate * 100).toFixed(2)}%</span>
              <span>Matures: T+${b.turns_remaining}</span>
            </div>
          `;
          oList.appendChild(c);
        });
      }
    }

    // Foreign Available Bonds
    const fList = document.getElementById('foreign-available-list');
    if (fList) {
      fList.innerHTML = '';
      const avail = sd.available_foreign_bonds || [];
      if (avail.length === 0) {
        fList.innerHTML = '<div class="empty-state">No foreign public offerings available.</div>';
      } else {
        avail.forEach(fb => {
          const c = document.createElement('div');
          c.className = 'item-card';
          c.innerHTML = `
            <div class="card-top">
              <span class="card-title">👑 ${fb.seller_nation} Bond</span>
              <span class="card-badge mastered">${fb.credit_rating || 'A'}</span>
            </div>
            <div class="card-meta-row">
              <span>Amount: <strong class="text-gold">$${fb.amount}</strong></span>
              <span>Yield: ${(fb.yield * 100).toFixed(2)}%</span>
            </div>
            <button class="btn btn-primary btn-sm mt-2 btn-buy-foreign" data-seller="${fb.seller_nation}" data-amt="${fb.amount}">
              💵 Purchase Tranche
            </button>
          `;
          c.querySelector('.btn-buy-foreign').addEventListener('click', () => {
            sendCommand('PURCHASE_FOREIGN_BOND', { seller_nation: fb.seller_nation, amount: fb.amount });
          });
          fList.appendChild(c);
        });
      }
    }
  }

  // ---------------- Suite 5: Science & Tech Tree ----------------

  function renderScienceTechs() {
    const rRibbon = document.getElementById('science-resources-ribbon');
    const tList = document.getElementById('science-tech-list');
    if (!worldState) return;

    // Endowments Ribbon
    if (rRibbon && worldState.resources) {
      rRibbon.innerHTML = '';
      worldState.resources.forEach(res => {
        const chip = document.createElement('span');
        chip.className = 'res-chip';
        chip.innerHTML = `⛏️ <strong>${res.name}</strong>: ${res.amount}`;
        rRibbon.appendChild(chip);
      });
    }

    if (!tList || !worldState.science_tree) return;
    tList.innerHTML = '';

    const techs = worldState.science_tree.filter(t => (t.era || 1) === activeScienceEra);
    if (techs.length === 0) {
      tList.innerHTML = '<div class="empty-state">No technologies recorded for this era.</div>';
      return;
    }

    techs.forEach(tech => {
      const card = document.createElement('div');
      card.className = 'item-card';
      const isMastered = (tech.status === 'MASTERED');

      card.innerHTML = `
        <div class="card-top">
          <span class="card-title">🔬 ${tech.name}</span>
          <span class="card-badge ${tech.status ? tech.status.toLowerCase() : 'locked'}">${tech.status || 'LOCKED'}</span>
        </div>
        <div class="card-desc">${tech.description || 'Scientific discovery expanding industrial production.'}</div>
        <div class="card-meta-row">
          <span>Prerequisites: ${tech.prereqs ? tech.prereqs.join(', ') : 'None'}</span>
          <span>Diffusing: ${Math.round((tech.diffusion || 0) * 100)}%</span>
        </div>
        ${!isMastered ? `
          <button class="btn btn-secondary btn-sm mt-2 btn-pledge-prize" data-tech="${tech.id}">
            🏆 Pledge Royal Bounty ($300)
          </button>
        ` : ''}
      `;

      if (!isMastered) {
        card.querySelector('.btn-pledge-prize').addEventListener('click', () => {
          sendCommand('RESEARCH_TECH', { action: 'pledge_prize', tech_id: tech.id, amount: 300 });
        });
      }

      tList.appendChild(card);
    });
  }

  // ---------------- Suite 6: Military Suite ----------------

  function renderMilitarySuite() {
    if (!worldState) return;
    const m = worldState.military || {};

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    setTxt('lbl-national-soldiers', `${(m.total_soldiers || 0).toLocaleString()} soldiers`);
    setTxt('lbl-military-upkeep', `$${Math.round(m.military_upkeep || 0).toLocaleString()} / turn`);

    const gCount = (selectedTileDetail && selectedTileDetail.garrison) || 0;
    setTxt('lbl-garrison-count', `${gCount} troops`);
    setTxt('military-tile-lbl', `Selected Territory: ${selectedTileName || 'None'}`);

    const aList = document.getElementById('military-armies-list');
    if (aList) {
      aList.innerHTML = '';
      const armies = m.armies || [];
      if (armies.length === 0) {
        aList.innerHTML = '<div class="empty-state">No standing field armies deployed.</div>';
      } else {
        armies.forEach(arm => {
          const c = document.createElement('div');
          c.className = 'item-card';
          c.innerHTML = `
            <div class="card-top">
              <span class="card-title">⚔️ ${arm.name || arm.regiment_id}</span>
              <span class="card-badge mastered">XP ${arm.veteran_xp || 1}</span>
            </div>
            <div class="card-meta-row">
              <span>Soldiers: <strong>${arm.soldiers}</strong></span>
              <span>Morale: ${Math.round((arm.morale || 1) * 100)}%</span>
              <span>Combat: ${arm.combat_power || 100}</span>
            </div>
          `;
          aList.appendChild(c);
        });
      }
    }
  }

  // ---------------- Right Inspection & Analytics Panel ----------------

  function setupRightPanel() {
    if (rightDrawerHandle) {
      rightDrawerHandle.addEventListener('click', () => {
        rightPanel.classList.toggle('collapsed');
      });
    }

    if (drawerToggleBtn) {
      drawerToggleBtn.addEventListener('click', () => {
        rightPanel.classList.toggle('collapsed');
      });
    }

    // Right Panel Tabs
    document.querySelectorAll('.panel-tabs .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.panel-tabs .tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeRightTab = btn.dataset.tab.replace('tab-', '');

        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        const target = document.getElementById(btn.dataset.tab);
        if (target) target.classList.add('active');

        if (activeRightTab === 'charts') renderHistoricalChart();
      });
    });

    // Chart Mode Switcher
    document.querySelectorAll('.scope-btn[data-chart-mode]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.scope-btn[data-chart-mode]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeChartMode = btn.dataset.chartMode;
        populateChartChips();
        renderHistoricalChart();
      });
    });

    // Citizen Subtabs
    document.querySelectorAll('.scope-btn[data-cit-sub]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.scope-btn[data-cit-sub]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCitizenSub = btn.dataset.citSub;

        const elC = document.getElementById('citizens-sub-class');
        const elL = document.getElementById('citizens-sub-labor');
        if (elC) elC.classList.toggle('hidden', activeCitizenSub !== 'class');
        if (elL) elL.classList.toggle('hidden', activeCitizenSub !== 'labor');
      });
    });

    // Cadastre Scroll Controls
    const bUp = document.getElementById('btn-plots-scroll-up');
    const bDown = document.getElementById('btn-plots-scroll-down');
    if (bUp) {
      bUp.addEventListener('click', () => {
        cadastreScrollOffset = Math.max(0, cadastreScrollOffset - 5);
        if (selectedTileDetail) updateTileInspectionUI(selectedTileDetail);
      });
    }
    if (bDown) {
      bDown.addEventListener('click', () => {
        cadastreScrollOffset += 5;
        if (selectedTileDetail) updateTileInspectionUI(selectedTileDetail);
      });
    }

    populateChartChips();
  }

  function populateChartChips() {
    const container = document.getElementById('chart-chips-container');
    if (!container) return;
    container.innerHTML = '';

    const chartCatalog = {
      economic: [
        { id: 'gdp', name: 'Real GDP' },
        { id: 'treasury', name: 'Treasury' },
        { id: 'food_price', name: 'Food Price' },
        { id: 'pop', name: 'Pop/Hunger' },
        { id: 'production', name: 'Production' },
        { id: 'trade', name: 'Trade Flow' },
        { id: 'gov_income', name: 'Gov Revenue' },
        { id: 'gini', name: 'Gini Inequality' },
        { id: 'inventories', name: 'Commodity Stocks' },
        { id: 'unrest', name: 'Protest Energy' }
      ],
      ecological: [
        { id: 'soil', name: 'Soil & Nutrition' },
        { id: 'smog', name: 'Smog Particulate' },
        { id: 'effluent', name: 'Water Effluent' },
        { id: 'epidemics', name: 'Epidemic Cases' },
        { id: 'health_outlays', name: 'Healthcare Outlays' },
        { id: 'illness_deaths', name: 'Illness Fatalities' }
      ],
      labor: [
        { id: 'shift_hours', name: 'Shift Hours & (s/v)' },
        { id: 'alienation', name: '4D Alienation' },
        { id: 'consciousness', name: 'Class Consciousness' },
        { id: 'strikes', name: 'Wildcat Strikes' }
      ]
    };

    const chips = chartCatalog[activeChartMode] || chartCatalog.economic;
    if (!chips.find(c => c.id === activeChartMetric)) {
      activeChartMetric = chips[0].id;
    }

    chips.forEach(c => {
      const btn = document.createElement('button');
      btn.className = `chip ${c.id === activeChartMetric ? 'active' : ''}`;
      btn.textContent = c.name;
      btn.addEventListener('click', () => {
        document.querySelectorAll('#chart-chips-container .chip').forEach(ch => ch.classList.remove('active'));
        btn.classList.add('active');
        activeChartMetric = c.id;
        renderHistoricalChart();
      });
      container.appendChild(btn);
    });
  }

  // ---------------- 20 Charts Engine ----------------

  function renderHistoricalChart() {
    const chartCanvas = document.getElementById('historical-chart-canvas');
    if (!chartCanvas || !worldState) return;

    const cCtx = chartCanvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = chartCanvas.clientWidth || 380;
    const h = chartCanvas.clientHeight || 220;

    chartCanvas.width = Math.round(w * dpr);
    chartCanvas.height = Math.round(h * dpr);

    cCtx.save();
    cCtx.scale(dpr, dpr);
    cCtx.clearRect(0, 0, w, h);

    // Look for data series either in tile deep inspection or world history
    let values = [];
    let turns = (worldState.history && worldState.history.turns) || [1, 2, 3];

    if (selectedTileDetail && selectedTileDetail.charts) {
      const cMode = selectedTileDetail.charts[activeChartMode];
      if (cMode && cMode[activeChartMetric]) values = cMode[activeChartMetric];
    }

    if (values.length === 0 && worldState.history) {
      values = worldState.history[activeChartMetric] || [];
    }

    // Default trend mock fallback if early turn
    if (values.length < 2) {
      const base = 50;
      values = [base, base + 4, base + 2, base + 7, base + 6];
    }

    const padL = 44;
    const padR = 14;
    const padT = 18;
    const padB = 24;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;

    let minVal = Math.min(...values);
    let maxVal = Math.max(...values);
    if (minVal === maxVal) {
      minVal -= 1;
      maxVal += 1;
    }
    const valSpan = maxVal - minVal;

    // Gridlines & Y-Axis
    cCtx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    cCtx.lineWidth = 1;
    cCtx.fillStyle = '#64748b';
    cCtx.font = '10px sans-serif';
    cCtx.textAlign = 'right';

    for (let i = 0; i <= 4; i++) {
      const y = padT + (plotH / 4) * i;
      const val = maxVal - (valSpan / 4) * i;
      cCtx.beginPath();
      cCtx.moveTo(padL, y);
      cCtx.lineTo(w - padR, y);
      cCtx.stroke();
      cCtx.fillText(val >= 1000 ? `${(val / 1000).toFixed(1)}k` : val.toFixed(val < 10 ? 1 : 0), padL - 6, y + 3);
    }

    // Line Curve
    cCtx.beginPath();
    const colors = {
      gdp: '#38bdf8',
      treasury: '#f59e0b',
      food_price: '#10b981',
      pop: '#a855f7',
      unrest: '#ef4444',
      soil: '#10b981',
      smog: '#94a3b8',
      alienation: '#f43f5e'
    };
    const strokeColor = colors[activeChartMetric] || '#38bdf8';
    cCtx.strokeStyle = strokeColor;
    cCtx.lineWidth = 2.5;

    values.forEach((v, idx) => {
      const x = padL + (plotW / Math.max(1, values.length - 1)) * idx;
      const y = padT + plotH - ((v - minVal) / valSpan) * plotH;
      if (idx === 0) cCtx.moveTo(x, y);
      else cCtx.lineTo(x, y);
    });
    cCtx.stroke();

    // Data Points
    cCtx.fillStyle = strokeColor;
    values.forEach((v, idx) => {
      const x = padL + (plotW / Math.max(1, values.length - 1)) * idx;
      const y = padT + plotH - ((v - minVal) / valSpan) * plotH;
      cCtx.beginPath();
      cCtx.arc(x, y, 2.5, 0, Math.PI * 2);
      cCtx.fill();
    });

    const lText = document.getElementById('chart-legend-text');
    if (lText) lText.textContent = `${activeChartMetric.toUpperCase()}: Historical Trend over Turns (Min ${minVal.toFixed(1)} | Max ${maxVal.toFixed(1)})`;

    cCtx.restore();
  }

  // ---------------- Tile Deep Inspection & Cadastre ----------------

  function updateTileInspectionUI(tile) {
    if (!tile) return;
    selectedTileDetail = tile;

    if (tileNameEl) tileNameEl.textContent = tile.display_name || tile.name;
    if (tileSubEl) tileSubEl.textContent = `${tile.nation || 'Wilderness'} • ${tile.biome} (▲${Math.round(tile.elevation_meters || 0)}m)`;

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    setTxt('stat-nation', tile.nation || 'Wilderness');
    setTxt('stat-pop', (tile.population || 0).toLocaleString());
    setTxt('stat-biome', tile.biome || 'Plains');
    setTxt('stat-elevation', `${Math.round(tile.elevation_meters || 0)}m`);
    setTxt('stat-gdp', `$${Math.round(tile.gdp || 0).toLocaleString()}`);
    setTxt('stat-unrest', `${(tile.protest_energy || 0).toFixed(2)}`);

    // Market Prices
    const pricesGrid = document.getElementById('market-prices-grid');
    if (pricesGrid && tile.market_prices) {
      pricesGrid.innerHTML = '';
      Object.entries(tile.market_prices).forEach(([g, price]) => {
        const item = document.createElement('div');
        item.className = 'price-item';
        item.innerHTML = `<div class="p-name">${g}</div><div class="p-val">$${price.toFixed(2)}</div>`;
        pricesGrid.appendChild(item);
      });
    }

    // Installed Buildings
    const bldList = document.getElementById('installed-buildings-list');
    if (bldList) {
      bldList.innerHTML = '';
      if (!tile.buildings || tile.buildings.length === 0) {
        bldList.innerHTML = '<span class="empty-tag">No structures installed</span>';
      } else {
        tile.buildings.forEach(b => {
          const tag = document.createElement('span');
          tag.className = 'building-tag';
          tag.textContent = `🏛️ ${b}`;
          bldList.appendChild(tag);
        });
      }
    }

    // Ecology
    if (tile.ecology) {
      setTxt('eco-soil', `${tile.ecology.soil_fertility}%`);
      setTxt('eco-smog', `${tile.ecology.pollution_air}`);
      setTxt('eco-nut', `${tile.ecology.nutrition_density}%`);
    }

    // Cadastre Tab
    if (tile.tenure) {
      const com = Math.round(tile.tenure.commons_access * 100);
      const feu = Math.round(tile.tenure.feudal_fraction * 100);
      const enc = Math.round(tile.tenure.enclosed_fraction * 100);

      const bCom = document.getElementById('bar-commons');
      const bFeu = document.getElementById('bar-feudal');
      const bEnc = document.getElementById('bar-enclosed');

      if (bCom) bCom.style.width = `${com}%`;
      if (bFeu) bFeu.style.width = `${feu}%`;
      if (bEnc) bEnc.style.width = `${enc}%`;

      setTxt('lbl-commons', `${com}%`);
      setTxt('lbl-feudal', `${feu}%`);
      setTxt('lbl-enclosed', `${enc}%`);

      const plotsList = document.getElementById('plots-list');
      const pCount = document.getElementById('plot-count');
      if (plotsList && tile.tenure.plots) {
        if (pCount) pCount.textContent = tile.tenure.plots.length;
        plotsList.innerHTML = '';

        const visiblePlots = tile.tenure.plots.slice(cadastreScrollOffset, cadastreScrollOffset + 8);
        if (visiblePlots.length === 0) {
          plotsList.innerHTML = '<div class="empty-state">No cadastral parcels registered.</div>';
        } else {
          visiblePlots.forEach(p => {
            const row = document.createElement('div');
            row.className = 'item-card';
            row.innerHTML = `
              <div class="card-top">
                <span class="card-title">📜 Parcel #${p.plot_id}</span>
                <span class="card-badge ${p.tenure === 'enclosed' ? 'mastered' : 'locked'}">${p.tenure}</span>
              </div>
              <div class="card-meta-row">
                <span>Land Use: <strong>${p.production_type || 'arable'}</strong></span>
                <span>Area: ${Math.round(p.fraction * 100)}%</span>
                <span>Tenants: ${p.bound_tenants || 0}</span>
              </div>
              ${p.foreclosure_debt ? `
                <div class="card-badge locked mt-1">⚠️ Foreclosure Debt: $${p.foreclosure_debt} (Due: T+${p.foreclosure_deadline})</div>
              ` : ''}
              <div class="dual-btn-row mt-2">
                ${p.tenure !== 'enclosed' ? `
                  <button class="btn btn-primary btn-xs btn-act-enclose" data-plot="${p.plot_id}">Enclose ($50)</button>
                ` : `
                  <button class="btn btn-secondary btn-xs btn-act-restore" data-plot="${p.plot_id}">Restore Commons</button>
                `}
                <button class="btn btn-secondary btn-xs btn-act-toggle-use" data-plot="${p.plot_id}" data-type="${p.production_type === 'pasture' ? 'arable' : 'pasture'}">
                  To ${p.production_type === 'pasture' ? 'Arable' : 'Pasture'}
                </button>
              </div>
            `;

            const btnEnc = row.querySelector('.btn-act-enclose');
            if (btnEnc) {
              btnEnc.addEventListener('click', () => {
                sendCommand('ENCLOSE_PLOT', { tile: tile.name, plot_id: p.plot_id });
              });
            }

            const btnRes = row.querySelector('.btn-act-restore');
            if (btnRes) {
              btnRes.addEventListener('click', () => {
                sendCommand('RESTORE_COMMONS', { tile: tile.name, plot_id: p.plot_id });
              });
            }

            const btnTog = row.querySelector('.btn-act-toggle-use');
            if (btnTog) {
              btnTog.addEventListener('click', () => {
                sendCommand('CADASTRE_TOGGLE_LAND_USE', { tile: tile.name, plot_id: p.plot_id, production_type: btnTog.dataset.type });
              });
            }

            plotsList.appendChild(row);
          });
        }
      }
    }

    // Living Residents Census
    const citList = document.getElementById('citizens-list');
    if (citList && tile.citizens) {
      citList.innerHTML = '';
      tile.citizens.forEach(c => {
        const row = document.createElement('div');
        row.className = 'citizen-row';
        row.innerHTML = `
          <div>
            <span class="citizen-role">${c.career}</span>
            <span class="text-dim"> (Age ${c.age})</span>
          </div>
          <div class="citizen-info">
            Cash: <strong class="text-gold">$${c.cash}</strong> • Wage: $${c.wage}
          </div>
        `;
        citList.appendChild(row);
      });
    }

    // Labor & Alienation Breakdown
    const wList = document.getElementById('workers-labor-list');
    if (wList && tile.citizens) {
      wList.innerHTML = '';
      tile.citizens.slice(0, 10).forEach(c => {
        const row = document.createElement('div');
        row.className = 'citizen-row';
        row.innerHTML = `
          <div>
            <span class="citizen-role">${c.career}</span>
            <span class="text-dim">Shift: ${c.workday || 12}h</span>
          </div>
          <div class="citizen-info">
            Alienation: <strong class="text-ruby">${c.alienation || '0.2'}</strong>
          </div>
        `;
        wList.appendChild(row);
      });
    }
  }

  function updateRightPanel() {
    if (!worldState) return;

    // News Feed Tab
    const feed = document.getElementById('ticker-feed');
    const badge = document.getElementById('news-badge');
    if (feed && worldState.ticker_events) {
      feed.innerHTML = '';
      if (badge) badge.textContent = worldState.ticker_events.length;
      worldState.ticker_events.slice(-30).reverse().forEach(ev => {
        const item = document.createElement('div');
        item.className = `news-item ${ev.kind || ''}`;
        item.innerHTML = `<strong>[T${ev.t}] ${ev.kind}:</strong> ${ev.text}`;
        feed.appendChild(item);
      });
    }

    if (activeRightTab === 'charts') renderHistoricalChart();
  }

  // ---------------- Modal 1: 6-Tab Comparison Suite [C] ----------------

  function setupCompareModal() {
    if (btnCompare) btnCompare.addEventListener('click', openCompareModal);
    if (btnCloseCompare) btnCloseCompare.addEventListener('click', closeCompareModal);
    if (compareBackdrop) compareBackdrop.addEventListener('click', closeCompareModal);

    document.querySelectorAll('.comp-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.comp-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeCompareTab = btn.dataset.compTab;
        renderCompareTabContent();
      });
    });

    document.querySelectorAll('.drilldown-bar .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.drilldown-bar .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeCompareDrilldown = chip.dataset.drilldown;
        renderCompareTabContent();
      });
    });
  }

  function openCompareModal() {
    hideMacroTooltip();
    if (!compareModal || !worldState) return;
    compareModal.classList.remove('hidden');
    renderCompareTabContent();
  }

  function closeCompareModal() {
    if (compareModal) compareModal.classList.add('hidden');
  }

  function renderCompareTabContent() {
    const container = document.getElementById('compare-tab-pane-container');
    if (!container || !worldState) return;
    container.innerHTML = '';

    const cs = worldState.comparison_suite || {};

    function getDrilldownData(tabObj) {
      if (!tabObj) return [];
      if (Array.isArray(tabObj)) return tabObj;
      const key = activeCompareDrilldown === 'country' ? 'by_country' : (activeCompareDrilldown === 'province' ? 'by_province' : 'by_tile');
      return tabObj[key] || tabObj.by_country || [];
    }

    const isCountry = (activeCompareDrilldown === 'country');
    const isProv = (activeCompareDrilldown === 'province');
    const isTile = (activeCompareDrilldown === 'tile');

    if (activeCompareTab === '1') {
      // Tab 1: Macro Leaderboard with Green/Red Turn Deltas
      const data = getDrilldownData(cs.tab1_macro);
      const table = document.createElement('table');
      table.className = 'table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>${isCountry ? 'Nation' : (isProv ? 'Province' : 'City / Tile')}</th>
            ${!isCountry ? `<th>Nation</th>` : `<th>Regime</th>`}
            ${isTile ? `<th>Province</th>` : ''}
            <th>Treasury ($)</th>
            <th>Population</th>
            <th>GDP ($)</th>
            <th>Unrest</th>
            <th>ISRB Rating</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${data.map(n => {
            const isPlayer = (n.name === worldState.player_nation || n.nation === worldState.player_nation);
            const tDelta = (n.treasury_delta >= 0) ? `<span class="delta-pos">+${Math.round(n.treasury_delta || 0)}</span>` : `<span class="delta-neg">${Math.round(n.treasury_delta || 0)}</span>`;
            let actionBtn = '—';
            if (isCountry && !isPlayer) {
              actionBtn = `<button class="btn btn-secondary btn-xs btn-switch-nat" data-nat="${n.name}">Assume Control</button>`;
            } else if (isTile) {
              actionBtn = `<button class="btn btn-secondary btn-xs btn-goto-tile" data-tile="${n.name}">Focus</button>`;
            }
            return `
              <tr>
                <td><strong style="color:${n.flag_color || '#38bdf8'}">${isCountry ? '👑 ' : (isProv ? '🏛️ ' : '🏙️ ')}${n.name}</strong> ${isPlayer ? '<span class="card-badge mastered">YOU</span>' : ''}</td>
                ${!isCountry ? `<td>${n.nation || '—'}</td>` : `<td>${n.regime_type || 'Monarchy'}</td>`}
                ${isTile ? `<td>${n.province || '—'}</td>` : ''}
                <td class="text-gold">$${Math.round(n.treasury_cash || 0).toLocaleString()} ${tDelta}</td>
                <td>${(n.population || 0).toLocaleString()}</td>
                <td class="text-cyan">$${Math.round(n.gdp || 0).toLocaleString()}</td>
                <td><span class="badge-unrest ${(n.unrest_stage || 'calm').toLowerCase()}">${n.unrest_stage || 'Calm'}</span></td>
                <td><strong class="text-gold">${n.credit_rating || 'BBB'}</strong></td>
                <td>${actionBtn}</td>
              </tr>
            `;
          }).join('')}
        </tbody>
      `;
      table.querySelectorAll('.btn-switch-nat').forEach(b => {
        b.addEventListener('click', () => {
          sendCommand('SELECT_NATION', { nation: b.dataset.nat });
          closeCompareModal();
        });
      });
      table.querySelectorAll('.btn-goto-tile').forEach(b => {
        b.addEventListener('click', () => {
          const t = (worldState.tiles || []).find(tile => tile.name === b.dataset.tile || tile.display_name === b.dataset.tile);
          if (t) {
            selectTile(t);
            camX = t.center_x !== undefined ? t.center_x : (t.col * 60);
            camY = t.center_y !== undefined ? t.center_y : (t.row * 52);
            renderMap();
          }
          closeCompareModal();
        });
      });
      container.appendChild(table);

    } else if (activeCompareTab === '2') {
      // Tab 2: Goods Market & Provincial Output Table
      const data = getDrilldownData(cs.tab2_goods);
      const table = document.createElement('table');
      table.className = 'table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>${isCountry ? 'Nation' : (isProv ? 'Province' : 'City / Tile')}</th>
            ${!isCountry ? `<th>Nation</th>` : ''}
            <th>Grain Output</th>
            <th>Timber Output</th>
            <th>Furniture Output</th>
            <th>Food Price</th>
            <th>Stockpiles</th>
          </tr>
        </thead>
        <tbody>
          ${data.map(p => `
            <tr>
              <td><strong>${p.province}</strong></td>
              ${!isCountry ? `<td>${p.nation || '—'}</td>` : ''}
              <td class="text-green">${p.food_output} t</td>
              <td>${p.wood_output} t</td>
              <td class="text-gold">${p.furniture_output} t</td>
              <td>$${Number(p.food_price || 0).toFixed(2)}</td>
              <td>${p.stockpiles} units</td>
            </tr>
          `).join('')}
        </tbody>
      `;
      container.appendChild(table);

    } else if (activeCompareTab === '3') {
      // Tab 3: Forex & Banking Matrix
      const fx = cs.tab3_forex || {};
      const banking = fx.banking || [];
      const fxMatrix = fx.fx_matrix || {};
      const currs = Object.keys(fxMatrix);

      const div = document.createElement('div');
      div.innerHTML = `
        <h4 class="sub-heading">Provincial Branch Banking Deposits & Currency Reserves</h4>
        <table class="table">
          <thead>
            <tr>
              <th>Entity / Region</th>
              <th>Nation</th>
              <th>Currency</th>
              <th>Bank Deposits</th>
              <th>Credit Liquidity</th>
              <th>Central Reserves</th>
              <th>NEER Index</th>
            </tr>
          </thead>
          <tbody>
            ${banking.map(b => `
              <tr>
                <td><strong>${b.name || b.province}</strong></td>
                <td>${b.nation}</td>
                <td><span class="badge-currency">${b.currency || 'USD'}</span></td>
                <td class="text-gold">$${Math.round(b.deposits || 0).toLocaleString()}</td>
                <td class="text-cyan">$${Math.round(b.liquidity || 0).toLocaleString()}</td>
                <td class="text-green">$${Math.round(b.reserves || 0).toLocaleString()}</td>
                <td><strong>${b.neer !== undefined ? Number(b.neer).toFixed(2) : '1.00'}</strong></td>
              </tr>
            `).join('')}
          </tbody>
        </table>

        <h4 class="sub-heading mt-3">Bilateral Sovereign Foreign Exchange (FX) Matrix</h4>
        ${currs.length > 0 ? `
          <table class="table">
            <thead>
              <tr>
                <th>Base \\ Quote</th>
                ${currs.map(c => `<th>${c}</th>`).join('')}
              </tr>
            </thead>
            <tbody>
              ${currs.map(base => `
                <tr>
                  <td><strong>${base}</strong></td>
                  ${currs.map(quote => {
                    const rate = fxMatrix[base] && fxMatrix[base][quote] !== undefined ? fxMatrix[base][quote] : 1.0;
                    return `<td>${base === quote ? '<span style="opacity:0.5;">1.000</span>' : `<span class="text-gold font-mono">${Number(rate).toFixed(3)}</span>`}</td>`;
                  }).join('')}
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : `<div class="empty-state">All foreign exchange clearings currently settled at par (1.000).</div>`}
      `;
      container.appendChild(div);

    } else if (activeCompareTab === '4') {
      // Tab 4: Class Wealth Extraction Table
      const data = getDrilldownData(cs.tab4_extraction);
      const table = document.createElement('table');
      table.className = 'table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>${isCountry ? 'Nation' : (isProv ? 'Province' : 'City / Tile')}</th>
            <th>Feudal Tribute</th>
            <th>Ground Rent</th>
            <th>Surplus Value</th>
            <th>s/v Exploitation Rate</th>
            <th>Tax Collected</th>
            <th>Health Attrition</th>
          </tr>
        </thead>
        <tbody>
          ${data.map(r => `
            <tr>
              <td><strong>${r.name}</strong></td>
              <td class="text-ruby">$${Math.round(r.tribute || 0).toLocaleString()}</td>
              <td>$${Math.round(r.rent || 0).toLocaleString()}</td>
              <td class="text-cyan">$${Math.round(r.surplus_value || 0).toLocaleString()}</td>
              <td class="text-gold">${(r.sv_rate !== undefined ? r.sv_rate : (r.s_v ? r.s_v * 100 : 0)).toFixed(1)}%</td>
              <td>$${Math.round(r.tax || r.taxes || 0).toLocaleString()}</td>
              <td class="text-ruby">${Number(r.attrition || 0).toFixed(1)} / 1k</td>
            </tr>
          `).join('')}
        </tbody>
      `;
      container.appendChild(table);

    } else if (activeCompareTab === '5') {
      // Tab 5: Protest Energy & 100% Stacked Horizontal Grievance Bars
      const data = getDrilldownData(cs.tab5_protest);
      const div = document.createElement('div');
      div.innerHTML = `
        <h4 class="sub-heading">Protest Energy Grievance Breakdown (100% Stacked)</h4>
        <table class="table">
          <thead>
            <tr>
              <th style="width: 20%;">${isCountry ? 'Nation' : (isProv ? 'Province' : 'City / Tile')}</th>
              <th style="width: 15%;">Unrest Score</th>
              <th style="width: 65%;">Cause Breakdown (Overwork / Enclosure / Hunger / Strikes / Repression / Inequality)</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(p => {
              const ow = p.overwork || 35;
              const enc = p.enclosure || 25;
              const hg = p.hunger || 20;
              const stk = p.strikes || 10;
              const rep = p.state || 5;
              const ineq = p.inequality || 5;
              const unrestVal = Number(p.unrest || 0).toFixed(1);
              const badgeCls = unrestVal > 3 ? 'riot' : (unrestVal > 1 ? 'unrest' : 'calm');
              return `
                <tr>
                  <td><strong>${p.name}</strong></td>
                  <td><span class="badge-unrest ${badgeCls}">${unrestVal}</span></td>
                  <td>
                    <div class="stacked-bar-container">
                      <div class="stacked-segment" style="width: ${ow}%; background: #ef4444;" title="Overwork ${ow}%"></div>
                      <div class="stacked-segment" style="width: ${enc}%; background: #f59e0b;" title="Enclosure ${enc}%"></div>
                      <div class="stacked-segment" style="width: ${hg}%; background: #10b981;" title="Hunger ${hg}%"></div>
                      <div class="stacked-segment" style="width: ${stk}%; background: #06b6d4;" title="Strikes ${stk}%"></div>
                      <div class="stacked-segment" style="width: ${rep}%; background: #a855f7;" title="Repression ${rep}%"></div>
                      <div class="stacked-segment" style="width: ${ineq}%; background: #ec4899;" title="Inequality ${ineq}%"></div>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:10px; font-size:0.68rem; margin-top:4px; opacity:0.85;">
                      <span><span style="color:#ef4444">■</span> Overwork ${ow}%</span>
                      <span><span style="color:#f59e0b">■</span> Enclosure ${enc}%</span>
                      <span><span style="color:#10b981">■</span> Hunger ${hg}%</span>
                      <span><span style="color:#06b6d4">■</span> Strikes ${stk}%</span>
                      <span><span style="color:#a855f7">■</span> Repression ${rep}%</span>
                      <span><span style="color:#ec4899">■</span> Inequality ${ineq}%</span>
                    </div>
                  </td>
                </tr>
              `;
            }).join('')}
          </tbody>
        </table>
      `;
      container.appendChild(div);

    } else if (activeCompareTab === '6') {
      // Tab 6: Environmental Health Table
      const data = getDrilldownData(cs.tab6_ecology);
      const table = document.createElement('table');
      table.className = 'table';
      table.innerHTML = `
        <thead>
          <tr>
            <th>${isCountry ? 'Nation' : (isProv ? 'Province' : 'City / Tile')}</th>
            <th>Soil Fertility</th>
            <th>Nutrition Density</th>
            <th>Air Pollution (Smog)</th>
            <th>Disease Infections</th>
          </tr>
        </thead>
        <tbody>
          ${data.map(e => `
            <tr>
              <td><strong>${e.name}</strong></td>
              <td class="${e.soil_fertility < 50 ? 'text-ruby' : 'text-green'}">${Number(e.soil_fertility || 0).toFixed(1)}%</td>
              <td class="text-cyan">${Number(e.nutrition || 0).toFixed(1)}%</td>
              <td class="${e.smog > 20 ? 'text-ruby' : ''}">${Number(e.smog || 0).toFixed(1)} ppm</td>
              <td class="${e.infections > 0 ? 'text-ruby' : ''}">${e.infections || 0} active cases</td>
            </tr>
          `).join('')}
        </tbody>
      `;
      container.appendChild(table);
    }
  }

  // ---------------- Modal 2: Sovereign Command Suite [A] ----------------

  function setupCommandSuiteModal() {
    if (btnCloseCommandSuite) btnCloseCommandSuite.addEventListener('click', closeCommandSuiteModal);
    if (commandSuiteBackdrop) commandSuiteBackdrop.addEventListener('click', closeCommandSuiteModal);
  }

  function openCommandSuiteModal() {
    hideMacroTooltip();
    if (!commandSuiteModal || !worldState) return;
    commandSuiteModal.classList.remove('hidden');

    const body = document.getElementById('command-suite-body');
    if (!body) return;

    body.innerHTML = `
      <div class="gov-card">
        <h4 class="card-title">👑 Sovereign Supreme Command Overview</h4>
        <p class="card-desc">Imperial Strategic Advisory: Macroeconomic stability is stable, civil unrest requires grain reserves.</p>
        <div class="dual-btn-row mt-3">
          <button class="btn btn-primary" id="btn-cmd-quick-play">▶ Advance Simulation</button>
          <button class="btn btn-secondary" id="btn-cmd-open-compare">⚖️ Open Comparison Suite</button>
        </div>
      </div>
    `;

    document.getElementById('btn-cmd-quick-play').addEventListener('click', () => {
      sendCommand('STEP');
    });
    document.getElementById('btn-cmd-open-compare').addEventListener('click', () => {
      closeCommandSuiteModal();
      openCompareModal();
    });
  }

  function closeCommandSuiteModal() {
    if (commandSuiteModal) commandSuiteModal.classList.add('hidden');
  }

  // ---------------- Modal 3: Fiscal Transfer & Shortfall Dialog ----------------

  function setupFiscalTransferModal() {
    if (btnCloseFiscalTransfer) btnCloseFiscalTransfer.addEventListener('click', closeFiscalTransferDialog);
    if (fiscalTransferBackdrop) fiscalTransferBackdrop.addEventListener('click', closeFiscalTransferDialog);

    const bProv = document.getElementById('btn-fiscal-prov-grant');
    if (bProv) {
      bProv.addEventListener('click', () => {
        resolveFiscalTransfer('province_grant');
      });
    }

    const bNat = document.getElementById('btn-fiscal-nat-bailout');
    if (bNat) {
      bNat.addEventListener('click', () => {
        resolveFiscalTransfer('national_bailout');
      });
    }

    const bBank = document.getElementById('btn-fiscal-bank-loan');
    if (bBank) {
      bBank.addEventListener('click', () => {
        resolveFiscalTransfer('bank_deficit_loan');
      });
    }
  }

  function openFiscalTransferDialog(tileName, recipeName, cost, onHand) {
    hideMacroTooltip();
    pendingFiscalTransfer = { tileName, recipeName, cost, onHand };
    const shortfall = Math.max(0, cost - onHand);

    const setTxt = (id, txt) => {
      const el = document.getElementById(id);
      if (el) el.textContent = txt;
    };

    setTxt('lbl-transfer-cost', `$${cost}`);
    setTxt('lbl-transfer-onhand', `$${Math.round(onHand)}`);
    setTxt('lbl-transfer-shortfall', `$${Math.round(shortfall)}`);

    if (fiscalTransferModal) fiscalTransferModal.classList.remove('hidden');
  }

  function closeFiscalTransferDialog() {
    if (fiscalTransferModal) fiscalTransferModal.classList.add('hidden');
    pendingFiscalTransfer = null;
  }

  function resolveFiscalTransfer(source) {
    if (!pendingFiscalTransfer) return;
    const { tileName, recipeName, cost } = pendingFiscalTransfer;

    sendCommand('FISCAL_TRANSFER_RESOLVE', {
      funding_source: source,
      tile: tileName,
      recipe_name: recipeName,
      cost
    });

    closeFiscalTransferDialog();
  }

  // ---------------- Modal 4: 3-Page System Manual & Encyclopedia [?] ----------------

  function setupHelpModal() {
    if (btnHelp) btnHelp.addEventListener('click', openHelpModal);
    if (btnCloseHelp) btnCloseHelp.addEventListener('click', closeHelpModal);
    if (helpBackdrop) helpBackdrop.addEventListener('click', closeHelpModal);

    document.querySelectorAll('.help-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.help-tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeHelpPage = btn.dataset.helpPage;
        renderHelpContent();
      });
    });
  }

  function openHelpModal() {
    hideMacroTooltip();
    if (!helpModal) return;
    helpModal.classList.remove('hidden');
    renderHelpContent();
  }

  function closeHelpModal() {
    if (helpModal) helpModal.classList.add('hidden');
  }

  function renderHelpContent() {
    const container = document.getElementById('help-content-container');
    if (!container) return;

    if (activeHelpPage === '1') {
      container.innerHTML = `
        <h4>1. Simulation Controls & Viewport</h4>
        <p>• <strong>Axial Hexagonal Projection:</strong> Pan with mouse/drag, pinch to zoom, or use <kbd>+</kbd>/<kbd>-</kbd>/<kbd>R</kbd> keys.</p>
        <p>• <strong>Topographic Rendering Pipeline:</strong> Toggle between GPU photorealistic terrain and vector flat view with <kbd>U</kbd> or the Top Bar button.</p>
        <p>• <strong>9 Map Thematic Layers:</strong> Press <kbd>1</kbd>–<kbd>9</kbd> to inspect Overview, Physical Elevation, Demographics, Economy, Production, Defense, Enclosure, Exploitation, and Ecology.</p>
        <div class="shortcuts-grid mt-3">
          <div><kbd>B</kbd> Build Menu</div>
          <div><kbd>G</kbd> Governance</div>
          <div><kbd>D</kbd> Diplomacy</div>
          <div><kbd>S</kbd> Sovereign Debt</div>
          <div><kbd>T</kbd> Science Tree</div>
          <div><kbd>M</kbd> Military</div>
          <div><kbd>C</kbd> Compare Nations</div>
          <div><kbd>A</kbd> Command Center</div>
        </div>
      `;
    } else if (activeHelpPage === '2') {
      container.innerHTML = `
        <h4>2. Macroeconomic Accounts & Financial Theory</h4>
        <p>• <strong>Conserved Money (Closed Loop):</strong> Pure closed-loop economy. Money moves strictly through wages, trade, tax, bonds, and contracts (0 Leak / 0 Shift).</p>
        <p>• <strong>Surplus Value & Exploitation Rate (s/v):</strong> Produced value minus subsistence wages. Elevated exploitation generates acute civil unrest and wildcat strikes.</p>
        <p>• <strong>Metabolic Rift:</strong> Intensive agronomy extracts soil phosphorus and nitrogen, sending grain to cities and polluting rivers unless circular sanitation systems are constructed.</p>
        <p>• <strong>ISRB Sovereign Credit Rating:</strong> Ratings from AAA to D determine coupon servicing rates on sovereign public debt offerings.</p>
      `;
    } else if (activeHelpPage === '3') {
      container.innerHTML = `
        <h4>3. Procedural World Seeds & Nations Registry</h4>
        <p>• Current World Seed: <strong>${(worldState && worldState.seed) || 4242}</strong></p>
        <div class="cards-list mt-2">
          ${(worldState && worldState.nations) ? worldState.nations.map(n => `
            <div class="item-card">
              <div class="card-top">
                <span class="card-title" style="color:${n.flag_color || '#38bdf8'}">👑 ${n.name}</span>
                <span class="card-badge mastered">${n.regime_type || 'Monarchy'}</span>
              </div>
              <div class="card-meta-row">
                <span>Territories: ${n.tiles_count || 0}</span>
                <span>GDP: $${Math.round(n.gdp || 0).toLocaleString()}</span>
                <span>Rating: ${n.credit_rating || 'BBB'}</span>
              </div>
            </div>
          `).join('') : ''}
        </div>
      `;
    }
  }

  // ---------------- Mobile QR Modal ----------------

  function setupQrModal() {
    if (btnQr) {
      btnQr.addEventListener('click', () => {
        hideMacroTooltip();
        if (qrUrlText) qrUrlText.value = window.location.origin;
        qrModal.classList.remove('hidden');
      });
    }
    if (btnCloseQr) btnCloseQr.addEventListener('click', () => qrModal.classList.add('hidden'));
    if (qrBackdrop) qrBackdrop.addEventListener('click', () => qrModal.classList.add('hidden'));
    if (btnCopyUrl) {
      btnCopyUrl.addEventListener('click', () => {
        if (qrUrlText) {
          navigator.clipboard.writeText(qrUrlText.value);
          showToast('URL copied to clipboard!');
        }
      });
    }
  }

  // ---------------- Thematic Layer Selector ----------------

  function setupLayerSelector() {
    if (btnLayerToggle && layerMenu) {
      btnLayerToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        layerMenu.classList.toggle('hidden');
      });
    }

    document.addEventListener('click', (e) => {
      if (layerMenu && !layerMenu.contains(e.target) && e.target !== btnLayerToggle) {
        layerMenu.classList.add('hidden');
      }
    });

    document.querySelectorAll('.layer-item').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('.layer-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        activeLayer = item.dataset.layer;

        const dot = item.querySelector('.layer-dot');
        const name = item.querySelector('.layer-name');
        if (activeLayerDot && dot) activeLayerDot.style.background = dot.style.background;
        if (activeLayerName && name) activeLayerName.textContent = name.textContent;

        if (layerMenu) layerMenu.classList.add('hidden');
        renderMap();
      });
    });
  }

  // ---------------- Toast Notifications ----------------

  function showToast(message, isError = false) {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${isError ? 'error' : ''}`;
    toast.textContent = message;
    toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.remove();
    }, 3000);
  }

  // ---------------- Pointer & Touch Gestures ----------------

  function selectTile(tileName) {
    selectedTileName = tileName;
    if (worldState && worldState.tiles) {
      const tile = worldState.tiles.find(t => t.name === tileName);
      if (tile) {
        updateTileInspectionUI(tile);
        if (quickPill && pillText) {
          pillText.textContent = `${tile.display_name || tile.name} (${tile.nation || 'Wilderness'})`;
          quickPill.classList.remove('hidden');
          setTimeout(() => quickPill.classList.add('hidden'), 2500);
        }
      }
    }
    updateLeftDrawerPanes();
    renderMap();
  }

  function handlePointerDown(e) {
    isDragging = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    camStartX = camX;
    camStartY = camY;
    touchStartTime = Date.now();
  }

  function handlePointerMove(e) {
    if (!isDragging) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    camX = camStartX + dx;
    camY = camStartY + dy;
    renderMap();
  }

  function handlePointerUp(e) {
    if (!isDragging) return;
    isDragging = false;
    const dx = Math.abs(e.clientX - dragStartX);
    const dy = Math.abs(e.clientY - dragStartY);
    const dt = Date.now() - touchStartTime;

    // Detect tap / click
    if (dx < 8 && dy < 8 && dt < 350) {
      const rect = canvas.getBoundingClientRect();
      const clickX = (e.clientX - rect.left - camX) / camZoom;
      const clickY = (e.clientY - rect.top - camY) / camZoom;

      const hexRadius = getHexRadius();
      const axial = pixelToAxial(clickX, clickY, hexRadius);

      if (worldState && worldState.tiles) {
        const hit = worldState.tiles.find(t => t.q === axial.q && t.r === axial.r);
        if (hit) selectTile(hit.name);
      }
    }
  }

  function handleWheel(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newZoom = Math.max(0.35, Math.min(3.5, camZoom * zoomFactor));

    camX = mouseX - (mouseX - camX) * (newZoom / camZoom);
    camY = mouseY - (mouseY - camY) * (newZoom / camZoom);
    camZoom = newZoom;
    renderMap();
  }

  function setupTouchEvents() {
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) {
        isDragging = false;
        initialPinchDist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        initialPinchZoom = camZoom;
      } else if (e.touches.length === 1) {
        handlePointerDown(e.touches[0]);
      }
    }, { passive: false });

    canvas.addEventListener('touchmove', (e) => {
      if (e.touches.length === 2 && initialPinchDist) {
        e.preventDefault();
        const dist = Math.hypot(
          e.touches[0].clientX - e.touches[1].clientX,
          e.touches[0].clientY - e.touches[1].clientY
        );
        const scale = dist / initialPinchDist;
        camZoom = Math.max(0.35, Math.min(3.5, initialPinchZoom * scale));
        renderMap();
      } else if (e.touches.length === 1) {
        handlePointerMove(e.touches[0]);
      }
    }, { passive: false });

    canvas.addEventListener('touchend', (e) => {
      if (e.touches.length === 0) {
        initialPinchDist = null;
        handlePointerUp(e.changedTouches[0]);
      }
    });
  }

  // ---------------- Keyboard Shortcuts ----------------

  function setupKeyboardShortcuts() {
    window.addEventListener('keydown', (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;

      const key = e.key.toUpperCase();
      if (key === 'B') openLeftDrawer('build');
      else if (key === 'G') openLeftDrawer('gov');
      else if (key === 'D') openLeftDrawer('diplomacy');
      else if (key === 'S') openLeftDrawer('debt');
      else if (key === 'T') openLeftDrawer('science');
      else if (key === 'M') openLeftDrawer('military');
      else if (key === 'C') openCompareModal();
      else if (key === 'A') openCommandSuiteModal();
      else if (key === 'U') {
        useTerrainImage = !useTerrainImage;
        if (btnTogglePipeline) btnTogglePipeline.querySelector('.btn-text').textContent = useTerrainImage ? 'Pipeline: Photoreal' : 'Pipeline: Flat';
        renderMap();
      }
      else if (key === 'R') centerCameraOnWorld();
      else if (key === '?' || key === 'H') openHelpModal();
      else if (key === ' ') {
        e.preventDefault();
        if (btnPlay) btnPlay.click();
      } else if (key === '+' || key === '=') {
        if (btnStep) btnStep.click();
      } else if (key === 'ESCAPE') {
        closeLeftDrawer();
        closeCompareModal();
        closeCommandSuiteModal();
        closeFiscalTransferDialog();
        closeHelpModal();
        qrModal.classList.add('hidden');
      } else if (key >= '1' && key <= '9') {
        const layers = ['overview', 'physical', 'population', 'economy', 'production', 'military', 'enclosure', 'exploitation', 'externalities'];
        const idx = parseInt(key, 10) - 1;
        if (layers[idx]) {
          const item = document.querySelector(`.layer-item[data-layer="${layers[idx]}"]`);
          if (item) item.click();
        }
      }
    });
  }

  // ---------------- Authoritative REST Server API Sync ----------------

  async function fetchState() {
    if (isRequestPending) return;
    try {
      const res = await fetch('/api/state');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      worldState = data;

      if (statusDot) {
        statusDot.className = 'status-dot connected';
        statusDot.title = 'Server Connected (Live)';
      }

      // Synchronize photorealistic terrain asset
      if (data.terrain_seed) syncTerrainImage(data.terrain_seed);

      // Camera initialization
      if (!isInitialCentered && data.tiles && data.tiles.length > 0) {
        centerCameraOnWorld();
      }

      // Default territory selection
      if (!selectedTileName && data.tiles && data.tiles.length > 0) {
        const inhabited = data.tiles.find(t => t.owner_nation || t.is_settlement) || data.tiles[0];
        selectTile(inhabited.name);
      } else if (selectedTileName && data.tiles) {
        const t = data.tiles.find(tile => tile.name === selectedTileName);
        if (t) updateTileInspectionUI(t);
      }

      updateTopMacroBar();
      updateLeftDrawerPanes();
      updateRightPanel();
      renderMap();

    } catch (err) {
      if (statusDot) {
        statusDot.className = 'status-dot';
        statusDot.title = 'Server Disconnected';
      }
    }
  }

  async function sendCommand(commandType, payload = {}) {
    isRequestPending = true;
    try {
      const res = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd_type: commandType, type: commandType, cmd: commandType, payload })
      });

      const result = await res.json();
      if (!result.success) {
        showToast(result.error || 'Command failed.', true);
      } else {
        if (result.message) showToast(result.message);
        await fetchState();
      }
    } catch (err) {
      showToast(`Network error: ${err.message}`, true);
    } finally {
      isRequestPending = false;
    }
  }

  // ---------------- Initialization ----------------

  function init() {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Mouse & Pointer Handlers
    canvas.addEventListener('mousedown', handlePointerDown);
    window.addEventListener('mousemove', handlePointerMove);
    window.addEventListener('mouseup', handlePointerUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });

    setupTouchEvents();
    setupLeftDrawer();
    setupRightPanel();
    setupCompareModal();
    setupCommandSuiteModal();
    setupFiscalTransferModal();
    setupHelpModal();
    setupQrModal();
    setupLayerSelector();
    setupTopBarTooltips();
    setupKeyboardShortcuts();

    // Top Controls
    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        const nextState = !isPlaying;
        isPlaying = nextState;
        btnPlay.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
        btnPlay.className = isPlaying ? 'btn btn-secondary' : 'btn btn-primary';
        sendCommand(nextState ? 'PLAY' : 'PAUSE');
      });
    }

    if (btnStep) {
      btnStep.addEventListener('click', () => {
        sendCommand('STEP');
      });
    }

    if (btnNew) {
      btnNew.addEventListener('click', () => {
        if (confirm('Regenerate world with random seeds?')) {
          const seed = Math.floor(Math.random() * 1000000);
          sendCommand('RELOAD_WORLD', { seed, terrain_seed: seed, nation_seed: seed });
        }
      });
    }

    if (selectNation) {
      selectNation.addEventListener('change', () => {
        sendCommand('SELECT_NATION', { nation: selectNation.value });
      });
    }

    if (btnToggleTerrain) {
      btnToggleTerrain.addEventListener('click', () => {
        useTerrainImage = !useTerrainImage;
        btnToggleTerrain.classList.toggle('active', useTerrainImage);
        renderMap();
      });
    }

    if (btnTogglePipeline) {
      btnTogglePipeline.addEventListener('click', () => {
        useTerrainImage = !useTerrainImage;
        btnTogglePipeline.querySelector('.btn-text').textContent = useTerrainImage ? 'Pipeline: Photoreal' : 'Pipeline: Flat';
        renderMap();
      });
    }

    if (btnTopDiplo) {
      btnTopDiplo.addEventListener('click', () => {
        openLeftDrawer('diplomacy');
      });
    }

    if (btnTopMilitary) {
      btnTopMilitary.addEventListener('click', () => {
        openLeftDrawer('military');
      });
    }

    // Zoom Buttons
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnResetCam = document.getElementById('btn-reset-cam');

    if (btnZoomIn) {
      btnZoomIn.addEventListener('click', () => {
        camZoom = Math.min(3.5, camZoom * 1.25);
        renderMap();
      });
    }
    if (btnZoomOut) {
      btnZoomOut.addEventListener('click', () => {
        camZoom = Math.max(0.35, camZoom * 0.8);
        renderMap();
      });
    }
    if (btnResetCam) {
      btnResetCam.addEventListener('click', centerCameraOnWorld);
    }

    // Initial Fetch & Poll Loop
    fetchState();
    pollTimer = setInterval(fetchState, 1000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
