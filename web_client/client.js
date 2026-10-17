/**
 * Call of Capital Web Client — Comprehensive Sovereign Macroeconomic Simulation Client
 * 100% Desktop Parity: 9 Thematic Layers, 6 Sovereign Suites, 20 Charts Engine,
 * Cadastre Plot Management, 6-Tab Comparison Suite, Fiscal Bailout Dialog,
 * 3-Page Paginated Encyclopedia, and Real-Time Authoritative WebSocket/REST Sync.
 */

(function () {
  'use strict';

  const DEFAULT_HEX_SIZE = 50.0;
  const uiUtils = window.CoCUIUtils;
  const { escapeHtml, safeClassToken, safeCssColor } = uiUtils;
  const hexGeo = window.CoCHexGeometry;
  const { axialToPixel, pixelToAxial, drawHexPolygon } = hexGeo || {};
  const voronoiGeo = window.CoCVoronoiGeometry;
  const { pointInPolygon, polygonBBox, polygonCentroid, drawPolygonPath } = voronoiGeo || {};
  const projection3D = window.CoCProjection3D;
  const { getCameraMVP, projectPoint3D, projectPolygon3D, screenToWorldRay, intersectRayPlane, computePitchYaw } = projection3D || {};
  const stateSync = window.CoCStateSync;
  const api = stateSync.createStateSync({
    async onCommandResult(result) {
      if (!result.success) {
        showToast(result.error || result.message || 'Command failed.', true);
      } else {
        if (result.message) showToast(result.message);
        await fetchState(true);
      }
    },
    onNetworkError(error) {
      showToast(`Network error: ${error.message}`, true);
    }
  });

  // Global World & Simulation State
  let worldState = null;
  let laborPanelCollapsed = false;
  let laborMapConfigured = false;
  let selectedTileName = null;
  let selectedTileDetail = null;
  let isPlaying = false;
  let pollTimer = null;
  let stateVersion = null;
  let mapFramePending = false;
  let tileByName = new Map();
  let tileByAxial = new Map();
  let positionedTiles = [];
  let terrainBoundaryCache = new Map();
  let terrainBoundaryCacheVersion = null;
  let lastTileDetailKey = null;
  let lastNewsKey = null;
  let lastDrawerKey = null;
  let stateFetchPromise = null;
  let tileDetailRequest = 0;
  let loadedTileDetailVersion = null;
  let pendingTileDetailVersion = null;
  let lastRecipesKey = null;
  let lastTileDetailErrorKey = null;
  let lastStateFetchError = null;

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
  let activeProgressMode = 'active'; // 'active' | 'all'
  let cadastreScrollOffset = 0;
  let hoveredTileName = null;
  let showTradeRoutes = true;
  let showTradeArrows = true;
  let showArbitrageRings = true;
  let mapAnimFrame = 0;

  // Photorealistic Topographic Terrain State
  let useTerrainImage = true;
  const terrainLayer = window.CoCTerrainLayer.createTerrainLayer(scheduleMapRender);
  const terrainMesh = window.CoCTerrainRenderer.createTerrainRenderer(scheduleMapRender);

  // Camera & Interaction State
  let camX = 0;
  let camY = 0;
  let camZoom = 1.0;
  let camPitch = 52.0;
  let camYaw = 9.0;
  let camTargetX = 500.0;
  let camTargetY = 500.0;
  let is3DMode = true;
  let isInitialCentered = false;
  let isDragging = false;
  let isOrbiting = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let camStartX = 0;
  let camStartY = 0;
  let camStartTargetX = 500.0;
  let camStartTargetY = 500.0;
  let startPitch = 52.0;
  let startYaw = 9.0;
  let touchStartTime = 0;
  let initialPinchDist = null;
  let initialPinchZoom = 1.0;

  // Pending Fiscal Transfer Data
  let pendingFiscalTransfer = null;

  // Nation Abbreviations Mapping for Compact Top Bar Display
  const NATION_ABBREVIATIONS = {
    'United States': 'USA',
    'United States of America': 'USA',
    'Great Britain': 'GBR',
    'United Kingdom': 'UK',
    'China': 'CHN',
    'Japan': 'JPN',
    'France': 'FRA',
    'Germany': 'GER',
    'Prussia': 'PRU',
    'Russia': 'RUS',
    'Russian Empire': 'RUS',
    'Ottoman Empire': 'OTT',
    'Austria': 'AUT',
    'Austria-Hungary': 'AH',
    'Spain': 'ESP',
    'Portugal': 'POR',
    'Netherlands': 'NED',
    'Italy': 'ITA'
  };

  function abbreviateNationName(name) {
    if (!name) return '';
    if (NATION_ABBREVIATIONS[name]) return NATION_ABBREVIATIONS[name];
    const parts = name.split(/\s+/);
    if (parts.length > 1) {
      return parts.map(p => p[0].toUpperCase()).join('');
    }
    return name.length > 4 ? name.substring(0, 3).toUpperCase() : name.toUpperCase();
  }

  // DOM Elements
  const canvas = document.getElementById('map-canvas');
  const ctx = canvas.getContext('2d');
  const terrainStatus = document.getElementById('terrain-status');
  const turnDisplay = document.getElementById('turn-display');
  const btnPlay = document.getElementById('btn-play');
  const btnStep = document.getElementById('btn-step');
  const btnNew = document.getElementById('btn-new');
  const btnCompare = document.getElementById('btn-compare');
  const btnHelp = document.getElementById('btn-help');
  const btnQr = document.getElementById('btn-qr');
  const btnSettings = document.getElementById('btn-settings');
  const btnToggle3D = document.getElementById('btn-toggle-3d');
  const btnToggleTerrain = document.getElementById('btn-toggle-terrain');
  const btnTogglePipeline = document.getElementById('btn-toggle-pipeline');
  const btnTopDiplo = document.getElementById('btn-top-diplo');
  const btnTopMilitary = document.getElementById('btn-top-military');
  const statusDot = document.getElementById('status-dot');
  const selectNation = document.getElementById('select-nation');
  const activeFlagDot = document.getElementById('active-flag-dot');
  const quickPill = document.getElementById('quick-pill');
  const pillText = document.getElementById('pill-text');
  const seasonalClock = document.getElementById('seasonal-clock');
  const seasonalPopover = document.getElementById('seasonal-popover');
  const hexHoverCard = document.getElementById('hex-hover-card');
  const scenarioPressuresRibbon = document.getElementById('scenario-pressures-ribbon');

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
  const settingsModal = document.getElementById('settings-modal');
  const btnCloseSettings = document.getElementById('btn-close-settings');
  const settingsBackdrop = document.getElementById('settings-backdrop');
  const scenarioBookendModal = document.getElementById('scenario-bookend-modal');
  const btnCloseBookend = document.getElementById('btn-close-bookend');
  const scenarioBookendBackdrop = document.getElementById('scenario-bookend-backdrop');

  // Toast Container
  const toastContainer = document.getElementById('toast-container');

  // ---------------- Hex & Voronoi Math & Geometry ----------------

  function isVoronoi() {
    return Boolean(
      worldState && (
        worldState.topology === 'voronoi' ||
        (worldState.tiles && worldState.tiles.length > 0 && Array.isArray(worldState.tiles[0].polygon))
      )
    );
  }

  function getHexRadius() {
    return (worldState && typeof worldState.hex_size === 'number') ? worldState.hex_size : DEFAULT_HEX_SIZE;
  }

  function indexTiles() {
    tileByName = new Map();
    tileByAxial = new Map();
    positionedTiles = [];
    if (!worldState || !worldState.tiles) return;

    if (isVoronoi()) {
      for (const tile of worldState.tiles) {
        if (!tile.centroid || !Array.isArray(tile.centroid) || tile.centroid.length < 2) {
          if (tile.polygon && typeof polygonCentroid === 'function') {
            tile.centroid = polygonCentroid(tile.polygon);
          } else {
            tile.centroid = [500.0, 500.0];
          }
        }
        if (tile.polygon && typeof polygonBBox === 'function') {
          tile._bbox = polygonBBox(tile.polygon);
        }
        tileByName.set(tile.name, tile);
        positionedTiles.push({
          tile,
          x: tile.centroid[0],
          y: tile.centroid[1],
          polygon: tile.polygon
        });
      }
    } else {
      const radius = getHexRadius();
      for (const tile of worldState.tiles) {
        const point = axialToPixel(tile.q, tile.r, radius);
        tileByName.set(tile.name, tile);
        tileByAxial.set(`${tile.q},${tile.r}`, tile);
        positionedTiles.push({ tile, x: point.x, y: point.y });
      }
    }
  }

  function scheduleMapRender() {
    if (mapFramePending) return;
    mapFramePending = true;
    requestAnimationFrame(() => {
      mapFramePending = false;
      renderMap();
    });
  }

  function toggle3DMode() {
    is3DMode = !is3DMode;
    if (btnToggle3D) {
      btnToggle3D.textContent = is3DMode ? '3D' : '2D';
      btnToggle3D.classList.toggle('active', is3DMode);
      btnToggle3D.title = is3DMode ? 'Toggle 2D Flat Perspective [3]' : 'Toggle 35mm 3D Perspective [3]';
    }
    showToast(is3DMode ? 'Camera: 35mm 3D Perspective' : 'Camera: 2D Orthographic');
    scheduleMapRender();
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
    scheduleMapRender();
  }

  function centerCameraOnWorld() {
    if (!worldState || !worldState.tiles || worldState.tiles.length === 0) return;
    const w = canvas.parentElement.clientWidth;
    const h = canvas.parentElement.clientHeight;

    if (isVoronoi()) {
      let minX = 0, maxX = 1000, minY = 0, maxY = 1000;
      if (worldState.terrain_bounds) {
        const tb = worldState.terrain_bounds;
        minX = tb.min_x !== undefined ? tb.min_x : 0;
        maxX = tb.max_x !== undefined ? tb.max_x : 1000;
        minY = tb.min_y !== undefined ? tb.min_y : 0;
        maxY = tb.max_y !== undefined ? tb.max_y : 1000;
      }
      camTargetX = (minX + maxX) / 2;
      camTargetY = (minY + maxY) / 2;
      camZoom = 1.0;

      if (typeof computePitchYaw === 'function') {
        const py = computePitchYaw(camZoom);
        camPitch = is3DMode ? py.pitch : 89.0;
        camYaw = is3DMode ? py.yaw : 0.0;
      } else {
        camPitch = is3DMode ? 58.0 : 89.0;
        camYaw = is3DMode ? 6.0 : 0.0;
      }

      camX = w / 2 - camTargetX * camZoom;
      camY = h / 2 - camTargetY * camZoom;
      isInitialCentered = true;
      scheduleMapRender();
      return;
    }

    const hexRadius = getHexRadius();
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

    worldState.tiles.forEach(t => {
      const { x, y } = axialToPixel(t.q, t.r, hexRadius);
      minX = Math.min(minX, x - hexRadius);
      maxX = Math.max(maxX, x + hexRadius);
      minY = Math.min(minY, y - hexRadius);
      maxY = Math.max(maxY, y + hexRadius);
    });

    const worldW = maxX - minX;
    const worldH = maxY - minY;
    camTargetX = (minX + maxX) / 2;
    camTargetY = (minY + maxY) / 2;

    const pad = 60;
    const zX = (w - pad * 2) / Math.max(worldW, 100);
    const zY = (h - pad * 2) / Math.max(worldH, 100);
    camZoom = Math.min(Math.max(Math.min(zX, zY), 0.4), 2.2);

    camX = w / 2 - camTargetX * camZoom;
    camY = h / 2 - camTargetY * camZoom;
    isInitialCentered = true;
    scheduleMapRender();
  }

  // ---------------- Terrain Image Synchronizer ----------------

  function syncTerrainImage(seed) {
    terrainLayer.sync(seed);
  }

  function hexToRgba(hex, alpha) {
    if (!hex) return `rgba(255, 255, 255, ${alpha})`;
    let c = hex.replace('#', '');
    if (c.length === 3) c = c.split('').map(x => x + x).join('');
    const num = parseInt(c, 16);
    if (isNaN(num)) return `rgba(255, 255, 255, ${alpha})`;
    const r = (num >> 16) & 255;
    const g = (num >> 8) & 255;
    const b = num & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  // ---------------- Map & Thematic Layers Renderer ----------------

  function getThematicLayerFill(tile) {
    if (!tile || activeLayer === 'overview') return null;

    if (activeLayer === 'physical') {
      const elev = tile.elevation_meters || 0;
      const norm = Math.min(Math.max(elev / 3000.0, 0), 1.0);
      return `rgba(140, 225, 255, ${norm * 0.55})`;
    } else if (activeLayer === 'population') {
      const pop = tile.population || 0;
      const norm = Math.min(pop / 150.0, 1.0);
      const unrest = Math.min((tile.protest_energy || 0) / 5.0, 1.0);
      return `rgba(${Math.round(245 * unrest + 56 * (1 - unrest))}, ${Math.round(140 * (1 - unrest))}, 60, ${0.15 + norm * 0.55})`;
    } else if (activeLayer === 'economy') {
      const gdp = tile.gdp || 0;
      const norm = Math.min(gdp / 1000.0, 1.0);
      return `rgba(120, 225, 130, ${0.15 + norm * 0.55})`;
    } else if (activeLayer === 'production') {
      const bCount = tile.buildings_count || (tile.buildings && tile.buildings.length) || 0;
      const norm = Math.min(bCount / 5.0, 1.0);
      return `rgba(245, 210, 90, ${0.15 + norm * 0.55})`;
    } else if (activeLayer === 'military') {
      const g = tile.garrison || 0;
      const norm = Math.min(g / 50.0, 1.0);
      return `rgba(235, 80, 80, ${0.15 + norm * 0.55})`;
    } else if (activeLayer === 'enclosure') {
      const enc = tile.enclosed_fraction ?? ((tile.tenure && tile.tenure.enclosed_fraction) || 0);
      return `rgba(215, 175, 75, ${0.15 + enc * 0.6})`;
    } else if (activeLayer === 'exploitation') {
      const s_v = tile.exploitation_rate ?? ((tile.tenure && tile.tenure.surplus_value_rate) || 0.5);
      const norm = Math.min(s_v / 2.0, 1.0);
      return `rgba(235, 75, 75, ${0.2 + norm * 0.6})`;
    } else if (activeLayer === 'externalities') {
      const smog = tile.pollution_air ?? ((tile.ecology && tile.ecology.pollution_air) || 0);
      const norm = Math.min(smog / 100.0, 1.0);
      return `rgba(100, 215, 140, ${0.15 + (1 - norm) * 0.4})`;
    }
    return null;
  }

  function renderThematicLayerOverlay(ctx, tile, cx, cy, size) {
    if (activeLayer === 'overview') return;
    const fill = getThematicLayerFill(tile);
    if (!fill) return;

    ctx.save();
    drawHexPolygon(ctx, cx, cy, size - 1.0);
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.restore();
  }

  const BIOME_COLOR_MAP = {
    ocean: '#1e3a8a',
    deep_ocean: '#0f172a',
    shallow_ocean: '#0284c7',
    coast: '#0ea5e9',
    beach: '#d97706',
    scorched: '#78716c',
    bare: '#a8a29e',
    tundra: '#94a3b8',
    snow: '#f8fafc',
    taiga: '#334155',
    shrubland: '#84cc16',
    grassland: '#22c55e',
    temperate_desert: '#f59e0b',
    subtropical_desert: '#d97706',
    temperate_rain_forest: '#047857',
    temperate_deciduous_forest: '#15803d',
    tropical_rain_forest: '#065f46',
    tropical_seasonal_forest: '#16a34a',
    plains: '#4ade80',
    forest: '#15803d',
    mountain: '#64748b',
    mountains: '#64748b',
    hills: '#65a30d',
    swamp: '#14532d',
    desert: '#eab308'
  };

  function getTileColor(tile) {
    if (!tile) return '#22c55e';
    if (tile.color && typeof tile.color === 'string') return tile.color;
    const isSea = (tile.is_ocean || (typeof tile.elevation === 'number' && tile.elevation <= 0) || tile.biome === 'ocean');
    if (isSea) {
      if (typeof tile.elevation === 'number' && tile.elevation < -0.4) return '#0f172a';
      return '#1e3a8a';
    }
    const b = (tile.biome || '').toLowerCase();
    if (b && BIOME_COLOR_MAP[b]) return BIOME_COLOR_MAP[b];
    const elev = Number(tile.elevation || 0);
    if (elev > 0.7) return '#f8fafc';
    if (elev > 0.5) return '#64748b';
    if (elev > 0.3) return '#15803d';
    return '#4ade80';
  }

  function getTileBoundary3D(tile, terrainReady) {
    const generation = worldState?.version?.split(':').slice(0, 2).join(':') || 'world';
    const cacheVersion = `${generation}:${terrainReady ? 'mesh' : 'flat'}`;
    if (cacheVersion !== terrainBoundaryCacheVersion) {
      terrainBoundaryCache.clear();
      terrainBoundaryCacheVersion = cacheVersion;
    }
    if (terrainBoundaryCache.has(tile.name)) return terrainBoundaryCache.get(tile.name);

    const polygon = tile.polygon || [];
    const points = [];
    const fallbackZ = Number(tile.elevation || 0) * 48.0 + 0.1;
    for (let edge = 0; edge < polygon.length; edge++) {
      const start = polygon[edge], end = polygon[(edge + 1) % polygon.length];
      const dx = end[0] - start[0], dy = end[1] - start[1];
      const steps = Math.max(1, Math.ceil(Math.hypot(dx, dy) / 6));
      for (let step = 0; step < steps; step++) {
        const t = step / steps;
        const x = start[0] + dx * t, y = start[1] + dy * t;
        const z = terrainReady ? terrainMesh.sampleElevation(x, y) : fallbackZ;
        points.push([x, y, z]);
      }
    }
    terrainBoundaryCache.set(tile.name, points);
    return points;
  }

  function renderVoronoiMap3D(w, h) {
    const camObj = {
      pitch: camPitch,
      yaw: camYaw,
      zoom: camZoom,
      target_x: camTargetX,
      target_y: camTargetY
    };
    const terrainReady = terrainMesh.draw(ctx, camObj, w, h, getCameraMVP);
    if (terrainStatus) {
      const phase = terrainMesh.status;
      terrainStatus.classList.toggle('hidden', phase === 'ready');
      if (phase !== 'ready') {
        const reason = terrainMesh.error;
        terrainStatus.textContent = phase === 'loading'
          ? 'Loading desktop terrain mesh…'
          : phase === 'retrying'
            ? `Retrying terrain mesh: ${reason}`
            : `Terrain mesh unavailable: ${reason}`;
      }
    }
    const mvp = getCameraMVP(camObj, w, h);
    if (!mvp) return;

    const tradeAnim = window.CoCTradeAnimator;
    const projectedGeom = [];

    // Pass 1: Voronoi 3D Polygons Projection, Biome Fill, Nation Tint, Layer Overlay & Borders
    for (let i = 0; i < positionedTiles.length; i++) {
      const { tile } = positionedTiles[i];
      if (!tile.polygon || tile.polygon.length < 3) continue;

      const isSelected = (selectedTileName && tile.name === selectedTileName);
      const isSea = (tile.is_ocean || (typeof tile.elevation === 'number' && tile.elevation <= 0) || tile.biome === 'ocean');
      if (isSea) continue;

      const elev = Number(tile.elevation || 0);
      const z = elev * 48.0 + 0.1;
      const pts3D = getTileBoundary3D(tile, terrainReady);
      const screenPts = projectPolygon3D(mvp, pts3D, w, h);
      if (!screenPts || screenPts.length < 3) continue;

      const cz = terrainReady
        ? terrainMesh.sampleElevation(tile.centroid[0], tile.centroid[1]) + 2.0
        : z + 0.2;
      const cScreen = projectPoint3D(mvp, tile.centroid[0], tile.centroid[1], cz, w, h);
      projectedGeom.push({ tile, screenPts, cScreen, isSelected, isSea });

      ctx.beginPath();
      ctx.moveTo(screenPts[0][0], screenPts[0][1]);
      for (let j = 1; j < screenPts.length; j++) {
        ctx.lineTo(screenPts[j][0], screenPts[j][1]);
      }
      ctx.closePath();

      // Keep tile polygons transparent over the shared desktop terrain mesh.
      // They still provide color fills as a fallback if WebGL cannot load.
      if (!terrainReady) {
        ctx.fillStyle = getTileColor(tile);
        ctx.fill();
        if (tile.nation_color) {
          const baseColor = tile.nation_color.startsWith('#')
            ? hexToRgba(tile.nation_color, 0.25)
            : tile.nation_color.replace('rgb', 'rgba').replace(')', ', 0.25)');
          ctx.fillStyle = baseColor;
          ctx.fill();
        }

        // Thematic fills are also overlays, so keep the terrain visible.
        if (activeLayer !== 'overview') {
          const layerFill = getThematicLayerFill(tile);
          if (layerFill) {
            ctx.fillStyle = layerFill;
            ctx.fill();
          }
        }
      }

      // Territorial boundaries
      if (isSelected) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 3.5;
        ctx.stroke();
      } else if (hoveredTileName && tile.name === hoveredTileName) {
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2.5;
        ctx.stroke();
      } else if (tile.nation_color) {
        ctx.strokeStyle = tile.nation_color;
        ctx.lineWidth = 1.8;
        ctx.stroke();
      } else if (!isSea) {
        ctx.strokeStyle = 'rgba(205, 220, 210, 0.35)';
        ctx.lineWidth = 1.0;
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(14, 116, 144, 0.25)';
        ctx.lineWidth = 0.5;
        ctx.stroke();
      }
    }

    // Pass 2: Overland Trade Routes in 3D perspective
    if (showTradeRoutes && tradeAnim && worldState.trade_network) {
      tradeAnim.drawTradeRoutes(ctx, worldState.trade_network, tileByName, 0, camZoom, (t) => {
        const tz = (Number(t.elevation || 0) * 48.0) + 0.5;
        return projectPoint3D(mvp, t.centroid[0], t.centroid[1], tz, w, h);
      });
    }
    if (showTradeArrows && tradeAnim && worldState.trade_network) {
      tradeAnim.drawTradeFlowParticles(ctx, worldState.trade_network, tileByName, 0, camZoom, performance.now(), (t) => {
        const tz = (Number(t.elevation || 0) * 48.0) + 0.5;
        return projectPoint3D(mvp, t.centroid[0], t.centroid[1], tz, w, h);
      });
    }

    // Pass 3: Information Badges & Glyphs at screen-projected 3D centroids
    for (let i = 0; i < projectedGeom.length; i++) {
      const { tile, cScreen } = projectedGeom[i];
      if (cScreen && cScreen.valid) {
        renderHexBadges(ctx, tile, cScreen.x, cScreen.y, 35.0 * Math.max(0.6, Math.min(camZoom, 1.8)));
      }
    }
  }

  function renderVoronoiMap2D(w, h) {
    ctx.save();
    ctx.translate(camX, camY);
    ctx.scale(camZoom, camZoom);

    // Continuous photorealistic terrain image layer backdrop if enabled
    if (useTerrainImage && worldState) terrainLayer.draw(ctx, worldState.terrain_bounds);

    const minX = -camX / camZoom - 100;
    const maxX = (w - camX) / camZoom + 100;
    const minY = -camY / camZoom - 100;
    const maxY = (h - camY) / camZoom + 100;

    for (let i = 0; i < positionedTiles.length; i++) {
      const { tile, x, y, polygon } = positionedTiles[i];
      if (!polygon || polygon.length < 3) continue;

      const bb = tile._bbox;
      if (bb && (bb.maxX < minX || bb.minX > maxX || bb.maxY < minY || bb.minY > maxY)) {
        continue;
      }

      const isSelected = (selectedTileName && tile.name === selectedTileName);
      const isSea = (tile.is_ocean || (typeof tile.elevation === 'number' && tile.elevation <= 0) || tile.biome === 'ocean');

      // Let the raster show through land cells and open water in overview mode.
      if (useTerrainImage && terrainLayer.loaded && activeLayer === 'overview' && isSea && !isSelected) {
        continue;
      }

      ctx.beginPath();
      ctx.moveTo(polygon[0][0], polygon[0][1]);
      for (let j = 1; j < polygon.length; j++) {
        ctx.lineTo(polygon[j][0], polygon[j][1]);
      }
      ctx.closePath();

      // Use the raster as the base when available; keep vector terrain as fallback.
      if (!useTerrainImage || !terrainLayer.loaded) {
        ctx.fillStyle = getTileColor(tile);
        ctx.fill();
      }

      if (tile.nation_color && !isSea) {
        const baseColor = tile.nation_color.startsWith('#')
          ? hexToRgba(tile.nation_color, 0.25)
          : tile.nation_color.replace('rgb', 'rgba').replace(')', ', 0.25)');
        ctx.fillStyle = baseColor;
        ctx.fill();
      }

      if (activeLayer !== 'overview') {
        const layerFill = getThematicLayerFill(tile);
        if (layerFill) {
          ctx.fillStyle = layerFill;
          ctx.fill();
        }
      }

      if (isSelected) {
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 3.5 / camZoom;
        ctx.stroke();
      } else if (hoveredTileName && tile.name === hoveredTileName) {
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2.5 / camZoom;
        ctx.stroke();
      } else if (tile.nation_color) {
        ctx.strokeStyle = tile.nation_color;
        ctx.lineWidth = 1.8 / camZoom;
        ctx.stroke();
      } else if (!isSea) {
        ctx.strokeStyle = 'rgba(205, 220, 210, 0.4)';
        ctx.lineWidth = 1.0 / camZoom;
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(14, 116, 144, 0.25)';
        ctx.lineWidth = 0.5 / camZoom;
        ctx.stroke();
      }

      renderHexBadges(ctx, tile, x, y, 35.0);
    }

    const tradeAnim = window.CoCTradeAnimator;
    if (showTradeRoutes && tradeAnim && worldState.trade_network) {
      tradeAnim.drawTradeRoutes(ctx, worldState.trade_network, tileByName, 0, camZoom);
    }
    if (showTradeArrows && tradeAnim && worldState.trade_network) {
      tradeAnim.drawTradeFlowParticles(ctx, worldState.trade_network, tileByName, 0, camZoom, performance.now());
    }

    ctx.restore();
  }

  function findVoronoiTileAtPoint(wx, wy) {
    if (!positionedTiles || positionedTiles.length === 0) return null;
    for (let i = 0; i < positionedTiles.length; i++) {
      const item = positionedTiles[i];
      const tile = item.tile;
      if (!tile.polygon) continue;
      const bb = tile._bbox;
      if (bb && (wx < bb.minX || wx > bb.maxX || wy < bb.minY || wy > bb.maxY)) {
        continue;
      }
      if (typeof pointInPolygon === 'function' && pointInPolygon(wx, wy, tile.polygon)) {
        return tile;
      }
    }
    return null;
  }

  function getTileAtScreenPos(screenX, screenY, rect) {
    if (!worldState || !worldState.tiles) return null;
    const w = rect.width;
    const h = rect.height;

    if (isVoronoi()) {
      if (is3DMode) {
        const camObj = { pitch: camPitch, yaw: camYaw, zoom: camZoom, target_x: camTargetX, target_y: camTargetY };
        const mvp = getCameraMVP(camObj, w, h);
        if (mvp && typeof screenToWorldRay === 'function' && typeof intersectRayPlane === 'function') {
          const ray = screenToWorldRay(screenX, screenY, mvp, w, h);
          if (ray) {
            // First check ground plane z=0
            const pt0 = intersectRayPlane(ray.origin, ray.dir, 0.0);
            if (pt0) {
              const hit0 = findVoronoiTileAtPoint(pt0.x, pt0.y);
              if (hit0) return hit0;
            }
            // Check elevated planes (e.g. z=12, z=24, z=36)
            for (const planeZ of [12.0, 24.0, 36.0]) {
              const ptElev = intersectRayPlane(ray.origin, ray.dir, planeZ);
              if (ptElev) {
                const hitElev = findVoronoiTileAtPoint(ptElev.x, ptElev.y);
                if (hitElev) return hitElev;
              }
            }
          }
        }
        return null;
      } else {
        const worldX = (screenX - camX) / camZoom;
        const worldY = (screenY - camY) / camZoom;
        return findVoronoiTileAtPoint(worldX, worldY);
      }
    } else {
      const worldX = (screenX - camX) / camZoom;
      const worldY = (screenY - camY) / camZoom;
      const hexRadius = getHexRadius();
      const axial = pixelToAxial(worldX, worldY, hexRadius);
      return tileByAxial.get(`${axial.q},${axial.r}`) || null;
    }
  }

  function renderMap() {
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.parentElement.clientWidth;
    const h = canvas.parentElement.clientHeight;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    // Deep oceanic background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, w, h);

    if (isVoronoi()) {
      if (is3DMode) {
        renderVoronoiMap3D(w, h);
      } else {
        if (terrainStatus) terrainStatus.classList.add('hidden');
        renderVoronoiMap2D(w, h);
      }
      ctx.restore();
      return;
    }

    ctx.save();
    ctx.translate(camX, camY);
    ctx.scale(camZoom, camZoom);

    // Photorealistic continuous terrain image layer
    if (useTerrainImage && worldState) terrainLayer.draw(ctx, worldState.terrain_bounds);

    // Render hex tiles
    if (worldState && worldState.tiles) {
      const hexRadius = getHexRadius();
      const minX = -camX / camZoom - hexRadius;
      const maxX = (w - camX) / camZoom + hexRadius;
      const minY = -camY / camZoom - hexRadius;
      const maxY = (h - camY) / camZoom + hexRadius;

      positionedTiles.forEach(({ tile, x, y }) => {
        if (x < minX || x > maxX || y < minY || y > maxY) return;
        const isSelected = (selectedTileName && tile.name === selectedTileName);

        // Desktop Client parity: Don't show tiles in the sea in overview mode if terrain image is loaded
        const isSea = (tile.is_ocean || (typeof tile.elevation === 'number' && tile.elevation <= 0) || tile.biome === 'ocean');
        if (isSea && useTerrainImage && terrainLayer.loaded && activeLayer === 'overview' && !isSelected) {
          return;
        }

        // If not using terrain image or terrain not loaded, render procedural vector terrain
        if (!useTerrainImage || !terrainLayer.loaded) {
          drawHexPolygon(ctx, x, y, hexRadius - 0.5);
          ctx.fillStyle = getTileColor(tile);
          ctx.fill();
        } else if (tile.nation_color && !isSea) {
          // Soft semi-transparent nation territory tint matching desktop client
          drawHexPolygon(ctx, x, y, hexRadius - 0.5);
          const baseColor = tile.nation_color.startsWith('#')
            ? hexToRgba(tile.nation_color, 0.20)
            : tile.nation_color.replace('rgb', 'rgba').replace(')', ', 0.20)');
          ctx.fillStyle = baseColor;
          ctx.fill();
        }

        // Active Thematic Layer overlay
        renderThematicLayerOverlay(ctx, tile, x, y, hexRadius);

        // Hex territorial boundary border matching desktop client
        drawHexPolygon(ctx, x, y, hexRadius);
        if (isSelected) {
          ctx.strokeStyle = '#38bdf8';
          ctx.lineWidth = 3.0 / camZoom;
          ctx.stroke();
        } else if (hoveredTileName && tile.name === hoveredTileName) {
          ctx.strokeStyle = '#fbbf24';
          ctx.lineWidth = 2.5 / camZoom;
          ctx.stroke();
        } else if (tile.nation_color) {
          ctx.strokeStyle = tile.nation_color;
          ctx.lineWidth = 1.8 / camZoom;
          ctx.stroke();
        } else {
          ctx.strokeStyle = 'rgba(255, 255, 255, 0.45)';
          ctx.lineWidth = 1.0 / camZoom;
          ctx.stroke();
        }

        // Hex information badges & icons
        renderHexBadges(ctx, tile, x, y, hexRadius);
      });

      // Overland Trade Route Network Lines & Smooth 60fps Flow Particles
      const tradeAnim = window.CoCTradeAnimator;
      if (showTradeRoutes && tradeAnim) {
        tradeAnim.drawTradeRoutes(ctx, worldState.trade_network, tileByName, hexRadius, camZoom);
      }
      if (showTradeArrows && tradeAnim) {
        tradeAnim.drawTradeFlowParticles(ctx, worldState.trade_network, tileByName, hexRadius, camZoom, performance.now());
      }
    }

    ctx.restore();
    ctx.restore();
  }

  function renderHexBadges(ctx, tile, cx, cy, size) {
    if (camZoom < 0.6) return;

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // 1. Terrain Glyphs (Farmland, Forest, Tundra)
    if (camZoom >= 0.75) {
      if (tile.biome === 'farmland' || (tile.ecology && tile.ecology.soil_fertility > 75)) {
        // Gold triangle (fertile farmland)
        ctx.beginPath();
        const gx = cx - size * 0.45;
        const gy = cy - size * 0.35;
        ctx.moveTo(gx, gy - 4);
        ctx.lineTo(gx + 4, gy + 3);
        ctx.lineTo(gx - 4, gy + 3);
        ctx.closePath();
        ctx.fillStyle = '#f59e0b';
        ctx.fill();
      } else if (tile.biome === 'forest') {
        // Green triangle (dense timber)
        ctx.beginPath();
        const gx = cx - size * 0.45;
        const gy = cy - size * 0.35;
        ctx.moveTo(gx, gy - 4);
        ctx.lineTo(gx + 4, gy + 3);
        ctx.lineTo(gx - 4, gy + 3);
        ctx.closePath();
        ctx.fillStyle = '#10b981';
        ctx.fill();
      } else if (tile.biome === 'tundra' || (tile.elevation_meters && tile.elevation_meters > 1800)) {
        // White circle (cold alpine/tundra)
        ctx.beginPath();
        ctx.arc(cx - size * 0.45, cy - size * 0.35, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = '#e2e8f0';
        ctx.fill();
      }
    }

    // 2. Price Arbitrage Rings (Hot / Cold price signals)
    if (showArbitrageRings && tile.market_prices && typeof tile.market_prices.food === 'number') {
      const p = tile.market_prices.food;
      if (p >= 1.25) {
        // Hot price ring (high food scarcity)
        ctx.beginPath();
        ctx.arc(cx, cy, size * 0.75, 0, Math.PI * 2);
        ctx.strokeStyle = '#f97316';
        ctx.lineWidth = 2.0 / camZoom;
        ctx.stroke();
      } else if (p <= 0.85) {
        // Cold price ring (food surplus / cheap exports)
        ctx.beginPath();
        ctx.arc(cx, cy, size * 0.75, 0, Math.PI * 2);
        ctx.strokeStyle = '#38bdf8';
        ctx.lineWidth = 2.0 / camZoom;
        ctx.stroke();
      }
    }

    // 3. Settlement / City Name Label
    if (tile.is_settlement || tile.population > 0) {
      const fontSize = Math.max(10, Math.min(13, Math.round(11 / camZoom)));
      ctx.font = `bold ${fontSize}px -apple-system, sans-serif`;
      ctx.fillStyle = '#ffffff';
      ctx.shadowColor = 'rgba(0, 0, 0, 0.85)';
      ctx.shadowBlur = 4;
      ctx.fillText(tile.display_name || tile.name, cx, cy - size * 0.25);
      ctx.shadowBlur = 0;
    }

    // 4. Badges (Population, Unrest Stage, Wilderness)
    if (tile.wilderness) {
      ctx.font = 'bold 9px -apple-system, sans-serif';
      ctx.fillStyle = '#10b981';
      ctx.fillText('[ W ]', cx, cy);
    } else if (tile.population > 0 && camZoom >= 0.8) {
      const subFont = Math.max(9, Math.min(11, Math.round(10 / camZoom)));
      ctx.font = `${subFont}px -apple-system, sans-serif`;
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(`👥 ${tile.population}`, cx, cy + size * 0.12);

      const u = tile.protest_energy || 0;
      if (u >= 0.3) {
        let tag = '[ U ]';
        let col = '#f59e0b';
        if (u >= 8.5) { tag = '[ T ]'; col = '#a855f7'; }
        else if (u >= 6.5) { tag = '[ C ]'; col = '#84cc16'; }
        else if (u >= 3.5) { tag = '[ M ]'; col = '#ef4444'; }
        else if (u >= 1.5) { tag = '[ P ]'; col = '#f97316'; }

        ctx.font = `bold ${subFont}px -apple-system, sans-serif`;
        ctx.fillStyle = col;
        ctx.fillText(`${tag} ${u.toFixed(1)}`, cx, cy + size * 0.42);
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

    const laborInfo = worldState.scenario_info?.scenario_name === 'Labor, Territory, and Rivalry'
      ? worldState.scenario_info : null;
    const trCash = Math.round(Number(laborInfo?.sovereign_cash ?? macro.treasury_cash ?? 0));
    const trFood = Math.round(macro.treasury_food !== undefined ? macro.treasury_food : (macro.granary_food || 0));
    setVal('val-treasury', `$${trCash.toLocaleString()}`);
    setVal('val-food', trFood.toLocaleString());
    setVal('val-pop', Number(laborInfo?.resident_count ?? macro.population ?? 0).toLocaleString());
    setVal('val-gdp', `$${Math.round(macro.gdp || 0).toLocaleString()}`);
    setVal('val-gini', (macro.gini || 0).toFixed(2));
    setVal('val-trade', `$${Math.round(macro.trade_balance || 0).toLocaleString()}`);
    const isrbYield = macro.bond_yield !== undefined ? `${macro.bond_yield.toFixed(2)}%` : '0.18%';
    setVal('val-col', (macro.cost_of_living || 1.0).toFixed(2));
    setVal('val-isrb', `${macro.credit_rating || 'BBB'} ${isrbYield}`);

    const elUnrest = document.getElementById('val-unrest');
    if (elUnrest) {
      const stage = macro.unrest_stage || 'Calm';
      elUnrest.textContent = `${(macro.unrest_energy || 0).toFixed(1)} ${stage}`;
      elUnrest.className = `macro-val badge-unrest ${safeClassToken(stage.toLowerCase(), 'calm')}`;
    }

    if (btnPlay) {
      isPlaying = Boolean(worldState.playing !== undefined ? worldState.playing : worldState.is_playing);
      btnPlay.textContent = isPlaying ? '⏸ Pause' : '▶ Play';
      btnPlay.className = isPlaying ? 'btn btn-secondary' : 'btn btn-primary';
    }

    // Sovereign Nations Switcher Dropdown with Mobile Abbreviation
    if (selectNation && worldState.nations) {
      const isMobile = window.innerWidth <= 768;
      const expectedCount = worldState.nations.length;
      const currentMode = selectNation.dataset.mode;
      const targetMode = isMobile ? 'mobile' : 'desktop';

      if (selectNation.children.length !== expectedCount || currentMode !== targetMode) {
        selectNation.innerHTML = '';
        selectNation.dataset.mode = targetMode;
        worldState.nations.forEach(nat => {
          const opt = document.createElement('option');
          opt.value = nat.name;
          const abbrev = abbreviateNationName(nat.name);
          opt.textContent = isMobile ? abbrev : `${abbrev} - ${nat.name}`;
          selectNation.appendChild(opt);
        });
      }
      selectNation.value = worldState.player_nation || '';

      const pNat = worldState.nations.find(n => n.name === worldState.player_nation);
      if (pNat && activeFlagDot) {
        activeFlagDot.style.background = safeCssColor(pNat.flag_color);
      }
    }

    if (btnTogglePipeline) {
      btnTogglePipeline.querySelector('.btn-text').textContent = useTerrainImage ? 'Pipeline: Photoreal' : 'Pipeline: Flat';
    }

    // Seasonal Agricultural Clock HUD & Scenario Ribbon
    updateSeasonalClock();
    updateScenarioPressures();

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
        const rows = [
          { label: 'Liquid Cash Vault', val: `$${trCash.toLocaleString()}`, valClass: 'text-gold' }
        ];
        if (trDelta !== 0) {
          rows.push({ label: 'Turn Balance Delta', val: deltaHtml });
        }
        const totalUpkeep = macro.treasury_upkeep || 0;
        if (totalUpkeep > 0) {
          rows.push({ label: 'Per-Turn Upkeep Drain', val: `-$${totalUpkeep.toLocaleString()} / turn`, valClass: 'text-ruby' });
          if ((macro.military_upkeep || 0) > 0) {
            rows.push({ label: '• Armed Forces Wages', val: `-$${(macro.military_upkeep || 0).toLocaleString()} / turn` });
          }
          if ((macro.debt_upkeep || 0) > 0) {
            rows.push({ label: '• Bond Coupon Servicing', val: `-$${(macro.debt_upkeep || 0).toLocaleString()} / turn` });
          }
        }
        if (trFood > 0) {
          rows.push({ label: 'Emergency Granary', val: `${trFood.toLocaleString()} food units`, valClass: 'text-green' });
        }
        if (macro.tax_rate !== undefined && macro.tax_rate > 0.005) {
          rows.push({ label: 'Statutory Income Tax', val: `${((macro.tax_rate || 0.15) * 100).toFixed(1)}%` });
        }
        if (macro.tariff_rate !== undefined && macro.tariff_rate > 0.005) {
          rows.push({ label: 'Customs Tariff Rate', val: `${((macro.tariff_rate || 0.10) * 100).toFixed(1)}%` });
        }
        if ((macro.public_debt || 0) > 0) {
          rows.push({ label: 'Outstanding Public Debt', val: `$${Math.round(macro.public_debt || 0).toLocaleString()}`, valClass: 'text-ruby' });
        }
        if ((macro.garrison || 0) > 0) {
          rows.push({ label: 'Armed Forces Payroll', val: `${macro.garrison || 0} stationed troops` });
        }
        return {
          title: '💰 Sovereign Treasury Vault',
          badge: `${cur} $${trCash.toLocaleString()}`,
          badgeClass: 'text-gold',
          rows,
          footer: 'Adjust statutory taxes in Governance [G] or float public bonds in Debt [S].'
        };
      }

      case 'granary': {
        const foodPrice = Number(macro.cost_of_living || 1.0).toFixed(2);
        const secLevel = trFood > 50 ? 'Secure Surplus' : (trFood > 15 ? 'Marginal Buffer' : 'Critical Depletion');
        const secClass = trFood > 50 ? 'text-green' : (trFood > 15 ? 'text-gold' : 'text-ruby');
        const unrestVal = Number(macro.unrest_energy || 0);
        const rows = [
          { label: 'Emergency Granary Reserve', val: `${trFood.toLocaleString()} units`, valClass: 'text-green' }
        ];
        if (Number(macro.cost_of_living || 0) > 0) {
          rows.push({ label: 'Market Staple Grain Price', val: `$${foodPrice} / unit`, valClass: 'text-gold' });
        }
        rows.push({ label: 'Food Security Status', val: secLevel, valClass: secClass });
        if (unrestVal > 0) {
          rows.push({ label: 'Famine & Starvation Risk', val: unrestVal > 3 ? 'Elevated' : 'Low', valClass: unrestVal > 3 ? 'text-ruby' : 'text-green' });
        }
        rows.push({ label: 'Emergency Bread Relief', val: 'Directly quells popular discontent' });
        return {
          title: '🌾 Crown Granary & Food Security',
          badge: `${trFood.toLocaleString()} Units`,
          badgeClass: 'text-green',
          rows,
          footer: 'Click Governance [G] -> Social Relief to disburse bread from the granary.'
        };
      }

      case 'pop': {
        const popVal = (macro.population || 0).toLocaleString();
        const pDelta = macro.population_delta || 0;
        const deltaHtml = pDelta >= 0
          ? `<span class="delta-pos">+${pDelta}</span>`
          : `<span class="delta-neg">${pDelta}</span>`;
        const rows = [
          { label: 'Total Living Population', val: `${popVal} citizens` }
        ];
        if (pDelta !== 0) {
          rows.push({ label: 'Turn Demographic Delta', val: `${deltaHtml} net / turn` });
        }
        const tilesCnt = macro.tiles_count || (worldState.tiles || []).length;
        if (tilesCnt > 0) {
          rows.push({ label: 'Productive Settlement Tiles', val: `${tilesCnt} regions` });
        }
        if ((macro.garrison || 0) > 0) {
          rows.push({ label: 'Standing Town Garrisons', val: `${macro.garrison || 0} soldiers` });
        }
        if ((macro.standing_armies || 0) > 0) {
          rows.push({ label: 'Field Military Formations', val: `${macro.standing_armies || 0} active regiments` });
        }
        rows.push({ label: 'Primary Class Hierarchy', val: 'Serfs, Tenants, Artisans, Gentry' });
        return {
          title: '👥 Demographics & Living Citizens',
          badge: `${popVal} Pops`,
          badgeClass: 'text-cyan',
          rows,
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
        const rows = [
          { label: 'Aggregate Real GDP Output', val: `$${gdpVal}`, valClass: 'text-cyan' }
        ];
        if (gDelta !== 0) {
          rows.push({ label: 'Turn Economic Delta', val: `${deltaHtml} / turn` });
        }
        if (Number(macro.gdp_per_capita || 0) > 0) {
          rows.push({ label: 'GDP per Capita', val: `$${gdpPc} / citizen`, valClass: 'text-gold' });
        }
        if ((macro.tiles_count || 0) > 0) {
          rows.push({ label: 'Territorial Market Centers', val: `${macro.tiles_count} claimed biomes` });
        }
        rows.push({ label: 'Production Sectors', val: 'Agriculture, Lumber, Furniture, Mining' });
        return {
          title: '📈 Gross Domestic Product (GDP)',
          badge: `$${gdpVal}`,
          badgeClass: 'text-cyan',
          rows,
          footer: 'Commission new mills, mines, and artisan workshops via Build Menu [B].'
        };
      }

      case 'unrest': {
        const unrestVal = Number(macro.unrest_energy || 0).toFixed(2);
        const stage = macro.unrest_stage || 'Calm';
        const uDelta = Number(macro.unrest_delta || 0).toFixed(2);
        const deltaHtml = Number(uDelta) <= 0
          ? `<span class="delta-pos">${uDelta}</span>`
          : `<span class="delta-neg">+${uDelta}</span>`;
        const rows = [
          { label: 'National Protest Energy', val: `${unrestVal} / 10.00`, valClass: Number(unrestVal) > 3 ? 'text-ruby' : 'text-green' }
        ];
        if (Math.abs(Number(uDelta)) >= 0.01) {
          rows.push({ label: 'Turn Protest Delta', val: deltaHtml });
        }
        rows.push({ label: 'Civil Threat Classification', val: stage, valClass: `badge-unrest ${safeClassToken(stage.toLowerCase(), 'calm')}` });
        rows.push({ label: 'Root Grievance Vectors', val: 'Overwork, Enclosure, Hunger, Taxes' });
        if ((macro.garrison || 0) > 0) {
          rows.push({ label: 'Stationed Garrisons', val: `${macro.garrison} soldiers active` });
        }
        rows.push({ label: 'Revolution Threshold', val: 'Riot (6.5) → Insurrection (8.0)' });
        return {
          title: '🔥 Civil Unrest & Popular Protest',
          badge: `Stage: ${stage}`,
          badgeClass: `badge-unrest ${safeClassToken(stage.toLowerCase(), 'calm')}`,
          rows,
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
        const rows = [
          { label: 'Net Commercial Balance', val: `${tbHtml}` }
        ];
        if (tDelta !== 0) {
          rows.push({ label: 'Turn Balance Delta', val: tDeltaHtml });
        }
        if (Math.round(macro.exports || 0) > 0) {
          rows.push({ label: 'Total Foreign Exports', val: `$${Math.round(macro.exports || 0).toLocaleString()}`, valClass: 'text-cyan' });
        }
        if (Math.round(macro.imports || 0) > 0) {
          rows.push({ label: 'Total Foreign Imports', val: `$${Math.round(macro.imports || 0).toLocaleString()}`, valClass: 'text-gold' });
        }
        if (macro.tariff_rate !== undefined && macro.tariff_rate > 0.005) {
          rows.push({ label: 'Statutory Customs Tariff', val: `${((macro.tariff_rate || 0.10) * 100).toFixed(1)}% import duty` });
        }
        return {
          title: '🚢 Foreign Trade & Customs Ledger',
          badge: tb >= 0 ? 'Trade Surplus' : 'Trade Deficit',
          badgeClass: tb >= 0 ? 'text-green' : 'text-ruby',
          rows,
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
        const rows = [
          { label: 'ISRB Sovereign Credit Grade', val: rating, valClass: 'text-gold' },
          { label: 'Benchmark 10Y Bond Yield', val: yld, valClass: 'text-cyan' }
        ];
        if ((macro.public_debt || 0) > 0) {
          rows.push({ label: 'Total Outstanding Debt', val: `$${Math.round(macro.public_debt || 0).toLocaleString()}`, valClass: 'text-ruby' });
        }
        rows.push(
          { label: 'International Market Access', val: ['AAA','AA','A'].includes(rating) ? 'Prime Tier (Low Cost)' : (['BBB','BB'].includes(rating) ? 'Investment Grade' : 'High Risk Speculative') },
          { label: 'Credit Rating Factors', val: 'Debt ratio, real GDP growth, unrest score' }
        );
        return {
          title: '🏛️ ISRB Sovereign Rating Desk',
          badge: `${rating} | ${yld}`,
          badgeClass: 'text-gold',
          rows,
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
          <span>${escapeHtml(data.title)}</span>
        </div>
        <div style="display:flex; align-items:center; gap:6px;">
          <span class="popover-badge ${safeClassToken(data.badgeClass)}">${escapeHtml(data.badge)}</span>
          <button class="popover-close-btn" id="popover-close-btn" aria-label="Close tooltip">&times;</button>
        </div>
      </div>
      <div class="popover-body">
        ${data.rows.map(r => `
          <div class="popover-row">
            <span class="row-label">${escapeHtml(r.label)}</span>
            <span class="row-val ${safeClassToken(r.valClass)}">${escapeHtml(r.val)}</span>
          </div>
        `).join('')}
      </div>
      <div class="popover-footer">
        ${escapeHtml(data.footer)}
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

  // ---------------- Seasonal Agricultural Clock HUD & Popover ----------------

  function updateSeasonalClock() {
    if (!seasonalClock || !worldState) return;
    const season = worldState.seasonal_info || {};
    const iconEl = document.getElementById('seasonal-icon');
    const nameEl = document.getElementById('seasonal-name');
    const yearEl = document.getElementById('seasonal-year');
    const multEl = document.getElementById('seasonal-mult');

    const cycleTurn = season.cycle_turn !== undefined ? season.cycle_turn : ((worldState.turn || 0) % 10);
    const yr = season.year !== undefined ? season.year : Math.floor((worldState.turn || 0) / 10) + 1;
    const sName = season.season_name || 'Spring';
    const sIcon = season.season_icon || '🌱';
    const mult = season.grain_multiplier !== undefined ? season.grain_multiplier : 1.0;
    const multPct = Math.round((mult - 1.0) * 100);
    const multStr = multPct >= 0 ? `+${multPct}%` : `${multPct}%`;

    if (iconEl) iconEl.textContent = sIcon;
    if (nameEl) {
      nameEl.textContent = `${sName} (${cycleTurn + 1}/10)`;
      nameEl.style.color = season.color || '#10b981';
    }
    if (yearEl) yearEl.textContent = `Crop yr ${yr}`;
    if (multEl) {
      multEl.textContent = multStr;
      multEl.className = multPct >= 0 ? 'seasonal-mult text-green' : 'seasonal-mult text-ruby';
    }

    const segments = document.querySelectorAll('.season-seg');
    segments.forEach((seg, idx) => {
      seg.classList.toggle('active', idx === cycleTurn);
      seg.classList.toggle('past', idx < cycleTurn);
    });
  }

  function setupSeasonalClockPopover() {
    if (seasonalClock) {
      seasonalClock.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleSeasonalPopover();
      });
    }

    document.addEventListener('click', (e) => {
      if (seasonalPopover && !seasonalPopover.classList.contains('hidden')) {
        if (!seasonalPopover.contains(e.target) && !seasonalClock.contains(e.target)) {
          hideSeasonalPopover();
        }
      }
    });
  }

  function toggleSeasonalPopover() {
    if (!seasonalPopover) return;
    if (seasonalPopover.classList.contains('hidden')) {
      renderSeasonalPopover();
      seasonalPopover.classList.remove('hidden');
    } else {
      hideSeasonalPopover();
    }
  }

  function hideSeasonalPopover() {
    if (seasonalPopover) seasonalPopover.classList.add('hidden');
  }

  function renderSeasonalPopover() {
    if (!seasonalPopover || !worldState) return;
    const s = worldState.seasonal_info || {};
    const yr = s.year !== undefined ? s.year : Math.floor((worldState.turn || 0) / 10) + 1;
    const mult = s.grain_multiplier !== undefined ? s.grain_multiplier : 1.0;
    const multPct = Math.round((mult - 1.0) * 100);
    const multStr = multPct >= 0 ? `+${multPct}% Crop Yield` : `${multPct}% Crop Yield`;

    seasonalPopover.innerHTML = `
      <div class="popover-header">
        <div class="popover-title-row">
          <span>${s.season_icon || '🌱'} ${escapeHtml(s.season_name || 'Spring')} (Crop year ${yr})</span>
        </div>
        <button class="popover-close-btn" id="seasonal-popover-close">&times;</button>
      </div>
      <div class="popover-body">
        <div class="popover-row">
          <span class="row-label">Agent lifecycle</span>
          <span class="row-val text-dim">1 year per turn; 10 turns per crop cycle</span>
        </div>
        <div class="popover-row">
          <span class="row-label">Bio Agricultural Yield</span>
          <span class="row-val ${multPct >= 0 ? 'text-green' : 'text-ruby'} font-bold">${multStr}</span>
        </div>
        <div class="popover-row">
          <span class="row-label">Climate & Temperature</span>
          <span class="row-val text-dim">${escapeHtml(s.temperature_desc || 'Temperate conditions')}</span>
        </div>
        <div class="popover-row">
          <span class="row-label">Winter Heating Demand</span>
          <span class="row-val text-dim">${escapeHtml(s.heating_demand || 'Baseline timber fuel consumption')}</span>
        </div>
        <div class="popover-row">
          <span class="row-label">Agricultural Labor Mobility</span>
          <span class="row-val text-dim">${escapeHtml(s.labor_impact || 'Standard rural planting workforce')}</span>
        </div>
      </div>
      <div class="popover-footer">
        ${escapeHtml(s.summary || 'Seasonal cycles dictate crop harvests and famine risks across the continent.')}
      </div>
    `;

    const closeBtn = seasonalPopover.querySelector('#seasonal-popover-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        hideSeasonalPopover();
      });
    }

    const rect = seasonalClock.getBoundingClientRect();
    const popW = Math.min(320, window.innerWidth - 20);
    seasonalPopover.style.width = `${popW}px`;
    let left = rect.right - popW;
    if (left < 10) left = 10;
    seasonalPopover.style.left = `${left}px`;
    seasonalPopover.style.top = `${rect.bottom + 8}px`;
  }

  // ---------------- Guided Scenario Priority Pressures Ribbon ----------------

  function updateScenarioPressures() {
    if (!scenarioPressuresRibbon || !worldState) return;
    const sc = worldState.scenario_info;
    if (sc && sc.scenario_name === 'Labor, Territory, and Rivalry') {
      if (!laborMapConfigured) {
        laborMapConfigured = true;
        useTerrainImage = false;
        is3DMode = false;
        if (btnToggle3D) {
          btnToggle3D.textContent = '2D';
          btnToggle3D.classList.remove('active');
        }
        if (btnTogglePipeline) btnTogglePipeline.querySelector('.btn-text').textContent = 'Pipeline: Flat';
        centerCameraOnWorld();
      }
      const previousScroll = scenarioPressuresRibbon.querySelector('.labor-scenario-scroll')?.scrollTop || 0;
      const cards = (sc.pressures || []).map(card => `
        <section class="labor-pressure ${safeClassToken(card.tone || '')}">
          <h4>${escapeHtml(card.title)}</h4>
          <strong>${escapeHtml(card.value)}</strong>
          <p>${escapeHtml(card.cause)}</p>
        </section>`).join('');
      const districts = (sc.districts || []).map(d =>
        `<span class="labor-district" title="${escapeHtml(d.people)} residents, ${escapeHtml(d.commons_rights)} usable commons rights">
          ${escapeHtml(d.name)} · ${escapeHtml(d.owner)} · ${escapeHtml(d.units)} soldiers</span>`).join('');
      const actions = (sc.actions || []).map(action => `
        <button type="button" class="labor-action" data-action="${escapeHtml(action.id)}"
          ${action.enabled ? '' : 'disabled'} title="${escapeHtml(action.enabled ? action.detail : action.reason)}">
          <strong>${escapeHtml(action.label)}</strong>
          <span>${escapeHtml(action.enabled ? action.detail : action.reason)}</span>
        </button>`).join('');
      const timeline = (sc.timeline || []).slice(-3).reverse().map(entry =>
        `<li><span>T${Number(entry.turn) || 0}</span> ${escapeHtml(entry.text || '')}</li>`).join('');
      const debrief = sc.debrief ? `
        <div class="labor-debrief"><h3>${escapeHtml(sc.debrief.title)}</h3>
          <p>${escapeHtml(sc.debrief.summary)}</p><p>${escapeHtml(sc.debrief.people)}</p>
          <p>${escapeHtml(sc.debrief.capacity)}</p><p>${escapeHtml(sc.debrief.commitments)}</p></div>` : '';
      scenarioPressuresRibbon.classList.remove('hidden');
      scenarioPressuresRibbon.classList.add('labor-scenario-ribbon');
      scenarioPressuresRibbon.innerHTML = `
        <div class="labor-scenario-panel" role="region" aria-label="Labor and frontier decisions">
          <button type="button" class="labor-panel-toggle" aria-expanded="${!laborPanelCollapsed}">
            <strong>Labor, Territory, and Rivalry</strong><span>T${Number(sc.turn) || 0}/20 ${laborPanelCollapsed ? '▾' : '▴'}</span>
          </button>
          ${laborPanelCollapsed ? '' : `<div class="labor-scenario-scroll">
            <p class="labor-mandate">${escapeHtml(sc.mandate || '')}</p>
            ${debrief || `${cards}<div class="labor-districts">${districts}</div>
              <h4>One decision this turn</h4><div class="labor-actions">${actions}</div>
              <h4>Recent consequences</h4><ol class="labor-timeline">${timeline}</ol>`}
          </div>`}
        </div>`;
      scenarioPressuresRibbon.querySelector('.labor-panel-toggle')?.addEventListener('click', () => {
        laborPanelCollapsed = !laborPanelCollapsed;
        updateScenarioPressures();
      });
      scenarioPressuresRibbon.querySelectorAll('.labor-action').forEach(button => {
        button.addEventListener('click', () => sendCommand('SCENARIO_ACTION', {
          action_id: button.dataset.action
        }));
      });
      const scroller = scenarioPressuresRibbon.querySelector('.labor-scenario-scroll');
      if (scroller) scroller.scrollTop = previousScroll;
      return;
    }
    scenarioPressuresRibbon.classList.remove('labor-scenario-ribbon');
    laborMapConfigured = false;
    if (!sc || (!sc.pressure_text && !sc.countdown_turns && !sc.pressures)) {
      scenarioPressuresRibbon.classList.add('hidden');
      return;
    }

    const name = sc.scenario_name || 'Grand Campaign';
    const p0 = (sc.pressures && sc.pressures[0]);
    const pressureDesc = sc.pressure_text || (p0 ? (typeof p0 === 'string' ? p0 : `${p0.title || 'Directive'}: ${p0.value || ''}`) : '') || sc.description || '';
    const countdown = sc.countdown_turns !== undefined && sc.countdown_turns !== null
      ? `<span class="countdown-pill">${sc.countdown_turns} turns left</span>`
      : '';

    scenarioPressuresRibbon.innerHTML = `
      <span class="pressure-badge">🎯 ${escapeHtml(name)}</span>
      <span class="pressure-text">${escapeHtml(pressureDesc)}</span>
      ${countdown}
    `;
    scenarioPressuresRibbon.classList.remove('hidden');

    if (sc.objective_met && scenarioBookendModal && scenarioBookendModal.classList.contains('hidden') && !scenarioBookendModal.dataset.dismissed) {
      openScenarioBookend(sc);
    }
  }

  function openScenarioBookend(sc) {
    if (!scenarioBookendModal) return;
    const titleEl = document.getElementById('scenario-bookend-title');
    const bodyEl = document.getElementById('scenario-bookend-body');
    if (titleEl) titleEl.textContent = `🏆 ${sc.scenario_name || 'Scenario'} Debrief & Victory Chronicle`;
    if (bodyEl) {
      bodyEl.innerHTML = `
        <div class="gov-card">
          <h4 class="card-title text-green">Campaign Objective Fulfilled!</h4>
          <p class="card-desc mt-2">${escapeHtml(sc.debrief_text || 'Your sovereign policies have successfully stabilized the realm and met the strategic directives of the era.')}</p>
          <div class="dual-btn-row mt-3">
            <button class="btn btn-primary" id="btn-bookend-continue">Continue In Free Play</button>
          </div>
        </div>
      `;
      const btnCont = document.getElementById('btn-bookend-continue');
      if (btnCont) {
        btnCont.addEventListener('click', () => {
          scenarioBookendModal.classList.add('hidden');
          scenarioBookendModal.dataset.dismissed = 'true';
        });
      }
    }
    scenarioBookendModal.classList.remove('hidden');
  }

  // ---------------- Live Hex Hover Inspector Card ----------------

  function updateHexHoverCard(tile, clientX, clientY) {
    if (!hexHoverCard || !tile) return;

    const nat = tile.nation || 'Unclaimed Frontier';
    const elev = tile.elevation_meters !== undefined ? `${tile.elevation_meters}m` : '0m';
    const biome = tile.biome || 'Grassland';
    const pop = tile.population !== undefined ? tile.population.toLocaleString() : '0';
    const gdp = tile.gdp !== undefined ? `$${Math.round(tile.gdp).toLocaleString()}` : '$0';
    const unrest = tile.unrest_stage || 'Calm';
    const unrestEnergy = tile.protest_energy !== undefined ? Number(tile.protest_energy).toFixed(1) : '0.0';
    const foodPrice = tile.market_prices && typeof tile.market_prices.food === 'number'
      ? `$${tile.market_prices.food.toFixed(2)}`
      : '$1.00';
    let foodStatus = '';
    if (tile.market_prices && typeof tile.market_prices.food === 'number') {
      if (tile.market_prices.food >= 1.25) foodStatus = ' <span class="text-ruby font-bold">[Hot Scarcity]</span>';
      else if (tile.market_prices.food <= 0.85) foodStatus = ' <span class="text-cyan font-bold">[Cold Surplus]</span>';
    }
    const bCount = tile.buildings_count || (tile.buildings && tile.buildings.length) || 0;
    const garrison = tile.garrison || 0;

    hexHoverCard.innerHTML = `
      <div class="hover-card-header">
        <strong style="color: ${safeCssColor(tile.nation_color) || '#38bdf8'}">${escapeHtml(tile.display_name || tile.name)}</strong>
        <span class="text-dim text-xs">${escapeHtml(nat)}</span>
      </div>
      <div class="hover-card-body">
        <div class="hover-row"><span>Terrain / Elev:</span><strong>${escapeHtml(biome)} (${elev})</strong></div>
        <div class="hover-row"><span>Population / GDP:</span><strong>${pop} • ${gdp}</strong></div>
        <div class="hover-row"><span>Grain Market Price:</span><strong>${foodPrice}${foodStatus}</strong></div>
        <div class="hover-row"><span>Civil Unrest:</span><strong class="${unrest.toLowerCase() === 'calm' ? 'text-green' : 'text-ruby'}">${unrestEnergy} (${escapeHtml(unrest)})</strong></div>
        <div class="hover-row"><span>Buildings / Troops:</span><strong>${bCount} built • ${garrison} soldiers</strong></div>
      </div>
    `;

    hexHoverCard.classList.remove('hidden');

    const cardW = 240;
    const cardH = 140;
    let posX = clientX + 16;
    let posY = clientY + 16;

    if (posX + cardW > window.innerWidth - 10) {
      posX = clientX - cardW - 16;
    }
    if (posY + cardH > window.innerHeight - 10) {
      posY = clientY - cardH - 16;
    }
    hexHoverCard.style.left = `${Math.max(10, posX)}px`;
    hexHoverCard.style.top = `${Math.max(10, posY)}px`;
  }

  function hideHexHoverCard() {
    if (hexHoverCard) hexHoverCard.classList.add('hidden');
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

    // Suite 7: Progress Suite Mode Filter Chips
    document.querySelectorAll('#pane-progress .tier-filter-chips .chip').forEach(chip => {
      chip.addEventListener('click', () => {
        document.querySelectorAll('#pane-progress .tier-filter-chips .chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');
        activeProgressMode = chip.dataset.progressMode || 'active';
        renderProgressSuite();
      });
    });
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
      military: '⚔️ Military Operations',
      progress: '⏱️ Progress & Infrastructure Lifecycle'
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
    } else if (activeLeftDrawer === 'progress') {
      renderProgressSuite();
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

    const laborLawSelect = document.getElementById('labor-law-select');
    const sendLaborLawAction = action => {
      if (!selectedTileName || !laborLawSelect) return;
      sendCommand('LABOR_LAW_ACTION', { tile: selectedTileName,
        law: laborLawSelect.value, action });
    };
    document.getElementById('btn-labor-law-enact')?.addEventListener('click', () => sendLaborLawAction('enact'));
    document.getElementById('btn-labor-law-repeal')?.addEventListener('click', () => sendLaborLawAction('repeal'));

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
    const recipesKey = `${activeBuildCat}:${activeBuildTier}:${JSON.stringify(worldState.build_recipes)}`;
    if (recipesKey === lastRecipesKey) return;
    lastRecipesKey = recipesKey;
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
          <span class="card-title">🏛️ ${escapeHtml(recipe.name)}</span>
          <span class="card-badge ${safeClassToken(recipe.status, 'unlocked')}">${escapeHtml(recipe.tier || 'Tier 1')}</span>
        </div>
        <div class="card-desc">${escapeHtml(recipe.description || 'Public works infrastructure blueprint.')}</div>
        <div class="card-meta-row">
          <span>Cost: <strong class="text-gold">$${Number(recipe.cost) || 100}</strong></span>
          <span>Time: ${Number(recipe.turns) || 3} turns</span>
        </div>
        <button class="btn btn-primary btn-sm mt-2 btn-construct" data-recipe="${escapeHtml(recipe.id || recipe.name)}">
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
          <span class="card-title">⏳ ${escapeHtml(p.recipe_name || 'Construction')}</span>
          <span class="text-xs text-dim">${Number(p.progress_turns) || 1} / ${Number(p.total_turns) || 3} turns</span>
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
          <h4 class="card-title" style="color:${safeCssColor(activeNat.flag_color)}">👑 ${escapeHtml(activeNat.name)}</h4>
            <span class="card-badge mastered">${escapeHtml(activeNat.regime_type || 'Empire')}</span>
          </div>
          <div class="stat-row mt-2">
            <span>Bilateral Relations Score:</span>
            <strong class="text-gold">${Number(activeNat.relations) || 0} / 100</strong>
          </div>
          <div class="stat-row">
            <span>Diplomatic Standing:</span>
            <strong class="text-green">${escapeHtml(activeNat.treaty_status || 'Peace')}</strong>
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
              <span class="card-title">📜 Tranche #${escapeHtml(b.tranche_id || '1')}</span>
              <span class="text-gold">$${Math.round(Number(b.principal) || 0).toLocaleString()}</span>
            </div>
            <div class="card-meta-row">
              <span>Coupon: ${(Number(b.coupon_rate) * 100).toFixed(2)}%</span>
              <span>Matures: T+${Number(b.turns_remaining) || 0}</span>
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
          <span class="card-title">👑 ${escapeHtml(fb.seller_nation)} Bond</span>
              <span class="card-badge mastered">${escapeHtml(fb.credit_rating || 'A')}</span>
            </div>
            <div class="card-meta-row">
              <span>Amount: <strong class="text-gold">$${Number(fb.amount) || 0}</strong></span>
              <span>Yield: ${(Number(fb.yield) * 100).toFixed(2)}%</span>
            </div>
            <button class="btn btn-primary btn-sm mt-2 btn-buy-foreign" data-seller="${escapeHtml(fb.seller_nation)}" data-amt="${Number(fb.amount) || 0}">
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
        chip.innerHTML = `⛏️ <strong>${escapeHtml(res.name)}</strong>: ${Number(res.amount) || 0}`;
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
          <span class="card-title">🔬 ${escapeHtml(tech.name)}</span>
          <span class="card-badge ${safeClassToken(tech.status ? tech.status.toLowerCase() : 'locked', 'locked')}">${escapeHtml(tech.status || 'LOCKED')}</span>
        </div>
        <div class="card-desc">${escapeHtml(tech.description || 'Scientific discovery expanding industrial production.')}</div>
        <div class="card-meta-row">
          <span>Prerequisites: ${escapeHtml(tech.prereqs ? tech.prereqs.join(', ') : 'None')}</span>
          <span>Diffusing: ${Math.round((tech.diffusion || 0) * 100)}%</span>
        </div>
        ${!isMastered ? `
          <button class="btn btn-secondary btn-sm mt-2 btn-pledge-prize" data-tech="${escapeHtml(tech.id)}">
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
          <span class="card-title">⚔️ ${escapeHtml(arm.name || arm.regiment_id)}</span>
              <span class="card-badge mastered">XP ${Number(arm.veteran_xp) || 1}</span>
            </div>
            <div class="card-meta-row">
              <span>Soldiers: <strong>${Number(arm.soldiers) || 0}</strong></span>
              <span>Morale: ${Math.round((Number(arm.morale) || 1) * 100)}%</span>
              <span>Combat: ${Number(arm.combat_power) || 100}</span>
            </div>
          `;
          aList.appendChild(c);
        });
      }
    }
  }

  // ---------------- Suite 7: Progress & Development Suite ----------------

  function renderProgressSuite() {
    const container = document.getElementById('progress-items-container');
    const warningBadge = document.getElementById('stalled-warning-badge');
    if (!container || !worldState) return;

    const suite = worldState.progress_suite || {};
    const playerNat = worldState.player_nation;
    const isAll = (activeProgressMode === 'all');

    const constructions = isAll ? (suite.all_constructions || []) : (suite.active_constructions || []);
    const stalledList = suite.stalled_constructions || [];

    if (warningBadge) {
      if (stalledList.length > 0) {
        warningBadge.textContent = `⚠️ ${stalledList.length} Stalled`;
        warningBadge.classList.remove('hidden');
      } else {
        warningBadge.classList.add('hidden');
      }
    }

    container.innerHTML = '';

    // 1. Capital Works & Infrastructure Constructions
    const constrHeading = document.createElement('h4');
    constrHeading.className = 'sub-heading';
    constrHeading.textContent = `🏗️ Capital Works & Municipal Infrastructure (${constructions.length})`;
    container.appendChild(constrHeading);

    if (constructions.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'empty-state';
      empty.textContent = isAll
        ? 'No active infrastructure construction underway across the continent.'
        : `No active construction projects in ${playerNat}. Queue new projects in Build & Infrastructure [B].`;
      container.appendChild(empty);
    } else {
      constructions.forEach(p => {
        const card = document.createElement('div');
        card.className = `item-card ${p.is_stalled ? 'border-ruby' : ''}`;
        const pct = p.progress_pct !== undefined ? p.progress_pct : Math.round(((p.turns_left ? p.total_turns - p.turns_left : 1) / (p.total_turns || 3)) * 100);

        card.innerHTML = `
          <div class="card-top">
            <span class="card-title">${p.is_stalled ? '🚨' : '⏳'} ${escapeHtml(p.recipe_name || p.project_name || 'Project')}</span>
            <span class="text-xs ${p.is_stalled ? 'text-ruby font-bold' : 'text-dim'}">
              ${p.is_stalled ? 'CONTRACTOR STALLED' : `${p.turns_left || 1}t remaining`}
            </span>
          </div>
          <div class="stat-row text-xs mt-1">
            <span>Location: <strong>${escapeHtml(p.tile || '—')}</strong></span>
            <span>Contractor: <strong>${escapeHtml(p.contractor_name || 'Private Guild')}</strong></span>
          </div>
          <div class="stat-row text-xs">
            <span>Contractor Liquidity: <strong class="${(p.contractor_cash || 0) < 20 ? 'text-ruby' : 'text-gold'}">$${Math.round(p.contractor_cash || 0)}</strong></span>
            <span>Est. Cost: <strong>$${Math.round(p.contractor_cost || 100)}</strong></span>
          </div>
          <div class="progress-gauge-container mt-2">
            <div class="progress-gauge-fill ${p.is_stalled ? 'bg-ruby' : ''}" style="width: ${Math.min(100, Math.max(5, pct))}%"></div>
          </div>
          ${p.is_stalled ? `
            <div class="mt-2">
              <button class="btn btn-secondary btn-sm btn-block btn-subsidize-contractor" data-tile="${escapeHtml(p.tile)}" data-proj="${escapeHtml(p.project_name || p.recipe_name)}">
                🚨 Grant Contractor Overrun Subsidy ($100)
              </button>
            </div>
          ` : ''}
        `;
        container.appendChild(card);
      });

      // Hook emergency subsidy buttons
      container.querySelectorAll('.btn-subsidize-contractor').forEach(btn => {
        btn.addEventListener('click', () => {
          const tile = btn.dataset.tile;
          const proj = btn.dataset.proj;
          sendCommand('EMERGENCY_OVERRUN_SUBSIDY', { tile, project_name: proj });
        });
      });
    }

    // 2. Science & Academic Research In-Progress
    const techHeading = document.createElement('h4');
    techHeading.className = 'sub-heading mt-3';
    techHeading.textContent = '🔬 Academic Research In-Progress';
    container.appendChild(techHeading);

    const res = suite.research;
    if (res && res.active_tech) {
      const resCard = document.createElement('div');
      resCard.className = 'item-card';
      const resPct = res.total > 0 ? Math.round((res.progress / res.total) * 100) : 0;
      resCard.innerHTML = `
        <div class="card-top">
          <span class="card-title">💡 ${escapeHtml(res.active_tech)}</span>
          <span class="text-xs text-dim">${res.eta_turns ? `${res.eta_turns}t remaining` : `${resPct}%`}</span>
        </div>
        <div class="stat-row text-xs mt-1">
          <span>Era: <strong>Era ${res.era || 1}</strong></span>
          <span>Points Invested: <strong>${res.progress} / ${res.total}</strong></span>
        </div>
        <div class="progress-gauge-container mt-2">
          <div class="progress-gauge-fill bg-cyan" style="width: ${Math.min(100, Math.max(5, resPct))}%"></div>
        </div>
      `;
      container.appendChild(resCard);
    } else {
      const emptyRes = document.createElement('div');
      emptyRes.className = 'empty-state';
      emptyRes.textContent = 'No academic research currently active. Select a discipline in Science & Tech [T].';
      container.appendChild(emptyRes);
    }

    // 3. Active Legislative Statutes & Decrees
    const legHeading = document.createElement('h4');
    legHeading.className = 'sub-heading mt-3';
    legHeading.textContent = '📜 Enacted Statutes & Historical Decrees';
    container.appendChild(legHeading);

    const legislation = suite.legislation || [];
    if (legislation.length === 0) {
      const emptyLeg = document.createElement('div');
      emptyLeg.className = 'empty-state';
      emptyLeg.textContent = 'No permanent imperial legislation on record.';
      container.appendChild(emptyLeg);
    } else {
      legislation.forEach(leg => {
        const legCard = document.createElement('div');
        legCard.className = 'item-card';
        legCard.innerHTML = `
          <div class="card-top">
            <span class="card-title">⚖️ ${escapeHtml(leg.title)}</span>
            <span class="card-badge mastered">${escapeHtml(leg.status || 'Active')}</span>
          </div>
          <div class="text-xs text-dim mt-1">
            In force for ${leg.turns_active || 1} turns across all provinces.
          </div>
        `;
        container.appendChild(legCard);
      });
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
        if (selectedTileDetail) updateTileInspectionUI(selectedTileDetail, true);
      });
    }
    if (bDown) {
      bDown.addEventListener('click', () => {
        cadastreScrollOffset += 5;
        if (selectedTileDetail) updateTileInspectionUI(selectedTileDetail, true);
      });
    }

    populateChartChips();
  }

  function populateChartChips() {
    const container = document.getElementById('chart-chips-container');
    if (!container) return;
    container.innerHTML = '';

    const charts = window.CoCCharts;
    const chartCatalog = charts.getChartCatalog();

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

    let values = [];
    if (selectedTileDetail && selectedTileDetail.charts) {
      const mode = selectedTileDetail.charts[activeChartMode];
      if (mode && mode[activeChartMetric]) values = mode[activeChartMetric];
    }
    if (values.length === 0 && worldState.history) {
      values = worldState.history[activeChartMetric] || [];
    }

    const charts = window.CoCCharts;
    const legend = charts.drawHistoricalChart(
      chartCanvas, values, activeChartMetric, window.devicePixelRatio || 1
    );
    const legendText = document.getElementById('chart-legend-text');
    if (legendText) legendText.textContent = legend;
  }

  // ---------------- Tile Deep Inspection & Cadastre ----------------

  function updateTileInspectionUI(tile, force = false) {
    if (!tile) return;
    const detailKey = JSON.stringify(tile);
    if (!force && detailKey === lastTileDetailKey) return;
    lastTileDetailKey = detailKey;
    if (tile.charts) selectedTileDetail = tile;

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
      const previousDetail = document.getElementById('market-price-trace-detail');
      if (previousDetail) previousDetail.remove();
      Object.entries(tile.market_prices).forEach(([g, price]) => {
        const item = document.createElement('div');
        item.className = 'price-item';
        item.innerHTML = `<div class="p-name">${escapeHtml(g)}</div><div class="p-val">$${Number(price).toFixed(2)}</div><button type="button" class="btn btn-secondary btn-xs">Why?</button>`;
        item.querySelector('button').addEventListener('click', () => {
          const detail = document.createElement('div');
          detail.id = 'market-price-trace-detail';
          detail.className = 'card';
          detail.innerHTML = `<h4>${escapeHtml(g)} price history</h4><label>Turn <input type="number" min="1" max="${Number(worldState.turn || 1)}" value="${Number(worldState.turn || 1)}" style="width:5rem"></label> <label>Price <select><option value="goods.price">Reference</option><option value="goods.seller_ask">Seller asks</option><option value="goods.delivered_quote">Delivered quotes</option><option value="goods.transaction_price">Paid</option><option value="goods.transaction_vwap">Paid average</option></select></label> <button type="button" class="btn btn-secondary btn-xs">Show price history</button><div class="price-trace-result" aria-live="polite"></div>`;
          const old = document.getElementById(detail.id);
          if (old) old.remove();
          pricesGrid.parentElement.appendChild(detail);
          const turnInput = detail.querySelector('input');
          const priceKind = detail.querySelector('select');
          const output = detail.querySelector('.price-trace-result');
          const load = async () => {
            const turn = Number(turnInput.value);
            if (!Number.isInteger(turn) || turn < 1 || turn > Number(worldState.turn || 0)) {
              output.textContent = 'Choose a completed turn.';
              return;
            }
            output.textContent = 'Loading price records…';
            try {
              const params = new URLSearchParams({turn: String(turn), entity: `tile:${tile.name}`,
                good: g, metric: priceKind.value, limit: '200'});
              const response = await fetch(`/api/trace?${params}`);
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              const result = await response.json();
              const rows = result.events || [];
              const bridge = priceKind.value === 'goods.price'
                ? rows.find(row => row.kind === 'price_bridge') : null;
              const writes = priceKind.value === 'goods.price'
                ? rows.filter(row => row.record_class === 'calculation')
                : rows.filter(row => row.kind !== 'metric_snapshot');
              output.innerHTML = '';
              if (bridge) {
                const line = document.createElement('p');
                const oldValue = bridge.value_before == null ? 'unknown' : Number(bridge.value_before).toFixed(3);
                const newValue = Number(bridge.value_after).toFixed(3);
                const pct = bridge.inputs && bridge.inputs.percent_change;
                line.textContent = `${oldValue} → ${newValue} ${bridge.unit || 'per unit'}; ${pct == null ? 'percent change unavailable' : pct.toFixed(1) + '%'} · ${bridge.explanation_status}`;
                output.appendChild(line);
              }
              if (!writes.length) {
                const line = document.createElement('p');
                line.textContent = priceKind.value === 'goods.price'
                  ? 'No reference-price update was recorded for this good in this turn.'
                  : 'No quotes or purchases of this kind were recorded in this turn.';
                output.appendChild(line);
              }
              for (const row of writes) {
                const line = document.createElement('p');
                const i = row.inputs || {};
                const terms = priceKind.value !== 'goods.price'
                  ? Object.entries(i).filter(([key]) => ['wage', 'cotton_cost', 'productive_slots', 'freight', 'quantity', 'buyer_cash', 'affordable'].includes(key)).map(([key, value]) => `${key} ${value}`).join(', ')
                  : row.kind === 'market_price_update'
                  ? `bids ${i.bids ?? '?'}, local asks ${i.local_asks ?? '?'}, imported asks ${i.imported_asks ?? '?'}, inventory ${i.average_producer_inventory ?? '?'}, recent sample mean ${i.recent_sample_mean ?? 'none'}, cost floor ${i.input_cost_floor ?? '?'}`
                  : row.kind === 'market_price_decay' ? `no orders; decay factor ${i.decay_factor}, cost floor ${i.input_cost_floor}`
                  : `demand ratio ${i.demand_ratio ?? '?'}; floor ${row.constraints?.min_price_floor ?? '?'}`;
                const valueText = row.value_before == null
                  ? `${Number(row.value_after).toFixed(3)}`
                  : `${Number(row.value_before).toFixed(3)} → ${Number(row.value_after).toFixed(3)}`;
                const replay = row.formula_replay
                  ? (row.formula_replay.matches ? 'formula verified' : 'formula mismatch')
                  : 'formula verification unavailable';
                line.textContent = `${row.kind}: ${valueText}. ${terms}. ${replay}. ${row.event_id}`;
                output.appendChild(line);
              }
              if (result.total > rows.length) {
                const line = document.createElement('p');
                line.textContent = `${result.total - rows.length} further records exist; use the trace download for the full history.`;
                output.appendChild(line);
              }
            } catch (error) { output.textContent = `Could not load price records: ${error.message}`; }
          };
          detail.querySelector('button').addEventListener('click', load);
          load();
        });
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
                <span class="card-title">📜 Parcel #${Number(p.plot_id) || 0}</span>
                <span class="card-badge ${p.tenure === 'enclosed' ? 'mastered' : 'locked'}">${escapeHtml(p.tenure)}</span>
              </div>
              <div class="card-meta-row">
                <span>Land Use: <strong>${escapeHtml(p.production_type || 'arable')}</strong></span>
                <span>Area: ${Math.round(p.fraction * 100)}%</span>
                <span>Tenants: ${Number(p.bound_tenants) || 0}</span>
              </div>
              ${p.foreclosure_debt ? `
                <div class="card-badge locked mt-1">⚠️ Foreclosure Debt: $${Number(p.foreclosure_debt) || 0} (Due: T+${Number(p.foreclosure_deadline) || 0})</div>
              ` : ''}
              <div class="dual-btn-row mt-2">
                ${p.tenure !== 'enclosed' ? `
                  <button class="btn btn-primary btn-xs btn-act-enclose" data-plot="${Number(p.plot_id) || 0}">Enclose ($50)</button>
                ` : `
                  <button class="btn btn-secondary btn-xs btn-act-restore" data-plot="${Number(p.plot_id) || 0}">Restore Commons</button>
                `}
                <button class="btn btn-secondary btn-xs btn-act-toggle-use" data-plot="${Number(p.plot_id) || 0}" data-type="${p.production_type === 'pasture' ? 'arable' : 'pasture'}">
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
            <span class="citizen-role">${escapeHtml(c.career)}</span>
            <span class="text-dim"> (Age ${Number(c.age) || 0})</span>
          </div>
          <div class="citizen-info">
            Cash: <strong class="text-gold">$${Number(c.cash) || 0}</strong> • ${escapeHtml(c.labor_regime || 'unemployed')} • Access ${Math.round((Number(c.usable_food_access) || 0) * 100)}%
          </div>
        `;
        citList.appendChild(row);
      });
    }

    // Labor & Alienation Breakdown
    const collective = tile.collective_action || {};
    const orgList = document.getElementById('collective-organization-list');
    if (orgList) {
      const orgs = collective.organizations || [];
      const politics = collective.politics || {};
      const politicalLine = politics.colonial_authority
        ? `<div class="citizen-info">Constitutional coalition: ${Number(politics.covered_residents) || 0}/${Number(politics.eligible_residents) || 0} residents · Agenda strength ${Number(politics.mobilization_index) || 0} (index, not odds of independence)</div>`
        : '';
      orgList.innerHTML = (orgs.length ? orgs.map(org => {
        const strike = org.latest_strike || {};
        const details = strike.id
          ? `<div class="citizen-info text-dim">Latest ${escapeHtml(strike.status)}: ${Number(strike.participants) || 0}/${Number(strike.eligible) || 0} workers · demanded $${Number(strike.target_wage).toFixed(2)} and ${Number(strike.target_hours).toFixed(1)} hours${strike.review_turn ? ` · review T${Number(strike.review_turn)}` : ''}${strike.victory !== null && strike.victory !== undefined ? ` · delivered ${Math.round(Number(strike.victory) * 100)}%` : ''}</div>`
          : '';
        return `<div class="citizen-info"><strong>${escapeHtml(org.firm_name)}</strong> · ${Number(org.members) || 0} members
          · Organization ${Math.round((Number(org.organization) || 0) * 100)}%
          · Confidence ${Math.round((Number(org.confidence) || 0) * 100)}%
          ${org.active_strike_id ? '· Strike active' : ''}</div>${details}`;
      }).join('')
        : '<span class="text-dim">No corporation has organized here.</span>') + politicalLine;
    }
    const eventList = document.getElementById('collective-event-list');
    if (eventList) {
      const events = (collective.events || []).slice(-8).reverse();
      eventList.innerHTML = events.length ? events.map(ev => `
        <div class="citizen-info">T${Number(ev.turn) || 0} · ${escapeHtml(ev.firm_name)} · ${escapeHtml(ev.message || ev.kind)}</div>`).join('')
        : '<span class="text-dim">No collective action recorded.</span>';
    }
    const wList = document.getElementById('workers-labor-list');
    if (wList && tile.citizens) {
      wList.innerHTML = '';
      const institution = tile.labor_institutions || {};
      const counts = institution.counts || {};
      const countEl = document.getElementById('labor-regime-counts');
      if (countEl) countEl.innerHTML = `Subsistence ${Number(counts.subsistence) || 0} · Tenants/sharecroppers ${Number(counts.tenant_sharecropper) || 0} · Wage workers ${Number(counts.wage) || 0} · Unemployed ${Number(counts.unemployed) || 0} · Compulsory ${Number(counts.compulsory) || 0}`;
      const lawsEl = document.getElementById('labor-law-status');
      if (lawsEl) {
        const laws = institution.laws || {};
        const lawNames = { vagrancy: 'Vagrancy', gathering_restriction: 'Gathering restriction', quit_penalty: 'Quit penalty', wage_cap: 'Wage cap' };
        const activeLaws = Object.entries(laws).filter(([, status]) => status === 'enacted')
          .map(([law]) => lawNames[law] || law);
        lawsEl.innerHTML = `<span>Enacted laws:</span> <strong>${activeLaws.length ? activeLaws.map(escapeHtml).join(', ') : 'None'}</strong> <span class="text-dim">· ${Number(institution.affected_households) || 0} households with active claims · Enforcement $${Number(institution.enforcement_costs) || 0}</span>`;
      }
      const casesEl = document.getElementById('labor-enforcement-cases');
      if (casesEl) {
        const cases = institution.cases || [];
        casesEl.innerHTML = cases.length
          ? `<div class="sub-heading">Recent enforcement cases</div>${cases.slice(-5).map(c => `<div class="citizen-info">Case ${Number(c.id)} · ${escapeHtml(c.kind)} · Person ${escapeHtml(c.target_person_id)} · ${escapeHtml(c.state)}${c.outcome ? ` — ${escapeHtml(c.outcome)}` : ''}</div>`).join('')}`
          : '<div class="citizen-info text-dim">No enforcement cases recorded.</div>';
      }
      tile.citizens.slice(0, 10).forEach(c => {
        const row = document.createElement('div');
        row.className = 'citizen-row';
        const obligations = (c.obligations || []).map(o => {
          const creditor = tile.citizens.find(x => String(x.id) === String(o.creditor_id));
          const creditorName = creditor ? creditor.career : `Agent ${o.creditor_id}`;
          return `${escapeHtml(o.origin)} $${Number(o.balance).toFixed(2)} owed to ${escapeHtml(creditorName)}${Number(o.due_turn) <= Number(worldState?.turn) ? ' (due)' : ` (due turn ${Number(o.due_turn)})`}`;
        });
        const history = (c.timeline || []).slice(-3).map(e => {
          const turn = Number(e.turn ?? e.t) || 0;
          const kind = e.event || e.cause || e.origin || (e.paid !== undefined ? 'payment' : 'change');
          const detail = e.paid !== undefined ? `paid $${Number(e.paid).toFixed(2)}`
            : e.amount !== undefined ? `$${Number(e.amount).toFixed(2)}`
            : e.quantity !== undefined ? `${Number(e.quantity)} ${escapeHtml(e.good || 'units')}`
            : e.after !== undefined ? `access ${Math.round(Number(e.before || 0) * 100)}% → ${Math.round(Number(e.after || 0) * 100)}%`
            : '';
          return `T${turn} ${escapeHtml(kind)}${detail ? `: ${detail}` : ''}`;
        });
        const latestOffer = c.recent_reasons?.slice(-1)[0];
        row.innerHTML = `
          <div>
            <span class="citizen-role">${escapeHtml(c.career)} · ${escapeHtml(c.labor_regime || 'unemployed')}</span>
            <span class="text-dim">${Number(c.labor_hours) || 0}h at pace ${Number(c.labor_pace) || 1} • ${escapeHtml(c.ability_to_quit || 'lawful exit')}</span>
          </div>
          <div class="citizen-info">
            Food access legal/usable: ${Math.round((Number(c.legal_food_access) || 0) * 100)}% / ${Math.round((Number(c.usable_food_access) || 0) * 100)}% • Realized pay: <strong class="text-gold">$${Number(c.real_wage_after_deductions) || 0}</strong> • Cash due: $${Number(c.cash_due) || 0} • Fatigue ${Number(c.work_fatigue) || 0}
            <div>${obligations.length ? obligations.join('<br>') : '<span class="text-dim">No named cash claims</span>'}</div>
            <div>${latestOffer ? `Latest offer: ${latestOffer.accepted ? 'accepted' : 'rejected'} — ${escapeHtml(latestOffer.reason)} ($${Number(latestOffer.offer).toFixed(2)} offered / $${Number(latestOffer.reservation).toFixed(2)} reservation)` : 'No recent job offer recorded'}</div>
            <div>${history.length ? history.join(' · ') : '<span class="text-dim">No recent institutional events</span>'}</div>
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
      const newsKey = JSON.stringify(worldState.ticker_events);
      if (newsKey !== lastNewsKey) {
        lastNewsKey = newsKey;
        feed.innerHTML = '';
        if (badge) badge.textContent = worldState.ticker_events.length;
        worldState.ticker_events.slice(-30).reverse().forEach(ev => {
          const item = document.createElement('div');
          item.className = `news-item ${safeClassToken(ev.kind)}`;
          item.innerHTML = `<strong>[T${Number(ev.t) || 0}] ${escapeHtml(ev.kind)}:</strong> ${escapeHtml(ev.text)}`;
          feed.appendChild(item);
        });
      }
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
            <th>Food access</th>
            <th>GDP ($)</th>
            <th>Unrest</th>
            <th>ISRB Rating</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          ${data.map(n => {
            const isPlayer = (n.name === worldState.player_nation || n.nation === worldState.player_nation);
            const tDelta = n.treasury_delta == null ? '—' : (n.treasury_delta >= 0) ? `<span class="delta-pos">+${Math.round(n.treasury_delta)}</span>` : `<span class="delta-neg">${Math.round(n.treasury_delta)}</span>`;
            let actionBtn = '—';
            if (isCountry && !isPlayer) {
              actionBtn = `<button class="btn btn-secondary btn-xs btn-switch-nat" data-nat="${escapeHtml(n.name)}">Assume Control</button>`;
            } else if (isTile) {
              actionBtn = `<button class="btn btn-secondary btn-xs btn-goto-tile" data-tile="${escapeHtml(n.name)}">Focus</button>`;
            }
            if (isCountry) actionBtn += ` <button class="btn btn-secondary btn-xs btn-ai-why" data-nat="${escapeHtml(n.name)}">Why AI?</button>`;
            return `
              <tr>
                <td><strong style="color:${safeCssColor(n.flag_color)}">${isCountry ? '👑 ' : (isProv ? '🏛️ ' : '🏙️ ')}${escapeHtml(n.name)}</strong> ${isPlayer ? '<span class="card-badge mastered">YOU</span>' : ''}</td>
                ${!isCountry ? `<td>${escapeHtml(n.nation || '—')}</td>` : `<td>${escapeHtml(n.regime_type || 'Monarchy')}</td>`}
                ${isTile ? `<td>${escapeHtml(n.province || '—')}</td>` : ''}
                <td class="text-gold">$${Math.round(n.treasury_cash || 0).toLocaleString()} ${tDelta} ${isCountry ? `<button class="btn btn-secondary btn-xs btn-treasury-why" data-nat="${escapeHtml(n.name)}">Why $?</button>` : ''}</td>
                <td>${(n.population || 0).toLocaleString()}</td>
                <td>${n.food_security ? `${Number(n.food_security.underfed || 0).toLocaleString()} underfed${Number(n.food_security.emergency_tiles || 0) ? ` · emergency in ${Number(n.food_security.emergency_tiles)} districts` : ''}${Number(n.food_security.enclosure_moratoria || 0) ? ` · commons protected in ${Number(n.food_security.enclosure_moratoria)} districts` : ''}${Number(n.food_security.aid_units_last_turn || 0) ? ` · ${Number(n.food_security.aid_units_last_turn).toLocaleString()} food units delivered` : ''}${Number(n.food_security.levy_units_last_turn || 0) ? ` · ${Number(n.food_security.levy_units_last_turn).toLocaleString()} levied` : ''}` : '—'}</td>
                <td class="text-cyan">$${Math.round(n.gdp || 0).toLocaleString()}</td>
                <td><span class="badge-unrest ${safeClassToken((n.unrest_stage || 'calm').toLowerCase(), 'calm')}">${escapeHtml(n.unrest_stage || 'Calm')}</span></td>
                <td><strong class="text-gold">${escapeHtml(n.credit_rating || 'BBB')}</strong></td>
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
            scheduleMapRender();
          }
          closeCompareModal();
        });
      });
      container.appendChild(table);
      if (isCountry) {
        const detail = document.createElement('div');
        detail.className = 'card';
        detail.hidden = true;
        container.appendChild(detail);
        table.querySelectorAll('.btn-ai-why').forEach(button => {
          button.addEventListener('click', async () => {
            detail.hidden = false;
            detail.textContent = 'Loading AI decision…';
            try {
              const params = new URLSearchParams({ turn: String(worldState.turn || 0),
                entity: `nation:${button.dataset.nat}`, limit: '100' });
              const response = await fetch(`/api/trace?${params}`);
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              const rows = (await response.json()).events || [];
              const decision = rows.find(e => e.kind === 'nation_ai_decision');
              if (!decision) {
                detail.textContent = 'Explanation unavailable: no AI decision was recorded for this nation and turn.';
                return;
              }
              const selected = (decision.inputs.selected || []).join(', ') || 'No intent submitted';
              const rejected = (decision.inputs.considered || [])
                .filter(c => c.feasible === false).slice(0, 4)
                .map(c => `${c.candidate}: ${c.reason || 'unavailable'}`).join('; ');
              const executed = rows.filter(e => e.kind === 'intent_execution')
                .map(e => `${e.inputs.intent_type} ${e.inputs.status_after}`).join('; ');
              const foodResponse = (decision.inputs.food_security || [])
                .filter(f => f.emergency || f.enclosure_moratorium)
                .map(f => `${f.tile}: ${f.diagnosis.replaceAll('_', ' ')}, ${f.underfed_residents}/${f.residents} underfed, $${Number(f.funding_transferred || 0).toFixed(0)} transferred${f.enclosure_moratorium ? ', commons protected until food harvest is reliable' : ''}`)
                .join('; ');
              detail.innerHTML = `<h4>${escapeHtml(button.dataset.nat)} · Turn ${Number(decision.turn)}</h4>
                <p>Chosen: ${escapeHtml(selected)}.</p>
                <p>Food response: ${escapeHtml(foodResponse || 'no emergency policy')}.</p>
                <p>Rejected or blocked: ${escapeHtml(rejected || 'none recorded')}.</p>
                <p>Execution: ${escapeHtml(executed || 'no intent execution recorded')}.</p>
                <p>Event ${escapeHtml(decision.event_id)}</p>`;
            } catch (error) {
              detail.textContent = `Could not load AI explanation: ${error.message}`;
            }
          });
        });
        table.querySelectorAll('.btn-treasury-why').forEach(button => {
          button.addEventListener('click', async () => {
            detail.hidden = false;
            detail.textContent = 'Loading treasury movements…';
            try {
              const params = new URLSearchParams({ turn: String(worldState.turn || 0),
                entity: `nation:${button.dataset.nat}`, limit: '100' });
              const response = await fetch(`/api/trace?${params}`);
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              const rows = (await response.json()).events || [];
              const reconciliation = rows.find(e => e.kind === 'treasury_reconciliation');
              if (!reconciliation) {
                detail.textContent = 'Explanation unavailable: no treasury reconciliation was recorded for this turn.';
                return;
              }
              const i = reconciliation.inputs || {};
              const known = Object.entries(i.flow_totals_by_kind || {})
                .map(([kind, amount]) => `${kind}: ${Number(amount).toFixed(2)}`).join('; ') || 'none';
              const residual = Number(i.unattributed_residual || 0);
              const phases = rows.filter(e => e.kind === 'treasury_phase_delta')
                .map(e => `${e.phase}: ${Number(e.delta).toFixed(2)}`).join('; ');
              detail.innerHTML = `<h4>${escapeHtml(button.dataset.nat)} treasury · Turn ${Number(reconciliation.turn)}</h4>
                <p>${Number(reconciliation.value_before).toFixed(2)} → ${Number(reconciliation.value_after).toFixed(2)} ${escapeHtml(reconciliation.unit || '')}.</p>
                <p>Recorded transfers: ${Number(i.known_flow_total || 0).toFixed(2)} from ${escapeHtml(known)}.</p>
                <p>Movement by phase: ${escapeHtml(phases || 'none recorded')}.</p>
                <p>${Math.abs(residual) < 0.000001 ? 'All movement is attributed to recorded flows.' : `Unattributed movement: ${residual.toFixed(2)}. Some treasury transfer sources have not been instrumented yet.`}</p>
                <p>Event ${escapeHtml(reconciliation.event_id)}</p>`;
            } catch (error) {
              detail.textContent = `Could not load treasury explanation: ${error.message}`;
            }
          });
        });
      }

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
              <td><strong>${escapeHtml(p.province)}</strong></td>
              ${!isCountry ? `<td>${escapeHtml(p.nation || '—')}</td>` : ''}
              <td class="text-green">${Number(p.food_output) || 0} t</td>
              <td>${Number(p.wood_output) || 0} t</td>
              <td class="text-gold">${Number(p.furniture_output) || 0} t</td>
              <td>$${Number(p.food_price || 0).toFixed(2)} ${p.tile_id ? `<button class="btn btn-secondary btn-xs btn-price-why" data-tile="${escapeHtml(p.tile_id)}">Why?</button>` : ''}</td>
              <td>${Number(p.stockpiles) || 0} units</td>
            </tr>
          `).join('')}
        </tbody>
      `;
      container.appendChild(table);
      if (isTile) {
        const detail = document.createElement('div');
        detail.className = 'card';
        detail.hidden = true;
        container.appendChild(detail);
        table.querySelectorAll('.btn-price-why').forEach(button => {
          button.addEventListener('click', async () => {
            detail.hidden = false;
            detail.textContent = 'Loading price calculation…';
            try {
              const params = new URLSearchParams({ turn: String(worldState.turn || 0),
                entity: `tile:${button.dataset.tile}`, good: 'food', metric: 'goods.price', limit: '100' });
              const response = await fetch(`/api/trace?${params}`);
              if (!response.ok) throw new Error(`HTTP ${response.status}`);
              const result = await response.json();
              const event = (result.events || []).find(e => e.kind === 'market_price_update'
                && e.subject && e.subject.good === 'food');
              if (!event) {
                detail.textContent = 'Explanation unavailable for this turn. The price calculation was not recorded.';
                return;
              }
              const i = event.inputs || {};
              const c = event.constraints || {};
              detail.innerHTML = `<h4>Why food price changed · Turn ${Number(event.turn)}</h4>
                <p>Reference price: $${Number(event.value_before).toFixed(3)} → $${Number(event.value_after).toFixed(3)} per unit.</p>
                <p>Buy bids ${Number(i.bids || 0).toFixed(1)} units; local asks ${Number(i.local_asks || 0).toFixed(1)}; imported asks ${Number(i.imported_asks || 0).toFixed(1)}. Demand divided by available asks: ${Number(i.demand_ratio).toFixed(2)}.</p>
                <p>Producer inventory averaged ${Number(i.average_producer_inventory).toFixed(1)} units. Scarcity term ${Number(i.scarcity).toFixed(3)}; market influence ${Number(i.bounded_influence).toFixed(3)}. Recent price sample mean: ${i.recent_sample_mean == null ? 'none' : '$' + Number(i.recent_sample_mean).toFixed(3)}.</p>
                <p>Input cost floor $${Number(i.input_cost_floor).toFixed(3)}${c.active_floor == null ? ' (inactive)' : ' (active)'}. Source: ${escapeHtml(event.formula_id || 'unknown')} · event ${escapeHtml(event.event_id)}.</p>`;
            } catch (error) {
              detail.textContent = `Could not load price explanation: ${error.message}`;
            }
          });
        });
      }

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
                <td><strong>${escapeHtml(b.name || b.province)}</strong></td>
                <td>${escapeHtml(b.nation)}</td>
                <td><span class="badge-currency">${escapeHtml(b.currency || 'USD')}</span></td>
                <td class="text-gold">$${Math.round(b.deposits || 0).toLocaleString()}</td>
                <td class="text-cyan">${b.liquidity == null ? '—' : '$' + Math.round(b.liquidity).toLocaleString()}</td>
                <td class="text-green">${b.reserves == null ? '—' : '$' + Math.round(b.reserves).toLocaleString()}</td>
                <td><strong>${b.neer == null ? '—' : Number(b.neer).toFixed(2)}</strong></td>
              </tr>
            `).join('')}
          </tbody>
        </table>

        <h4 class="sub-heading mt-3">Bilateral FX quotes (home units per 1 foreign unit)</h4>
        ${currs.length > 0 ? `
          <table class="table">
            <thead>
              <tr>
                <th>Home \\ Foreign</th>
                ${currs.map(c => `<th>${escapeHtml(c)}</th>`).join('')}
              </tr>
            </thead>
            <tbody>
              ${currs.map(base => `
                <tr>
                  <td><strong>${escapeHtml(base)}</strong></td>
                  ${currs.map(quote => {
                    const rate = fxMatrix[base] ? fxMatrix[base][quote] : null;
                    return `<td>${base === quote ? '<span style="opacity:0.5;">1.000</span>' : rate == null ? '—' : `<span class="text-gold font-mono">${Number(rate).toFixed(3)}</span> <button class="btn btn-secondary btn-xs btn-fx-why" data-home="${escapeHtml(base)}" data-foreign="${escapeHtml(quote)}">Why?</button>`}</td>`;
                  }).join('')}
                </tr>
              `).join('')}
            </tbody>
          </table>
        ` : `<div class="empty-state">No bilateral FX quotes are available.</div>`}
      `;
      container.appendChild(div);
      const fxDetail = document.createElement('div');
      fxDetail.className = 'card';
      fxDetail.hidden = true;
      container.appendChild(fxDetail);
      div.querySelectorAll('.btn-fx-why').forEach(button => {
        button.addEventListener('click', async () => {
          const home = button.dataset.home;
          const foreign = button.dataset.foreign;
          fxDetail.hidden = false;
          fxDetail.textContent = `Loading ${home}/${foreign} FX explanation…`;
          try {
            const params = new URLSearchParams({ turn: String(worldState.turn || 0),
              base: home, quote: foreign, metric: 'fx.bilateral_mid', limit: '200' });
            const response = await fetch(`/api/trace?${params}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const rows = (await response.json()).events || [];
            const events = rows.filter(event => event.kind === 'fx_mid_update');
            if (!events.length) {
              fxDetail.textContent = `Explanation unavailable: no ${home}/${foreign} desk update was recorded for this turn.`;
              return;
            }
            fxDetail.innerHTML = `<h4>${escapeHtml(home)} per ${escapeHtml(foreign)} · Turn ${Number(events[0].turn)}</h4>
              ${events.map(event => {
                const i = event.inputs || {};
                const c = event.constraints || {};
                const cap = c.active ? ` Band constraint: ${escapeHtml(c.active)} of ${JSON.stringify(c.band || [])}.` : '';
                return `<p>${escapeHtml(event.subject?.id || 'Desk')}: ${Number(event.value_before).toFixed(4)} → ${Number(event.value_after).toFixed(4)}. Regime ${escapeHtml(i.regime || 'unknown')}; reserve ratio ${Number(i.reserve_ratio || 0).toFixed(3)}, reserve pressure ${Number(i.pressure_term || 0).toFixed(4)}, PPP target ${i.ppp_target == null ? 'unavailable' : Number(i.ppp_target).toFixed(4)}, PPP gap ${Number(i.ppp_gap || 0).toFixed(4)}.${cap} Event ${escapeHtml(event.event_id || '')}.</p>`;
              }).join('')}`;
          } catch (error) {
            fxDetail.textContent = `Could not load FX explanation: ${error.message}`;
          }
        });
      });

    } else if (activeCompareTab === '4') {
      // Tab 4: Class Wealth Extraction Table & Canvas Visualizers
      const data = getDrilldownData(cs.tab4_extraction);

      const visGrid = document.createElement('div');
      visGrid.className = 'vis-grid-2col mb-3';

      const cardPyramid = document.createElement('div');
      cardPyramid.className = 'vis-card';
      const cPyramid = document.createElement('canvas');
      cPyramid.style.width = '100%';
      cPyramid.style.height = '240px';
      cardPyramid.appendChild(cPyramid);

      const cardLorenz = document.createElement('div');
      cardLorenz.className = 'vis-card';
      const cLorenz = document.createElement('canvas');
      cLorenz.style.width = '100%';
      cLorenz.style.height = '240px';
      cardLorenz.appendChild(cLorenz);

      visGrid.appendChild(cardPyramid);
      visGrid.appendChild(cardLorenz);
      container.appendChild(visGrid);

      setTimeout(() => {
        const visPyramid = window.CoCVisPyramid;
        if (visPyramid) {
          visPyramid.drawWealthPyramid(cPyramid, { data, macro: worldState ? worldState.macro : null });
          const gini = (worldState && worldState.macro && worldState.macro.gini) || 0.42;
          visPyramid.drawLorenzCurve(cLorenz, { gini });
        }
      }, 0);

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
              <td><strong>${escapeHtml(r.name)}</strong></td>
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
      // Tab 5: Protest Energy, 100% Stacked Grievance Bars & 4D Alienation / Attractor
      const data = getDrilldownData(cs.tab5_protest);

      const visGrid = document.createElement('div');
      visGrid.className = 'vis-grid-2col mb-3';

      const cardRadar = document.createElement('div');
      cardRadar.className = 'vis-card';
      const cRadar = document.createElement('canvas');
      cRadar.style.width = '100%';
      cRadar.style.height = '240px';
      cardRadar.appendChild(cRadar);

      const cardAttractor = document.createElement('div');
      cardAttractor.className = 'vis-card';
      const cAttractor = document.createElement('canvas');
      cAttractor.style.width = '100%';
      cAttractor.style.height = '240px';
      cardAttractor.appendChild(cAttractor);

      visGrid.appendChild(cardRadar);
      visGrid.appendChild(cardAttractor);
      container.appendChild(visGrid);

      setTimeout(() => {
        const visRadarAttractor = window.CoCVisRadarAttractor;
        if (visRadarAttractor) {
          const shiftHours = (worldState && worldState.workday_hours) || 12.0;
          const unrest = (worldState && worldState.macro && worldState.macro.unrest_energy) || 1.5;
          const consciousness = Math.min(1.0, Math.max(0.1, unrest / 5.0));
          visRadarAttractor.drawAlienationRadar(cRadar, { shiftHours });
          visRadarAttractor.drawRebellionAttractor(cAttractor, { shiftHours, consciousness });
        }
      }, 0);

      const div = document.createElement('div');
      div.innerHTML = `
        <h4 class="sub-heading">Protest Energy Grievance Breakdown (100% Stacked)</h4>
        <table class="table">
          <thead>
            <tr>
              <th style="width: 20%;">${isCountry ? 'Nation' : (isProv ? 'Province' : 'City / Tile')}</th>
              <th style="width: 15%;">Unrest Score</th>
              <th style="width: 65%;">Grievance Sources (Overwork / Enclosure / Hunger / Labor / State / Inequality & Jobs)</th>
            </tr>
          </thead>
          <tbody>
            ${data.map(p => {
              const ow = Number(p.overwork ?? 0);
              const enc = Number(p.enclosure ?? 0);
              const hg = Number(p.hunger ?? 0);
              const stk = Number(p.strikes ?? 0);
              const rep = Number(p.state ?? 0);
              const ineq = Number(p.inequality ?? 0);
              const unrestVal = Number(p.unrest || 0).toFixed(1);
              const badgeCls = unrestVal > 3 ? 'riot' : (unrestVal > 1 ? 'unrest' : 'calm');
              return `
                <tr>
                  <td><strong>${escapeHtml(p.name)}</strong></td>
                  <td><span class="badge-unrest ${safeClassToken(badgeCls, 'calm')}">${unrestVal}</span></td>
                  <td>
                    <div class="stacked-bar-container">
                      <div class="stacked-segment" style="width: ${ow}%; background: #ef4444;" title="Overwork ${ow}%"></div>
                      <div class="stacked-segment" style="width: ${enc}%; background: #f59e0b;" title="Enclosure ${enc}%"></div>
                      <div class="stacked-segment" style="width: ${hg}%; background: #10b981;" title="Hunger ${hg}%"></div>
                      <div class="stacked-segment" style="width: ${stk}%; background: #06b6d4;" title="Labor ${stk}%"></div>
                      <div class="stacked-segment" style="width: ${rep}%; background: #a855f7;" title="State ${rep}%"></div>
                      <div class="stacked-segment" style="width: ${ineq}%; background: #ec4899;" title="Inequality and jobs ${ineq}%"></div>
                    </div>
                    <div style="display:flex; flex-wrap:wrap; gap:10px; font-size:0.68rem; margin-top:4px; opacity:0.85;">
                      <span><span style="color:#ef4444">■</span> Overwork ${ow}%</span>
                      <span><span style="color:#f59e0b">■</span> Enclosure ${enc}%</span>
                      <span><span style="color:#10b981">■</span> Hunger ${hg}%</span>
                      <span><span style="color:#06b6d4">■</span> Labor ${stk}%</span>
                      <span><span style="color:#a855f7">■</span> State ${rep}%</span>
                      <span><span style="color:#ec4899">■</span> Inequality &amp; jobs ${ineq}%</span>
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
      // Tab 6: Environmental Health Table & Marxian Capital Circuit / TRPF Decay
      const data = getDrilldownData(cs.tab6_ecology);

      const visGrid = document.createElement('div');
      visGrid.className = 'vis-grid-2col mb-3';

      const cardSankey = document.createElement('div');
      cardSankey.className = 'vis-card';
      const cSankey = document.createElement('canvas');
      cSankey.style.width = '100%';
      cSankey.style.height = '240px';
      cardSankey.appendChild(cSankey);

      const cardTrpf = document.createElement('div');
      cardTrpf.className = 'vis-card';
      const cTrpf = document.createElement('canvas');
      cTrpf.style.width = '100%';
      cTrpf.style.height = '240px';
      cardTrpf.appendChild(cTrpf);

      visGrid.appendChild(cardSankey);
      visGrid.appendChild(cardTrpf);
      container.appendChild(visGrid);

      setTimeout(() => {
        const visCircuits = window.CoCVisCircuits;
        if (visCircuits) {
          const macro = (worldState && worldState.macro) || {};
          const gdp = macro.gdp || 1000;
          visCircuits.drawCircuitSankey(cSankey, {
            moneyCapital: Math.round(gdp * 0.8),
            productiveCapital: Math.round(gdp * 0.6),
            commodityCapital: Math.round(gdp * 0.75),
            realizedMoney: Math.round(gdp * 1.1)
          });
          visCircuits.drawTRPFCurve(cTrpf, {
            organicComp: 2.8,
            profitRate: 14.5
          });
        }
      }, 0);

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
              <td><strong>${escapeHtml(e.name)}</strong></td>
              <td class="${Number(e.soil_fertility) < 50 ? 'text-ruby' : 'text-green'}">${Number(e.soil_fertility || 0).toFixed(1)}%</td>
              <td class="text-cyan">${Number(e.nutrition || 0).toFixed(1)}%</td>
              <td class="${Number(e.smog) > 20 ? 'text-ruby' : ''}">${Number(e.smog || 0).toFixed(1)} ppm</td>
              <td class="${Number(e.infections) > 0 ? 'text-ruby' : ''}">${Number(e.infections) || 0} active cases</td>
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
    const helpContent = window.CoCHelpContent;
    if (container && helpContent) container.innerHTML = helpContent.renderHelpPage(activeHelpPage, worldState);
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
        scheduleMapRender();
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
    if (selectedTileName !== tileName) {
      selectedTileDetail = null;
      loadedTileDetailVersion = null;
      lastTileDetailKey = null;
    }
    selectedTileName = tileName;
    if (worldState && worldState.tiles) {
      const tile = tileByName.get(tileName);
      if (tile) {
        updateTileInspectionUI(tile);
        fetchTileDetail();
        if (quickPill && pillText) {
          pillText.textContent = `${tile.display_name || tile.name} (${tile.nation || 'Wilderness'})`;
          quickPill.classList.remove('hidden');
          setTimeout(() => quickPill.classList.add('hidden'), 2500);
        }
      }
    }
    updateLeftDrawerPanes();
    scheduleMapRender();
  }

  function handlePointerDown(e) {
    if (e.button === 2 || e.altKey) {
      // Right click or Alt + click -> 3D Orbit
      isOrbiting = true;
      isDragging = false;
      orbitStartX = e.clientX;
      orbitStartY = e.clientY;
      startPitch = camPitch;
      startYaw = camYaw;
      return;
    }
    isDragging = true;
    isOrbiting = false;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    camStartX = camX;
    camStartY = camY;
    camStartTargetX = camTargetX;
    camStartTargetY = camTargetY;
    touchStartTime = Date.now();
  }

  function handlePointerMove(e) {
    if (isOrbiting) {
      const dx = e.clientX - orbitStartX;
      const dy = e.clientY - orbitStartY;
      camYaw = (startYaw + dx * 0.4) % 360;
      camPitch = Math.max(15.0, Math.min(89.5, startPitch - dy * 0.3));
      scheduleMapRender();
      return;
    }

    if (isDragging) {
      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      if (isVoronoi() && is3DMode) {
        const yawRad = (camYaw * Math.PI) / 180.0;
        const speed = 1.0 / Math.max(0.2, camZoom);
        camTargetX = camStartTargetX - (dx * Math.cos(yawRad) + dy * Math.sin(yawRad)) * speed;
        camTargetY = camStartTargetY + (-dx * Math.sin(yawRad) + dy * Math.cos(yawRad)) * speed;
      } else {
        camX = camStartX + dx;
        camY = camStartY + dy;
      }
      hideHexHoverCard();
      scheduleMapRender();
      return;
    }

    // Live hover hit-test & hover card
    const rect = canvas.getBoundingClientRect();
    if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
      if (hoveredTileName) {
        hoveredTileName = null;
        hideHexHoverCard();
        scheduleMapRender();
      }
      return;
    }

    const screenX = e.clientX - rect.left;
    const screenY = e.clientY - rect.top;
    const hit = getTileAtScreenPos(screenX, screenY, rect);

    if (hit) {
      if (hoveredTileName !== hit.name) {
        hoveredTileName = hit.name;
        scheduleMapRender();
      }
      updateHexHoverCard(hit, e.clientX, e.clientY);
    } else {
      if (hoveredTileName) {
        hoveredTileName = null;
        hideHexHoverCard();
        scheduleMapRender();
      }
    }
  }

  function handlePointerUp(e) {
    if (isOrbiting) {
      isOrbiting = false;
      return;
    }
    if (!isDragging) return;
    isDragging = false;
    const dx = Math.abs(e.clientX - dragStartX);
    const dy = Math.abs(e.clientY - dragStartY);
    const dt = Date.now() - touchStartTime;

    // Detect tap / click
    if (dx < 8 && dy < 8 && dt < 350) {
      const rect = canvas.getBoundingClientRect();
      const screenX = e.clientX - rect.left;
      const screenY = e.clientY - rect.top;
      const hit = getTileAtScreenPos(screenX, screenY, rect);
      if (hit) selectTile(hit.name);
    }
  }

  function handleWheel(e) {
    e.preventDefault();
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const zoomFactor = e.deltaY < 0 ? 1.15 : 0.85;
    const newZoom = Math.max(0.35, Math.min(3.5, camZoom * zoomFactor));

    if (isVoronoi() && is3DMode) {
      camZoom = newZoom;
      // Dynamic Civ-style zoom tilt: S-curve transition between overview 89° and 3D tilt 52°
      if (typeof computePitchYaw === 'function') {
        const py = computePitchYaw(camZoom);
        camPitch = py.pitch;
        camYaw = py.yaw;
      }
    } else {
      camX = mouseX - (mouseX - camX) * (newZoom / camZoom);
      camY = mouseY - (mouseY - camY) * (newZoom / camZoom);
      camZoom = newZoom;
    }
    scheduleMapRender();
  }

  function setupTouchEvents() {
    canvas.addEventListener('touchstart', (e) => {
      if (e.touches.length === 2) {
        isDragging = false;
        isOrbiting = false;
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
        if (isVoronoi() && is3DMode && typeof computePitchYaw === 'function') {
          const py = computePitchYaw(camZoom);
          camPitch = py.pitch;
          camYaw = py.yaw;
        }
        scheduleMapRender();
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

  // ---------------- Modal 5: System Settings & Preferences Modal ----------------

  function setupSettingsModal() {
    if (btnSettings) {
      btnSettings.addEventListener('click', openSettingsModal);
    }
    if (btnCloseSettings) btnCloseSettings.addEventListener('click', closeSettingsModal);
    if (settingsBackdrop) settingsBackdrop.addEventListener('click', closeSettingsModal);

    const sliderSpeed = document.getElementById('slider-sim-speed');
    const lblSpeed = document.getElementById('lbl-sim-speed');
    if (sliderSpeed) {
      sliderSpeed.addEventListener('input', () => {
        const val = parseInt(sliderSpeed.value, 10);
        if (lblSpeed) lblSpeed.textContent = `${val} ms`;
        if (pollTimer) {
          clearInterval(pollTimer);
          pollTimer = setInterval(fetchState, val);
        }
      });
    }

    const chkRoutes = document.getElementById('chk-trade-routes');
    if (chkRoutes) {
      chkRoutes.checked = showTradeRoutes;
      chkRoutes.addEventListener('change', () => {
        showTradeRoutes = chkRoutes.checked;
        scheduleMapRender();
      });
    }

    const chkArrows = document.getElementById('chk-trade-arrows');
    if (chkArrows) {
      chkArrows.checked = showTradeArrows;
      chkArrows.addEventListener('change', () => {
        showTradeArrows = chkArrows.checked;
        scheduleMapRender();
      });
    }

    const chkArbRings = document.getElementById('chk-arbitrage-rings');
    if (chkArbRings) {
      chkArbRings.checked = showArbitrageRings;
      chkArbRings.addEventListener('change', () => {
        showArbitrageRings = chkArbRings.checked;
        scheduleMapRender();
      });
    }

    const btnReload = document.getElementById('btn-settings-reload');
    if (btnReload) {
      btnReload.addEventListener('click', () => {
        const seed = Math.floor(Math.random() * 1000000);
        sendCommand('RELOAD_WORLD', { seed, terrain_seed: seed, nation_seed: seed });
        closeSettingsModal();
      });
    }

    const btnRestartServer = document.getElementById('btn-restart-server');
    if (btnRestartServer) btnRestartServer.addEventListener('click', restartWebServer);
  }

  async function restartWebServer() {
    const button = document.getElementById('btn-restart-server');
    const token = window.COC_API_TOKEN || '';
    if (button) { button.disabled = true; button.textContent = 'Restarting web server…'; }
    try {
      const response = await fetch('/api/restart', {
        method: 'POST',
        headers: { 'X-COC-Token': token }
      });
      if (!response.ok) throw new Error(`Server returned ${response.status}`);
      closeSettingsModal();
      showToast('Web server restarting. Reconnecting…');
      await new Promise(resolve => setTimeout(resolve, 1200));
      let consecutiveHealthChecks = 0;
      for (let attempt = 0; attempt < 60; attempt++) {
        try {
          const health = await fetch('/api/state?compact=1', { cache: 'no-store' });
          if (health.ok) consecutiveHealthChecks++;
          else consecutiveHealthChecks = 0;
        } catch (_) {}
        if (consecutiveHealthChecks >= 2) { window.location.reload(); return; }
        await new Promise(resolve => setTimeout(resolve, 300));
      }
      throw new Error('The server did not come back online.');
    } catch (error) {
      if (button) { button.disabled = false; button.textContent = '↻ Restart Web Server'; }
      showToast(`Could not restart web server: ${error.message}`, true);
    }
  }

  function openSettingsModal() {
    hideMacroTooltip();
    hideHexHoverCard();
    if (settingsModal) settingsModal.classList.remove('hidden');
  }

  function closeSettingsModal() {
    if (settingsModal) settingsModal.classList.add('hidden');
  }

  function cyclePolicyScope() {
    const scopes = ['tile', 'province', 'nation', 'frontier'];
    const curIdx = scopes.indexOf(activeGovScope);
    const nextScope = scopes[(curIdx + 1) % scopes.length];
    const btn = document.querySelector(`.scope-btn[data-gov-scope="${nextScope}"]`);
    if (btn) btn.click();
    else {
      activeGovScope = nextScope;
      ['tile', 'province', 'nation', 'frontier'].forEach(s => {
        const el = document.getElementById(`gov-scope-${s}`);
        if (el) el.classList.toggle('hidden', s !== activeGovScope);
      });
    }
    if (activeLeftDrawer !== 'gov') openLeftDrawer('gov');
  }

  function cycleSovereignNation() {
    if (!worldState || !worldState.nations || worldState.nations.length === 0) return;
    const curNat = worldState.player_nation;
    const curIdx = worldState.nations.findIndex(n => n.name === curNat);
    const nextIdx = (curIdx + 1) % worldState.nations.length;
    const nextNat = worldState.nations[nextIdx].name;
    sendCommand('SELECT_NATION', { nation: nextNat });
  }

  function resetActiveLayer() {
    const item = document.querySelector('.layer-item[data-layer="overview"]');
    if (item) item.click();
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
      else if (key === 'P') openLeftDrawer('progress');
      else if (key === 'V') cyclePolicyScope();
      else if (key === 'N') cycleSovereignNation();
      else if (key === '0') resetActiveLayer();
      else if (key === 'F10') {
        e.preventDefault();
        openSettingsModal();
      }
      else if (key === 'C') openCompareModal();
      else if (key === 'A') openCommandSuiteModal();
      else if (key === '3') toggle3DMode();
      else if (key === 'U') {
        useTerrainImage = !useTerrainImage;
        if (btnTogglePipeline) btnTogglePipeline.querySelector('.btn-text').textContent = useTerrainImage ? 'Pipeline: Photoreal' : 'Pipeline: Flat';
        scheduleMapRender();
      }
      else if (key === 'R') centerCameraOnWorld();
      else if (key === '?' || key === 'H') openHelpModal();
      else if (key === ' ') {
        e.preventDefault();
        if (btnPlay) btnPlay.click();
      } else if (key === '+' || key === '=' || key === '.') {
        if (btnStep) btnStep.click();
      } else if (key === 'ARROWUP') {
        camY += 40; scheduleMapRender();
      } else if (key === 'ARROWDOWN') {
        camY -= 40; scheduleMapRender();
      } else if (key === 'ARROWLEFT') {
        camX += 40; scheduleMapRender();
      } else if (key === 'ARROWRIGHT') {
        camX -= 40; scheduleMapRender();
      } else if (key === 'ESCAPE') {
        closeLeftDrawer();
        closeCompareModal();
        closeCommandSuiteModal();
        closeFiscalTransferDialog();
        closeHelpModal();
        closeSettingsModal();
        if (scenarioBookendModal) scenarioBookendModal.classList.add('hidden');
        qrModal.classList.add('hidden');
        hideMacroTooltip();
        hideSeasonalPopover();
        hideHexHoverCard();
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

  async function fetchTileDetail() {
    if (!selectedTileName || !stateVersion) return;
    const name = selectedTileName;
    const version = stateVersion;
    const detailVersion = `${version}:${name}`;
    if (loadedTileDetailVersion === detailVersion || pendingTileDetailVersion === detailVersion) return;
    pendingTileDetailVersion = detailVersion;
    const request = ++tileDetailRequest;
    try {
      const res = await api.fetchTile(name);
      if (!res.ok) return;
      const tile = await res.json();
      if (request !== tileDetailRequest || selectedTileName !== name || stateVersion !== version) return;
      loadedTileDetailVersion = detailVersion;
      lastTileDetailErrorKey = null;
      updateTileInspectionUI(tile);
      if (activeLeftDrawer === 'build') updateLeftDrawerPanes();
      if (activeRightTab === 'charts') renderHistoricalChart();
    } catch (err) {
      if (lastTileDetailErrorKey !== detailVersion) {
        console.warn(`Could not load details for ${name}; the next state refresh will retry.`, err);
        lastTileDetailErrorKey = detailVersion;
      }
    } finally {
      if (pendingTileDetailVersion === detailVersion) pendingTileDetailVersion = null;
    }
  }

  async function performStateFetch(force) {
    try {
      const res = await api.fetchState(!force ? stateVersion : null);
      if (res.status === 304) {
        if (statusDot) {
          statusDot.className = 'status-dot connected';
          statusDot.title = 'Server Connected (Live)';
        }
        fetchTileDetail();
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (stateVersion && stateVersion.split(':').slice(0, 2).join(':') !== data.version.split(':').slice(0, 2).join(':')) {
        isInitialCentered = false;
        selectedTileDetail = null;
        loadedTileDetailVersion = null;
        lastTileDetailKey = null;
        lastRecipesKey = null;
      }
      worldState = data;
      stateVersion = data.version;
      lastStateFetchError = null;
      indexTiles();

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
        const inhabited = data.tiles.find(t => t.nation || t.population > 0) || data.tiles[0];
        selectTile(inhabited.name);
      } else if (selectedTileName && data.tiles) {
        const t = tileByName.get(selectedTileName);
        if (t) {
          if (!selectedTileDetail || selectedTileDetail.name !== t.name) updateTileInspectionUI(t);
          fetchTileDetail();
        } else if (data.tiles.length) {
          selectTile(data.tiles[0].name);
        }
      }

      updateTopMacroBar();
      const drawerKey = `${activeLeftDrawer}:${selectedTileName}:${stateVersion}`;
      if (drawerKey !== lastDrawerKey) {
        updateLeftDrawerPanes();
        lastDrawerKey = drawerKey;
      }
      updateRightPanel();
      scheduleMapRender();

    } catch (err) {
      if (statusDot) {
        statusDot.className = 'status-dot';
        statusDot.title = `Server Disconnected: ${err.message}`;
      }
      const errorKey = `${err.name}:${err.message}`;
      if (lastStateFetchError !== errorKey) {
        console.warn('Could not refresh simulation state; retrying automatically.', err);
        lastStateFetchError = errorKey;
      }
    }
  }

  async function fetchState(force = false) {
    if (stateFetchPromise) {
      return force ? stateFetchPromise.then(() => fetchState(true)) : stateFetchPromise;
    }
    const request = performStateFetch(force);
    stateFetchPromise = request;
    try { return await request; }
    finally { if (stateFetchPromise === request) stateFetchPromise = null; }
  }

  async function sendCommand(commandType, payload = {}) {
    await api.sendCommand(commandType, payload);
  }

  // ---------------- Initialization ----------------

  function init() {
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Mouse & Pointer Handlers
    canvas.addEventListener('mousedown', handlePointerDown);
    canvas.addEventListener('contextmenu', (e) => e.preventDefault());
    window.addEventListener('mousemove', handlePointerMove);
    window.addEventListener('mouseup', handlePointerUp);
    canvas.addEventListener('wheel', handleWheel, { passive: false });
    canvas.addEventListener('mouseleave', () => {
      if (hoveredTileName) {
        hoveredTileName = null;
        hideHexHoverCard();
        scheduleMapRender();
      }
    });

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
    setupSeasonalClockPopover();
    setupSettingsModal();
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

    if (btnToggle3D) {
      btnToggle3D.addEventListener('click', toggle3DMode);
    }

    if (btnToggleTerrain) {
      btnToggleTerrain.addEventListener('click', () => {
        useTerrainImage = !useTerrainImage;
        btnToggleTerrain.classList.toggle('active', useTerrainImage);
        scheduleMapRender();
      });
    }

    if (btnTogglePipeline) {
      btnTogglePipeline.addEventListener('click', () => {
        useTerrainImage = !useTerrainImage;
        btnTogglePipeline.querySelector('.btn-text').textContent = useTerrainImage ? 'Pipeline: Photoreal' : 'Pipeline: Flat';
        scheduleMapRender();
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
        if (isVoronoi() && is3DMode && typeof computePitchYaw === 'function') {
          const py = computePitchYaw(camZoom);
          camPitch = py.pitch;
          camYaw = py.yaw;
        }
        scheduleMapRender();
      });
    }
    if (btnZoomOut) {
      btnZoomOut.addEventListener('click', () => {
        camZoom = Math.max(0.35, camZoom * 0.8);
        if (isVoronoi() && is3DMode && typeof computePitchYaw === 'function') {
          const py = computePitchYaw(camZoom);
          camPitch = py.pitch;
          camYaw = py.yaw;
        }
        scheduleMapRender();
      });
    }
    if (btnResetCam) {
      btnResetCam.addEventListener('click', centerCameraOnWorld);
    }

    // Initial Fetch & Poll Loop
    fetchState();
    pollTimer = setInterval(fetchState, 1000);

    // Independent 60fps Animation Loop for Smooth Trade Commodity Flows
    const tradeAnim = window.CoCTradeAnimator;
    if (tradeAnim) {
      const tradeTicker = tradeAnim.createAnimationTicker(() => {
        if (showTradeArrows && worldState && worldState.trade_network && worldState.trade_network.flows && worldState.trade_network.flows.length > 0) {
          scheduleMapRender();
        }
      });
      tradeTicker.start();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
