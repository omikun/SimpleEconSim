/**
 * REGNUM Mobile Web Client
 * Pure vanilla JavaScript with HTML5 Canvas, axial hex projection,
 * touch gestures (1-finger pan, 2-finger pinch zoom, tap selection),
 * and REST API synchronization.
 */

(function () {
  'use strict';

  const SQRT3 = Math.sqrt(3.0);
  const BASE_HEX_SIZE = 48; // Base radius in pixels

  // State
  let worldState = null;
  let selectedTileName = null;
  let selectedTileDetail = null;
  let isPlaying = false;
  let pollTimer = null;
  let isRequestPending = false;

  // Camera State
  let camX = 0;
  let camY = 0;
  let camZoom = 1.0;
  let isInitialCentered = false;

  // Touch & Pointer Interaction State
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
  const statusDot = document.getElementById('status-dot');
  const quickPill = document.getElementById('quick-pill');
  const pillText = document.getElementById('pill-text');

  // Drawer Elements
  const drawer = document.getElementById('drawer');
  const drawerHandle = document.getElementById('drawer-handle');
  const drawerToggleBtn = document.getElementById('drawer-toggle-btn');
  const tileNameEl = document.getElementById('tile-name');
  const tileSubEl = document.getElementById('tile-sub');
  const newsBadge = document.getElementById('news-badge');

  // Detail Elements
  const statNation = document.getElementById('stat-nation');
  const statPop = document.getElementById('stat-pop');
  const statBiome = document.getElementById('stat-biome');
  const statElevation = document.getElementById('stat-elevation');
  const statCol = document.getElementById('stat-col');
  const statCoords = document.getElementById('stat-coords');

  const barCommons = document.getElementById('bar-commons');
  const barFeudal = document.getElementById('bar-feudal');
  const barEnclosed = document.getElementById('bar-enclosed');
  const lblCommons = document.getElementById('lbl-commons');
  const lblFeudal = document.getElementById('lbl-feudal');
  const lblEnclosed = document.getElementById('lbl-enclosed');
  const plotCount = document.getElementById('plot-count');
  const plotsList = document.getElementById('plots-list');

  const inputWorkday = document.getElementById('input-workday');
  const valWorkday = document.getElementById('val-workday');
  const badgeTenHour = document.getElementById('badge-ten-hour');
  const btnApplyLabor = document.getElementById('btn-apply-labor');
  const statShift = document.getElementById('stat-shift');
  const statSurplus = document.getElementById('stat-surplus');
  const statExploitation = document.getElementById('stat-exploitation');

  const whStatus = document.getElementById('wh-status');
  const whDesc = document.getElementById('wh-desc');
  const censusList = document.getElementById('census-list');
  const tickerFeed = document.getElementById('ticker-feed');

  // Biome Color Palette
  const BIOME_COLORS = {
    ocean: '#0d1e33',
    shelf: '#16314f',
    plains: '#3d5c31',
    forest: '#21421e',
    mountain: '#615f5a',
    hill: '#4e593b',
    desert: '#7d6f43',
    snow: '#8a9fa8',
    tundra: '#5a686b',
  };

  // Nation Colors (deterministic hashing)
  const NATION_COLORS = [
    '#e5534b', '#58a6ff', '#3fb950', '#d29922',
    '#bc8cff', '#39c5bb', '#f0883e', '#7ee787'
  ];

  function getNationColor(name) {
    if (!name) return '#6e7681';
    let h = 0;
    for (let i = 0; i < name.length; i++) {
      h = (h * 31 + name.charCodeAt(i)) & 0xffffffff;
    }
    return NATION_COLORS[Math.abs(h) % NATION_COLORS.length];
  }

  // Hex Math
  function axialToPixel(q, r, size) {
    return {
      x: size * SQRT3 * (q + r / 2.0),
      y: size * 1.5 * r
    };
  }

  function pixelToAxial(px, py, size) {
    const q = (SQRT3 / 3.0 * px - 1.0 / 3.0 * py) / size;
    const r = (2.0 / 3.0 * py) / size;
    return axialRound(q, r);
  }

  function axialRound(fracQ, fracR) {
    let x = fracQ;
    let y = fracR;
    let z = -fracQ - fracR;
    let rx = Math.round(x);
    let ry = Math.round(y);
    let rz = Math.round(z);
    const dx = Math.abs(rx - x);
    const dy = Math.abs(ry - y);
    const dz = Math.abs(rz - z);

    if (dx > dy && dx > dz) {
      rx = -ry - rz;
    } else if (dy > dz) {
      ry = -rx - rz;
    } else {
      rz = -rx - ry;
    }
    return { q: rx, r: ry };
  }

  function getHexCorners(cx, cy, size) {
    const corners = [];
    for (let i = 0; i < 6; i++) {
      const angle = (Math.PI / 180.0) * (60 * i - 30);
      corners.push({
        x: cx + size * Math.cos(angle),
        y: cy + size * Math.sin(angle)
      });
    }
    return corners;
  }

  // Canvas Sizing & High-DPI
  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    render();
  }

  window.addEventListener('resize', resizeCanvas);

  // Center Camera on World
  function centerCameraOnWorld() {
    if (!worldState || !worldState.tiles || worldState.tiles.length === 0) return;
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;

    worldState.tiles.forEach(t => {
      const pt = axialToPixel(t.q, t.r, BASE_HEX_SIZE);
      minX = Math.min(minX, pt.x);
      maxX = Math.max(maxX, pt.x);
      minY = Math.min(minY, pt.y);
      maxY = Math.max(maxY, pt.y);
    });

    const midX = (minX + maxX) / 2;
    const midY = (minY + maxY) / 2;
    const rect = canvas.getBoundingClientRect();

    // Auto-fit zoom so the entire island map fits in the mobile/desktop viewport
    const worldW = (maxX - minX) + BASE_HEX_SIZE * 3;
    const worldH = (maxY - minY) + BASE_HEX_SIZE * 3;
    const fitZoom = Math.min(
      (rect.width * 0.95) / Math.max(1, worldW),
      ((rect.height - 80) * 0.88) / Math.max(1, worldH)
    );
    camZoom = Math.max(0.35, Math.min(1.5, fitZoom));

    camX = (rect.width / 2) - midX * camZoom;
    camY = ((rect.height - 40) / 2) - midY * camZoom;
    isInitialCentered = true;
    render();
  }

  // Rendering
  function render() {
    const dpr = window.devicePixelRatio || 1;
    const width = canvas.width / dpr;
    const height = canvas.height / dpr;

    ctx.save();
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    if (!worldState || !worldState.tiles) {
      ctx.fillStyle = '#8b949e';
      ctx.font = '14px system-ui';
      ctx.textAlign = 'center';
      ctx.fillText('Connecting to REGNUM Simulation Server...', width / 2, height / 2);
      ctx.restore();
      return;
    }

    const currentHexSize = BASE_HEX_SIZE * camZoom;

    // Draw Hex Tiles
    worldState.tiles.forEach(tile => {
      const worldPos = axialToPixel(tile.q, tile.r, BASE_HEX_SIZE);
      const screenX = camX + worldPos.x * camZoom;
      const screenY = camY + worldPos.y * camZoom;

      // Cull off-screen tiles
      if (
        screenX < -currentHexSize * 2 ||
        screenX > width + currentHexSize * 2 ||
        screenY < -currentHexSize * 2 ||
        screenY > height + currentHexSize * 2
      ) {
        return;
      }

      const corners = getHexCorners(screenX, screenY, currentHexSize);

      // 1. Fill Hex Interior
      ctx.beginPath();
      ctx.moveTo(corners[0].x, corners[0].y);
      for (let i = 1; i < 6; i++) {
        ctx.lineTo(corners[i].x, corners[i].y);
      }
      ctx.closePath();

      // Determine Base Color
      let fillColor = BIOME_COLORS[tile.biome] || BIOME_COLORS.plains;
      if (tile.is_ocean) {
        fillColor = tile.elevation < -0.4 ? BIOME_COLORS.ocean : BIOME_COLORS.shelf;
      }
      ctx.fillStyle = fillColor;
      ctx.fill();

      // 2. Nation Territory Border / Subtle Glow
      if (tile.nation && !tile.is_ocean) {
        ctx.strokeStyle = getNationColor(tile.nation);
        ctx.lineWidth = Math.max(1.5, 2.5 * camZoom);
        ctx.stroke();
      } else {
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      // 3. Selection Highlight
      if (tile.name === selectedTileName) {
        ctx.save();
        ctx.strokeStyle = '#f2cc60';
        ctx.lineWidth = Math.max(3, 4.5 * camZoom);
        ctx.shadowColor = 'rgba(242, 204, 96, 0.8)';
        ctx.shadowBlur = 12;
        ctx.stroke();
        ctx.restore();
      }

      // 4. Settlements / Cities & Names
      if (!tile.wilderness && !tile.is_ocean && currentHexSize >= 22) {
        // Town Icon / Center Marker
        ctx.beginPath();
        const iconRadius = Math.max(4, 6 * camZoom);
        ctx.arc(screenX, screenY - (currentHexSize * 0.15), iconRadius, 0, Math.PI * 2);
        ctx.fillStyle = '#f2cc60';
        ctx.fill();
        ctx.strokeStyle = '#121418';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // City Name Text
        if (currentHexSize >= 28) {
          const fontSize = Math.max(10, Math.min(13, 11 * camZoom));
          ctx.font = `bold ${fontSize}px system-ui`;
          ctx.textAlign = 'center';
          ctx.fillStyle = '#ffffff';
          ctx.shadowColor = 'rgba(0,0,0,0.9)';
          ctx.shadowBlur = 4;
          ctx.fillText(tile.display_name || tile.name, screenX, screenY + (currentHexSize * 0.45));
          ctx.shadowBlur = 0;
        }
      }
    });

    ctx.restore();
  }

  // API Interaction
  async function fetchWorldState() {
    if (isRequestPending) return;
    isRequestPending = true;

    try {
      const res = await fetch('/api/state');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      worldState = data;
      statusDot.className = 'status-dot connected';
      updateUI();

      if (!isInitialCentered && worldState.tiles && worldState.tiles.length > 0) {
        centerCameraOnWorld();
      } else {
        render();
      }

      // If selected tile is open, refresh its detail
      if (selectedTileName) {
        fetchTileDetail(selectedTileName, false);
      }
    } catch (err) {
      statusDot.className = 'status-dot error';
    } finally {
      isRequestPending = false;
    }
  }

  async function fetchTileDetail(tileName, expandDrawer = true) {
    try {
      const res = await fetch(`/api/tile?name=${encodeURIComponent(tileName)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const detail = await res.json();
      selectedTileDetail = detail;
      updateDrawer(detail);
      if (expandDrawer) {
        drawer.classList.remove('collapsed');
        drawer.classList.add('expanded');
      }
    } catch (err) {
      console.error("Error fetching tile detail:", err);
    }
  }

  async function postCommand(cmdType, payload = {}) {
    try {
      const res = await fetch('/api/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd_type: cmdType, payload: payload })
      });
      const data = await res.json();
      await fetchWorldState();
      return data;
    } catch (err) {
      console.error("Command failed:", err);
    }
  }

  // Update UI Elements
  function updateUI() {
    if (!worldState) return;
    turnDisplay.textContent = worldState.turn || 0;
    isPlaying = Boolean(worldState.playing);

    if (isPlaying) {
      btnPlay.textContent = '⏸ Pause';
      btnPlay.classList.add('playing');
    } else {
      btnPlay.textContent = '▶ Play';
      btnPlay.classList.remove('playing');
    }

    // Update Ticker
    if (worldState.ticker_events) {
      updateTickerFeed(worldState.ticker_events);
      newsBadge.textContent = worldState.ticker_events.length;
    }
  }

  function updateTickerFeed(events) {
    if (!events || events.length === 0) return;
    const items = [...events].reverse().slice(0, 25);
    tickerFeed.innerHTML = items.map(ev => `
      <div class="news-item">
        <div class="news-meta">
          <span class="news-turn">T-${ev.t}</span>
          <span class="news-kind">${ev.kind}</span>
        </div>
        <div class="news-text">${ev.text}</div>
      </div>
    `).join('');
  }

  function updateDrawer(detail) {
    tileNameEl.textContent = detail.display_name || detail.name;
    tileSubEl.textContent = `${detail.nation || 'Unclaimed Wilds'} • ${detail.biome.toUpperCase()}`;

    // Overview Tab
    statNation.textContent = detail.nation || 'None';
    statNation.style.color = getNationColor(detail.nation);
    statPop.textContent = `${detail.population} residents`;
    statBiome.textContent = detail.biome.charAt(0).toUpperCase() + detail.biome.slice(1);
    statElevation.textContent = `${detail.elevation_meters.toFixed(0)} m`;
    statCol.textContent = `§${detail.cost_of_living.toFixed(2)}`;
    statCoords.textContent = `q: ${detail.q}, r: ${detail.r}`;

    // Cadastre Tab
    const tenure = detail.tenure || {};
    const commonsPct = Math.round((tenure.commons_access || 0) * 100);
    const feudalPct = Math.round((tenure.feudal_fraction || 0) * 100);
    const enclosedPct = Math.round((tenure.enclosed_fraction || 0) * 100);

    barCommons.style.width = `${commonsPct}%`;
    barFeudal.style.width = `${feudalPct}%`;
    barEnclosed.style.width = `${enclosedPct}%`;
    lblCommons.textContent = `${commonsPct}%`;
    lblFeudal.textContent = `${feudalPct}%`;
    lblEnclosed.textContent = `${enclosedPct}%`;

    const plots = tenure.plots || [];
    plotCount.textContent = plots.length;
    if (plots.length === 0) {
      plotsList.innerHTML = '<div class="empty-state">No individual cadastral plots surveyed. Common pastures dominate.</div>';
    } else {
      plotsList.innerHTML = plots.map(p => `
        <div class="plot-item">
          <div>
            <div class="plot-name">${p.display_name || p.name}</div>
            <div class="plot-sub">Lord: ${p.lord_id || 'Freehold'} • ${p.tenant_count} tenants</div>
          </div>
          <div style="text-align: right;">
            <span class="plot-badge ${p.production_type === 'pasture' ? 'badge-pasture' : 'badge-arable'}">
              ${p.production_type.toUpperCase()}
            </span>
            <div class="plot-sub mt-1">Rent: §${p.rent_rate.toFixed(1)}/yr</div>
          </div>
        </div>
      `).join('');
    }

    // Labor Tab
    const labor = detail.labor || {};
    inputWorkday.value = labor.max_workday_hours || 12;
    valWorkday.textContent = `${labor.max_workday_hours || 12}h`;
    if (labor.ten_hour_act) {
      badgeTenHour.textContent = '10.0h Factory Act';
      badgeTenHour.classList.add('active');
    } else {
      badgeTenHour.textContent = `${labor.max_workday_hours || 12}h Normal`;
      badgeTenHour.classList.remove('active');
    }
    statShift.textContent = `${(labor.shift_hours || 8).toFixed(1)} hrs`;
    statSurplus.textContent = `§${(labor.surplus_value || 0).toFixed(2)}`;
    statExploitation.textContent = `${((labor.rate_of_exploitation || 0) * 100).toFixed(1)}%`;

    // Workhouse Tab
    const wh = detail.workhouse || {};
    if (wh.active) {
      whStatus.textContent = 'Municipal Workhouse Active';
      whDesc.textContent = `${wh.inmate_count} paupers sheltered under harsh regime`;
      if (wh.census && wh.census.length > 0) {
        censusList.innerHTML = wh.census.map(c => `
          <div class="plot-item">
            <span class="plot-name">Inmate #${c.agent_id || '—'}</span>
            <span class="plot-sub">Classification: Pauper Labor</span>
          </div>
        `).join('');
      } else {
        censusList.innerHTML = '<div class="empty-state">No census records filed.</div>';
      }
    } else {
      whStatus.textContent = 'No Municipal Workhouse';
      whDesc.textContent = 'Indigent paupers rely on parish outdoor relief or roaming vagrancy.';
      censusList.innerHTML = '<div class="empty-state">Workhouse system not yet erected in this municipality.</div>';
    }
  }

  // Tile Selection by Coordinate
  function handleTileTap(screenX, screenY) {
    if (!worldState || !worldState.tiles) return;

    // Convert Screen to World
    const worldX = (screenX - camX) / camZoom;
    const worldY = (screenY - camY) / camZoom;

    const axial = pixelToAxial(worldX, worldY, BASE_HEX_SIZE);
    const match = worldState.tiles.find(t => t.q === axial.q && t.r === axial.r);

    if (match) {
      selectedTileName = match.name;
      pillText.textContent = `${match.display_name || match.name} (${match.biome})`;
      quickPill.classList.remove('hidden');
      fetchTileDetail(match.name, true);
      render();

      setTimeout(() => {
        quickPill.classList.add('hidden');
      }, 2500);
    }
  }

  // Pointer & Touch Events
  canvas.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) {
      isDragging = true;
      dragStartX = e.touches[0].clientX;
      dragStartY = e.touches[0].clientY;
      camStartX = camX;
      camStartY = camY;
      touchStartTime = Date.now();
      initialPinchDist = null;
    } else if (e.touches.length === 2) {
      isDragging = false;
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      initialPinchDist = Math.hypot(dx, dy);
      initialPinchZoom = camZoom;
    }
  }, { passive: false });

  canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    if (e.touches.length === 1 && isDragging) {
      const dx = e.touches[0].clientX - dragStartX;
      const dy = e.touches[0].clientY - dragStartY;
      camX = camStartX + dx;
      camY = camStartY + dy;
      render();
    } else if (e.touches.length === 2 && initialPinchDist) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.hypot(dx, dy);
      const zoomFactor = dist / initialPinchDist;
      camZoom = Math.min(3.0, Math.max(0.35, initialPinchZoom * zoomFactor));
      render();
    }
  }, { passive: false });

  canvas.addEventListener('touchend', (e) => {
    if (isDragging && e.changedTouches.length === 1) {
      const touch = e.changedTouches[0];
      const dist = Math.hypot(touch.clientX - dragStartX, touch.clientY - dragStartY);
      const elapsed = Date.now() - touchStartTime;

      if (dist < 10 && elapsed < 300) {
        const rect = canvas.getBoundingClientRect();
        handleTileTap(touch.clientX - rect.left, touch.clientY - rect.top);
      }
    }
    isDragging = false;
    initialPinchDist = null;
  });

  // Mouse fallback (Desktop)
  let isMouseDown = false;
  canvas.addEventListener('mousedown', (e) => {
    isMouseDown = true;
    dragStartX = e.clientX;
    dragStartY = e.clientY;
    camStartX = camX;
    camStartY = camY;
    touchStartTime = Date.now();
  });

  window.addEventListener('mousemove', (e) => {
    if (!isMouseDown) return;
    const dx = e.clientX - dragStartX;
    const dy = e.clientY - dragStartY;
    camX = camStartX + dx;
    camY = camStartY + dy;
    render();
  });

  window.addEventListener('mouseup', (e) => {
    if (isMouseDown) {
      const dist = Math.hypot(e.clientX - dragStartX, e.clientY - dragStartY);
      const elapsed = Date.now() - touchStartTime;
      if (dist < 6 && elapsed < 300) {
        const rect = canvas.getBoundingClientRect();
        handleTileTap(e.clientX - rect.left, e.clientY - rect.top);
      }
      isMouseDown = false;
    }
  });

  canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomDelta = e.deltaY < 0 ? 1.15 : 0.87;
    camZoom = Math.min(3.0, Math.max(0.35, camZoom * zoomDelta));
    render();
  }, { passive: false });

  // Floating Controls
  document.getElementById('btn-zoom-in').addEventListener('click', () => {
    camZoom = Math.min(3.0, camZoom * 1.25);
    render();
  });

  document.getElementById('btn-zoom-out').addEventListener('click', () => {
    camZoom = Math.max(0.35, camZoom / 1.25);
    render();
  });

  document.getElementById('btn-reset-cam').addEventListener('click', () => {
    camZoom = 1.0;
    centerCameraOnWorld();
  });

  // Top Buttons
  btnPlay.addEventListener('click', () => {
    if (isPlaying) {
      postCommand('PAUSE');
    } else {
      postCommand('PLAY');
    }
  });

  btnStep.addEventListener('click', () => {
    postCommand('STEP');
  });

  btnNew.addEventListener('click', () => {
    if (confirm('Randomize world seed and generate a new realm?')) {
      const newSeed = Math.floor(Math.random() * 900000) + 100000;
      postCommand('RELOAD_WORLD', { seed: newSeed, terrain_seed: newSeed, nation_seed: newSeed });
    }
  });

  // Drawer Toggling & Tabs
  function toggleDrawer() {
    drawer.classList.toggle('collapsed');
    drawer.classList.toggle('expanded');
  }

  drawerHandle.addEventListener('click', toggleDrawer);
  drawerToggleBtn.addEventListener('click', toggleDrawer);

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));

      btn.classList.add('active');
      const target = document.getElementById(btn.getAttribute('data-tab'));
      if (target) target.classList.add('active');

      if (drawer.classList.contains('collapsed')) {
        drawer.classList.remove('collapsed');
        drawer.classList.add('expanded');
      }
    });
  });

  // Labor Policy Slider
  inputWorkday.addEventListener('input', (e) => {
    valWorkday.textContent = `${parseFloat(e.target.value).toFixed(1)}h`;
  });

  btnApplyLabor.addEventListener('click', () => {
    if (!selectedTileDetail || !selectedTileDetail.nation) return;
    const val = parseFloat(inputWorkday.value);
    postCommand('SET_POLICY', {
      nation: selectedTileDetail.nation,
      key: 'max_workday_hours',
      val: val
    });
  });

  // QR Modal Dialog
  const btnQr = document.getElementById('btn-qr');
  const qrModal = document.getElementById('qr-modal');
  const qrBackdrop = document.getElementById('qr-backdrop');
  const btnCloseQr = document.getElementById('btn-close-qr');
  const qrUrlText = document.getElementById('qr-url-text');
  const btnCopyUrl = document.getElementById('btn-copy-url');

  function openQrModal() {
    const url = (worldState && worldState.lan_url) || window.location.href;
    if (qrUrlText) qrUrlText.value = url;
    const qrImg = document.getElementById('qr-img');
    if (qrImg) qrImg.src = '/api/qr.svg?t=' + Date.now();
    if (qrModal) qrModal.classList.remove('hidden');
  }

  function closeQrModal() {
    if (qrModal) qrModal.classList.add('hidden');
  }

  if (btnQr) btnQr.addEventListener('click', openQrModal);
  if (btnCloseQr) btnCloseQr.addEventListener('click', closeQrModal);
  if (qrBackdrop) qrBackdrop.addEventListener('click', closeQrModal);

  if (btnCopyUrl && qrUrlText) {
    btnCopyUrl.addEventListener('click', () => {
      qrUrlText.select();
      navigator.clipboard.writeText(qrUrlText.value).then(() => {
        btnCopyUrl.textContent = 'Copied!';
        setTimeout(() => { btnCopyUrl.textContent = 'Copy'; }, 2000);
      }).catch(() => {
        btnCopyUrl.textContent = 'Copied!';
      });
    });
  }

  // Polling Loop
  function startPolling() {
    fetchWorldState();
    pollTimer = setInterval(fetchWorldState, 400);
  }

  // Initialization
  resizeCanvas();
  startPolling();
})();
