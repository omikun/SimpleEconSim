/**
 * REGNUM Web Client — Comprehensive Client Controller
 * Pure vanilla JavaScript with HTML5 Canvas, axial hex projection,
 * 9 thematic information layers, 6 sovereign suites, interactive charts,
 * citizen census, and full REST API synchronization.
 */

(function () {
  'use strict';

  const SQRT3 = Math.sqrt(3.0);
  const DEFAULT_HEX_SIZE = 50.0;

  // Global State
  let worldState = null;
  let selectedTileName = null;
  let selectedTileDetail = null;
  let isPlaying = false;
  let pollTimer = null;
  let isRequestPending = false;

  // Active UI Navigation State
  let activeLeftDrawer = null;       // 'build' | 'gov' | 'diplomacy' | 'debt' | 'science' | 'military' | null
  let activeRightTab = 'overview';   // 'overview' | 'charts' | 'cadastre' | 'citizens' | 'workhouse' | 'news'
  let activeLayer = 'overview';      // 'overview' | 'physical' | 'population' | 'economy' | 'production' | 'military' | 'enclosure' | 'exploitation' | 'externalities'
  let activeBuildTier = 'all';       // 'all' | 'tile' | 'province' | 'nation'
  let activeGovScope = 'tile';       // 'tile' | 'province' | 'nation'
  let activeScienceEra = 1;          // 1 | 2 | 3 | 4
  let activeBondDuration = 20;       // 20 | 50 | 100
  let activeChartMetric = 'gdp';     // 'gdp' | 'treasury' | 'food_price' | 'pop' | 'unrest'

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

    if (dq > dr && dq > ds) {
      rq = -rr - rs;
    } else if (dr > ds) {
      rr = -rq - rs;
    }
    return { q: rq, r: rr };
  }

  function getHexCorners(cx, cy, size) {
    const pts = [];
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 180.0) * (60.0 * i - 30.0);
      pts.push({
        x: cx + size * Math.cos(angle),
        y: cy + size * Math.sin(angle)
      });
    }
    return pts;
  }

  function drawHexPolygon(ctx, cx, cy, size) {
    const pts = getHexCorners(cx, cy, size);
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < 6; i++) {
      ctx.lineTo(pts[i].x, pts[i].y);
    }
    ctx.closePath();
  }

  function getTerrainBounds() {
    if (worldState && worldState.terrain_bounds) {
      return worldState.terrain_bounds;
    }
    if (!worldState || !worldState.tiles || worldState.tiles.length === 0) return null;
    const hexRadius = getHexRadius();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    worldState.tiles.forEach(t => {
      const pt = axialToPixel(t.q, t.r, hexRadius);
      minX = Math.min(minX, pt.x);
      maxX = Math.max(maxX, pt.x);
      minY = Math.min(minY, pt.y);
      maxY = Math.max(maxY, pt.y);
    });
    const padX = (maxX - minX + hexRadius * 2) * 0.2;
    const padY = (maxY - minY + hexRadius * 2) * 0.2;
    return {
      min_x: minX - hexRadius - padX,
      min_y: minY - hexRadius - padY,
      width: (maxX - minX + hexRadius * 2) + 2 * padX,
      height: (maxY - minY + hexRadius * 2) + 2 * padY,
      hex_size: hexRadius
    };
  }

  // ---------------- Terrain Image Sync ----------------

  function syncTerrainImage() {
    if (!worldState) return;
    const seed = worldState.terrain_seed !== undefined ? worldState.terrain_seed : (worldState.seed || 4242);
    if (seed === currentTerrainSeed && (terrainLoaded || terrainLoading)) {
      return;
    }
    currentTerrainSeed = seed;
    terrainLoaded = false;
    terrainLoading = true;

    const img = new Image();
    img.onload = () => {
      if (seed === currentTerrainSeed) {
        terrainImage = img;
        terrainLoaded = true;
        terrainLoading = false;
        renderMap();
      }
    };
    img.onerror = () => {
      // Fallback to PNG
      const pngImg = new Image();
      pngImg.onload = () => {
        if (seed === currentTerrainSeed) {
          terrainImage = pngImg;
          terrainLoaded = true;
          terrainLoading = false;
          renderMap();
        }
      };
      pngImg.onerror = () => {
        terrainLoading = false;
      };
      pngImg.src = `/api/terrain.png?seed=${seed}&t=${Date.now()}`;
    };
    img.src = `/api/terrain.jpg?seed=${seed}&t=${Date.now()}`;
  }

  // ---------------- Viewport & Canvas Rendering ----------------

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    renderMap();
  }

  function centerCameraOnWorld() {
    if (!worldState || !worldState.tiles || worldState.tiles.length === 0) return;
    const hexRadius = getHexRadius();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    worldState.tiles.forEach(t => {
      const pt = axialToPixel(t.q, t.r, hexRadius);
      minX = Math.min(minX, pt.x);
      maxX = Math.max(maxX, pt.x);
      minY = Math.min(minY, pt.y);
      maxY = Math.max(maxY, pt.y);
    });
    const worldCenterX = (minX + maxX) / 2.0;
    const worldCenterY = (minY + maxY) / 2.0;

    const rect = canvas.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;

    const worldW = (maxX - minX) + hexRadius * 3.0;
    const worldH = (maxY - minY) + hexRadius * 3.0;
    const fitZoom = Math.min(w / worldW, h / worldH) * 0.95;

    camZoom = Math.max(0.4, Math.min(2.5, fitZoom));
    camX = w / 2.0 - worldCenterX * camZoom;
    camY = h / 2.0 - worldCenterY * camZoom;
    isInitialCentered = true;
  }

  function renderMap() {
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    ctx.fillStyle = '#0a0d14';
    ctx.fillRect(0, 0, w, h);

    if (!worldState || !worldState.tiles) {
      ctx.restore();
      return;
    }

    ctx.save();
    ctx.translate(camX, camY);
    ctx.scale(camZoom, camZoom);

    // 1. Draw Photorealistic Topographic Terrain
    if (useTerrainImage && terrainLoaded && terrainImage) {
      const bounds = getTerrainBounds();
      if (bounds) {
        ctx.drawImage(terrainImage, bounds.min_x, bounds.min_y, bounds.width, bounds.height);
      }
    }

    const hexRadius = getHexRadius();

    // 2. Draw Hex Grid & Thematic Information Overlays
    worldState.tiles.forEach(tile => {
      const pt = axialToPixel(tile.q, tile.r, hexRadius);
      const isSelected = (tile.name === selectedTileName);

      // If terrain image not loaded or toggled off, draw biome base
      if (!useTerrainImage || !terrainLoaded) {
        drawHexPolygon(ctx, pt.x, pt.y, hexRadius);
        ctx.fillStyle = getBiomeColor(tile.biome, tile.is_ocean);
        ctx.fill();
      }

      // Draw Thematic Layer Overlay Tint
      renderThematicLayerOverlay(ctx, tile, pt.x, pt.y, hexRadius);

      // Hex Edge Stroke
      drawHexPolygon(ctx, pt.x, pt.y, hexRadius);
      if (isSelected) {
        ctx.strokeStyle = '#f59e0b';
        ctx.lineWidth = 3.5 / camZoom;
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1.0 / camZoom;
        ctx.stroke();
      }

      // Draw Selected Glow
      if (isSelected) {
        ctx.fillStyle = 'rgba(245, 158, 11, 0.22)';
        drawHexPolygon(ctx, pt.x, pt.y, hexRadius);
        ctx.fill();
      }

      // Draw Hex Labels & Badges according to active layer
      renderHexBadges(ctx, tile, pt.x, pt.y, hexRadius);
    });

    ctx.restore();
    ctx.restore();
  }

  // Thematic Layer Overlays
  function renderThematicLayerOverlay(ctx, tile, cx, cy, size) {
    if (activeLayer === 'overview') {
      // Subtle nation border tint
      if (tile.nation && !tile.is_ocean) {
        ctx.fillStyle = getNationColor(tile.nation, 0.12);
        drawHexPolygon(ctx, cx, cy, size);
        ctx.fill();
      }
    } else if (activeLayer === 'population') {
      // Unrest Heatmap: Green (calm) -> Yellow -> Red -> Purple (riot)
      const u = tile.protest_energy || 0.0;
      let col = 'rgba(16, 185, 129, 0.15)';
      if (u >= 8.0) col = 'rgba(239, 68, 68, 0.60)';
      else if (u >= 5.0) col = 'rgba(249, 115, 22, 0.45)';
      else if (u >= 2.5) col = 'rgba(245, 158, 11, 0.35)';
      ctx.fillStyle = col;
      drawHexPolygon(ctx, cx, cy, size);
      ctx.fill();
    } else if (activeLayer === 'economy') {
      // GDP Wealth glow
      const gdp = tile.gdp || 0.0;
      if (gdp > 0) {
        const alpha = Math.min(0.55, 0.10 + (gdp / 2500.0) * 0.45);
        ctx.fillStyle = `rgba(56, 189, 248, ${alpha})`;
        drawHexPolygon(ctx, cx, cy, size);
        ctx.fill();
      }
    } else if (activeLayer === 'military') {
      // Garrison & Border Defense
      const gar = tile.garrison || 0;
      if (gar > 0) {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.35)';
        drawHexPolygon(ctx, cx, cy, size);
        ctx.fill();
      }
    } else if (activeLayer === 'enclosure') {
      // Commons vs Enclosed
      const enc = (tile.tenure && tile.tenure.enclosed_fraction) || 0.0;
      ctx.fillStyle = `rgba(168, 85, 247, ${enc * 0.45})`;
      drawHexPolygon(ctx, cx, cy, size);
      ctx.fill();
    } else if (activeLayer === 'exploitation') {
      // Rate of exploitation s/v
      const roe = (tile.labor && tile.labor.rate_of_exploitation) || 0.0;
      if (roe > 1.0) {
        ctx.fillStyle = `rgba(239, 68, 68, ${Math.min(0.5, (roe - 1.0) * 0.25)})`;
        drawHexPolygon(ctx, cx, cy, size);
        ctx.fill();
      }
    } else if (activeLayer === 'externalities') {
      // Smog & Soil
      const smog = (tile.ecology && tile.ecology.pollution_air) || 0.0;
      if (smog > 5.0) {
        ctx.fillStyle = 'rgba(100, 116, 139, 0.45)';
        drawHexPolygon(ctx, cx, cy, size);
        ctx.fill();
      }
    }
  }

  function renderHexBadges(ctx, tile, cx, cy, size) {
    if (tile.is_ocean) return;
    const fontSize = Math.max(9, Math.min(12, 11 / camZoom));
    ctx.font = `700 ${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // 1. City / Region Name
    const name = tile.display_name || tile.name;
    ctx.fillStyle = '#ffffff';
    ctx.shadowColor = 'rgba(0, 0, 0, 0.85)';
    ctx.shadowBlur = 4;
    ctx.fillText(name, cx, cy - 8);

    // 2. Layer Badge Line
    let badgeText = '';
    let badgeColor = '#94a3b8';

    if (activeLayer === 'overview') {
      if (tile.population > 0) {
        badgeText = `👥 ${tile.population}`;
        badgeColor = '#38bdf8';
      }
    } else if (activeLayer === 'physical') {
      badgeText = `▲ ${Math.round(tile.elevation_meters || 0)}m`;
      badgeColor = '#8ce1ff';
    } else if (activeLayer === 'population') {
      const u = tile.protest_energy || 0.0;
      badgeText = `🔥 ${u.toFixed(1)}`;
      badgeColor = u > 4.0 ? '#ef4444' : '#f59e0b';
    } else if (activeLayer === 'economy') {
      badgeText = `$${Math.round(tile.gdp || 0)}`;
      badgeColor = '#38bdf8';
    } else if (activeLayer === 'production') {
      const count = (tile.buildings && tile.buildings.length) || 0;
      badgeText = `🏭 ${count} bld`;
      badgeColor = '#f5d25a';
    } else if (activeLayer === 'military') {
      badgeText = `🛡️ ${tile.garrison || 0}`;
      badgeColor = '#ef4444';
    } else if (activeLayer === 'enclosure') {
      const enc = Math.round(((tile.tenure && tile.tenure.enclosed_fraction) || 0) * 100);
      badgeText = `◩ ${enc}%`;
      badgeColor = '#a855f7';
    } else if (activeLayer === 'exploitation') {
      const roe = (tile.labor && tile.labor.rate_of_exploitation) || 0.0;
      badgeText = `⚡ ${roe.toFixed(1)} s/v`;
      badgeColor = '#f87171';
    } else if (activeLayer === 'externalities') {
      const soil = (tile.ecology && tile.ecology.soil_fertility) || 100;
      badgeText = `🌿 ${soil}%`;
      badgeColor = '#10b981';
    }

    if (badgeText) {
      ctx.fillStyle = badgeColor;
      ctx.fillText(badgeText, cx, cy + 8);
    }
    ctx.shadowBlur = 0;
  }

  function getBiomeColor(biome, isOcean) {
    if (isOcean) return '#0d1e33';
    switch (biome) {
      case 'mountain': return '#504c46';
      case 'hill': return '#4c5738';
      case 'forest': return '#1f3d1b';
      case 'plains': return '#3a542e';
      case 'desert': return '#786638';
      case 'snow': return '#d8e5ee';
      case 'tundra': return '#4e5b5c';
      case 'shelf': return '#16314f';
      default: return '#3a542e';
    }
  }

  function getNationColor(nationName, alpha = 1.0) {
    if (!worldState || !worldState.nations) return `rgba(56, 189, 248, ${alpha})`;
    const nat = worldState.nations.find(n => n.name === nationName);
    if (nat && nat.flag_color) {
      const hex = nat.flag_color.replace('#', '');
      const r = parseInt(hex.substring(0, 2), 16) || 80;
      const g = parseInt(hex.substring(2, 4), 16) || 160;
      const b = parseInt(hex.substring(4, 6), 16) || 240;
      return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    return `rgba(56, 189, 248, ${alpha})`;
  }

  // ---------------- REST API Synchronization ----------------

  async function fetchState() {
    if (isRequestPending) return;
    isRequestPending = true;
    try {
      const res = await fetch('/api/state', { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      updateWorldState(data);
      if (statusDot) {
        statusDot.className = 'status-dot connected';
        statusDot.title = 'Connected';
      }
    } catch (err) {
      console.warn('[WebClient] fetchState error:', err);
      if (statusDot) {
        statusDot.className = 'status-dot error';
        statusDot.title = 'Connection lost';
      }
    } finally {
      isRequestPending = false;
    }
  }

  async function sendCommand(cmdType, payload = {}) {
    try {
      const res = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd_type: cmdType, payload })
      });
      const data = await res.json();
      if (data.message) {
        showToast(data.message, !data.success);
      }
      await fetchState();
      return data;
    } catch (err) {
      showToast(`Command error: ${err.message}`, true);
      return { success: false, error: err.message };
    }
  }

  function updateWorldState(data) {
    worldState = data;
    isPlaying = !!data.playing;

    if (turnDisplay) {
      turnDisplay.textContent = data.turn || 0;
    }

    if (btnPlay) {
      if (isPlaying) {
        btnPlay.textContent = '⏸ Pause';
        btnPlay.classList.add('playing');
      } else {
        btnPlay.textContent = '▶ Play';
        btnPlay.classList.remove('playing');
      }
    }

    // 1. Sync Top Macro Ribbon
    updateMacroRibbon(data.macro);

    // 2. Sync Nation Dropdown
    syncNationDropdown(data.nations, data.player_nation);

    // 3. Sync Terrain Image if seed changed
    syncTerrainImage();

    // 4. Center Camera on First Load
    if (!isInitialCentered) {
      centerCameraOnWorld();
    }

    // 5. If no tile selected, auto-select first player tile
    if (!selectedTileName && data.player_nation && data.tiles) {
      const firstTile = data.tiles.find(t => t.nation === data.player_nation);
      if (firstTile) {
        selectTile(firstTile.name);
      }
    } else if (selectedTileName && data.tiles) {
      const current = data.tiles.find(t => t.name === selectedTileName);
      if (current) {
        updateTileInspectionUI(current);
      }
    }

    // 6. Update Active Left Drawer Panes
    updateLeftDrawerPanes();

    // 7. Update Active Right Panel
    updateRightPanel();

    // 8. Redraw Map
    renderMap();
  }

  // ---------------- Macroeconomic Ribbon ----------------

  function updateMacroRibbon(macro) {
    if (!macro) return;

    const elTreasury = document.getElementById('val-treasury');
    const elFood = document.getElementById('val-food');
    const elPop = document.getElementById('val-pop');
    const elGdp = document.getElementById('val-gdp');
    const elUnrest = document.getElementById('val-unrest');
    const elGini = document.getElementById('val-gini');
    const elTrade = document.getElementById('val-trade');
    const elCol = document.getElementById('val-col');

    if (elTreasury) elTreasury.textContent = `$${Math.round(macro.treasury_cash || 0).toLocaleString()}`;
    if (elFood) elFood.textContent = `${macro.treasury_food || 0}`;
    if (elPop) elPop.textContent = `${(macro.population || 0).toLocaleString()}`;
    if (elGdp) elGdp.textContent = `$${Math.round(macro.gdp || 0).toLocaleString()}`;
    
    if (elUnrest) {
      const st = macro.unrest_stage || 'Calm';
      elUnrest.textContent = `${(macro.unrest_energy || 0).toFixed(1)} ${st}`;
      elUnrest.className = `macro-val badge-unrest ${st.toLowerCase().replace('/', '')}`;
    }

    if (elGini) elGini.textContent = `${(macro.gini || 0).toFixed(2)}`;
    
    if (elTrade) {
      const net = macro.trade_balance || 0;
      elTrade.textContent = `${net >= 0 ? '+' : ''}$${Math.round(net).toLocaleString()}`;
      elTrade.className = `macro-val ${net >= 0 ? 'text-green' : 'text-ruby'}`;
    }

    if (elCol) elCol.textContent = `${(macro.cost_of_living || 1.0).toFixed(2)}`;
  }

  function syncNationDropdown(nations, activeNationName) {
    if (!selectNation || !nations) return;
    const currentVal = selectNation.value;
    
    // Only rebuild options if nation count or names changed
    const optValues = Array.from(selectNation.options).map(o => o.value);
    const newValues = nations.map(n => n.name);
    const isSame = (optValues.length === newValues.length && optValues.every((v, i) => v === newValues[i]));

    if (!isSame) {
      selectNation.innerHTML = '';
      nations.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n.name;
        opt.textContent = `${n.name} (${n.regime_type || 'State'})`;
        selectNation.appendChild(opt);
      });
    }

    if (activeNationName) {
      selectNation.value = activeNationName;
      const activeNat = nations.find(n => n.name === activeNationName);
      if (activeFlagDot && activeNat && activeNat.flag_color) {
        activeFlagDot.style.background = activeNat.flag_color;
      }
    }
  }

  // ---------------- Left Sovereign Drawer Navigation ----------------

  function setupLeftDrawer() {
    // Dock Tab Buttons
    document.querySelectorAll('.dock-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetDrawer = btn.dataset.drawer;
        if (activeLeftDrawer === targetDrawer && !leftDrawer.classList.contains('closed')) {
          closeLeftDrawer();
        } else {
          openLeftDrawer(targetDrawer);
        }
      });
    });

    if (btnCloseLeft) {
      btnCloseLeft.addEventListener('click', closeLeftDrawer);
    }

    // Build Tier Chips
    document.querySelectorAll('.tier-filter-chips .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.tier-filter-chips .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeBuildTier = chip.dataset.tier;
        renderBuildRecipes();
      });
    });

    // Governance Scope Buttons
    document.querySelectorAll('.scope-switch-bar .scope-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.scope-switch-bar .scope-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeGovScope = btn.dataset.scope;
      });
    });

    // Governance Controls
    const sliderTax = document.getElementById('slider-income-tax');
    const lblTax = document.getElementById('lbl-income-tax');
    if (sliderTax && lblTax) {
      sliderTax.addEventListener('input', () => {
        lblTax.textContent = `${(parseFloat(sliderTax.value) * 100).toFixed(1)}%`;
      });
      sliderTax.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'tax_rate', val: parseFloat(sliderTax.value) });
      });
    }

    const sliderTariff = document.getElementById('slider-tariff-rate');
    const lblTariff = document.getElementById('lbl-tariff-rate');
    if (sliderTariff && lblTariff) {
      sliderTariff.addEventListener('input', () => {
        lblTariff.textContent = `${(parseFloat(sliderTariff.value) * 100).toFixed(1)}%`;
      });
      sliderTariff.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'tariff_rate', val: parseFloat(sliderTariff.value) });
      });
    }

    const sliderWorkday = document.getElementById('slider-gov-workday');
    const lblWorkday = document.getElementById('lbl-gov-workday');
    const chkTenHour = document.getElementById('chk-ten-hour');
    if (sliderWorkday && lblWorkday) {
      sliderWorkday.addEventListener('input', () => {
        lblWorkday.textContent = `${parseFloat(sliderWorkday.value).toFixed(1)}h`;
      });
      sliderWorkday.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'workday', val: parseFloat(sliderWorkday.value) });
      });
    }

    if (chkTenHour) {
      chkTenHour.addEventListener('change', () => {
        sendCommand('SET_POLICY', { key: 'ten_hour_act', val: chkTenHour.checked });
      });
    }

    const btnGranary = document.getElementById('btn-decree-granary');
    if (btnGranary) {
      btnGranary.addEventListener('click', () => {
        sendCommand('SET_POLICY', { key: 'granary_relief' });
      });
    }

    const btnOrder = document.getElementById('btn-decree-order');
    if (btnOrder) {
      btnOrder.addEventListener('click', () => {
        sendCommand('SET_POLICY', { key: 'law_enforcement' });
      });
    }

    // Sovereign Debt Controls
    document.querySelectorAll('#bond-duration-chips .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('#bond-duration-chips .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeBondDuration = parseInt(chip.dataset.duration, 10);
      });
    });

    const btnBond500 = document.getElementById('btn-issue-bond-500');
    if (btnBond500) {
      btnBond500.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'issue_bond', amount: 500, duration: activeBondDuration });
      });
    }

    const btnBond1000 = document.getElementById('btn-issue-bond-1000');
    if (btnBond1000) {
      btnBond1000.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'issue_bond', amount: 1000, duration: activeBondDuration });
      });
    }

    const btnLobby = document.getElementById('btn-lobby-isrb');
    if (btnLobby) {
      btnLobby.addEventListener('click', () => {
        sendCommand('SOVEREIGN_BOND', { action: 'lobby_upgrade' });
      });
    }

    // Science Era Chips
    document.querySelectorAll('.era-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.era-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeScienceEra = parseInt(chip.dataset.era, 10);
        renderScienceTechs();
      });
    });

    // Military Garrison Recruitment
    const btnRecruit = document.getElementById('btn-recruit-garrison');
    if (btnRecruit) {
      btnRecruit.addEventListener('click', () => {
        sendCommand('RECRUIT_UNIT', { tile: selectedTileName, soldiers: 10 });
      });
    }
  }

  function openLeftDrawer(drawerName) {
    activeLeftDrawer = drawerName;
    leftDrawer.classList.remove('closed');

    // Update Tab Active Indicators
    document.querySelectorAll('.dock-tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.drawer === drawerName);
    });

    // Update Drawer Title
    const titles = {
      build: '🔨 Build & Infrastructure Suite',
      gov: '🏛️ Governance & Sovereign Decrees',
      diplomacy: '🤝 Global Diplomacy & Treaties',
      debt: '📜 Sovereign Debt & Bond Market',
      science: '🔬 Science & Technology Tree',
      military: '⚔️ Military & Territorial Defense'
    };
    if (drawerTitle) drawerTitle.textContent = titles[drawerName] || 'Sovereign Suite';

    // Show correct pane
    document.querySelectorAll('.drawer-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === `pane-${drawerName}`);
    });

    updateLeftDrawerPanes();
  }

  function closeLeftDrawer() {
    activeLeftDrawer = null;
    leftDrawer.classList.add('closed');
    document.querySelectorAll('.dock-tab-btn').forEach(btn => btn.classList.remove('active'));
  }

  function updateLeftDrawerPanes() {
    if (!worldState) return;

    // 1. Build Suite
    const targetBadge = document.getElementById('build-target-tile');
    if (targetBadge) {
      targetBadge.textContent = selectedTileName ? `Target Territory: ${selectedTileName}` : 'Target Territory: Capital';
    }
    renderBuildRecipes();
    renderActiveProjects();

    // 2. Governance Suite
    if (worldState.macro) {
      const sliderTax = document.getElementById('slider-income-tax');
      const lblTax = document.getElementById('lbl-income-tax');
      if (sliderTax && lblTax && document.activeElement !== sliderTax) {
        sliderTax.value = worldState.macro.tax_rate;
        lblTax.textContent = `${(worldState.macro.tax_rate * 100).toFixed(1)}%`;
      }

      const sliderTariff = document.getElementById('slider-tariff-rate');
      const lblTariff = document.getElementById('lbl-tariff-rate');
      if (sliderTariff && lblTariff && document.activeElement !== sliderTariff) {
        sliderTariff.value = worldState.macro.tariff_rate;
        lblTariff.textContent = `${(worldState.macro.tariff_rate * 100).toFixed(1)}%`;
      }

      const sliderWorkday = document.getElementById('slider-gov-workday');
      const lblWorkday = document.getElementById('lbl-gov-workday');
      const chkTenHour = document.getElementById('chk-ten-hour');
      if (sliderWorkday && lblWorkday && document.activeElement !== sliderWorkday) {
        sliderWorkday.value = worldState.macro.max_workday_hours;
        lblWorkday.textContent = `${worldState.macro.max_workday_hours.toFixed(1)}h`;
      }
      if (chkTenHour && document.activeElement !== chkTenHour) {
        chkTenHour.checked = worldState.macro.ten_hour_act;
      }
    }

    // 3. Diplomacy Suite
    renderDiplomacyNations();

    // 4. Sovereign Debt Suite
    renderSovereignDebt();

    // 5. Science Suite
    renderScienceTechs();

    // 6. Military Suite
    renderMilitarySuite();
  }

  // 1. Build Recipes
  function renderBuildRecipes() {
    const list = document.getElementById('build-recipes-list');
    if (!list || !worldState || !worldState.build_recipes) return;

    list.innerHTML = '';
    const recipes = Object.values(worldState.build_recipes);
    const filtered = recipes.filter(r => (activeBuildTier === 'all' || r.tier === activeBuildTier));

    filtered.forEach(r => {
      const card = document.createElement('div');
      card.className = 'item-card';

      const tierBadge = r.tier === 'tile' ? 'City' : (r.tier === 'province' ? 'Province' : 'Sovereign');

      card.innerHTML = `
        <div class="card-top">
          <strong class="card-title">${r.display_name}</strong>
          <span class="card-badge unlocked">${tierBadge}</span>
        </div>
        <p class="card-desc">${r.description}</p>
        <div class="card-meta-row">
          <span>Cost: <strong class="text-gold">$${r.cost}</strong></span>
          <span>Time: <strong>${r.base_turns} turns</strong></span>
        </div>
        <button class="btn btn-secondary btn-block mt-2 btn-commission" data-recipe="${r.name}">
          🔨 Commission Project ($${r.cost})
        </button>
      `;

      card.querySelector('.btn-commission').addEventListener('click', () => {
        sendCommand('BUILD_PROJECT', { tile: selectedTileName, building: r.name });
      });

      list.appendChild(card);
    });
  }

  function renderActiveProjects() {
    const section = document.getElementById('active-projects-section');
    const list = document.getElementById('active-projects-list');
    if (!section || !list || !worldState || !worldState.tiles) return;

    // Aggregate active projects from tiles
    const allProjects = [];
    worldState.tiles.forEach(t => {
      if (t.construction_projects && t.construction_projects.length > 0) {
        t.construction_projects.forEach(p => {
          allProjects.push({ ...p, tileName: t.display_name || t.name });
        });
      }
    });

    if (allProjects.length === 0) {
      section.classList.add('hidden');
      return;
    }

    section.classList.remove('hidden');
    list.innerHTML = '';

    allProjects.forEach(p => {
      const item = document.createElement('div');
      item.className = 'item-card mt-2';
      item.innerHTML = `
        <div class="card-top">
          <strong>${p.name}</strong>
          <span class="text-gold">${p.turns_left}t remaining</span>
        </div>
        <div class="card-desc">Location: ${p.tileName}</div>
        <div class="enclosure-bar mt-2">
          <div class="bar-segment commons" style="width: ${p.progress}%"></div>
        </div>
      `;
      list.appendChild(item);
    });
  }

  // 3. Diplomacy List
  function renderDiplomacyNations() {
    const list = document.getElementById('diplomacy-nations-list');
    if (!list || !worldState || !worldState.diplomacy) return;

    list.innerHTML = '';
    if (worldState.diplomacy.length === 0) {
      list.innerHTML = '<div class="empty-state">No sovereign diplomatic partners detected.</div>';
      return;
    }

    worldState.diplomacy.forEach(d => {
      const card = document.createElement('div');
      card.className = 'item-card';

      const treatiesBadges = d.treaties.map(t => `<span class="card-badge mastered">${t}</span>`).join(' ') || '<span class="text-dim">None</span>';

      card.innerHTML = `
        <div class="card-top">
          <strong style="color: ${d.flag_color}">👑 ${d.nation}</strong>
          <span class="card-badge ${d.relation >= 0.2 ? 'mastered' : (d.relation <= -0.2 ? 'locked' : 'unlocked')}">${d.status} (${d.relation > 0 ? '+' : ''}${d.relation.toFixed(2)})</span>
        </div>
        <div class="card-meta-row">
          <span>Active Treaties: ${treatiesBadges}</span>
        </div>
        <div class="dual-btn-row mt-2">
          <button class="btn btn-secondary btn-propose-trade">Trade Pact</button>
          <button class="btn btn-secondary btn-propose-nap">NAP</button>
          <button class="btn btn-secondary btn-propose-alliance">Alliance</button>
          <button class="btn btn-secondary btn-war" style="color:var(--ruby)">War</button>
        </div>
      `;

      card.querySelector('.btn-propose-trade').addEventListener('click', () => {
        sendCommand('DIPLOMATIC_ACTION', { action: 'propose_trade', target: d.nation });
      });
      card.querySelector('.btn-propose-nap').addEventListener('click', () => {
        sendCommand('DIPLOMATIC_ACTION', { action: 'propose_nap', target: d.nation });
      });
      card.querySelector('.btn-propose-alliance').addEventListener('click', () => {
        sendCommand('DIPLOMATIC_ACTION', { action: 'propose_alliance', target: d.nation });
      });
      card.querySelector('.btn-war').addEventListener('click', () => {
        if (confirm(`Are you sure you want to declare war on ${d.nation}?`)) {
          sendCommand('DIPLOMATIC_ACTION', { action: 'declare_war', target: d.nation });
        }
      });

      list.appendChild(card);
    });
  }

  // 4. Sovereign Debt
  function renderSovereignDebt() {
    if (!worldState || !worldState.sovereign_debt) return;
    const debt = worldState.sovereign_debt;

    const elRating = document.getElementById('debt-isrb-rating');
    const elYield = document.getElementById('debt-market-yield');
    const elTotal = document.getElementById('debt-total-amount');

    if (elRating) elRating.textContent = debt.rating || 'BBB';
    if (elYield) elYield.textContent = `${(debt.yield_rate || 0.18).toFixed(2)}% / t`;
    if (elTotal) elTotal.textContent = `$${Math.round(debt.public_debt || 0).toLocaleString()}`;

    const list = document.getElementById('active-offerings-list');
    if (list) {
      list.innerHTML = '';
      if (!debt.offerings || debt.offerings.length === 0) {
        list.innerHTML = '<div class="empty-state">No live bond offerings active.</div>';
      } else {
        debt.offerings.forEach(off => {
          const item = document.createElement('div');
          item.className = 'item-card';
          item.innerHTML = `
            <div class="card-top">
              <strong>$${off.principal.toLocaleString()} Bond</strong>
              <span class="text-gold">${off.status.toUpperCase()}</span>
            </div>
            <div class="card-meta-row">
              <span>Duration: ${off.duration} turns</span>
              <span>Coupon: ${(off.coupon_rate * 100).toFixed(2)}%/t</span>
            </div>
          `;
          list.appendChild(item);
        });
      }
    }
  }

  // 5. Science Techs
  function renderScienceTechs() {
    const list = document.getElementById('science-tech-list');
    if (!list || !worldState || !worldState.science_tree) return;

    list.innerHTML = '';
    const filtered = worldState.science_tree.filter(t => t.era === activeScienceEra);

    filtered.forEach(tech => {
      const card = document.createElement('div');
      card.className = 'item-card';

      const isMastered = tech.status === 'mastered';
      const hasBounty = tech.status === 'bounty_active';

      card.innerHTML = `
        <div class="card-top">
          <strong class="card-title">${tech.name}</strong>
          <span class="card-badge ${tech.status}">${tech.status.toUpperCase().replace('_', ' ')}</span>
        </div>
        <p class="card-desc">${tech.description}</p>
        <div class="card-meta-row">
          <span>Domain: <strong>${tech.domain}</strong></span>
          <span>Base XP: <strong>${tech.base_xp}</strong></span>
        </div>
        ${!isMastered ? `
          <button class="btn btn-secondary btn-block mt-2 btn-pledge" ${hasBounty ? 'disabled' : ''}>
            ${hasBounty ? '👑 Royal Prize Active ($300)' : '🔬 Pledge Royal Science Prize ($300)'}
          </button>
        ` : ''}
      `;

      if (!isMastered && !hasBounty) {
        card.querySelector('.btn-pledge').addEventListener('click', () => {
          sendCommand('RESEARCH_TECH', { action: 'pledge_prize', tech_id: tech.id, amount: 300 });
        });
      }

      list.appendChild(card);
    });
  }

  // 6. Military Suite
  function renderMilitarySuite() {
    if (!worldState) return;

    const tileLbl = document.getElementById('military-tile-lbl');
    const garLbl = document.getElementById('lbl-garrison-count');
    const list = document.getElementById('military-armies-list');

    if (tileLbl) {
      tileLbl.textContent = selectedTileName ? `Selected Territory: ${selectedTileName}` : 'Selected Territory: Capital';
    }

    if (garLbl && worldState.tiles && selectedTileName) {
      const tile = worldState.tiles.find(t => t.name === selectedTileName);
      if (tile) {
        garLbl.textContent = `${tile.garrison || 0} soldiers`;
      }
    }

    if (list) {
      list.innerHTML = '';
      if (!worldState.armies || worldState.armies.length === 0) {
        list.innerHTML = '<div class="empty-state">No standing mobile divisions. Territorial defense provided by local garrisons.</div>';
      } else {
        worldState.armies.forEach(a => {
          const item = document.createElement('div');
          item.className = 'item-card';
          item.innerHTML = `
            <div class="card-top">
              <strong>⚔️ ${a.id}</strong>
              <span class="text-gold">${a.soldiers} Soldiers</span>
            </div>
            <div class="card-meta-row">
              <span>Combat Strength: ${a.strength}</span>
              <span>XP: ${a.xp}</span>
            </div>
          `;
          list.appendChild(item);
        });
      }
    }
  }

  // ---------------- Right Inspection Panel ----------------

  function setupRightPanel() {
    // Tab Switching
    document.querySelectorAll('.panel-tabs .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.panel-tabs .tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeRightTab = btn.dataset.tab.replace('tab-', '');

        document.querySelectorAll('.panel-body .tab-pane').forEach(p => p.classList.remove('active'));
        const pane = document.getElementById(btn.dataset.tab);
        if (pane) pane.classList.add('active');

        if (activeRightTab === 'charts') {
          renderHistoricalChart();
        }
      });
    });

    // Chart Metric Chips
    document.querySelectorAll('.chart-selector-chips .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('.chart-selector-chips .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeChartMetric = chip.dataset.chart;
        renderHistoricalChart();
      });
    });

    // Mobile Drawer Expand / Collapse
    if (rightDrawerHandle) {
      rightDrawerHandle.addEventListener('click', toggleRightDrawer);
    }
    if (drawerToggleBtn) {
      drawerToggleBtn.addEventListener('click', toggleRightDrawer);
    }
  }

  function toggleRightDrawer() {
    rightPanel.classList.toggle('collapsed');
    const isCollapsed = rightPanel.classList.contains('collapsed');
    if (drawerToggleBtn) {
      drawerToggleBtn.textContent = isCollapsed ? '▲' : '▼';
    }
  }

  function updateTileInspectionUI(tile) {
    if (!tile) return;
    selectedTileDetail = tile;

    if (tileNameEl) tileNameEl.textContent = tile.display_name || tile.name;
    if (tileSubEl) tileSubEl.textContent = `${tile.nation || 'Wilderness'} • ${tile.biome} (▲${Math.round(tile.elevation_meters || 0)}m)`;

    // Overview Tab
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
        item.innerHTML = `
          <div class="p-name">${g}</div>
          <div class="p-val">$${price.toFixed(2)}</div>
        `;
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
      if (plotsList && tile.tenure.plots) {
        plotsList.innerHTML = '';
        if (tile.tenure.plots.length === 0) {
          plotsList.innerHTML = '<div class="empty-state">No cadastral plots registered.</div>';
        } else {
          tile.tenure.plots.forEach(p => {
            const row = document.createElement('div');
            row.className = 'citizen-row';
            row.innerHTML = `
              <span class="citizen-role">${p.display_name || p.plot_id}</span>
              <span class="citizen-info">${p.tenure} • ${Math.round(p.fraction * 100)}% area</span>
            `;
            plotsList.appendChild(row);
          });
        }
      }
    }

    // Citizens Census Tab
    const citList = document.getElementById('citizens-list');
    if (citList) {
      citList.innerHTML = '';
      if (!tile.citizens || tile.citizens.length === 0) {
        citList.innerHTML = '<div class="empty-state">No resident citizens on this territory.</div>';
      } else {
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
      worldState.ticker_events.slice(-25).reverse().forEach(ev => {
        const item = document.createElement('div');
        item.className = `news-item ${ev.kind || ''}`;
        item.innerHTML = `<strong>[T${ev.t}] ${ev.kind}:</strong> ${ev.text}`;
        feed.appendChild(item);
      });
    }

    if (activeRightTab === 'charts') {
      renderHistoricalChart();
    }
  }

  // ---------------- Interactive HTML5 Canvas Chart Engine ----------------

  function renderHistoricalChart() {
    const chartCanvas = document.getElementById('historical-chart-canvas');
    if (!chartCanvas || !worldState || !worldState.history) return;

    const cCtx = chartCanvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const w = chartCanvas.clientWidth;
    const h = chartCanvas.clientHeight;

    chartCanvas.width = Math.round(w * dpr);
    chartCanvas.height = Math.round(h * dpr);

    cCtx.save();
    cCtx.scale(dpr, dpr);
    cCtx.clearRect(0, 0, w, h);

    const hist = worldState.history;
    const values = hist[activeChartMetric] || [];
    const turns = hist.turns || [];

    if (values.length < 2) {
      cCtx.fillStyle = '#64748b';
      cCtx.font = '12px sans-serif';
      cCtx.textAlign = 'center';
      cCtx.fillText('Advancing simulation turns to plot time-series...', w / 2, h / 2);
      cCtx.restore();
      return;
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

    // Draw Gridlines & Y-Axis Labels
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

    // Draw Line Curve
    cCtx.beginPath();
    const metricColors = {
      gdp: '#38bdf8',
      treasury: '#f59e0b',
      food_price: '#10b981',
      pop: '#a855f7',
      unrest: '#ef4444'
    };
    const strokeColor = metricColors[activeChartMetric] || '#38bdf8';
    cCtx.strokeStyle = strokeColor;
    cCtx.lineWidth = 2.5;

    values.forEach((v, idx) => {
      const x = padL + (plotW / (values.length - 1)) * idx;
      const y = padT + plotH - ((v - minVal) / valSpan) * plotH;
      if (idx === 0) cCtx.moveTo(x, y);
      else cCtx.lineTo(x, y);
    });
    cCtx.stroke();

    // Data Points
    cCtx.fillStyle = strokeColor;
    values.forEach((v, idx) => {
      const x = padL + (plotW / (values.length - 1)) * idx;
      const y = padT + plotH - ((v - minVal) / valSpan) * plotH;
      cCtx.beginPath();
      cCtx.arc(x, y, 2.5, 0, Math.PI * 2);
      cCtx.fill();
    });

    // X-Axis Turn Labels
    cCtx.fillStyle = '#64748b';
    cCtx.textAlign = 'center';
    cCtx.fillText(`T${turns[0]}`, padL, h - 6);
    cCtx.fillText(`T${turns[turns.length - 1]}`, w - padR, h - 6);

    cCtx.restore();
  }

  // ---------------- Compare Nations Modal ----------------

  function setupCompareModal() {
    if (btnCompare) {
      btnCompare.addEventListener('click', openCompareModal);
    }
    if (btnCloseCompare) {
      btnCloseCompare.addEventListener('click', closeCompareModal);
    }
    if (compareBackdrop) {
      compareBackdrop.addEventListener('click', closeCompareModal);
    }
  }

  function openCompareModal() {
    if (!compareModal || !worldState || !worldState.nations) return;
    compareModal.classList.remove('hidden');

    const tbody = document.getElementById('compare-tbody');
    if (!tbody) return;
    tbody.innerHTML = '';

    worldState.nations.forEach(n => {
      const tr = document.createElement('tr');
      const isPlayer = (n.name === worldState.player_nation);

      tr.innerHTML = `
        <td><strong style="color: ${n.flag_color || '#38bdf8'}">👑 ${n.name}</strong> ${isPlayer ? '<span class="card-badge mastered">YOU</span>' : ''}</td>
        <td>${n.regime_type || 'Monarchy'}</td>
        <td class="text-gold">$${Math.round(n.treasury_cash || 0).toLocaleString()}</td>
        <td>${(n.population || 0).toLocaleString()}</td>
        <td class="text-cyan">$${Math.round(n.gdp || 0).toLocaleString()}</td>
        <td>$${Math.round(n.gdp_per_capita || 0)}</td>
        <td><span class="badge-unrest ${n.unrest_stage.toLowerCase()}">${n.unrest_stage}</span></td>
        <td><strong class="text-gold">${n.credit_rating || 'BBB'}</strong></td>
        <td>${n.tiles_count || 0}</td>
        <td>
          ${!isPlayer ? `<button class="btn btn-secondary btn-switch-nation" data-nat="${n.name}">Play</button>` : '—'}
        </td>
      `;

      if (!isPlayer) {
        tr.querySelector('.btn-switch-nation').addEventListener('click', () => {
          sendCommand('SELECT_NATION', { nation: n.name });
          closeCompareModal();
        });
      }

      tbody.appendChild(tr);
    });
  }

  function closeCompareModal() {
    if (compareModal) compareModal.classList.add('hidden');
  }

  // ---------------- Help & Guide Modal ----------------

  function setupHelpModal() {
    if (btnHelp) {
      btnHelp.addEventListener('click', () => helpModal.classList.remove('hidden'));
    }
    if (btnCloseHelp) {
      btnCloseHelp.addEventListener('click', () => helpModal.classList.add('hidden'));
    }
    if (helpBackdrop) {
      helpBackdrop.addEventListener('click', () => helpModal.classList.add('hidden'));
    }
  }

  // ---------------- Mobile QR Modal ----------------

  function setupQrModal() {
    if (btnQr) {
      btnQr.addEventListener('click', () => {
        if (qrUrlText) qrUrlText.value = window.location.origin;
        qrModal.classList.remove('hidden');
      });
    }
    if (btnCloseQr) {
      btnCloseQr.addEventListener('click', () => qrModal.classList.add('hidden'));
    }
    if (qrBackdrop) {
      qrBackdrop.addEventListener('click', () => qrModal.classList.add('hidden'));
    }
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

  // ---------------- Selection & Input Gestures ----------------

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

    // Detect tap / click (less than 8px movement and under 350ms)
    if (dx < 8 && dy < 8 && dt < 350) {
      const rect = canvas.getBoundingClientRect();
      const clickX = (e.clientX - rect.left - camX) / camZoom;
      const clickY = (e.clientY - rect.top - camY) / camZoom;

      const hexRadius = getHexRadius();
      const axial = pixelToAxial(clickX, clickY, hexRadius);

      if (worldState && worldState.tiles) {
        const hit = worldState.tiles.find(t => t.q === axial.q && t.r === axial.r);
        if (hit) {
          selectTile(hit.name);
        }
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

    // Zoom toward mouse position
    camX = mouseX - (mouseX - camX) * (newZoom / camZoom);
    camY = mouseY - (mouseY - camY) * (newZoom / camZoom);
    camZoom = newZoom;
    renderMap();
  }

  // Touch Pinch-to-Zoom
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
      else if (key === '?' || key === 'H') helpModal.classList.toggle('hidden');
      else if (key === ' ') {
        e.preventDefault();
        if (btnPlay) btnPlay.click();
      } else if (key === '+' || key === '=') {
        if (btnStep) btnStep.click();
      } else if (key === 'ESCAPE') {
        closeLeftDrawer();
        closeCompareModal();
        helpModal.classList.add('hidden');
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
    setupHelpModal();
    setupQrModal();
    setupLayerSelector();
    setupKeyboardShortcuts();

    // Top Controls
    if (btnPlay) {
      btnPlay.addEventListener('click', () => {
        sendCommand(isPlaying ? 'PAUSE' : 'PLAY');
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
